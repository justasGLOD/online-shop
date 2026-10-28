from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Order


CENT = Decimal("0.01")
ZERO = Decimal("0.00")
FIVE_PERCENT = Decimal("5.00")
TEN_PERCENT = Decimal("10.00")

PURCHASE_WINDOW = timedelta(days=90)
FIVE_PERCENT_ORDER_COUNT = 4
TEN_PERCENT_ORDER_COUNT = 10
SPENDING_THRESHOLD = Decimal("500.00")


class LoyaltyDiscountError(Exception):
    """Raised when loyalty eligibility or discount calculation fails."""


def _validate_user_id(user_id):
    """Reject invalid customer IDs."""
    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id < 1
    ):
        raise LoyaltyDiscountError("Invalid customer ID.")


def get_loyalty_discount_percent(
    completed_order_count,
    completed_order_spending=ZERO,
):
    """Calculate a loyalty tier from recent purchases or total spending."""
    if (
        not isinstance(completed_order_count, int)
        or isinstance(completed_order_count, bool)
        or completed_order_count < 0
    ):
        raise LoyaltyDiscountError(
            "Completed order count must be a non-negative integer."
        )

    try:
        spending = Decimal(str(completed_order_spending))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise LoyaltyDiscountError(
            "Completed order spending is invalid."
        ) from error

    if not spending.is_finite() or spending < ZERO:
        raise LoyaltyDiscountError(
            "Completed order spending cannot be negative."
        )

    # The higher purchase-frequency tier takes precedence.
    if completed_order_count >= TEN_PERCENT_ORDER_COUNT:
        return TEN_PERCENT

    # Either four recent purchases or spending above €500 qualifies.
    if (
        completed_order_count >= FIVE_PERCENT_ORDER_COUNT
        or spending > SPENDING_THRESHOLD
    ):
        return FIVE_PERCENT

    return ZERO


def get_completed_order_count(user_id, now=None):
    """Count completed purchases within the previous 90 days."""
    _validate_user_id(user_id)

    if now is None:
        now = datetime.now(timezone.utc)
    elif not isinstance(now, datetime):
        raise LoyaltyDiscountError("The purchase-window date is invalid.")

    # Store and compare timestamps consistently in UTC.
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    cutoff = now - PURCHASE_WINDOW

    statement = select(func.count(Order.id)).where(
        Order.user_id == user_id,
        Order.status == "completed",
        Order.created_at >= cutoff,
        Order.created_at <= now,
    )

    try:
        return int(db.session.scalar(statement) or 0)
    except SQLAlchemyError as error:
        db.session.rollback()
        raise LoyaltyDiscountError(
            "Customer loyalty eligibility could not be checked."
        ) from error


def get_completed_order_spending(user_id):
    """Sum all historical completed-order totals for a customer."""
    _validate_user_id(user_id)

    statement = select(func.sum(Order.total_price)).where(
        Order.user_id == user_id,
        Order.status == "completed",
    )

    try:
        result = db.session.scalar(statement)
        spending = ZERO if result is None else Decimal(str(result))

        if not spending.is_finite() or spending < ZERO:
            raise LoyaltyDiscountError(
                "Completed order spending is invalid."
            )

        return spending.quantize(CENT, rounding=ROUND_HALF_UP)

    except SQLAlchemyError as error:
        db.session.rollback()
        raise LoyaltyDiscountError(
            "Customer spending could not be calculated."
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

    multiplier = (
        Decimal("100.00") - discount_percent
    ) / Decimal("100.00")

    final_amount = (amount * multiplier).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )

    return max(ZERO, final_amount)