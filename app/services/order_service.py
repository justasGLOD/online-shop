
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..crud.order_crud import get_orders_for_user
from ..extensions import db
from ..models import Order


class OrderHistoryError(Exception):
    """Raised when order history cannot be retrieved."""


def get_user_order_history(user_id: int) -> list[Order]:
    """Fetch order history for a valid user ID."""
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise OrderHistoryError("Invalid user ID.")

    try:
        return get_orders_for_user(user_id)

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to retrieve order history for user %s.",
            user_id,
        )
        raise OrderHistoryError(
            "Unable to load your order history."
        ) from error
