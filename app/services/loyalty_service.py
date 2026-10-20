
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Order


CENT = Decimal("0.01")
ZERO = Decimal("0.00")
FIVE_PERCENT = Decimal("5.00")
TEN_PERCENT = Decimal("10.00")


class LoyaltyDiscountError(Exception):
    """Raised when loyalty eligibility or discount calculation fails."""


def get_loyalty_discount_percent(completed_order_count):
    """Return the loyalty discount earned from previous completed orders."""
    if (
        not isinstance(completed_order_count, int)
        or isinstance(completed_order_count, bool)
        or completed_order_count < 0
    ):
        raise LoyaltyDiscountError(
            "Completed order count must be a non-negative integer."
        )

    if completed_order_count >= 10:
        return TEN_PERCENT

    if completed_order_count >= 5:
        return FIVE_PERCENT

    return ZERO


def get_completed_order_count(user_id):
    """Count a customer's completed orders."""
    if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id < 1:
        raise LoyaltyDiscountError("Invalid customer ID.")

    statement = select(func.count(Order.id)).where(
        Order.user_id == user_id,
        Order.status == "completed",
    )

    try:
        return int(db.session.scalar(statement) or 0)
    except SQLAlchemyError as error:
        db.session.rollback()
        raise LoyaltyDiscountError(
            "Customer loyalty eligibility could not be checked."
        ) from error


def apply_loyalty_discount(amount, discount_percent):
    """Apply a loyalty percentage to an already discounted price."""
    try:
        amount = Decimal(str(amount))
        discount_percent = Decimal(str(discount_percent))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise LoyaltyDiscountError(
            "Invalid amount or loyalty discount."
        ) from error

    if not amount.is_finite() or amount < ZERO:
        raise LoyaltyDiscountError(
            "The purchase amount cannot be negative."
        )

    if (
        not discount_percent.is_finite()
        or discount_percent < ZERO
        or discount_percent > Decimal("100.00")
    ):
        raise LoyaltyDiscountError(
            "Loyalty discount must be between 0% and 100%."
        )

    multiplier = (Decimal("100.00") - discount_percent) / Decimal("100.00")
    final_amount = (amount * multiplier).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )

    return max(ZERO, final_amount)
