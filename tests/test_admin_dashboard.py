from decimal import Decimal
from datetime import datetime

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from sqlalchemy import select
from app.models import Order, OrderItem, Product, Review, User
from app.services.admin_dashboard_service import get_admin_dashboard_data


class TestConfig:
    TESTING = True
    SECRET_KEY = "admin-dashboard-test-secret"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def app():
    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def accounts(app):
    with app.app_context():
        admin = User(
            username="dashboardadmin",
            email="dashboardadmin@example.com",
            password_hash=generate_password_hash("AdminPass123!"),
            is_admin=True,
            is_active=True,
        )

        customer = User(
            username="dashboardcustomer",
            email="dashboardcustomer@example.com",
            password_hash=generate_password_hash("CustomerPass123!"),
            is_admin=False,
            is_active=True,
        )

        db.session.add_all([admin, customer])
        db.session.commit()

        return {
            "admin_username": "dashboardadmin",
            "admin_password": "AdminPass123!",
            "customer_username": "dashboardcustomer",
            "customer_password": "CustomerPass123!",
            "customer_id": customer.id,
        }


def login_as(client, username, password):
    return client.post(
        "/login",
        data={
            "identity": username,
            "password": password,
        },
        follow_redirects=True,
    )


def test_dashboard_requires_login(client):
    response = client.get("/admin/dashboard")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_regular_user_cannot_access_dashboard(client, accounts):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    response = client.get("/admin/dashboard")

    assert response.status_code == 403


def test_admin_dashboard_displays_statistics(
    app,
    client,
    accounts,
):
    with app.app_context():
        inactive_user = User(
            username="inactivecustomer",
            email="inactivecustomer@example.com",
            password_hash=generate_password_hash("InactivePass123!"),
            is_admin=False,
            is_active=False,
        )

        products = [
            Product(
                name="Active Product One",
                price=Decimal("10.00"),
                stock=5,
                is_active=True,
            ),
            Product(
                name="Active Product Two",
                price=Decimal("20.00"),
                stock=3,
                is_active=True,
            ),
            Product(
                name="Inactive Product",
                price=Decimal("30.00"),
                stock=0,
                is_active=False,
            ),
        ]

        db.session.add(inactive_user)
        db.session.add_all(products)
        db.session.flush()

        orders = [
            Order(
                user_id=accounts["customer_id"],
                total_price=Decimal("25.00"),
                status="completed",
            ),
            Order(
                user_id=accounts["customer_id"],
                total_price=Decimal("15.00"),
                status="completed",
            ),
            Order(
                user_id=accounts["customer_id"],
                total_price=Decimal("50.00"),
                status="pending",
            ),
        ]

        db.session.add_all(orders)
        db.session.commit()

        stats = get_admin_dashboard_data()

        assert stats["total_products"] == 3
        assert stats["active_products"] == 2
        assert stats["inactive_products"] == 1

        assert stats["total_users"] == 3
        assert stats["active_users"] == 2
        assert stats["inactive_users"] == 1

        assert stats["total_orders"] == 3
        assert stats["completed_orders"] == 2
        assert stats["total_revenue"] == Decimal("40.00")

    login_as(
        client,
        accounts["admin_username"],
        accounts["admin_password"],
    )

    response = client.get("/admin/dashboard")

    assert response.status_code == 200
    assert b"Admin Dashboard" in response.data
    assert b"Active Product One" not in response.data
    assert b"Total products:" in response.data
    assert b"Active products:" in response.data
    assert b"Total registered users:" in response.data
    assert b"Total orders:" in response.data
    assert b"Completed-order revenue:" in response.data
    assert "€40.00".encode("utf-8") in response.data



def test_empty_database_returns_zero_statistics(app):
    with app.app_context():
        stats = get_admin_dashboard_data()

        assert stats == {
            "total_products": 0,
            "active_products": 0,
            "inactive_products": 0,
            "total_users": 0,
            "active_users": 0,
            "inactive_users": 0,
            "total_orders": 0,
            "completed_orders": 0,
            "total_revenue": Decimal("0.00"),
            "total_cost": Decimal("0.00"),
            "total_gross_profit": Decimal("0.00"),
            "orders_with_known_cost": 0,
            "orders_missing_cost": 0,
            "daily_sales": [],
            "monthly_revenue": [],
            "top_revenue_month": None,
            "monthly_profit": [],
            "top_profit_month": None,
            "best_rated_products": [],
        }

def test_admin_dashboard_navigation_links_are_available(
    client,
    accounts,
):
    login_as(
        client,
        accounts["admin_username"],
        accounts["admin_password"],
    )

    products_response = client.get("/admin/products")
    users_response = client.get("/admin/users")

    assert products_response.status_code == 200
    assert users_response.status_code == 200

    assert b"Dashboard" in products_response.data
    assert b"Dashboard" in users_response.data

def test_dashboard_calculates_daily_monthly_sales_and_product_ratings(
    app,
    accounts,
):
    """Calculate sales trends and rank products by their customer ratings."""
    with app.app_context():
        customer_id = accounts["customer_id"]
        admin_id = db.session.scalar(
            select(User.id).where(
                User.username == accounts["admin_username"]
            )
        )

        best_product = Product(
            name="Top Rated Widget",
            price=Decimal("50.00"),
            stock=10,
            is_active=True,
        )
        second_product = Product(
            name="Runner Up Gadget",
            price=Decimal("25.00"),
            stock=10,
            is_active=True,
        )
        third_product = Product(
            name="Budget Item",
            price=Decimal("20.00"),
            stock=10,
            is_active=True,
        )
        db.session.add_all([
            best_product,
            second_product,
            third_product,
        ])
        db.session.flush()

        # Two completed orders on the same day.
        january_order_one = Order(
            user_id=customer_id,
            total_price=Decimal("100.00"),
            status="completed",
            created_at=datetime(2026, 1, 5, 10, 0),
        )
        january_order_two = Order(
            user_id=customer_id,
            total_price=Decimal("25.00"),
            status="completed",
            created_at=datetime(2026, 1, 5, 15, 0),
        )
        february_order = Order(
            user_id=customer_id,
            total_price=Decimal("40.00"),
            status="completed",
            created_at=datetime(2026, 2, 2, 12, 0),
        )

        # This order must not contribute to completed sales or revenue.
        pending_order = Order(
            user_id=customer_id,
            total_price=Decimal("900.00"),
            status="pending",
            created_at=datetime(2026, 1, 6, 12, 0),
        )

        db.session.add_all([
            january_order_one,
            january_order_two,
            february_order,
            pending_order,
        ])
        db.session.flush()

        db.session.add_all([
            OrderItem(
                order_id=january_order_one.id,
                product_id=best_product.id,
                quantity=2,
                price_at_purchase=Decimal("50.00"),
            ),
            OrderItem(
                order_id=january_order_two.id,
                product_id=second_product.id,
                quantity=1,
                price_at_purchase=Decimal("25.00"),
            ),
            OrderItem(
                order_id=february_order.id,
                product_id=third_product.id,
                quantity=2,
                price_at_purchase=Decimal("20.00"),
            ),
            OrderItem(
                order_id=pending_order.id,
                product_id=best_product.id,
                quantity=10,
                price_at_purchase=Decimal("90.00"),
            ),
        ])

        # The first product averages 5 stars; the second averages 4.5.
        db.session.add_all([
            Review(
                user_id=admin_id,
                product_id=best_product.id,
                rating=5,
                comment="Excellent product!",
            ),
            Review(
                user_id=customer_id,
                product_id=best_product.id,
                rating=5,
                comment="Really good!",
            ),
            Review(
                user_id=admin_id,
                product_id=second_product.id,
                rating=4,
                comment="Good product.",
            ),
            Review(
                user_id=customer_id,
                product_id=second_product.id,
                rating=5,
                comment="Very good!",
            ),
            Review(
                user_id=customer_id,
                product_id=third_product.id,
                rating=3,
                comment="It is okay.",
            ),
        ])

        db.session.commit()

        stats = get_admin_dashboard_data()

        # The pending order is counted in total orders, but not in sales.
        assert stats["total_orders"] == 4
        assert stats["completed_orders"] == 3
        assert stats["total_revenue"] == Decimal("165.00")

        # Daily sales are ordered newest first.
        assert stats["daily_sales"] == [
            {
                "date": "2026-02-02",
                "items_sold": 2,
                "order_count": 1,
                "revenue": Decimal("40.00"),
            },
            {
                "date": "2026-01-05",
                "items_sold": 3,
                "order_count": 2,
                "revenue": Decimal("125.00"),
            },
        ]

        # Monthly revenue is also ordered newest first.
        assert stats["monthly_revenue"] == [
            {
                "month": "2026-02",
                "order_count": 1,
                "revenue": Decimal("40.00"),
            },
            {
                "month": "2026-01",
                "order_count": 2,
                "revenue": Decimal("125.00"),
            },
        ]

        assert stats["top_revenue_month"] == {
            "month": "2026-01",
            "order_count": 2,
            "revenue": Decimal("125.00"),
        }

        # Products are ranked by average rating, with review counts included.
        assert stats["best_rated_products"] == [
            {
                "name": "Top Rated Widget",
                "average_rating": 5.0,
                "review_count": 2,
            },
            {
                "name": "Runner Up Gadget",
                "average_rating": 4.5,
                "review_count": 2,
            },
            {
                "name": "Budget Item",
                "average_rating": 3.0,
                "review_count": 1,
            },
        ]
def test_dashboard_calculates_monthly_costs_and_gross_profit(
    app,
    accounts,
):
    """Calculate monthly gross profit using historical item costs."""
    with app.app_context():
        customer_id = accounts["customer_id"]

        january_product = Product(
            name="January Product",
            price=Decimal("50.00"),
            cost_price=Decimal("35.00"),
            stock=10,
        )

        february_product = Product(
            name="February Product",
            price=Decimal("50.00"),
            cost_price=Decimal("40.00"),
            stock=10,
        )

        db.session.add_all([
            january_product,
            february_product,
        ])
        db.session.flush()

        january_order = Order(
            user_id=customer_id,
            total_price=Decimal("100.00"),
            status="completed",
            created_at=datetime(2026, 1, 5, 10, 0),
        )

        february_order = Order(
            user_id=customer_id,
            total_price=Decimal("200.00"),
            status="completed",
            created_at=datetime(2026, 2, 12, 10, 0),
        )

        db.session.add_all([
            january_order,
            february_order,
        ])
        db.session.flush()

        db.session.add_all([
            OrderItem(
                order_id=january_order.id,
                product_id=january_product.id,
                quantity=2,
                price_at_purchase=Decimal("50.00"),
                cost_at_purchase=Decimal("30.00"),
            ),
            OrderItem(
                order_id=february_order.id,
                product_id=february_product.id,
                quantity=4,
                price_at_purchase=Decimal("50.00"),
                cost_at_purchase=Decimal("25.00"),
            ),
        ])

        db.session.commit()

        stats = get_admin_dashboard_data()

        # Overall totals.
        assert stats["total_revenue"] == Decimal("300.00")
        assert stats["total_cost"] == Decimal("160.00")
        assert stats["total_gross_profit"] == Decimal("140.00")

        assert stats["orders_with_known_cost"] == 2
        assert stats["orders_missing_cost"] == 0

        # Monthly reports are ordered newest first.
        assert stats["monthly_profit"] == [
            {
                "month": "2026-02",
                "order_count": 1,
                "revenue": Decimal("200.00"),
                "cost": Decimal("100.00"),
                "gross_profit": Decimal("100.00"),
                "cost_data_complete": True,
                "orders_with_known_cost": 1,
                "orders_missing_cost": 0,
            },
            {
                "month": "2026-01",
                "order_count": 1,
                "revenue": Decimal("100.00"),
                "cost": Decimal("60.00"),
                "gross_profit": Decimal("40.00"),
                "cost_data_complete": True,
                "orders_with_known_cost": 1,
                "orders_missing_cost": 0,
            },
        ]

        # February has the highest gross profit.
        assert stats["top_profit_month"] == {
            "month": "2026-02",
            "order_count": 1,
            "revenue": Decimal("200.00"),
            "cost": Decimal("100.00"),
            "gross_profit": Decimal("100.00"),
            "cost_data_complete": True,
            "orders_with_known_cost": 1,
            "orders_missing_cost": 0,
        }

def test_dashboard_does_not_invent_missing_historical_costs(
    app,
    accounts,
):
    """Do not report complete profit figures when historical costs are missing."""
    with app.app_context():
        customer_id = accounts["customer_id"]

        product = Product(
            name="Historical Cost Test Product",
            price=Decimal("30.00"),
            cost_price=Decimal("15.00"),
            stock=10,
        )

        db.session.add(product)
        db.session.flush()

        january_known_order = Order(
            user_id=customer_id,
            total_price=Decimal("20.00"),
            status="completed",
            created_at=datetime(2026, 1, 5, 10, 0),
        )

        january_unknown_order = Order(
            user_id=customer_id,
            total_price=Decimal("30.00"),
            status="completed",
            created_at=datetime(2026, 1, 10, 10, 0),
        )

        february_order = Order(
            user_id=customer_id,
            total_price=Decimal("100.00"),
            status="completed",
            created_at=datetime(2026, 2, 5, 10, 0),
        )

        db.session.add_all([
            january_known_order,
            january_unknown_order,
            february_order,
        ])
        db.session.flush()

        db.session.add_all([
            OrderItem(
                order_id=january_known_order.id,
                product_id=product.id,
                quantity=1,
                price_at_purchase=Decimal("20.00"),
                cost_at_purchase=Decimal("8.00"),
            ),
            OrderItem(
                order_id=january_unknown_order.id,
                product_id=product.id,
                quantity=1,
                price_at_purchase=Decimal("30.00"),
                cost_at_purchase=None,
            ),
            OrderItem(
                order_id=february_order.id,
                product_id=product.id,
                quantity=2,
                price_at_purchase=Decimal("50.00"),
                cost_at_purchase=Decimal("10.00"),
            ),
        ])

        db.session.commit()

        stats = get_admin_dashboard_data()

        # Revenue remains available even when historical costs are missing.
        assert stats["total_revenue"] == Decimal("150.00")

        # Overall profit must not be calculated using incomplete cost data.
        assert stats["total_cost"] is None
        assert stats["total_gross_profit"] is None

        assert stats["orders_with_known_cost"] == 2
        assert stats["orders_missing_cost"] == 1

        january = next(
            month
            for month in stats["monthly_profit"]
            if month["month"] == "2026-01"
        )

        assert january["revenue"] == Decimal("50.00")
        assert january["cost"] is None
        assert january["gross_profit"] is None
        assert january["cost_data_complete"] is False
        assert january["orders_with_known_cost"] == 1
        assert january["orders_missing_cost"] == 1

        february = next(
            month
            for month in stats["monthly_profit"]
            if month["month"] == "2026-02"
        )

        assert february["revenue"] == Decimal("100.00")
        assert february["cost"] == Decimal("20.00")
        assert february["gross_profit"] == Decimal("80.00")
        assert february["cost_data_complete"] is True

        # One incomplete month means a global winner cannot be confirmed.
        assert stats["top_profit_month"] is None
