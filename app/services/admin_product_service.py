
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..crud.product_crud import (
    create_product,
    deactivate_product,
    get_all_products,
    get_product_for_admin,
    increase_product_stock,
    update_product_details,
)
from ..extensions import db
from ..models import Product


CENT = Decimal("0.01")
MAX_PRICE = Decimal("99999999.99")
MAX_DISCOUNT = Decimal("100.00")
MAX_STOCK = 2_147_483_647


class AdminProductError(Exception):
    """Raised when product management fails."""


class AdminProductNotFoundError(AdminProductError):
    """Raised when the requested product does not exist."""


def _normalize_product_details(name, description, price):
    """Validate and normalize a product's name, description, and price."""
    name = (name or "").strip()
    description = (description or "").strip()

    if not 2 <= len(name) <= 150:
        raise AdminProductError(
            "Product name must contain 2–150 characters."
        )

    if len(description) > 5000:
        raise AdminProductError(
            "Description cannot exceed 5000 characters."
        )

    try:
        price = Decimal(str(price))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise AdminProductError("Enter a valid product price.") from error

    if not price.is_finite():
        raise AdminProductError("Enter a valid product price.")

    if price < CENT or price > MAX_PRICE:
        raise AdminProductError(
            "Price must be between €0.01 and €99,999,999.99."
        )

    if price != price.quantize(CENT):
        raise AdminProductError(
            "Price can have no more than two decimal places."
        )

    return name, description or None, price


def _normalize_discount_percent(value):
    """Validate and normalize a product discount percentage."""
    try:
        discount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise AdminProductError(
            "Enter a valid discount percentage."
        ) from error

    if not discount.is_finite():
        raise AdminProductError("Enter a valid discount percentage.")

    if discount < Decimal("0.00") or discount > MAX_DISCOUNT:
        raise AdminProductError("Discount must be between 0% and 100%.")

    if discount != discount.quantize(CENT):
        raise AdminProductError(
            "Discount can have no more than two decimal places."
        )

    return discount


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


def create_admin_product(
    name,
    description,
    price,
    stock,
    discount_percent=Decimal("0.00"),
):
    """Validate and create a product, including its discount."""
    name, description, price = _normalize_product_details(
        name,
        description,
        price,
    )
    discount = _normalize_discount_percent(discount_percent)

    try:
        stock = int(stock)
    except (TypeError, ValueError) as error:
        raise AdminProductError(
            "Stock must be a whole number."
        ) from error

    if stock < 0:
        raise AdminProductError("Stock cannot be negative.")

    if stock > MAX_STOCK:
        raise AdminProductError("The stock quantity is too large.")

    product = Product(
        name=name,
        description=description,
        price=price,
        discount_percent=discount,
        stock=stock,
        is_active=True,
    )

    try:
        return create_product(product)
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Failed to create a product.")
        raise AdminProductError(
            "The product could not be saved. Please try again."
        ) from error


def update_admin_product(
    product_id,
    name,
    description,
    price,
    discount_percent=None,
):
    """Validate and update product details without changing stock."""
    product = get_admin_product_details(product_id)
    name, description, price = _normalize_product_details(
        name,
        description,
        price,
    )

    discount = (
        Decimal(str(product.discount_percent or Decimal("0.00")))
        if discount_percent is None
        else _normalize_discount_percent(discount_percent)
    )

    try:
        product.discount_percent = discount
        return update_product_details(
            product=product,
            name=name,
            description=description,
            price=price,
        )
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to update product %s.",
            product_id,
        )
        raise AdminProductError(
            "The product could not be updated. Please try again."
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

        if product.stock + quantity > MAX_STOCK:
            raise AdminProductError(
                "The resulting stock quantity is too large."
            )

        return increase_product_stock(product, quantity)

    except AdminProductError:
        db.session.rollback()
        raise
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Failed to update product stock.")
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

    except AdminProductError:
        db.session.rollback()
        raise
    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception("Failed to deactivate product.")
        raise AdminProductError(
            "The product could not be removed from sale. Please try again."
        ) from error
