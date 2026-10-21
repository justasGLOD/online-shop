
from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..crud.user_crud import (
    deactivate_user,
    delete_user,
    get_all_users,
    get_user_for_admin,
)
from ..extensions import db
from ..models import Payment


class AdminUserError(Exception):
    """Raised when user administration fails."""


class AdminUserNotFoundError(AdminUserError):
    """Raised when the requested user does not exist."""


def _normalize_user_id(value):
    """Return a positive user ID, or None if the value is invalid."""
    if isinstance(value, bool):
        return None

    try:
        user_id = int(value)
    except (TypeError, ValueError, OverflowError):
        return None

    return user_id if user_id > 0 else None


def list_admin_users():
    """Return registered users for the admin management page."""
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
    """Deactivate a customer without deleting their records."""
    target_id = _normalize_user_id(user_id)
    admin_id = _normalize_user_id(acting_admin_id)

    if target_id is None:
        raise AdminUserNotFoundError("The requested user was not found.")

    if admin_id is None:
        raise AdminUserError("Administrator authorization is required.")

    if target_id == admin_id:
        raise AdminUserError("You cannot deactivate your own account.")

    try:
        acting_admin = get_user_for_admin(admin_id)

        if (
            acting_admin is None
            or not acting_admin.is_admin
            or not acting_admin.is_active
        ):
            raise AdminUserError(
                "Administrator authorization is required."
            )

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
            raise AdminUserError("This account is already inactive.")

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


def delete_admin_user(user_id, acting_admin_id):
    """Delete a customer account while preserving financial history."""
    target_id = _normalize_user_id(user_id)
    admin_id = _normalize_user_id(acting_admin_id)

    if target_id is None:
        raise AdminUserNotFoundError("The requested user was not found.")

    if admin_id is None:
        raise AdminUserError("Administrator authorization is required.")

    if target_id == admin_id:
        raise AdminUserError("You cannot delete your own account.")

    try:
        # Verify the administrator performing the action.
        acting_admin = get_user_for_admin(admin_id)

        if (
            acting_admin is None
            or not acting_admin.is_admin
            or not acting_admin.is_active
        ):
            raise AdminUserError(
                "Administrator authorization is required."
            )

        # Find the customer account.
        user = get_user_for_admin(target_id)

        if user is None:
            raise AdminUserNotFoundError(
                "The requested user was not found."
            )

        if user.is_admin:
            raise AdminUserError(
                "Administrator accounts cannot be deleted here."
            )

        # Do not delete an account while Stripe payment confirmation is pending.
        pending_payment_id = db.session.scalar(
            select(Payment.id)
            .where(
                Payment.user_id == target_id,
                Payment.status == "pending",
            )
            .limit(1)
        )

        if pending_payment_id is not None:
            raise AdminUserError(
                "This account has a pending payment. "
                "Wait for its confirmation or expiration before deleting it."
            )

        username = user.username

        # The model relationships preserve financial records and remove
        # the user's cart and reviews when the account is deleted.
        delete_user(user)

        current_app.logger.info(
            "Administrator %s deleted customer account %s (user ID %s).",
            admin_id,
            username,
            target_id,
        )
        return username

    except AdminUserError:
        db.session.rollback()
        raise
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to delete customer account %s.",
            target_id,
        )
        raise AdminUserError(
            "The account could not be deleted. Please try again."
        ) from error
