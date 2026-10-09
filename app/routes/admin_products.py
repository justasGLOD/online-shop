
from functools import wraps

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

from app.forms import (
    ProductActionForm,
    ProductForm,
    RestockForm,
)
from app.services.admin_product_service import (
    AdminProductError,
    AdminProductNotFoundError,
    create_admin_product,
    deactivate_admin_product,
    get_admin_product_details,
    list_admin_products,
    restock_admin_product,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    """Require an authenticated administrator."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)

        return view(*args, **kwargs)

    return wrapped


@admin_bp.route("/products")
@admin_required
def products():
    """Display all products, including inactive products."""
    try:
        products_list = list_admin_products()

    except AdminProductError as error:
        current_app.logger.warning(
            "Unable to display admin product list: %s", error
        )
        flash(str(error), "error")
        return render_template(
            "admin/products.html",
            products=[],
            action_form=ProductActionForm(),
        ), 503

    return render_template(
        "admin/products.html",
        products=products_list,
        action_form=ProductActionForm(),
    )


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_required
def create_product():
    """Create a product through the admin interface."""
    form = ProductForm()

    if form.validate_on_submit():
        try:
            create_admin_product(
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
                stock=form.stock.data,
            )

            flash("Product created successfully.", "success")
            return redirect(url_for("admin.products"))

        except AdminProductError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while creating a product."
            )
            flash(
                "The product could not be created. Please try again.",
                "error",
            )

    return render_template(
        "admin/product_form.html",
        form=form,
    )


@admin_bp.route(
    "/products/<int:product_id>/restock",
    methods=["GET", "POST"],
)
@admin_required
def restock_product(product_id):
    """Increase the stock of an existing product."""
    try:
        product = get_admin_product_details(product_id)

    except AdminProductNotFoundError:
        abort(404)

    except AdminProductError as error:
        flash(str(error), "error")
        return redirect(url_for("admin.products"))

    form = RestockForm()

    if form.validate_on_submit():
        try:
            restock_admin_product(
                product_id,
                form.quantity.data,
            )

            flash("Product stock updated successfully.", "success")
            return redirect(url_for("admin.products"))

        except AdminProductError as error:
            flash(str(error), "error")

        except Exception:
            current_app.logger.exception(
                "Unexpected error while updating stock."
            )
            flash(
                "Stock could not be updated. Please try again.",
                "error",
            )

    return render_template(
        "admin/restock_form.html",
        product=product,
        form=form,
    )


@admin_bp.route(
    "/products/<int:product_id>/deactivate",
    methods=["POST"],
)
@admin_required
def deactivate_product(product_id):
    """Remove a product from sale without deleting its history."""
    form = ProductActionForm()

    if not form.validate_on_submit():
        abort(400)

    try:
        deactivate_admin_product(product_id)
        flash("Product removed from sale.", "success")

    except AdminProductNotFoundError:
        abort(404)

    except AdminProductError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Unexpected error while deactivating a product."
        )
        flash(
            "The product could not be removed from sale.",
            "error",
        )

    return redirect(url_for("admin.products"))
