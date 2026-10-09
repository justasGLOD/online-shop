
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.crud.product_crud import (
    create_product,
    deactivate_product,
    get_all_products,
    get_product_for_admin,
    increase_product_stock,
)
from app.extensions import db
from app.models import Product


CENT = Decimal("0.01")
MAX_PRICE = Decimal("99999999.99")


class AdminProductError(Exception):
    """Expected product-management error."""


class AdminProductNotFoundError(AdminProductError):
    """Raised when the requested product does not exist."""

def list_admin_products():
    """Return all products, including inactive products."""
    try:
        return get_all_products()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to load products for administration."
        )
        raise AdminProductError(
            "Products could not be loaded. Please try again."
        ) from error

def create_admin_product(name, description, price, stock):
    """Validate and create a product."""
    normalized_name = (name or "").strip()
    normalized_description = (description or "").strip()

    if len(normalized_name) < 2 or len(normalized_name) > 150:
        raise AdminProductError(
            "Product name must contain 2–150 characters."
        )

    if len(normalized_description) > 5000:
        raise AdminProductError(
            "Description cannot exceed 5000 characters."
        )

    try:
        normalized_price = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise AdminProductError(
            "Enter a valid product price."
        ) from error

    if not normalized_price.is_finite():
        raise AdminProductError(
            "Enter a valid product price."
        )

    if normalized_price < CENT or normalized_price > MAX_PRICE:
        raise AdminProductError(
            "Price must be between €0.01 and €99,999,999.99."
        )

    if normalized_price != normalized_price.quantize(CENT):
        raise AdminProductError(
            "Price can have no more than two decimal places."
        )

    try:
        normalized_stock = int(stock)
    except (TypeError, ValueError) as error:
        raise AdminProductError(
            "Stock must be a whole number."
        ) from error

    if normalized_stock < 0:
        raise AdminProductError(
            "Stock cannot be negative."
        )

    product = Product(
        name=normalized_name,
        description=normalized_description or None,
        price=normalized_price,
        stock=normalized_stock,
        is_active=True,
    )

    try:
        return create_product(product)

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to create a product."
        )
        raise AdminProductError(
            "The product could not be saved. Please try again."
        ) from error

def restock_admin_product(product_id, quantity):
    """Increase the stock of an existing product."""
    try:
        product_id = int(product_id)
        quantity = int(quantity)
    except (TypeError, ValueError) as error:
        raise AdminProductError(
            "Product ID and quantity must be valid whole numbers."
        ) from error

    if product_id < 1:
        raise AdminProductNotFoundError(
            "The requested product was not found."
        )

    if quantity < 1:
        raise AdminProductError(
            "Restock quantity must be at least one."
        )

    try:
        product = get_product_for_admin(product_id)

        if product is None:
            raise AdminProductNotFoundError(
                "The requested product was not found."
            )

        # Keep quantities within the database Integer range.
        if product.stock + quantity > 2147483647:
            raise AdminProductError(
                "The resulting stock quantity is too large."
            )

        return increase_product_stock(product, quantity)

    except (AdminProductError, SQLAlchemyError) as error:
        db.session.rollback()

        if isinstance(error, AdminProductError):
            raise

        current_app.logger.exception(
            "Failed to update product stock."
        )
        raise AdminProductError(
            "Stock could not be updated. Please try again."
        ) from error

def deactivate_admin_product(product_id):
    """Remove a product from sale without deleting its record."""
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as error:
        raise AdminProductNotFoundError(
            "The requested product was not found."
        ) from error

    if product_id < 1:
        raise AdminProductNotFoundError(
            "The requested product was not found."
        )

    try:
        product = get_product_for_admin(product_id)

        if product is None:
            raise AdminProductNotFoundError(
                "The requested product was not found."
            )

        if not product.is_active:
            raise AdminProductError(
                "This product has already been removed from sale."
            )

        return deactivate_product(product)

    except (AdminProductError, SQLAlchemyError) as error:
        db.session.rollback()

        if isinstance(error, AdminProductError):
            raise

        current_app.logger.exception(
            "Failed to deactivate product."
        )
        raise AdminProductError(
            "The product could not be removed from sale. "
            "Please try again."
        ) from error

def get_admin_product_details(product_id):
    """Find a product for administration, including inactive products."""
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as error:
        raise AdminProductNotFoundError(
            "The requested product was not found."
        ) from error

    if product_id < 1:
        raise AdminProductNotFoundError(
            "The requested product was not found."
        )

    try:
        product = get_product_for_admin(product_id)

        if product is None:
            raise AdminProductNotFoundError(
                "The requested product was not found."
            )

        return product

    except AdminProductNotFoundError:
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to retrieve product for administration."
        )
        raise AdminProductError(
            "Product details could not be loaded."
        ) from error
