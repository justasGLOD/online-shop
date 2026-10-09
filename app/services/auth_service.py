from flask import current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.crud.user_crud import (
    create_user,
    get_user_by_email,
    get_user_by_username,
)
from app.extensions import db
from app.models import User


class RegistrationError(Exception):
    """Expected error raised when registration cannot be completed."""


def register_user(username, email, password):
    """Validate and create a new user account."""

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
            "We couldn't create your account because of a database error. "
            "Please try again."
        ) from error