
from decimal import Decimal

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Product, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "admin-product-test-secret"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def app():
    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def accounts(app):
    """Create ordinary and administrator accounts in the test database."""
    with app.app_context():
        regular_user = User(
            username="regularuser",
            email="regular@example.com",
            password_hash=generate_password_hash("RegularPass123!"),
            is_admin=False,
        )

        admin_user = User(
            username="testadmin",
            email="admin@example.com",
            password_hash=generate_password_hash("AdminPass123!"),
            is_admin=True,
        )

        db.session.add_all([regular_user, admin_user])
        db.session.commit()

        return {
            "regular_username": "regularuser",
            "regular_password": "RegularPass123!",
            "admin_username": "testadmin",
            "admin_password": "AdminPass123!",
        }


@pytest.fixture
def sample_product(app):
    """Create a product for stock and deactivation tests."""
    with app.app_context():
        product = Product(
            name="Test Desk Lamp",
            description="A test product.",
            price=Decimal("19.99"),
            stock=5,
            is_active=True,
        )

        db.session.add(product)
        db.session.commit()

        return product.id


def login_as(client, username, password):
    """Log in using the existing login route."""
    return client.post(
        "/login",
        data={
            "identity": username,
            "password": password,
        },
        follow_redirects=True,
    )


def test_admin_products_requires_login(client):
    response = client.get("/admin/products")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_regular_user_cannot_access_admin_products(
    client,
    accounts,
):
    login_as(
        client,
        accounts["regular_username"],
        accounts["regular_password"],
    )

    response = client.get("/admin/products")

    assert response.status_code == 403


def test_admin_can_create_product(client, app, accounts):
    login_as(
        client,
        accounts["admin_username"],
        accounts["admin_password"],
    )

    response = client.post(
        "/admin/products/new",
        data={
            "name": "Wireless Mouse",
            "description": "A wireless computer mouse.",
            "price": "24.99",
            "stock": "10",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product created successfully." in response.data

    with app.app_context():
        product = db.session.scalar(
            select(Product).where(
                Product.name == "Wireless Mouse"
            )
        )

        assert product is not None
        assert product.price == Decimal("24.99")
        assert product.stock == 10
        assert product.is_active is True


def test_admin_cannot_create_product_with_invalid_price(
    client,
    app,
    accounts,
):
    login_as(
        client,
        accounts["admin_username"],
        accounts["admin_password"],
    )

    response = client.post(
        "/admin/products/new",
        data={
            "name": "Invalid Product",
            "description": "Invalid price test.",
            "price": "0",
            "stock": "5",
        },
    )

    assert response.status_code == 200

    with app.app_context():
        product = db.session.scalar(
            select(Product).where(
                Product.name == "Invalid Product"
            )
        )

        assert product is None


def test_admin_can_increase_stock(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["admin_username"],
        accounts["admin_password"],
    )

    response = client.post(
        f"/admin/products/{sample_product}/restock",
        data={"quantity": "7"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product stock updated successfully." in response.data

    with app.app_context():
        product = db.session.get(Product, sample_product)

        assert product is not None
        assert product.stock == 12


def test_admin_can_deactivate_product_without_deleting_it(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["admin_username"],
        accounts["admin_password"],
    )

    response = client.post(
        f"/admin/products/{sample_product}/deactivate",
        data={},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product removed from sale." in response.data

    with app.app_context():
        product = db.session.get(Product, sample_product)

        assert product is not None
        assert product.is_active is False

    public_response = client.get("/products/")

    assert b"Test Desk Lamp" not in public_response.data
