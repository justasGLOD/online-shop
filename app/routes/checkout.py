
from decimal import Decimal

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.forms import CheckoutForm
from app.services.cart_service import (
    CartError,
    calculate_cart_total,
    get_user_cart,
)
from app.services.checkout_service import (
    CheckoutError,
    EmptyCartError,
    checkout_cart,
)


checkout_bp = Blueprint(
    "checkout",
    __name__,
    url_prefix="/checkout",
)


@checkout_bp.route("/", methods=["GET", "POST"])
@login_required
def checkout_page():
    """Display checkout and process a confirmed purchase."""
    form = CheckoutForm()

    if form.validate_on_submit():
        try:
            order = checkout_cart(current_user.id)

            flash(
                f"Order #{order.id} placed successfully. "
                f"Total: €{order.total_price:.2f}",
                "success",
            )

            return redirect(url_for("cart.view_cart"))

        except EmptyCartError as error:
            flash(str(error), "error")
            return redirect(url_for("cart.view_cart"))

        except CheckoutError as error:
            flash(str(error), "error")
            return redirect(url_for("cart.view_cart"))

        except Exception:
            current_app.logger.exception(
                "Unexpected error processing checkout for user %s.",
                current_user.id,
            )
            flash(
                "Your purchase could not be completed. "
                "Please try again.",
                "error",
            )
            return redirect(url_for("cart.view_cart"))

    try:
        cart = get_user_cart(current_user.id)

        if not cart.items:
            flash("Your shopping cart is empty.", "error")
            return redirect(url_for("cart.view_cart"))

        total = calculate_cart_total(cart)
        balance = Decimal(str(current_user.balance))

        return render_template(
            "checkout/checkout.html",
            cart=cart,
            total=total,
            balance=balance,
            form=form,
        )

    except CartError as error:
        flash(str(error), "error")
        return redirect(url_for("cart.view_cart"))

    except Exception:
        current_app.logger.exception(
            "Unexpected error displaying checkout for user %s.",
            current_user.id,
        )
        flash(
            "Checkout could not be loaded. Please try again.",
            "error",
        )
        return redirect(url_for("cart.view_cart"))
