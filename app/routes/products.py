
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.forms import CartQuantityForm, ReviewForm
from app.services.product_service import (
    ALLOWED_SORT_OPTIONS,
    ProductCatalogueError,
    ProductNotFoundError,
    get_product_details,
    list_products,
)
from app.services.review_service import (
    get_product_reviews,
    get_user_review,
    has_purchased_product,
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
    """Display product details, ratings, reviews and available actions."""
    try:
        product, average_rating, review_count = get_product_details(
            product_id
        )

        reviews = get_product_reviews(product.id)

        can_review = False
        existing_review = None

        if current_user.is_authenticated:
            can_review = has_purchased_product(
                current_user.id,
                product.id,
            )

            existing_review = get_user_review(
                current_user.id,
                product.id,
            )

    except ProductNotFoundError:
        abort(404)

    except ProductCatalogueError:
        flash(
            "We couldn't load this product. Please try again.",
            "error",
        )
        return redirect(url_for("products.catalogue"))

    except Exception:
        current_app.logger.exception(
            "Unexpected error loading product %s.",
            product_id,
        )
        flash(
            "Product details could not be loaded. Please try again.",
            "error",
        )
        return redirect(url_for("products.catalogue"))

    return render_template(
        "products/detail.html",
        product=product,
        average_rating=average_rating,
        review_count=review_count,
        reviews=reviews,
        can_review=can_review,
        existing_review=existing_review,
        cart_form=CartQuantityForm(),
        review_form=ReviewForm(),
    )
