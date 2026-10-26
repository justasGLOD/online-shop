from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Order, Product, Review, User


ZERO = Decimal("0.00")


def get_dashboard_statistics():
    """Calculate store totals, sales trends, revenue, costs, profit, and ratings."""

    # ---------------------------------------------------------
    # 1. General store statistics
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 2. Load completed orders and their items
    # ---------------------------------------------------------
    completed_orders = db.session.scalars(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.status == "completed")
        .order_by(Order.created_at.asc(), Order.id.asc())
    ).all()

    total_revenue = ZERO
    total_known_cost = ZERO

    orders_with_known_cost = 0
    orders_missing_cost = 0

    daily_sales = defaultdict(
        lambda: {
            "date": "",
            "items_sold": 0,
            "order_count": 0,
            "revenue": ZERO,
        }
    )

    monthly_revenue_data = defaultdict(
        lambda: {
            "month": "",
            "order_count": 0,
            "revenue": ZERO,
        }
    )

    monthly_profit_data = defaultdict(
        lambda: {
            "month": "",
            "order_count": 0,
            "revenue": ZERO,
            "known_cost_total": ZERO,
            "orders_with_known_cost": 0,
            "orders_missing_cost": 0,
        }
    )

    # ---------------------------------------------------------
    # 3. Calculate daily sales, monthly revenue, and costs
    # ---------------------------------------------------------
    for order in completed_orders:
        order_date = order.created_at.date().isoformat()
        month_key = order.created_at.strftime("%Y-%m")

        order_revenue = Decimal(str(order.total_price))

        total_revenue += order_revenue

        # Determine whether every item in this order has
        # a recorded historical unit cost.
        #
        # An order without items is also treated as unknown.
        has_complete_cost_data = (
            bool(order.items)
            and all(
                item.cost_at_purchase is not None
                for item in order.items
            )
        )

        if has_complete_cost_data:
            order_cost = sum(
                (
                    Decimal(str(item.cost_at_purchase))
                    * item.quantity
                    for item in order.items
                ),
                ZERO,
            )

            total_known_cost += order_cost
            orders_with_known_cost += 1
        else:
            order_cost = None
            orders_missing_cost += 1

        # Daily sales statistics.
        day = daily_sales[order_date]
        day["date"] = order_date
        day["order_count"] += 1
        day["items_sold"] += sum(
            item.quantity for item in order.items
        )
        day["revenue"] += order_revenue

        # Monthly revenue statistics.
        revenue_month = monthly_revenue_data[month_key]
        revenue_month["month"] = month_key
        revenue_month["order_count"] += 1
        revenue_month["revenue"] += order_revenue

        # Monthly profit-related statistics.
        profit_month = monthly_profit_data[month_key]
        profit_month["month"] = month_key
        profit_month["order_count"] += 1
        profit_month["revenue"] += order_revenue

        if has_complete_cost_data:
            profit_month["known_cost_total"] += order_cost
            profit_month["orders_with_known_cost"] += 1
        else:
            profit_month["orders_missing_cost"] += 1

    # ---------------------------------------------------------
    # 4. Sort daily sales and monthly revenue
    # ---------------------------------------------------------
    daily_sales = sorted(
        daily_sales.values(),
        key=lambda row: row["date"],
        reverse=True,
    )

    monthly_revenue = sorted(
        monthly_revenue_data.values(),
        key=lambda row: row["month"],
        reverse=True,
    )

    top_revenue_month = max(
        monthly_revenue,
        key=lambda row: row["revenue"],
        default=None,
    )

    # ---------------------------------------------------------
    # 5. Build reliable monthly cost and gross profit reports
    # ---------------------------------------------------------
    monthly_profit = []

    for row in sorted(
        monthly_profit_data.values(),
        key=lambda item: item["month"],
        reverse=True,
    ):
        cost_data_complete = (
            row["orders_missing_cost"] == 0
            and row["orders_with_known_cost"] == row["order_count"]
        )

        if cost_data_complete:
            monthly_cost = row["known_cost_total"]
            gross_profit = row["revenue"] - monthly_cost
        else:
            # Do not present incomplete costs or profit as totals.
            monthly_cost = None
            gross_profit = None

        monthly_profit.append(
            {
                "month": row["month"],
                "order_count": row["order_count"],
                "revenue": row["revenue"],
                "cost": monthly_cost,
                "gross_profit": gross_profit,
                "cost_data_complete": cost_data_complete,
                "orders_with_known_cost": (
                    row["orders_with_known_cost"]
                ),
                "orders_missing_cost": (
                    row["orders_missing_cost"]
                ),
            }
        )

    # The highest-profit month is only reliable when every month
    # has complete cost information.
    all_months_have_complete_costs = (
        bool(monthly_profit)
        and all(
            row["cost_data_complete"]
            for row in monthly_profit
        )
    )

    if all_months_have_complete_costs:
        top_profit_month = max(
            monthly_profit,
            key=lambda row: row["gross_profit"],
        )
    else:
        top_profit_month = None

    # Lifetime costs and gross profit are also reported only
    # when all completed orders have recorded cost data.
    if orders_missing_cost == 0:
        total_cost = total_known_cost
        total_gross_profit = total_revenue - total_cost
    else:
        total_cost = None
        total_gross_profit = None

    # ---------------------------------------------------------
    # 6. Rank the five best-rated products
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 7. Return dashboard statistics
    # ---------------------------------------------------------
    return {
        # General statistics
        "total_products": int(total_products),
        "active_products": int(active_products),
        "inactive_products": int(
            total_products - active_products
        ),
        "total_users": int(total_users),
        "active_users": int(active_users),
        "inactive_users": int(
            total_users - active_users
        ),
        "total_orders": int(total_orders),
        "completed_orders": len(completed_orders),

        # Overall financial statistics
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_gross_profit": total_gross_profit,
        "orders_with_known_cost": orders_with_known_cost,
        "orders_missing_cost": orders_missing_cost,

        # Sales reports
        "daily_sales": daily_sales,
        "monthly_revenue": monthly_revenue,
        "top_revenue_month": top_revenue_month,

        # Profit reports
        "monthly_profit": monthly_profit,
        "top_profit_month": top_profit_month,

        # Product ratings
        "best_rated_products": best_rated_products,
    }