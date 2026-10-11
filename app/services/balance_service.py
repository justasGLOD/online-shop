
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.crud.balance_crud import (
    create_balance_transaction,
    get_balance_transactions,
    get_user_by_id,
)
from app.extensions import db
from app.models import BalanceTransaction, User


CENT = Decimal("0.01")
MAX_BALANCE = Decimal("99999999.99")


class BalanceError(Exception):
    """Base exception for balance-management operations."""


class BalanceUserNotFoundError(BalanceError):
    """Raised when the requested user does not exist."""


class InvalidTopUpAmountError(BalanceError):
    """Raised when a top-up amount is invalid."""


class BalanceLimitExceededError(BalanceError):
    """Raised when a top-up would exceed the balance limit."""


def _validate_top_up_amount(amount):
    """Convert an amount to Decimal and validate currency precision."""
    try:
        value = Decimal(str(amount).strip())

        if not value.is_finite() or value <= 0:
            raise InvalidTopUpAmountError(
                "The top-up amount must be greater than zero."
            )

        if value.as_tuple().exponent < -2:
            raise InvalidTopUpAmountError(
                "The top-up amount can have at most two decimal places."
            )
        
        normalized = value.quantize(CENT)

    except InvalidTopUpAmountError:
        raise

    except (InvalidOperation, ValueError, TypeError, AttributeError) as error:
        raise InvalidTopUpAmountError(
            "Enter a valid amount with no more than two decimal places."
        ) from error

    if value != normalized:
        raise InvalidTopUpAmountError(
            "The top-up amount can have at most two decimal places."
        )

    if normalized > MAX_BALANCE:
        raise InvalidTopUpAmountError(
            "The top-up amount is too large."
        )

    return normalized


def get_balance_overview(user_id):
    """Return the user's current balance and transaction history."""
    user = get_user_by_id(user_id)

    if user is None:
        raise BalanceUserNotFoundError(
            "Your account could not be found."
        )

    transactions = get_balance_transactions(user.id)

    return Decimal(str(user.balance)), transactions


def top_up_balance(user_id, amount):
    """
    Add store credit and record the top-up atomically.

    If saving either the balance or its transaction fails, both changes
    are rolled back.
    """
    amount = _validate_top_up_amount(amount)

    try:
        # Lock the user row on databases that support row-level locking.
        statement = (
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        user = db.session.scalar(statement)

        if user is None:
            raise BalanceUserNotFoundError(
                "Your account could not be found."
            )

        current_balance = Decimal(str(user.balance))
        new_balance = current_balance + amount

        if new_balance > MAX_BALANCE:
            raise BalanceLimitExceededError(
                "This top-up would exceed your maximum account balance."
            )

        user.balance = new_balance

        transaction = BalanceTransaction(
            user_id=user.id,
            amount=amount,
            transaction_type="top_up",
        )

        create_balance_transaction(transaction)

        # Commit the balance and transaction record together.
        db.session.commit()

        return new_balance, transaction

    except BalanceError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()

        current_app.logger.exception(
            "Database error while topping up balance for user %s.",
            user_id,
        )

        raise BalanceError(
            "Your balance could not be updated. Please try again."
        ) from error

    except Exception as error:
        db.session.rollback()

        current_app.logger.exception(
            "Unexpected balance top-up error for user %s.",
            user_id,
        )

        raise BalanceError(
            "An unexpected error prevented the top-up. Please try again."
        ) from error
