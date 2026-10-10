
from decimal import Decimal

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    BalanceTransaction,
    Cart,
    CartItem,
    Order,
    OrderItem,
    Product,
    User,
)
from app.services.checkout_service import (
    CheckoutProductUnavailableError,
    EmptyCartError,
    InsufficientBalanceError,
    InsufficientStockError,
    checkout_cart,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "checkout-test-secret"
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
def checkout_data(app):
    """Create a customer, a product, a cart and a cart item."""
    with app.app_context():
        user = User(
            username="checkoutuser",
            email="checkoutuser@example.com",
            password_hash=generate_password_hash("CheckoutPass123!"),
            balance=Decimal("100.00"),
            is_admin=False,
        )

        product = Product(
            name="Checkout Test Keyboard",
            description="A keyboard for checkout tests.",
            price=Decimal("12.50"),
            stock=5,
            is_active=True,
        )

        db.session.add_all([user, product])
        db.session.flush()

        cart = Cart(user_id=user.id)
        db.session.add(cart)
        db.session.flush()

        item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=2,
        )

        db.session.add(item)
        db.session.commit()

        return {
            "user_id": user.id,
            "username": user.username,
            "password": "CheckoutPass123!",
            "product_id": product.id,
            "cart_id": cart.id,
            "item_id": item.id,
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


def get_order_items(order_id):
    return db.session.scalars(
        select(OrderItem).where(OrderItem.order_id == order_id)
    ).all()


def get_cart_items(cart_id):
    return db.session.scalars(
        select(CartItem).where(CartItem.cart_id == cart_id)
    ).all()


def get_user_orders(user_id):
    return db.session.scalars(
        select(Order).where(Order.user_id == user_id)
    ).all()


def get_user_transactions(user_id):
    return db.session.scalars(
        select(BalanceTransaction).where(
            BalanceTransaction.user_id == user_id
        )
    ).all()


def test_successful_checkout_updates_everything(app, checkout_data):
    """A successful purchase updates balance, stock, order and cart."""
    with app.app_context():
        order = checkout_cart(checkout_data["user_id"])

        user = db.session.get(User, checkout_data["user_id"])
        product = db.session.get(Product, checkout_data["product_id"])
        cart = db.session.get(Cart, checkout_data["cart_id"])

        assert order.id is not None
        assert order.total_price == Decimal("25.00")
        assert order.status == "completed"

        assert user.balance == Decimal("75.00")
        assert product.stock == 3

        order_items = get_order_items(order.id)

        assert len(order_items) == 1
        assert order_items[0].product_id == checkout_data["product_id"]
        assert order_items[0].quantity == 2
        assert order_items[0].price_at_purchase == Decimal("12.50")

        transactions = get_user_transactions(user.id)

        assert len(transactions) == 1
        assert transactions[0].amount == Decimal("-25.00")
        assert transactions[0].transaction_type == "purchase"

        assert cart is not None
        assert get_cart_items(cart.id) == []


def test_insufficient_balance_changes_nothing(app, checkout_data):
    """An unaffordable order must not deduct money or stock."""
    with app.app_context():
        user = db.session.get(User, checkout_data["user_id"])
        user.balance = Decimal("10.00")
        db.session.commit()

        with pytest.raises(InsufficientBalanceError):
            checkout_cart(user.id)

        db.session.expire_all()

        user = db.session.get(User, checkout_data["user_id"])
        product = db.session.get(Product, checkout_data["product_id"])

        assert user.balance == Decimal("10.00")
        assert product.stock == 5
        assert get_user_orders(user.id) == []
        assert get_user_transactions(user.id) == []
        assert len(get_cart_items(checkout_data["cart_id"])) == 1


def test_insufficient_stock_changes_nothing(app, checkout_data):
    """Checkout fails if stock is lower than the cart quantity."""
    with app.app_context():
        product = db.session.get(Product, checkout_data["product_id"])
        product.stock = 1
        db.session.commit()

        with pytest.raises(InsufficientStockError):
            checkout_cart(checkout_data["user_id"])

        db.session.expire_all()

        user = db.session.get(User, checkout_data["user_id"])
        product = db.session.get(Product, checkout_data["product_id"])

        assert user.balance == Decimal("100.00")
        assert product.stock == 1
        assert get_user_orders(user.id) == []
        assert get_user_transactions(user.id) == []
        assert len(get_cart_items(checkout_data["cart_id"])) == 1


def test_inactive_product_rejects_checkout(app, checkout_data):
    """An inactive product cannot be purchased."""
    with app.app_context():
        product = db.session.get(Product, checkout_data["product_id"])
        product.is_active = False
        db.session.commit()

        with pytest.raises(CheckoutProductUnavailableError):
            checkout_cart(checkout_data["user_id"])

        db.session.expire_all()

        user = db.session.get(User, checkout_data["user_id"])
        product = db.session.get(Product, checkout_data["product_id"])

        assert user.balance == Decimal("100.00")
        assert product.stock == 5
        assert get_user_orders(user.id) == []
        assert get_user_transactions(user.id) == []
        assert len(get_cart_items(checkout_data["cart_id"])) == 1


def test_empty_cart_cannot_be_purchased(app, checkout_data):
    """Checkout refuses to create an order for an empty cart."""
    with app.app_context():
        for item in get_cart_items(checkout_data["cart_id"]):
            db.session.delete(item)

        db.session.commit()

        with pytest.raises(EmptyCartError):
            checkout_cart(checkout_data["user_id"])

        user = db.session.get(User, checkout_data["user_id"])

        assert user.balance == Decimal("100.00")
        assert get_user_orders(user.id) == []
        assert get_user_transactions(user.id) == []


def test_checkout_page_requires_login(client):
    response = client.get("/checkout/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_checkout_page_shows_order_summary(
    client,
    checkout_data,
):
    login_response = login_as(
        client,
        checkout_data["username"],
        checkout_data["password"],
    )

    assert login_response.status_code == 200

    response = client.get("/checkout/")

    assert response.status_code == 200
    assert b"Checkout" in response.data
    assert b"Checkout Test Keyboard" in response.data
    assert b"25.00" in response.data
    assert b"100.00" in response.data


def test_checkout_form_completes_purchase(
    client,
    app,
    checkout_data,
):
    login_as(
        client,
        checkout_data["username"],
        checkout_data["password"],
    )

    response = client.post(
        "/checkout/",
        data={"submit": "Confirm purchase"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"placed successfully" in response.data

    with app.app_context():
        user = db.session.get(User, checkout_data["user_id"])
        product = db.session.get(Product, checkout_data["product_id"])

        assert user.balance == Decimal("75.00")
        assert product.stock == 3
        assert len(get_user_orders(user.id)) == 1
        assert len(get_user_transactions(user.id)) == 1
        assert get_cart_items(checkout_data["cart_id"]) == []
