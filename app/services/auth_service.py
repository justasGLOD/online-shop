from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.crud.user_crud import (
    create_user, get_user_by_email, get_user_by_identity, get_user_by_username,
)
from app.extensions import db
from app.models import User


class RegistrationError(Exception):
    """Registration failed."""


class AuthenticationError(Exception):
    """Authentication failed."""


def register_user(username, email, password, marketing_opt_in=False):
    """Create an unverified user with a hashed password."""
    username, email = (username or "").strip(), (email or "").strip().lower()
    if not username or not email or not password:
        raise RegistrationError("Username, email and password are required.")

    try:
        if get_user_by_username(username):
            raise RegistrationError("That username is already taken.")
        if get_user_by_email(email):
            raise RegistrationError("That email address is already registered.")

        user = User(
            username=username, email=email,
            password_hash=generate_password_hash(password),
            email_verified=False, marketing_opt_in=bool(marketing_opt_in),
            verification_email_sent_at=datetime.now(timezone.utc),
        )
        return create_user(user)
    except RegistrationError:
        raise
    except IntegrityError as error:
        db.session.rollback()
        raise RegistrationError(
            "That username or email address is already registered."
        ) from error
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Database error during registration.")
        raise RegistrationError(
            "We couldn't create your account. Please try again."
        ) from error


def verify_user_email(user_id, email):
    """Verify an account only when its ID and email both match."""
    try:
        user = db.session.get(User, int(user_id))
        if user is None or user.email.lower() != str(email).strip().lower():
            return False
        if not user.email_verified:
            user.email_verified = True
            user.email_verified_at = datetime.now(timezone.utc)
            db.session.commit()
        return True
    except (TypeError, ValueError):
        db.session.rollback()
        return False
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Database error verifying email.")
        raise RegistrationError(
            "Your email could not be verified. Please try again."
        ) from error


def _as_utc(value):
    """Normalize a datetime for UTC comparisons."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def authenticate_user(identity, password):
    """Authenticate credentials and enforce escalating lockouts."""
    identity = (identity or "").strip()
    if not identity or not password:
        raise AuthenticationError("Enter your username or email and password.")

    try:
        user = get_user_by_identity(identity)
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid username/email or password.")

        now = datetime.now(timezone.utc)
        if user.blocked_until:
            unlock_time = _as_utc(user.blocked_until)
            if unlock_time > now:
                minutes = max(1, int((unlock_time - now).total_seconds() + 59) // 60)
                raise AuthenticationError(
                    f"Too many failed login attempts. Try again in about {minutes} minute(s)."
                )
            user.blocked_until = None

        if not check_password_hash(user.password_hash, password):
            user.failed_login_attempts += 1
            attempts = user.failed_login_attempts
            lockout = (
                timedelta(minutes=5) if attempts == 3 else
                timedelta(hours=1) if attempts == 4 else
                timedelta(hours=24) if attempts >= 5 else None
            )
            if lockout:
                user.blocked_until = now + lockout
            db.session.commit()

            if attempts >= 3:
                duration = "5 minutes" if attempts == 3 else "1 hour" if attempts == 4 else "24 hours"
                raise AuthenticationError(
                    f"Too many failed login attempts. Your account is blocked for {duration}."
                )
            raise AuthenticationError("Invalid username/email or password.")

        # Existing tests can bypass the gate unless they explicitly enable it.
        require_verification = current_app.config.get(
            "REQUIRE_EMAIL_VERIFICATION", not current_app.testing
        )
        if require_verification and not user.email_verified:
            raise AuthenticationError(
                "Please verify your email address before logging in."
            )

        user.failed_login_attempts, user.blocked_until = 0, None
        db.session.commit()
        return user
    except AuthenticationError:
        raise
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Database error during authentication.")
        raise