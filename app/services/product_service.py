
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.crud.product_crud import (
    get_active_product_by_id,
    get_active_products,
)
from app.extensions import db


ALLOWED_SORT_OPTIONS = {
    "price_asc",
    "price_desc",
    "rating_asc",
    "rating_desc",
    "newest",
    "name_asc",
    "name_desc",
}


class ProductCatalogueError(Exception):
    """Raised when the product catalogue cannot be loaded."""


class ProductNotFoundError(ProductCatalogueError):
    """Raised when an active product cannot be found."""


def list_products(sort_by="newest"):
    """Return active products in a validated sort order."""
    if sort_by not in ALLOWED_SORT_OPTIONS:
        sort_by = "newest"

    try:
        return get_active_products(sort_by)

    except SQLAlchemyError as error:
        db.session.rollback()

        current_app.logger.exception(
            "Database error while loading the product catalogue."
        )

        raise ProductCatalogueError(
            "We couldn't load the products. Please try again."
        ) from error


def get_product_details(product_id):
    """Return an active product with its average rating and review count."""
    try:
        product_id = int(product_id)

        if product_id < 1:
            raise ValueError("Product ID must be positive.")

    except (TypeError, ValueError) as error:
        raise ProductNotFoundError(
            "The requested product could not be found."
        ) from error

    try:
        result = get_active_product_by_id(product_id)

        if result is None:
            raise ProductNotFoundError(
                "The requested product could not be found."
            )

        return result

    except ProductNotFoundError:
        raise

    except SQLAlchemyError as error:
        db.session.rollback()

        current_app.logger.exception(
            "Database error while loading product details."
        )

        raise ProductCatalogueError(
            "We couldn't load this product. Please try again."
        ) from error
