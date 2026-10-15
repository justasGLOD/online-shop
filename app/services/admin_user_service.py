
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.crud.user_crud import (
    deactivate_user,
    get_all_users,
    get_user_for_admin,
)
from app.extensions import db


class AdminUserError(Exception):
    """Expected error during user administration."""


class AdminUserNotFoundError(AdminUserError):
    """Raised when the requested user does not exist."""


def _normalize_user_id(value):
    """Return a valid positive user ID, or None for invalid input."""
    if isinstance(value, bool):
        return None

    try:
        user_id = int(value)
    except (TypeError, ValueError):
        return None

    if user_id < 1:
        return None

    return user_id


def list_admin_users():
    """Return all registered users for the admin management page."""
    try:
        return get_all_users()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to load users for administration."
        )
        raise AdminUserError(
            "Users could not be loaded. Please try again."
        ) from error


def deactivate_admin_user(user_id, acting_admin_id):
    """Deactivate an ordinary customer without deleting their records."""

    target_id = _normalize_user_id(user_id)
    admin_id = _normalize_user_id(acting_admin_id)

    if target_id is None:
        raise AdminUserNotFoundError(
            "The requested user was not found."
        )

    if admin_id is None:
        raise AdminUserError(
            "Administrator authorization is required."
        )

    if target_id == admin_id:
        raise AdminUserError(
            "You cannot deactivate your own account."
        )

    try:
        # Verify the acting account is an active administrator.
        acting_admin = get_user_for_admin(admin_id)

        if (
            acting_admin is None
            or not acting_admin.is_admin
            or not acting_admin.is_active
        ):
            raise AdminUserError(
                "Administrator authorization is required."
            )

        # Find the target account.
        user = get_user_for_admin(target_id)

        if user is None:
            raise AdminUserNotFoundError(
                "The requested user was not found."
            )

        if user.is_admin:
            raise AdminUserError(
                "Administrator accounts cannot be deactivated here."
            )

        if not user.is_active:
            raise AdminUserError(
                "This account is already inactive."
            )

        # Changes is_active only; orders and transactions remain stored.
        return deactivate_user(user)

    except AdminUserError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to deactivate user %s.",
            target_id,
        )
        raise AdminUserError(
            "The account could not be deactivated. Please try again."
        ) from error
