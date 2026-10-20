
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from ..forms import BalanceTopUpForm
from ..services.balance_service import BalanceError, get_balance_overview
from ..services.payment_service import (
    PaymentError,
    create_balance_top_up_session,
)


balance_bp = Blueprint("balance", __name__, url_prefix="/balance")


@balance_bp.route("/")
@login_required
def overview():
    """Show the current balance and transaction history."""
    try:
        balance, transactions = get_balance_overview(current_user.id)

        return render_template(
            "balance/overview.html",
            balance=balance,
            transactions=transactions,
            form=BalanceTopUpForm(),
        )

    except BalanceError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Failed to load balance for user %s.",
            current_user.id,
        )
        flash("Your balance information could not be loaded.", "error")

    return redirect(url_for("auth.home"))


@balance_bp.route("/top-up", methods=["POST"])
@login_required
def top_up():
    """Start a Stripe Checkout Session without crediting funds directly."""
    form = BalanceTopUpForm()

    if not form.validate_on_submit():
        flash("Please enter a valid top-up amount.", "error")
        return redirect(url_for("balance.overview"))

    try:
        _, checkout_url = create_balance_top_up_session(
            user_id=current_user.id,
            amount=form.amount.data,
            success_url=(
                url_for("payments.success", _external=True)
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
            cancel_url=url_for("payments.cancel", _external=True),
        )
        return redirect(checkout_url, code=303)

    except PaymentError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Unexpected payment setup error for user %s.",
            current_user.id,
        )
        flash("Checkout could not be started. Please try again.", "error")

    return redirect(url_for("balance.overview"))
