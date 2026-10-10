
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.forms import CartActionForm, CartQuantityForm
from app.services.cart_service import (
    CartError,
    CartItemNotFoundError,
    add_product_to_cart,
    calculate_cart_total,
    get_user_cart,
    remove_cart_item,
    update_cart_quantity,
)


cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


@cart_bp.route("/")
@login_required
def view_cart():
    """Display the current user's saved cart."""
    try:
        cart = get_user_cart(current_user.id)
        total = calculate_cart_total(cart)

        return render_template(
            "cart/cart.html",
            cart=cart,
            total=total,
            quantity_form=CartQuantityForm(),
            action_form=CartActionForm(),
        )

    except CartError as error:
        current_app.logger.warning(
            "Could not load cart for user %s: %s",
            current_user.id,
            error,
        )
        flash(str(error), "error")
        return redirect(url_for("products.catalogue"))

    except Exception:
        current_app.logger.exception("Unexpected error loading cart.")
        flash(
            "Your cart could not be loaded. Please try again.",
            "error",
        )
        return redirect(url_for("products.catalogue"))


@cart_bp.route("/add/<int:product_id>", methods=["POST"])
@login_required
def add(product_id):
    """Add a product to the current user's cart."""
    form = CartQuantityForm()

    if not form.validate_on_submit():
        flash(
            "Enter a valid quantity greater than zero.",
            "error",
        )
        return redirect(url_for("products.catalogue"))

    try:
        add_product_to_cart(
            user_id=current_user.id,
            product_id=product_id,
            quantity=form.quantity.data,
        )

        flash("Product added to your cart.", "success")
        return redirect(url_for("cart.view_cart"))

    except CartError as error:
        flash(str(error), "error")
        return redirect(url_for("products.catalogue"))

    except Exception:
        current_app.logger.exception("Unexpected error adding to cart.")
        flash(
            "The product could not be added to your cart.",
            "error",
        )
        return redirect(url_for("products.catalogue"))


@cart_bp.route("/item/<int:item_id>/update", methods=["POST"])
@login_required
def update(item_id):
    """Update a quantity in the current user's cart."""
    form = CartQuantityForm()

    if not form.validate_on_submit():
        flash("Enter a valid quantity greater than zero.", "error")
        return redirect(url_for("cart.view_cart"))

    try:
        update_cart_quantity(
            user_id=current_user.id,
            item_id=item_id,
            quantity=form.quantity.data,
        )

        flash("Cart quantity updated.", "success")

    except CartItemNotFoundError:
        abort(404)

    except CartError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception("Unexpected error updating cart.")
        flash("The cart could not be updated. Please try again.", "error")

    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/item/<int:item_id>/remove", methods=["POST"])
@login_required
def remove(item_id):
    """Remove a line from the current user's cart."""
    form = CartActionForm()

    if not form.validate_on_submit():
        abort(400)

    try:
        remove_cart_item(
            user_id=current_user.id,
            item_id=item_id,
        )

        flash("Product removed from your cart.", "success")

    except CartItemNotFoundError:
        abort(404)

    except CartError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception("Unexpected error removing cart item.")
        flash("The cart item could not be removed.", "error")

    return redirect(url_for("cart.view_cart"))
