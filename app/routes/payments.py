from flask import Blueprint, current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Payment
from app.services.payment_service import (
    PaymentConfigurationError,
    PaymentError,
    PaymentWebhookVerificationError,
    cancel_balance_top_up,
    process_stripe_webhook,
)

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.route("/webhook", methods=["POST"])
def stripe_webhook():
    """Accept only signed Stripe webhook events."""
    try:
        result = process_stripe_webhook(
            request.get_data(),
            request.headers.get("Stripe-Signature", ""),
        )
        return jsonify(received=True, result=result), 200
    except PaymentWebhookVerificationError as error:
        return jsonify(error=str(error)), 400
    except PaymentConfigurationError:
        current_app.logger.exception("Stripe webhook is not configured.")
        return jsonify(error="Webhook configuration error."), 500
    except PaymentError as error:
        current_app.logger.exception("Stripe webhook processing failed.")
        return jsonify(error=str(error)), 500
    except Exception:
        current_app.logger.exception("Unexpected Stripe webhook error.")
        return jsonify(error="Webhook processing failed."), 500


@payments_bp.route("/success")
@login_required
def success():
    """Show status only; never credit a balance from a browser redirect."""
    session_id = request.args.get("session_id", "")
    if not session_id:
        flash("Payment confirmation is still pending.", "info")
        return redirect(url_for("balance.overview"))

    try:
        payment = db.session.scalar(
            select(Payment).where(
                Payment.stripe_checkout_session_id == session_id,
                Payment.user_id == current_user.id,
            )
        )
        if payment is None:
            flash("Payment could not be found.", "error")
        elif payment.status == "paid":
            flash(
                f"Your €{payment.amount:.2f} top-up is confirmed.",
                "success",
            )
        elif payment.status == "pending":
            flash(
                "Payment is being verified. Your balance updates after confirmation.",
                "info",
            )
        else:
            flash(f"Payment status: {payment.status}.", "info")

    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Unable to load payment status.")
        flash("Payment status could not be loaded.", "error")

    return redirect(url_for("balance.overview"))


@payments_bp.route("/cancel")
@login_required
def cancel():
    """Expire the customer's pending Checkout Session."""
    payment_id = request.args.get("payment_id", type=int)
    if not payment_id:
        flash("Payment reference is missing.", "error")
        return redirect(url_for("balance.overview"))

    try:
        status = cancel_balance_top_up(payment_id, current_user.id)
        if status == "cancelled":
            flash("Payment cancelled. Your balance has not changed.", "info")
        elif status == "paid":
            flash("Payment was already confirmed.", "success")
        elif status == "pending":
            flash(
                "Payment may have completed. Its signed confirmation is being checked.",
                "info",
            )
        else:
            flash(f"Payment status: {status}.", "info")

    except PaymentError as error:
        flash(str(error), "error")
    except Exception:
        current_app.logger.exception("Unable to cancel payment %s.", payment_id)
        flash("Payment cancellation could not be verified.", "error")

    return redirect(url_for("balance.overview"))