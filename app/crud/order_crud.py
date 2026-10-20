
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Order, OrderItem


def get_orders_for_user(user_id: int) -> list[Order]:
    """Return a user's orders with their items and products."""
    statement = (
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product)
        )
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return db.session.scalars(statement).all()
