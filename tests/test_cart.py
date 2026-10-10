
from decimal import Decimal

import pytest
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Cart, CartItem, Product, User


class TestConfig:
    TESTING = True
    SECRET_KEY = "shopping-cart-test-secret"
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
    """Create two separate customer accounts."""
    with app.app_context():
        customer = User(
            username="cartcustomer",
            email="cartcustomer@example.com",
            password_hash=generate_password_hash("CartPass123!"),
            is_admin=False,
        )

        other_customer = User(
            username="othercustomer",
            email="othercustomer@example.com",
            password_hash=generate_password_hash("OtherPass123!"),
            is_admin=False,
        )

        db.session.add_all([customer, other_customer])
        db.session.commit()

        return {
            "customer_id": customer.id,
            "customer_username": "cartcustomer",
            "customer_password": "CartPass123!",
            "other_id": other_customer.id,
            "other_username": "othercustomer",
            "other_password": "OtherPass123!",
        }


@pytest.fixture
def sample_product(app):
    """Create an active product with limited stock."""
    with app.app_context():
        product = Product(
            name="Test Mouse",
            description="A mouse for cart tests.",
            price=Decimal("12.50"),
            stock=5,
            is_active=True,
        )

        db.session.add(product)
        db.session.commit()

        return product.id


def login_as(client, username, password):
    """Authenticate through the existing login route."""
    return client.post(
        "/login",
        data={
            "identity": username,
            "password": password,
        },
        follow_redirects=True,
    )


def get_cart_items(user_id):
    """Return the cart items belonging to one user."""
    statement = (
        select(CartItem)
        .join(Cart, CartItem.cart_id == Cart.id)
        .where(Cart.user_id == user_id)
    )

    return db.session.scalars(statement).all()


def test_cart_requires_login(client):
    response = client.get("/cart/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_can_add_product_to_cart(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    response = client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "2"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product added to your cart." in response.data
    assert b"Test Mouse" in response.data
    assert b"\xe2\x82\xac25.00" in response.data

    with app.app_context():
        items = get_cart_items(accounts["customer_id"])

        assert len(items) == 1
        assert items[0].product_id == sample_product
        assert items[0].quantity == 2


def test_adding_same_product_updates_existing_cart_line(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "2"},
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "1"},
    )

    with app.app_context():
        items = get_cart_items(accounts["customer_id"])

        assert len(items) == 1
        assert items[0].quantity == 3


def test_customer_cannot_add_more_than_available_stock(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    response = client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "6"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Only 5 item(s) are currently in stock." in response.data

    with app.app_context():
        items = get_cart_items(accounts["customer_id"])
        assert items == []


def test_customer_cannot_add_inactive_product(
    client,
    app,
    accounts,
    sample_product,
):
    with app.app_context():
        product = db.session.get(Product, sample_product)
        product.is_active = False
        db.session.commit()

    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    response = client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "1"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"no longer available" in response.data.lower()

    with app.app_context():
        assert get_cart_items(accounts["customer_id"]) == []


def test_customer_can_update_cart_quantity(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "2"},
    )

    with app.app_context():
        items = get_cart_items(accounts["customer_id"])
        item_id = items[0].id

    response = client.post(
        f"/cart/item/{item_id}/update",
        data={"quantity": "4"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Cart quantity updated." in response.data

    with app.app_context():
        items = get_cart_items(accounts["customer_id"])

        assert len(items) == 1
        assert items[0].quantity == 4


def test_quantity_update_cannot_exceed_stock(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "2"},
    )

    with app.app_context():
        item_id = get_cart_items(accounts["customer_id"])[0].id

    response = client.post(
        f"/cart/item/{item_id}/update",
        data={"quantity": "6"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Only 5 item(s) are currently in stock." in response.data

    with app.app_context():
        items = get_cart_items(accounts["customer_id"])

        assert len(items) == 1
        assert items[0].quantity == 2


def test_customer_can_remove_cart_item(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "1"},
    )

    with app.app_context():
        item_id = get_cart_items(accounts["customer_id"])[0].id

    response = client.post(
        f"/cart/item/{item_id}/remove",
        data={},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Product removed from your cart." in response.data
    assert b"Your shopping cart is empty." in response.data

    with app.app_context():
        assert get_cart_items(accounts["customer_id"]) == []


def test_customer_cannot_modify_another_customers_cart(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "1"},
    )

    with app.app_context():
        item_id = get_cart_items(accounts["customer_id"])[0].id

    client.post("/logout")

    login_as(
        client,
        accounts["other_username"],
        accounts["other_password"],
    )

    response = client.post(
        f"/cart/item/{item_id}/remove",
        data={},
    )

    assert response.status_code == 404

    with app.app_context():
        original_items = get_cart_items(accounts["customer_id"])
        other_items = get_cart_items(accounts["other_id"])

        assert len(original_items) == 1
        assert original_items[0].id == item_id
        assert other_items == []


def test_cart_persists_between_page_visits(
    client,
    app,
    accounts,
    sample_product,
):
    login_as(
        client,
        accounts["customer_username"],
        accounts["customer_password"],
    )

    client.post(
        f"/cart/add/{sample_product}",
        data={"quantity": "3"},
    )

    first_visit = client.get("/cart/")
    second_visit = client.get("/cart/")

    assert first_visit.status_code == 200
    assert second_visit.status_code == 200
    assert b"Test Mouse" in second_visit.data
    assert b"Quantity: 3" in second_visit.data

    with app.app_context():
        carts = db.session.scalars(
            select(Cart).where(
                Cart.user_id == accounts["customer_id"]
            )
        ).all()

        assert len(carts) == 1
        assert len(get_cart_items(accounts["customer_id"])) == 1
