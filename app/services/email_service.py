import smtplib
from email.message import EmailMessage

from datetime import datetime, timedelta, timezone
from flask import current_app, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models import User
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

class EmailDeliveryError(Exception):
    """Email could not be delivered."""


def generate_verification_token(user):
    """Create a signed token containing the user ID and email."""
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="online-shop-email-verification"
    )
    return serializer.dumps({"user_id": user.id, "email": user.email})


def load_verification_token(token):
    """Return verified token data or None for invalid/expired tokens."""
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="online-shop-email-verification"
    )
    try:
        data = serializer.loads(
            token, max_age=current_app.config.get(
                "EMAIL_VERIFICATION_TOKEN_MAX_AGE", 3600
            )
        )
        if not isinstance(data, dict) or "user_id" not in data or "email" not in data:
            return None
        return data
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def _deliver_email(recipient, subject, body):
    """Send a plain-text email through configured SMTP."""
    config = current_app.config
    server = config.get("MAIL_SERVER", "")
    sender = config.get("MAIL_DEFAULT_SENDER") or config.get("MAIL_USERNAME", "")

    if not server or not sender:
        if current_app.testing:
            current_app.logger.info("Email skipped in test mode for %s.", recipient)
            return False
        raise EmailDeliveryError("Email delivery is not configured.")

    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, recipient, subject
    message.set_content(body)

    try:
        with smtplib.SMTP(server, config.get("MAIL_PORT", 587), timeout=15) as smtp:
            if config.get("MAIL_USE_TLS", True):
                smtp.starttls()
            username, password = config.get("MAIL_USERNAME"), config.get("MAIL_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as error:
        current_app.logger.exception("Email delivery failed.")
        raise EmailDeliveryError("The email could not be sent. Please try again.") from error


def send_verification_email(user, verification_url):
    """Send a time-limited email-verification link."""
    if current_app.debug and not current_app.config.get("MAIL_SERVER"):
        current_app.logger.warning(
            "SMTP is not configured; local verification URL for %s: %s",
            user.email, verification_url,
        )
        return False

    age = current_app.config.get("EMAIL_VERIFICATION_TOKEN_MAX_AGE", 3600)
    body = (
        f"Hello {user.username},\n\n"
        "Please verify your email by opening this link:\n"
        f"{verification_url}\n\n"
        f"This link expires in approximately {age // 60} minutes.\n"
        "If you did not create this account, you can ignore this email."
    )
    return _deliver_email(user.email, "Verify your Online Shop email", body)

def send_marketing_email(subject, body):
    """Send promotional emails only to eligible customers."""
    subject, body = (subject or "").strip(), (body or "").strip()
    if not subject or not body:
        raise EmailDeliveryError("Subject and message are required.")

    try:
        users = db.session.scalars(
            select(User).where(
                User.is_active.is_(True),
                User.email_verified.is_(True),
                User.marketing_opt_in.is_(True),
            )
        ).all()
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Could not load marketing recipients.")
        raise EmailDeliveryError("Could not load campaign recipients.") from error

    sent = failed = 0
    for user in users:
        try:
            if _deliver_email(user.email, subject, body):
                sent += 1
            else:
                failed += 1
                current_app.logger.warning(
                    "Marketing email delivery failed for user %s.", user.id
                )
        except EmailDeliveryError:
            failed += 1
            current_app.logger.exception(
                "Marketing email delivery failed for user %s.", user.id
            )

    return {"sent": sent, "failed": failed}

def request_verification_email(email):
    """Resend verification email with a persistent 60-second cooldown."""
    email = (email or "").strip().lower()

    try:
        user = db.session.scalar(
            select(User).where(User.email == email).with_for_update()
        )
        if user is None or not user.is_active or user.email_verified:
            db.session.rollback()
            return "unavailable"

        now = datetime.now(timezone.utc)
        last_sent = user.verification_email_sent_at

        if last_sent:
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            else:
                last_sent = last_sent.astimezone(timezone.utc)

            if (now - last_sent).total_seconds() < 60:
                db.session.rollback()
                return "cooldown"

        user_id = user.id
        token = generate_verification_token(user)
        link = url_for("auth.verify_email", token=token, _external=True)
        user.verification_email_sent_at = now
        db.session.commit()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Could not prepare verification email.")
        raise EmailDeliveryError(
            "The verification email request could not be processed."
        ) from error

    try:
        send_verification_email(user, link)
    except Exception as error:
        try:
            db.session.execute(
                update(User)
                .where(
                    User.id == user_id,
                    User.verification_email_sent_at == now,
                )
                .values(verification_email_sent_at=None),
                execution_options={"synchronize_session": False},
            )
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception(
                "Could not reset verification cooldown after delivery failure."
            )

        if isinstance(error, EmailDeliveryError):
            raise

        current_app.logger.exception("Unexpected verification email error.")
        raise EmailDeliveryError(
            "The verification email could not be sent. Please try again."
        ) from error

    return "sent"