
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import stripe
from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Payment, User
from datetime import datetime, timezone
from sqlalchemy import select, update
from app.models import BalanceTransaction, Payment, User
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CENT = Decimal("0.01")
MIN_TOP_UP = Decimal("0.50")
MAX_BALANCE = Decimal("99999999.99")


class PaymentError(Exception):
    """Base error for payment operations."""


class PaymentConfigurationError(PaymentError):
    """Raised when payment-provider configuration is missing."""


class PaymentAmountError(PaymentError):
    """Raised when a top-up amount is invalid."""


class PaymentUserNotFoundError(PaymentError):
    """Raised when the customer cannot be found."""

class PaymentWebhookVerificationError(PaymentError):
    """Raised when a Stripe webhook cannot be verified."""

class PaymentProviderError(PaymentError):
    """Raised when the payment provider cannot process a request."""


def validate_payment_amount(amount):
    """Validate a top-up amount and normalize it to cents."""
    try:
        value = Decimal(str(amount).strip())
    except (InvalidOperation, ValueError, TypeError, AttributeError) as error:
        raise PaymentAmountError("Enter a valid top-up amount.") from error

    if not value.is_finite() or value < MIN_TOP_UP:
        raise PaymentAmountError(
            "The minimum top-up amount is €0.50."
        )

    if value.as_tuple().exponent < -2:
        raise PaymentAmountError(
            "The amount can have at most two decimal places."
        )

    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def create_balance_top_up_session(
    user_id,
    amount,
    success_url,
    cancel_url,
):
    """Create a pending top-up and a Stripe-hosted Checkout Session."""
    api_key = current_app.config.get("STRIPE_SECRET_KEY")
    currency = current_app.config.get("STRIPE_CURRENCY", "eur").lower()

    if not api_key:
        raise PaymentConfigurationError(
            "Stripe test mode is not configured yet."
        )

    amount = validate_payment_amount(amount)

    try:
        user = db.session.scalar(
            select(User).where(User.id == user_id)
        )

        if user is None or not user.is_active:
            raise PaymentUserNotFoundError(
                "Your active account could not be found."
            )

        balance = Decimal(str(user.balance))
        if balance + amount > MAX_BALANCE:
            raise PaymentAmountError(
                "This top-up would exceed your maximum account balance."
            )

        payment = Payment(
            user_id=user.id,
            amount=amount,
            currency=currency,
            status="pending",
        )
        db.session.add(payment)
        db.session.commit()

    except PaymentError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Could not create a pending payment for user %s.",
            user_id,
        )
        raise PaymentError(
            "The payment could not be initialized. Please try again."
        ) from error

    metadata = {
        "payment_id": str(payment.id),
        "user_id": str(user.id),
    }

    try:
        stripe.api_key = api_key

        parts = urlsplit(cancel_url)
        query = dict(parse_qsl(parts.query))
        query["payment_id"] = str(payment.id)
        cancel_url = urlunsplit((
            parts.scheme, parts.netloc, parts.path,
            urlencode(query), parts.fragment,
        ))

        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=user.email,
            client_reference_id=str(payment.id),
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
            line_items=[
                {
                    "price_data": {
                        "currency": currency,
                        "unit_amount": int(amount * 100),
                        "product_data": {
                            "name": f"Account balance top-up (€{amount:.2f})",
                        },
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            idempotency_key=f"balance-top-up-{payment.id}",
        )

        if not session.id or not session.url:
            raise PaymentProviderError(
                "Stripe did not return a valid Checkout Session."
            )

    except Exception as error:
        db.session.rollback()
        current_app.logger.exception(
            "Stripe Checkout Session creation failed for payment %s.",
            payment.id,
        )

        try:
            payment.status = "failed"
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception(
                "Could not mark payment %s as failed.",
                payment.id,
            )

        if isinstance(error, PaymentError):
            raise

        raise PaymentProviderError(
            "The payment provider could not start checkout. Please try again."
        ) from error

    try:
        payment.stripe_checkout_session_id = session.id
        db.session.commit()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Could not save Stripe Session for payment %s.",
            payment.id,
        )
        raise PaymentError(
            "The payment session could not be saved. Please try again."
        ) from error

    return payment, session.url


def process_stripe_webhook(payload, signature_header):
    """Verify a Stripe event and credit successful top-ups exactly once."""
    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise PaymentConfigurationError(
            "Stripe webhook is not configured."
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, signature_header, secret
        )
    except ValueError as error:
        raise PaymentWebhookVerificationError(
            "Invalid Stripe webhook payload."
        ) from error
    except stripe.error.SignatureVerificationError as error:
        raise PaymentWebhookVerificationError(
            "Invalid Stripe webhook signature."
        ) from error

    # Stripe SDK v15+ objects are not regular dictionaries.
    # to_dict() recursively converts nested Stripe objects too.
    if not isinstance(event, dict):
        event = event.to_dict()

    event_type = event.get("type")
    success_events = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }
    failure_events = {"checkout.session.async_payment_failed"}
    cancel_events = {"checkout.session.expired"}

    if event_type not in success_events | failure_events | cancel_events:
        return "ignored"

    data = event.get("data")
    session = data.get("object") if data else None
    if not session:
        raise PaymentWebhookVerificationError(
            "Stripe webhook has no Checkout Session."
        )

    session_id = session.get("id")
    metadata = session.get("metadata") or {}
    payment_id = metadata.get("payment_id")

    try:
        payment_id = int(payment_id)
    except (TypeError, ValueError) as error:
        raise PaymentWebhookVerificationError(
            "The payment reference is invalid."
        ) from error

    try:
        payment = db.session.scalar(
            select(Payment)
            .where(Payment.id == payment_id)
            .with_for_update()
        )

        if payment is None:
            current_app.logger.warning(
                "Ignoring Stripe event for unknown payment %s.",
                payment_id,
            )
            db.session.rollback()
            return "ignored"

        # Match the event to the exact stored payment.
        if (
            not session_id
            or metadata.get("user_id") != str(payment.user_id)
            or session.get("client_reference_id") != str(payment.id)
            or (
                payment.stripe_checkout_session_id is not None
                and payment.stripe_checkout_session_id != session_id
            )
        ):
            raise PaymentWebhookVerificationError(
                "Stripe Session does not match the stored payment."
            )

        expected_cents = int(payment.amount * 100)
        if (
            session.get("mode") != "payment"
            or session.get("amount_total") != expected_cents
            or (
                (session.get("currency") or "").lower()
                != payment.currency.lower()
            )
        ):
            raise PaymentWebhookVerificationError(
                "Stripe payment amount or currency does not match."
            )

        # A completed Checkout Session must also be marked as paid.
        if event_type in success_events:
            if session.get("payment_status") != "paid":
                db.session.rollback()
                return "pending"

            if payment.status == "paid":
                db.session.rollback()
                return "already_processed"

            if payment.status != "pending":
                db.session.rollback()
                return "not_pending"

            user = db.session.scalar(
                select(User)
                .where(User.id == payment.user_id)
                .with_for_update()
            )
            if user is None:
                raise PaymentUserNotFoundError(
                    "The payment account could not be found."
                )

            amount = Decimal(str(payment.amount))
            balance = Decimal(str(user.balance))

            if balance + amount > MAX_BALANCE:
                raise PaymentAmountError(
                    "The payment succeeded, but the account balance limit "
                    "would be exceeded. Manual reconciliation is required."
                )

            intent = session.get("payment_intent")
            intent_id = (
                intent
                if isinstance(intent, str)
                else intent.get("id") if intent else None
            )

            # Atomically transition pending -> paid.
            # Only the request that updates one row may credit the balance.
            result = db.session.execute(
                update(Payment)
                .where(
                    Payment.id == payment.id,
                    Payment.status == "pending",
                )
                .values(
                    status="paid",
                    stripe_checkout_session_id=session_id,
                    stripe_payment_intent_id=intent_id,
                    paid_at=datetime.now(timezone.utc),
                ),
                execution_options={"synchronize_session": False},
            )

            if result.rowcount != 1:
                db.session.rollback()
                return "already_processed"

            user.balance = balance + amount
            db.session.add(
                BalanceTransaction(
                    user_id=user.id,
                    amount=amount,
                    transaction_type="top_up",
                )
            )

            # Payment status, balance and history commit together.
            db.session.commit()
            return "paid"

        new_status = (
            "failed" if event_type in failure_events else "cancelled"
        )

        result = db.session.execute(
            update(Payment)
            .where(
                Payment.id == payment.id,
                Payment.status == "pending",
            )
            .values(
                status=new_status,
                stripe_checkout_session_id=session_id,
            ),
            execution_options={"synchronize_session": False},
        )

        db.session.commit()
        return (
            new_status
            if result.rowcount == 1
            else "already_processed"
        )

    except PaymentError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Database error processing Stripe payment webhook."
        )
        raise PaymentError(
            "Payment confirmation could not be saved. Please retry."
        ) from error

    except Exception as error:
        db.session.rollback()
        current_app.logger.exception(
            "Unexpected error processing Stripe payment webhook."
        )
        raise PaymentError(
            "Payment confirmation could not be processed."
        ) from error

def cancel_balance_top_up(payment_id, user_id):
    """Expire a pending Stripe session before marking it cancelled."""
    api_key = current_app.config.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise PaymentConfigurationError("Stripe is not configured.")

    try:
        payment = db.session.scalar(
            select(Payment).where(
                Payment.id == payment_id,
                Payment.user_id == user_id,
            )
        )
        if payment is None:
            raise PaymentError("Payment could not be found.")

        if payment.status != "pending":
            status = payment.status
            db.session.rollback()
            return status

        session_id = payment.stripe_checkout_session_id
        db.session.rollback()

        if not session_id:
            raise PaymentProviderError("The Checkout Session is unavailable.")

        stripe.api_key = api_key

        try:
            session = stripe.checkout.Session.expire(session_id)
        except Exception as expire_error:
            # Expiration fails if the customer has already completed checkout.
            try:
                session = stripe.checkout.Session.retrieve(session_id)
            except Exception as retrieve_error:
                raise PaymentProviderError(
                    "Cancellation could not be verified. Please try again."
                ) from retrieve_error

            if session.status == "complete":
                return "pending"  # The signed webhook decides the final status.
            if session.status != "expired":
                raise PaymentProviderError(
                    "Stripe could not confirm cancellation."
                ) from expire_error

        if session.status != "expired":
            raise PaymentProviderError(
                "Stripe did not confirm the session expiry."
            )

        result = db.session.execute(
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.user_id == user_id,
                Payment.status == "pending",
            )
            .values(status="cancelled"),
            execution_options={"synchronize_session": False},
        )
        db.session.commit()
        return "cancelled" if result.rowcount == 1 else "already_processed"

    except PaymentError:
        db.session.rollback()
        raise
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Failed to cancel payment %s.", payment_id)
        raise PaymentError("The payment status could not be saved.") from error
    except Exception as error:
        db.session.rollback()
        current_app.logger.exception("Stripe cancellation failed.")
        raise PaymentProviderError(
            "Payment cancellation could not be completed."
        ) from error