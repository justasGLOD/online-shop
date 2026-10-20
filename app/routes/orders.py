
from flask import Blueprint, current_app, flash, render_template
from flask_login import current_user, login_required

from ..services.order_service import (
    OrderHistoryError,
    get_user_order_history,
)


orders_bp = Blueprint("orders", __name__, url_prefix="/orders")


@orders_bp.route("/")
@login_required
def history():
    """Display the current user's order history."""
    try:
        orders = get_user_order_history(current_user.id)

    except OrderHistoryError:
        current_app.logger.exception(
            "Could not display order history for user %s.",
            current_user.id,
        )
        flash(
            "Your order history could not be loaded. Please try again.",
            "error",
        )
        orders = []

    return render_template("orders/history.html", orders=orders)
