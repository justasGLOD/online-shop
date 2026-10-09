
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db
from app.models import Product, Review, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "product-catalogue-test-secret"
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
def catalogue_data(app):
    """Create sample products and reviews in the isolated test database."""
    with app.app_context():
        user = User(
            username="cataloguetester",
            email="catalogue@example.com",
            password_hash="test-password-hash",
        )
        db.session.add(user)
        db.session.flush()

        budget_mug = Product(
            name="Budget Mug",
            description="An affordable mug.",
            price=Decimal("10.00"),
            stock=5,
            is_active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        premium_bottle = Product(
            name="Premium Bottle",
            description="A reusable bottle.",
            price=Decimal("20.00"),
            stock=8,
            is_active=True,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        rated_gadget = Product(
            name="Rated Gadget",
            description="A highly rated gadget.",
            price=Decimal("15.00"),
            stock=3,
            is_active=True,
            created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )

        hidden_item = Product(
            name="Hidden Item",
            description="This product is not for sale.",
            price=Decimal("1.00"),
            stock=10,
            is_active=False,
            created_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
        )

        products = [
            budget_mug,
            premium_bottle,
            rated_gadget,
            hidden_item,
        ]
        db.session.add_all(products)
        db.session.flush()

        db.session.add_all([
            Review(
                user_id=user.id,
                product_id=budget_mug.id,
                rating=5,
                comment="Excellent!",
            ),
            Review(
                user_id=user.id,
                product_id=budget_mug.id,
                rating=4,
                comment="Very good.",
            ),
            Review(
                user_id=user.id,
                product_id=premium_bottle.id,
                rating=3,
                comment="Average.",
            ),
            Review(
                user_id=user.id,
                product_id=rated_gadget.id,
                rating=5,
                comment="Fantastic!",
            ),
        ])

        db.session.commit()

        return {
            "budget_id": budget_mug.id,
            "premium_id": premium_bottle.id,
            "rated_id": rated_gadget.id,
            "hidden_id": hidden_item.id,
        }


def test_catalogue_shows_active_products_only(client, catalogue_data):
    response = client.get("/products/")

    assert response.status_code == 200
    assert b"Budget Mug" in response.data
    assert b"Premium Bottle" in response.data
    assert b"Rated Gadget" in response.data
    assert b"Hidden Item" not in response.data


def test_products_sort_by_price_ascending(client, catalogue_data):
    response = client.get("/products/?sort=price_asc")

    assert response.status_code == 200

    budget = response.data.index(b"Budget Mug")
    gadget = response.data.index(b"Rated Gadget")
    premium = response.data.index(b"Premium Bottle")

    assert budget < gadget < premium


def test_products_sort_by_price_descending(client, catalogue_data):
    response = client.get("/products/?sort=price_desc")

    assert response.status_code == 200

    premium = response.data.index(b"Premium Bottle")
    gadget = response.data.index(b"Rated Gadget")
    budget = response.data.index(b"Budget Mug")

    assert premium < gadget < budget


def test_products_sort_by_rating_descending(client, catalogue_data):
    response = client.get("/products/?sort=rating_desc")

    assert response.status_code == 200

    gadget = response.data.index(b"Rated Gadget")
    budget = response.data.index(b"Budget Mug")
    premium = response.data.index(b"Premium Bottle")

    assert gadget < budget < premium


def test_invalid_sort_falls_back_to_newest(client, catalogue_data):
    response = client.get("/products/?sort=invalid_option")

    assert response.status_code == 200

    gadget = response.data.index(b"Rated Gadget")
    premium = response.data.index(b"Premium Bottle")
    budget = response.data.index(b"Budget Mug")

    assert gadget < premium < budget


def test_product_details_show_price_and_rating(client, catalogue_data):
    response = client.get(
        f"/products/{catalogue_data['budget_id']}"
    )

    assert response.status_code == 200
    assert b"Budget Mug" in response.data
    assert "€10.00".encode() in response.data
    assert b"4.5" in response.data
    assert b"2 reviews" in response.data


def test_inactive_product_details_return_404(client, catalogue_data):
    response = client.get(
        f"/products/{catalogue_data['hidden_id']}"
    )

    assert response.status_code == 404


def test_missing_product_details_return_404(client):
    response = client.get("/products/999999")

    assert response.status_code == 404
