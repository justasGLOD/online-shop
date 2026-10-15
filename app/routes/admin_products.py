
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash,
    redirect, render_template, url_for,
)
from flask_login import current_user, login_required

from app.forms import (
    ProductActionForm, ProductEditForm, ProductForm,
    RestockForm, UserActionForm,
)
from app.services.admin_product_service import (
    AdminProductError, AdminProductNotFoundError,
    create_admin_product, deactivate_admin_product,
    get_admin_product_details, list_admin_products,
    restock_admin_product, update_admin_product,
)
from app.services.admin_user_service import (
    AdminUserError, AdminUserNotFoundError,
    deactivate_admin_user, list_admin_users,
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
        current_app.logger.warning("Unable to display products: %s", error)
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


@admin_bp.route("/products/<int:product_id>")
@admin_required
def product_detail(product_id):
    """Display one product's details to an administrator."""
    try:
        product = get_admin_product_details(product_id)
    except AdminProductNotFoundError:
        abort(404)
    except AdminProductError as error:
        current_app.logger.warning(
            "Unable to load product %s: %s", product_id, error
        )
        flash(str(error), "error")
        return redirect(url_for("admin.products"))
    except Exception:
        current_app.logger.exception(
            "Unexpected error loading product %s.", product_id
        )
        flash("Product details could not be loaded.", "error")
        return redirect(url_for("admin.products"))

    return render_template("admin/product_detail.html", product=product)


@admin_bp.route("/users")
@admin_required
def users():
    """Display registered users to administrators."""
    try:
        users_list = list_admin_users()
    except AdminUserError as error:
        current_app.logger.warning("Unable to display users: %s", error)
        flash(str(error), "error")
        return render_template(
            "admin/users.html",
            users=[],
            action_form=UserActionForm(),
        ), 503

    return render_template(
        "admin/users.html",
        users=users_list,
        action_form=UserActionForm(),
    )


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_customer(user_id):
    """Deactivate a customer without deleting their records."""
    form = UserActionForm()
    if not form.validate_on_submit():
        abort(400)

    try:
        user = deactivate_admin_user(user_id, current_user.id)
        flash(
            f"Account for {user.username} deactivated successfully.",
            "success",
        )
    except AdminUserNotFoundError:
        abort(404)
    except AdminUserError as error:
        flash(str(error), "error")
    except Exception:
        current_app.logger.exception(
            "Unexpected error deactivating user %s.", user_id
        )
        flash("The account could not be deactivated. Please try again.", "error")

    return redirect(url_for("admin.users"))


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
            current_app.logger.exception("Unexpected product creation error.")
            flash("The product could not be created. Please try again.", "error")

    return render_template("admin/product_form.html", form=form)


@admin_bp.route(
    "/products/<int:product_id>/edit", methods=["GET", "POST"]
)
@admin_required
def edit_product(product_id):
    """Edit product details without changing stock or active status."""
    try:
        product = get_admin_product_details(product_id)
    except AdminProductNotFoundError:
        abort(404)
    except AdminProductError as error:
        flash(str(error), "error")
        return redirect(url_for("admin.products"))

    form = ProductEditForm(obj=product)
    if form.validate_on_submit():
        try:
            update_admin_product(
                product_id=product.id,
                name=form.name.data,
                description=form.description.data,
                price=form.price.data,
            )
            flash("Product updated successfully.", "success")
            return redirect(url_for("admin.products"))
        except AdminProductNotFoundError:
            abort(404)
        except AdminProductError as error:
            flash(str(error), "error")
        except Exception:
            current_app.logger.exception(
                "Unexpected error editing product %s.", product_id
            )
            flash("The product could not be updated. Please try again.", "error")

    return render_template(
        "admin/product_edit_form.html", product=product, form=form
    )


@admin_bp.route(
    "/products/<int:product_id>/restock", methods=["GET", "POST"]
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
            restock_admin_product(product_id, form.quantity.data)
            flash("Product stock updated successfully.", "success")
            return redirect(url_for("admin.products"))
        except AdminProductError as error:
            flash(str(error), "error")
        except Exception:
            current_app.logger.exception("Unexpected stock update error.")
            flash("Stock could not be updated. Please try again.", "error")

    return render_template(
        "admin/restock_form.html", product=product, form=form
    )


@admin_bp.route(
    "/products/<int:product_id>/deactivate", methods=["POST"]
)
@admin_required
def deactivate_product(product_id):
    """Remove a product from sale without deleting its history."""
    if not ProductActionForm().validate_on_submit():
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
            "Unexpected error deactivating product %s.", product_id
        )
        flash("The product could not be removed from sale.", "error")

    return redirect(url_for("admin.products"))
