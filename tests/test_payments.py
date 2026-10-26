from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
import stripe
import time
from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import BalanceTransaction, Payment, User
from app.services.payment_service import (
    PaymentProviderError,
    create_balance_top_up_session,
)

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

def test_invalid_webhook_signature_is_rejected(
    app,
    client,
    accounts,
):
    """Reject an invalid Stripe signature without changing the balance."""
    payment_id, user_id, original_balance = create_pending_payment(
        app, accounts
    )

    timestamp = int(time.time())

    # This is valid JSON, but the Stripe signature is deliberately invalid.
    payload = (
        b'{"id":"evt_test_invalid_signature",'
        b'"type":"checkout.session.completed",'
        b'"data":{"object":{}}}'
    )

    response = client.post(
        "/payments/webhook",
        data=payload,
        headers={
            "Stripe-Signature": (
                f"t={timestamp},v1=deliberately_invalid_signature"
            )
        },
    )

    assert response.status_code == 400
    assert response.json["error"] == "Invalid Stripe webhook signature."

    with app.app_context():
        user = db.session.get(User, user_id)
        payment = db.session.get(Payment, payment_id)

        assert Decimal(str(user.balance)) == original_balance
        assert payment.status == "pending"

def test_checkout_session_creation_saves_pending_payment(
    app,
    accounts,
    monkeypatch,
):
    """Create Checkout with the correct amount and save its session ID."""
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            id="cs_test_checkout_created",
            url="https://checkout.stripe.test/session",
        )

    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        fake_create,
    )

    success_url = (
        "https://shop.example.test/payments/success"
        "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = "https://shop.example.test/payments/cancel?source=balance"

    with app.app_context():
        payment, checkout_url = create_balance_top_up_session(
            user_id=accounts["user_id"],
            amount=Decimal("25.50"),
            success_url=success_url,
            cancel_url=cancel_url,
        )

        assert checkout_url == "https://checkout.stripe.test/session"
        assert payment.amount == Decimal("25.50")
        assert payment.currency == "eur"
        assert payment.status == "pending"
        assert payment.stripe_checkout_session_id == (
            "cs_test_checkout_created"
        )

        # Stripe receives the amount in cents.
        assert captured["mode"] == "payment"
        assert captured["customer_email"] == "paymentuser@example.com"
        assert captured["client_reference_id"] == str(payment.id)
        assert captured["line_items"][0]["price_data"]["unit_amount"] == 2550
        assert captured["line_items"][0]["price_data"]["currency"] == "eur"

        # The metadata links the Checkout Session to the database payment.
        assert captured["metadata"] == {
            "payment_id": str(payment.id),
            "user_id": str(accounts["user_id"]),
        }
        assert captured["payment_intent_data"]["metadata"] == (
            captured["metadata"]
        )

        # Retry protection and return URLs are configured.
        assert captured["idempotency_key"] == (
            f"balance-top-up-{payment.id}"
        )
        assert captured["success_url"] == success_url

        cancel_query = parse_qs(
            urlsplit(captured["cancel_url"]).query
        )
        assert cancel_query["source"] == ["balance"]
        assert cancel_query["payment_id"] == [str(payment.id)]

        # Starting Checkout must not credit the customer's balance.
        user = db.session.get(User, accounts["user_id"])
        assert Decimal(str(user.balance)) == Decimal("40.00")

        transactions = db.session.scalars(
            select(BalanceTransaction).where(
                BalanceTransaction.user_id == accounts["user_id"],
                BalanceTransaction.transaction_type == "top_up",
            )
        ).all()
        assert transactions == []


def test_checkout_creation_failure_marks_payment_failed(
    app,
    accounts,
    monkeypatch,
):
    """Record Checkout creation failure without crediting the balance."""

    def fail_create(**kwargs):
        raise RuntimeError("Simulated Stripe API failure.")

    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        fail_create,
    )

    with app.app_context():
        with pytest.raises(
            PaymentProviderError,
            match="could not start checkout",
        ):
            create_balance_top_up_session(
                user_id=accounts["user_id"],
                amount=Decimal("25.50"),
                success_url=(
                    "https://shop.example.test/payments/success"
                    "?session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url="https://shop.example.test/payments/cancel",
            )

        payment = db.session.scalar(
            select(Payment)
            .where(Payment.user_id == accounts["user_id"])
            .order_by(Payment.id.desc())
        )

        assert payment is not None
        assert payment.status == "failed"
        assert payment.stripe_checkout_session_id is None

        user = db.session.get(User, accounts["user_id"])
        assert Decimal(str(user.balance)) == Decimal("40.00")

        transactions = db.session.scalars(
            select(BalanceTransaction).where(
                BalanceTransaction.user_id == accounts["user_id"],
                BalanceTransaction.transaction_type == "top_up",
            )
        ).all()
        assert transactions == []