from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Order, Product, User
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