
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Order, Product, Review, User


ZERO = Decimal("0.00")


def get_dashboard_statistics():
    """Calculate store totals, sales trends, revenue, and product ratings."""
    total_products = db.session.scalar(
        select(func.count(Product.id))
    ) or 0

    active_products = db.session.scalar(
        select(func.count(Product.id)).where(Product.is_active.is_(True))
    ) or 0

    total_users = db.session.scalar(
        select(func.count(User.id))
    ) or 0

    active_users = db.session.scalar(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ) or 0

    total_orders = db.session.scalar(
        select(func.count(Order.id))
    ) or 0

    # Load completed orders with their items to calculate sales by date.
    completed_orders = db.session.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.status == "completed")
        .order_by(Order.created_at.asc(), Order.id.asc())
    ).all()

    total_revenue = ZERO
    daily_sales = defaultdict(
        lambda: {
            "date": "",
            "items_sold": 0,
            "order_count": 0,
            "revenue": ZERO,
        }
    )
    monthly_revenue = defaultdict(
        lambda: {
            "month": "",
            "order_count": 0,
            "revenue": ZERO,
        }
    )

    for order in completed_orders:
        order_date = order.created_at.date().isoformat()
        month_key = order.created_at.strftime("%Y-%m")
        order_revenue = Decimal(str(order.total_price))

        total_revenue += order_revenue

        day = daily_sales[order_date]
        day["date"] = order_date
        day["order_count"] += 1
        day["items_sold"] += sum(item.quantity for item in order.items)
        day["revenue"] += order_revenue

        month = monthly_revenue[month_key]
        month["month"] = month_key
        month["order_count"] += 1
        month["revenue"] += order_revenue

    daily_sales = sorted(
        daily_sales.values(),
        key=lambda row: row["date"],
        reverse=True,
    )
    monthly_revenue = sorted(
        monthly_revenue.values(),
        key=lambda row: row["month"],
        reverse=True,
    )

    top_revenue_month = max(
        monthly_revenue,
        key=lambda row: row["revenue"],
        default=None,
    )

    # Rank only products that have received reviews.
    rating_rows = db.session.execute(
        select(
            Product.name,
            func.avg(Review.rating).label("average_rating"),
            func.count(Review.id).label("review_count"),
        )
        .join(Review, Review.product_id == Product.id)
        .group_by(Product.id, Product.name)
        .order_by(
            func.avg(Review.rating).desc(),
            func.count(Review.id).desc(),
            Product.name.asc(),
        )
        .limit(5)
    ).all()

    best_rated_products = [
        {
            "name": name,
            "average_rating": float(average_rating),
            "review_count": int(review_count),
        }
        for name, average_rating, review_count in rating_rows
    ]

    return {
        "total_products": int(total_products),
        "active_products": int(active_products),
        "inactive_products": int(total_products - active_products),
        "total_users": int(total_users),
        "active_users": int(active_users),
        "inactive_users": int(total_users - active_users),
        "total_orders": int(total_orders),
        "completed_orders": len(completed_orders),
        "total_revenue": total_revenue,
        "daily_sales": daily_sales,
        "monthly_revenue": monthly_revenue,
        "top_revenue_month": top_revenue_month,
        "best_rated_products": best_rated_products,
    }
