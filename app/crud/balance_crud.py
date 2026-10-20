
from sqlalchemy import select

from ..extensions import db
from ..models import BalanceTransaction, User


def get_user_by_id(user_id):
    """Return a user by their database ID."""
    return db.session.get(User, user_id)


def get_balance_transactions(user_id):
    """Return a user's transactions, newest first."""
    statement = (
        select(BalanceTransaction)
        .where(BalanceTransaction.user_id == user_id)
        .order_by(
            BalanceTransaction.created_at.desc(),
            BalanceTransaction.id.desc(),
        )
    )
    return db.session.scalars(statement).all()


def create_balance_transaction(transaction):
    """Add a transaction without committing the entire session."""
    db.session.add(transaction)
    db.session.flush()
    return transaction
