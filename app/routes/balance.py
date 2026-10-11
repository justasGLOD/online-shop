
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.forms import BalanceTopUpForm
from app.services.balance_service import (
    BalanceError,
    get_balance_overview,
    top_up_balance,
)


balance_bp = Blueprint(
    "balance",
    __name__,
    url_prefix="/balance",
)


@balance_bp.route("/")
@login_required
def overview():
    """Display the current balance and transaction history."""
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
        return redirect(url_for("auth.home"))

    except Exception:
        current_app.logger.exception(
            "Failed to load balance overview for user %s.",
            current_user.id,
        )
        flash(
            "Your balance information could not be loaded.",
            "error",
        )
        return redirect(url_for("auth.home"))


@balance_bp.route("/top-up", methods=["POST"])
@login_required
def top_up():
    """Add funds and record the transaction."""
    form = BalanceTopUpForm()

    if not form.validate_on_submit():
        flash("Please enter a valid top-up amount.", "error")
        return redirect(url_for("balance.overview"))

    try:
        new_balance, transaction = top_up_balance(
            current_user.id,
            form.amount.data,
        )

        flash(
            f"Successfully added €{transaction.amount:.2f}. "
            f"Your new balance is €{new_balance:.2f}.",
            "success",
        )

    except BalanceError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Unexpected top-up error for user %s.",
            current_user.id,
        )
        flash(
            "Your top-up could not be completed. Please try again.",
            "error",
        )

    return redirect(url_for("balance.overview"))
