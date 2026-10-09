
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from app.crud.user_crud import (
    create_user,
    get_user_by_email,
    get_user_by_identity,
    get_user_by_username,
)
from app.extensions import db
from app.models import User


class RegistrationError(Exception):
    """Expected error during registration."""


class AuthenticationError(Exception):
    """Expected error during authentication."""


def register_user(username, email, password):
    """Validate and create a new user."""
    username = username.strip()
    email = email.strip().lower()

    try:
        if get_user_by_username(username):
            raise RegistrationError(
                "That username is already taken."
            )

        if get_user_by_email(email):
            raise RegistrationError(
                "That email address is already registered."
            )

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )

        return create_user(user)

    except RegistrationError:
        raise

    except IntegrityError as error:
        db.session.rollback()

        current_app.logger.warning(
            "Registration encountered a database uniqueness conflict."
        )

        raise RegistrationError(
            "That username or email address is already registered."
        ) from error

    except SQLAlchemyError as error:
        db.session.rollback()

        current_app.logger.exception(
            "Database error occurred during registration."
        )

        raise RegistrationError(
            "We couldn't create your account. Please try again."
        ) from error


def _as_utc(value):
    """Normalize a database datetime for safe UTC comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def authenticate_user(identity, password):
    """Authenticate a user and enforce escalating lockouts."""
    identity = (identity or "").strip()

    if not identity or not password:
        raise AuthenticationError(
            "Enter your username or email and password."
        )

    try:
        user = get_user_by_identity(identity)

        # Use the same credential error for unknown and inactive accounts.
        if user is None or not user.is_active:
            raise AuthenticationError(
                "Invalid username/email or password."
            )

        now = datetime.now(timezone.utc)

        if user.blocked_until is not None:
            unlock_time = _as_utc(user.blocked_until)

            if unlock_time > now:
                remaining = int(
                    (unlock_time - now).total_seconds()
                )
                minutes = max(1, (remaining + 59) // 60)

                raise AuthenticationError(
                    "Too many failed login attempts. "
                    f"Try again in about {minutes} minute(s)."
                )

            # The previous lockout expired. Keep the attempt count
            # so a subsequent failure receives a longer lockout.
            user.blocked_until = None

        if not check_password_hash(
            user.password_hash,
            password,
        ):
            user.failed_login_attempts += 1
            attempts = user.failed_login_attempts

            lockout = None

            if attempts == 3:
                lockout = timedelta(minutes=5)
            elif attempts == 4:
                lockout = timedelta(hours=1)
            elif attempts >= 5:
                lockout = timedelta(hours=24)

            if lockout is not None:
                user.blocked_until = now + lockout

            db.session.commit()

            if attempts == 3:
                raise AuthenticationError(
                    "Too many failed login attempts. "
                    "Your account is blocked for 5 minutes."
                )

            if attempts == 4:
                raise AuthenticationError(
                    "Too many failed login attempts. "
                    "Your account is blocked for 1 hour."
                )

            if attempts >= 5:
                raise AuthenticationError(
                    "Too many failed login attempts. "
                    "Your account is blocked for 24 hours."
                )

            raise AuthenticationError(
                "Invalid username/email or password."
            )

        # Successful authentication clears previous failed attempts.
        user.failed_login_attempts = 0
        user.blocked_until = None

        db.session.commit()

        return user

    except AuthenticationError:
        raise

    except SQLAlchemyError as error:
        db.session.rollback()

        current_app.logger.exception(
            "Database error occurred during authentication."
        )

        raise AuthenticationError(
            "We couldn't complete login. Please try again."
        ) from error
