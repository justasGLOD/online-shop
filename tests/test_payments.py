
from decimal import Decimal

import pytest
import stripe
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import BalanceTransaction, Payment, User


class PaymentTestConfig:
    TESTING = True
    SECRET_KEY = "payment-tests-only"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STRIPE_SECRET_KEY = "sk_test_placeholder"
    STRIPE_WEBHOOK_SECRET = "whsec_test_only"
    STRIPE_CURRENCY = "eur"


@pytest.fixture
def app():
    """Create an isolated in-memory application for payment tests."""
    test_app = create_app(PaymentTestConfig)

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Provide a Flask test client."""
    return app.test_client()


@pytest.fixture
def accounts(app):
    """Create a test customer."""
    with app.app_context():
        user = User(
            username="paymentuser",
            email="paymentuser@example.com",
            password_hash="test-password-hash",
            balance=Decimal("40.00"),
            is_admin=False,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        return {"user_id": user.id}


def create_pending_payment(app, accounts):
    """Create a pending top-up without contacting Stripe."""
    with app.app_context():
        user = db.session.get(User, accounts["user_id"])
        original_balance = Decimal(str(user.balance))

        payment = Payment(
            user_id=user.id,
            amount=Decimal("25.50"),
            currency="eur",
            status="pending",
            stripe_checkout_session_id="cs_test_payment_123",
        )
        db.session.add(payment)
        db.session.commit()

        return payment.id, user.id, original_balance


def build_checkout_event(
    payment_id,
    user_id,
    event_type="checkout.session.completed",
    payment_status="paid",
):
    """Build a Stripe-like event for mocked webhook tests."""
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_payment_123",
                "client_reference_id": str(payment_id),
                "metadata": {
                    "payment_id": str(payment_id),
                    "user_id": str(user_id),
                },
                "mode": "payment",
                "amount_total": 2550,
                "currency": "eur",
                "payment_status": payment_status,
                "payment_intent": "pi_test_payment_123",
            }
        },
    }


def mock_stripe_event(app, monkeypatch, event):
    """Mock verified Stripe event construction."""
    app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test_only"

    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        lambda payload, signature, secret: event,
    )


def send_webhook(client):
    """Send a request to the payment webhook."""
    return client.post(
        "/payments/webhook",
        data=b'{"test": true}',
        headers={"Stripe-Signature": "test-signature"},
    )


def test_paid_webhook_credits_balance_once(
    app,
    client,
    accounts,
    monkeypatch,
):
    payment_id, user_id, original_balance = create_pending_payment(
        app, accounts
    )
    event = build_checkout_event(payment_id, user_id)
    mock_stripe_event(app, monkeypatch, event)

    response = send_webhook(client)

    assert response.status_code == 200
    assert response.json["result"] == "paid"

    # Deliver the same successful event again.
    duplicate_response = send_webhook(client)

    assert duplicate_response.status_code == 200
    assert duplicate_response.json["result"] == "already_processed"

    with app.app_context():
        user = db.session.get(User, user_id)
        payment = db.session.get(Payment, payment_id)

        assert Decimal(str(user.balance)) == (
            original_balance + Decimal("25.50")
        )
        assert payment.status == "paid"
        assert payment.stripe_payment_intent_id == "pi_test_payment_123"

        transactions = db.session.scalars(
            select(BalanceTransaction).where(
                BalanceTransaction.user_id == user_id,
                BalanceTransaction.transaction_type == "top_up",
                BalanceTransaction.amount == Decimal("25.50"),
            )
        ).all()

        assert len(transactions) == 1


def test_unpaid_completed_session_does_not_credit_balance(
    app,
    client,
    accounts,
    monkeypatch,
):
    payment_id, user_id, original_balance = create_pending_payment(
        app, accounts
    )
    event = build_checkout_event(
        payment_id,
        user_id,
        payment_status="unpaid",
    )
    mock_stripe_event(app, monkeypatch, event)

    response = send_webhook(client)

    assert response.status_code == 200
    assert response.json["result"] == "pending"

    with app.app_context():
        user = db.session.get(User, user_id)
        payment = db.session.get(Payment, payment_id)

        assert Decimal(str(user.balance)) == original_balance
        assert payment.status == "pending"


def test_failed_payment_does_not_credit_balance(
    app,
    client,
    accounts,
    monkeypatch,
):
    payment_id, user_id, original_balance = create_pending_payment(
        app, accounts
    )
    event = build_checkout_event(
        payment_id,
        user_id,
        event_type="checkout.session.async_payment_failed",
        payment_status="unpaid",
    )
    mock_stripe_event(app, monkeypatch, event)

    response = send_webhook(client)

    assert response.status_code == 200
    assert response.json["result"] == "failed"

    with app.app_context():
        user = db.session.get(User, user_id)
        payment = db.session.get(Payment, payment_id)

        assert Decimal(str(user.balance)) == original_balance
        assert payment.status == "failed"


def test_invalid_webhook_payload_is_rejected(
    app,
    client,
    monkeypatch,
):
    app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test_only"

    def invalid_payload(payload, signature, secret):
        raise ValueError("Invalid test payload")

    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        invalid_payload,
    )

    response = send_webhook(client)

    assert response.status_code == 400
    assert b"Invalid Stripe webhook payload" in response.data
