
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import BalanceTransaction, User
from app.services.balance_service import (
    BalanceError,
    BalanceLimitExceededError,
    InvalidTopUpAmountError,
    top_up_balance,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "balance-test-secret"
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
    with app.app_context():
        user = User(
            username="balanceuser",
            email="balanceuser@example.com",
            password_hash=generate_password_hash("BalancePass123!"),
            balance=Decimal("40.00"),
            is_admin=False,
        )

        other = User(
            username="otherbalanceuser",
            email="otherbalanceuser@example.com",
            password_hash=generate_password_hash("OtherBalance123!"),
            balance=Decimal("40.00"),
            is_admin=False,
        )

        db.session.add_all([user, other])
        db.session.commit()

        return {
            "user_id": user.id,
            "username": user.username,
            "password": "BalancePass123!",
            "other_id": other.id,
        }


def login_as(client, username, password):
    return client.post(
        "/login",
        data={"identity": username, "password": password},
        follow_redirects=True,
    )


def get_transactions(user_id):
    statement = (
        select(BalanceTransaction)
        .where(BalanceTransaction.user_id == user_id)
        .order_by(
            BalanceTransaction.created_at.desc(),
            BalanceTransaction.id.desc(),
        )
    )
    return db.session.scalars(statement).all()


def test_balance_page_requires_login(client):
    response = client.get("/balance/")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_customer_can_view_balance(client, accounts):
    login_as(client, accounts["username"], accounts["password"])

    response = client.get("/balance/")

    assert response.status_code == 200
    assert b"My Balance" in response.data
    assert b"40.00" in response.data


def test_customer_can_top_up_balance(client, app, accounts):
    login_as(client, accounts["username"], accounts["password"])

    response = client.post(
        "/balance/top-up",
        data={"amount": "25.50"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Successfully added" in response.data
    assert b"65.50" in response.data

    with app.app_context():
        user = db.session.get(User, accounts["user_id"])
        transactions = get_transactions(user.id)

        assert user.balance == Decimal("65.50")
        assert len(transactions) == 1
        assert transactions[0].amount == Decimal("25.50")
        assert transactions[0].transaction_type == "top_up"


@pytest.mark.parametrize(
    "amount",
    [
        "0",
        "-1",
        "abc",
        "",
        "NaN",
        "Infinity",
        "1.239",
        "1.230",
    ],
)
def test_invalid_amount_is_rejected(app, accounts, amount):
    with app.app_context():
        with pytest.raises(InvalidTopUpAmountError):
            top_up_balance(accounts["user_id"], amount)

        user = db.session.get(User, accounts["user_id"])

        assert user.balance == Decimal("40.00")
        assert get_transactions(user.id) == []


def test_top_up_cannot_exceed_maximum_balance(app, accounts):
    with app.app_context():
        user = db.session.get(User, accounts["user_id"])
        user.balance = Decimal("99999999.00")
        db.session.commit()

        with pytest.raises(BalanceLimitExceededError):
            top_up_balance(user.id, "1.00")

        db.session.expire_all()
        user = db.session.get(User, accounts["user_id"])

        assert user.balance == Decimal("99999999.00")
        assert get_transactions(user.id) == []


def test_database_failure_rolls_back_top_up(
    app,
    accounts,
    monkeypatch,
):
    import app.services.balance_service as balance_service

    def fail_creating_transaction(transaction):
        raise SQLAlchemyError("Simulated database failure")

    monkeypatch.setattr(
        balance_service,
        "create_balance_transaction",
        fail_creating_transaction,
    )

    with app.app_context():
        with pytest.raises(BalanceError):
            balance_service.top_up_balance(
                accounts["user_id"],
                "15.00",
            )

        db.session.expire_all()
        user = db.session.get(User, accounts["user_id"])

        assert user.balance == Decimal("40.00")
        assert get_transactions(user.id) == []


def test_transaction_history_shows_top_ups_and_purchases(
    client,
    app,
    accounts,
):
    with app.app_context():
        db.session.add_all([
            BalanceTransaction(
                user_id=accounts["user_id"],
                amount=Decimal("25.00"),
                transaction_type="top_up",
            ),
            BalanceTransaction(
                user_id=accounts["user_id"],
                amount=Decimal("-10.00"),
                transaction_type="purchase",
            ),
            BalanceTransaction(
                user_id=accounts["other_id"],
                amount=Decimal("999.00"),
                transaction_type="top_up",
            ),
        ])
        db.session.commit()

    login_as(client, accounts["username"], accounts["password"])
    response = client.get("/balance/")

    assert response.status_code == 200
    assert b"Top Up" in response.data
    assert b"Purchase" in response.data
    assert b"+\xe2\x82\xac25.00" in response.data
    assert b"-\xe2\x82\xac10.00" in response.data
    assert b"+\xe2\x82\xac999.00" not in response.data


def test_top_up_only_changes_logged_in_customer(
    client,
    app,
    accounts,
):
    login_as(client, accounts["username"], accounts["password"])

    client.post(
        "/balance/top-up",
        data={"amount": "7.50"},
        follow_redirects=True,
    )

    with app.app_context():
        user = db.session.get(User, accounts["user_id"])
        other = db.session.get(User, accounts["other_id"])

        assert user.balance == Decimal("47.50")
        assert other.balance == Decimal("40.00")
        assert len(get_transactions(user.id)) == 1
        assert get_transactions(other.id) == []
