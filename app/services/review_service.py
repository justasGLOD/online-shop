
from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Order, OrderItem, Product, Review


class ReviewError(Exception):
    """Base exception for product review operations."""


class ReviewProductNotFoundError(ReviewError):
    """Raised when the product does not exist."""


class ReviewPurchaseRequiredError(ReviewError):
    """Raised when the customer has not purchased the product."""


class ReviewAlreadyExistsError(ReviewError):
    """Raised when the customer has already reviewed the product."""


class InvalidReviewError(ReviewError):
    """Raised when the review rating or comment is invalid."""


def has_purchased_product(user_id, product_id):
    """Check whether the customer has a completed order for the product."""
    statement = (
        select(OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.user_id == user_id,
            OrderItem.product_id == product_id,
            Order.status == "completed",
        )
        .limit(1)
    )
    return db.session.scalar(statement) is not None


def get_product_reviews(product_id):
    """Return a product's reviews, newest first."""
    if db.session.get(Product, product_id) is None:
        raise ReviewProductNotFoundError(
            "This product could not be found."
        )

    statement = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    )
    return db.session.scalars(statement).all()


def submit_product_review(user_id, product_id, rating, comment):
    """Submit a review after verifying purchase eligibility."""
    if (
        not isinstance(rating, int)
        or isinstance(rating, bool)
        or not 1 <= rating <= 5
    ):
        raise InvalidReviewError(
            "Rating must be a whole number between 1 and 5."
        )

    if not isinstance(comment, str):
        raise InvalidReviewError("Please write a review.")

    comment = comment.strip()
    if not 3 <= len(comment) <= 2000:
        raise InvalidReviewError(
            "Your review must contain between 3 and 2000 characters."
        )

    try:
        if db.session.get(Product, product_id) is None:
            raise ReviewProductNotFoundError(
                "This product could not be found."
            )

        if not has_purchased_product(user_id, product_id):
            raise ReviewPurchaseRequiredError(
                "You can review a product only after purchasing it."
            )

        existing_review = db.session.scalar(
            select(Review.id)
            .where(
                Review.user_id == user_id,
                Review.product_id == product_id,
            )
            .limit(1)
        )
        if existing_review is not None:
            raise ReviewAlreadyExistsError(
                "You have already reviewed this product."
            )

        review = Review(
            user_id=user_id,
            product_id=product_id,
            rating=rating,
            comment=comment,
        )
        db.session.add(review)
        db.session.commit()
        return review

    except ReviewError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Database error submitting a review for product %s by user %s.",
            product_id,
            user_id,
        )
        raise ReviewError(
            "Your review could not be saved. Please try again."
        ) from error


def get_user_review(user_id, product_id):
    """Return this user's existing review for a product, if any."""
    statement = (
        select(Review)
        .where(
            Review.user_id == user_id,
            Review.product_id == product_id,
        )
        .limit(1)
    )
    return db.session.scalar(statement)
