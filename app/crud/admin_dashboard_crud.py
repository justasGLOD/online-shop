
from decimal import Decimal

from sqlalchemy import func, select

from app.extensions import db
from app.models import Order, Product, User


def get_dashboard_statistics():
    """Calculate product, user and order statistics from the database."""

    total_products = db.session.scalar(
        select(func.count(Product.id))
    ) or 0

    active_products = db.session.scalar(
        select(func.count(Product.id)).where(
            Product.is_active.is_(True)
        )
    ) or 0

    total_users = db.session.scalar(
        select(func.count(User.id))
    ) or 0

    active_users = db.session.scalar(
        select(func.count(User.id)).where(
            User.is_active.is_(True)
        )
    ) or 0

    total_orders = db.session.scalar(
        select(func.count(Order.id))
    ) or 0

    completed_orders = db.session.scalar(
        select(func.count(Order.id)).where(
            Order.status == "completed"
        )
    ) or 0

    total_revenue = db.session.scalar(
        select(func.sum(Order.total_price)).where(
            Order.status == "completed"
        )
    )

    if total_revenue is None:
        total_revenue = Decimal("0.00")
    else:
        total_revenue = Decimal(str(total_revenue))

    return {
        "total_products": int(total_products),
        "active_products": int(active_products),
        "inactive_products": int(total_products - active_products),
        "total_users": int(total_users),
        "active_users": int(active_users),
        "inactive_users": int(total_users - active_users),
        "total_orders": int(total_orders),
        "completed_orders": int(completed_orders),
        "total_revenue": total_revenue,
    }
