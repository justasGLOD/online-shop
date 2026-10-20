
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    url_for,
)
from flask_login import current_user, login_required

from ..forms import ReviewForm
from ..services.review_service import (
    ReviewError,
    ReviewProductNotFoundError,
    submit_product_review,
)


reviews_bp = Blueprint("reviews", __name__, url_prefix="/products")


@reviews_bp.route("/<int:product_id>/reviews", methods=["POST"])
@login_required
def submit_review(product_id):
    """Submit a product review for an authenticated customer."""
    form = ReviewForm()
    product_url = url_for("products.detail", product_id=product_id)

    if not form.validate_on_submit():
        flash(
            "Please provide a rating from 1 to 5 and a valid review.",
            "error",
        )
        return redirect(product_url)

    try:
        submit_product_review(
            user_id=current_user.id,
            product_id=product_id,
            rating=form.rating.data,
            comment=form.comment.data,
        )
        flash("Your review was submitted successfully.", "success")

    except ReviewProductNotFoundError:
        abort(404)

    except ReviewError as error:
        flash(str(error), "error")

    except Exception:
        current_app.logger.exception(
            "Unexpected error submitting review for product %s.",
            product_id,
        )
        flash(
            "Your review could not be submitted. Please try again.",
            "error",
        )

    return redirect(product_url)
