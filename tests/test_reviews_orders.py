
from decimal import Decimal

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Order, OrderItem, Product, Review, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "review-orders-test-secret"
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
def review_data(app):
    """Create a customer and product for review and order-history tests."""
    with app.app_context():
        user = User(
            username="reviewuser",
            email="reviewuser@example.com",
            password_hash=generate_password_hash("ReviewPass123!"),
            balance=Decimal("100.00"),
            is_admin=False,
        )

        product = Product(
            name="Review Test Keyboard",
            description="A keyboard for review and order tests.",
            price=Decimal("12.50"),
            stock=10,
            is_active=True,
        )

        db.session.add_all([user, product])
        db.session.commit()

        return {
            "user_id": user.id,
            "username": user.username,
            "password": "ReviewPass123!",
            "product_id": product.id,
        }


def login_as(client, username, password):
    """Log in through the existing authentication route."""
    return client.post(
        "/login",
        data={
            "identity": username,
            "password": password,
        },
        follow_redirects=True,
    )


def create_completed_order(
    user_id,
    product_id,
    quantity=2,
    item_price=Decimal("12.50"),
):
    """Create a completed order containing the specified product."""
    order = Order(
        user_id=user_id,
        total_price=item_price * quantity,
        status="completed",
    )

    db.session.add(order)
    db.session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product_id,
        quantity=quantity,
        price_at_purchase=item_price,
    )

    db.session.add(item)
    db.session.commit()

    return order.id


def get_reviews(user_id, product_id):
    """Return reviews submitted by a customer for a product."""
    statement = select(Review).where(
        Review.user_id == user_id,
        Review.product_id == product_id,
    )

    return db.session.scalars(statement).all()


# -----------------------------
# PRODUCT REVIEW TESTS
# -----------------------------

def test_review_submission_requires_login(client, review_data):
    response = client.post(
        f"/products/{review_data['product_id']}/reviews",
        data={
            "rating": 5,
            "comment": "Excellent keyboard.",
        },
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_cannot_review_without_purchase(
    app,
    client,
    review_data,
):
    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    response = client.post(
        f"/products/{review_data['product_id']}/reviews",
        data={
            "rating": 5,
            "comment": "Excellent keyboard.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    with app.app_context():
        reviews = get_reviews(
            review_data["user_id"],
            review_data["product_id"],
        )

        assert reviews == []


def test_customer_can_review_purchased_product(
    app,
    client,
    review_data,
):
    with app.app_context():
        create_completed_order(
            review_data["user_id"],
            review_data["product_id"],
        )

    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    response = client.post(
        f"/products/{review_data['product_id']}/reviews",
        data={
            "rating": 5,
            "comment": "Excellent keyboard.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"submitted successfully" in response.data
    assert b"Excellent keyboard." in response.data

    with app.app_context():
        reviews = get_reviews(
            review_data["user_id"],
            review_data["product_id"],
        )

        assert len(reviews) == 1
        assert reviews[0].rating == 5
        assert reviews[0].comment == "Excellent keyboard."


def test_customer_cannot_submit_duplicate_review(
    app,
    client,
    review_data,
):
    with app.app_context():
        create_completed_order(
            review_data["user_id"],
            review_data["product_id"],
        )

    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    review_url = (
        f"/products/{review_data['product_id']}/reviews"
    )

    first_response = client.post(
        review_url,
        data={
            "rating": 5,
            "comment": "Excellent keyboard.",
        },
        follow_redirects=True,
    )

    assert first_response.status_code == 200

    second_response = client.post(
        review_url,
        data={
            "rating": 4,
            "comment": "I tried to review it again.",
        },
        follow_redirects=True,
    )

    assert second_response.status_code == 200

    with app.app_context():
        reviews = get_reviews(
            review_data["user_id"],
            review_data["product_id"],
        )

        assert len(reviews) == 1
        assert reviews[0].rating == 5


def test_review_rejects_invalid_rating(
    app,
    client,
    review_data,
):
    with app.app_context():
        create_completed_order(
            review_data["user_id"],
            review_data["product_id"],
        )

    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    response = client.post(
        f"/products/{review_data['product_id']}/reviews",
        data={
            "rating": 6,
            "comment": "This rating is invalid.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert (
        b"Please provide a rating from 1 to 5"
        in response.data
    )

    with app.app_context():
        reviews = get_reviews(
            review_data["user_id"],
            review_data["product_id"],
        )

        assert reviews == []


# -----------------------------
# ORDER HISTORY TESTS
# -----------------------------

def test_order_history_requires_login(client):
    response = client.get("/orders/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_can_view_own_order_history(
    app,
    client,
    review_data,
):
    with app.app_context():
        order_id = create_completed_order(
            review_data["user_id"],
            review_data["product_id"],
        )

    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    response = client.get("/orders/")

    assert response.status_code == 200
    assert f"Order #{order_id}".encode() in response.data
    assert b"Review Test Keyboard" in response.data
    assert b"completed" in response.data.lower()
    assert b"25.00" in response.data
    assert b"12.50" in response.data


def test_customer_cannot_see_another_users_orders(
    app,
    client,
    review_data,
):
    with app.app_context():
        own_order_id = create_completed_order(
            review_data["user_id"],
            review_data["product_id"],
        )

        other_user = User(
            username="anothercustomer",
            email="anothercustomer@example.com",
            password_hash=generate_password_hash(
                "AnotherPass123!"
            ),
            balance=Decimal("100.00"),
            is_admin=False,
        )

        db.session.add(other_user)
        db.session.flush()

        other_order_id = create_completed_order(
            other_user.id,
            review_data["product_id"],
            quantity=1,
            item_price=Decimal("12.50"),
        )

    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    response = client.get("/orders/")

    assert response.status_code == 200
    assert f"Order #{own_order_id}".encode() in response.data
    assert f"Order #{other_order_id}".encode() not in response.data


def test_empty_order_history_shows_message(
    client,
    review_data,
):
    login_as(
        client,
        review_data["username"],
        review_data["password"],
    )

    response = client.get("/orders/")

    assert response.status_code == 200
    assert b"You haven't placed any orders yet." in response.data
