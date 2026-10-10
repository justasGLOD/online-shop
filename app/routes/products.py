
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from app.forms import CartQuantityForm
from app.services.product_service import (
    ALLOWED_SORT_OPTIONS,
    ProductCatalogueError,
    ProductNotFoundError,
    get_product_details,
    list_products,
)


products_bp = Blueprint("products", __name__, url_prefix="/products")


@products_bp.route("/")
def catalogue():
    """Display active products with validated sorting."""
    requested_sort = request.args.get("sort", "newest")
    sort_by = (
        requested_sort
        if requested_sort in ALLOWED_SORT_OPTIONS
        else "newest"
    )

    try:
        products = list_products(sort_by)
    except ProductCatalogueError:
        flash(
            "We couldn't load the products. Please try again.",
            "error",
        )
        return render_template(
            "products/list.html",
            products=[],
            sort_by=sort_by,
        ), 503

    return render_template(
        "products/list.html",
        products=products,
        sort_by=sort_by,
    )


@products_bp.route("/<int:product_id>")
def detail(product_id):
    """Display details for one active product."""
    try:
        product_data = get_product_details(product_id)
        product, average_rating, review_count = product_data

    except ProductNotFoundError:
        abort(404)

    except ProductCatalogueError:
        flash(
            "We couldn't load this product. Please try again.",
            "error",
        )
        return redirect(url_for("products.catalogue"))

    return render_template(
        "products/detail.html",
        product=product,
        average_rating=average_rating,
        review_count=review_count,
        cart_form=CartQuantityForm(),
    )
