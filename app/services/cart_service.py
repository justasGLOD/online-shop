
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.crud.cart_crud import (
    create_cart_item,
    delete_cart_item,
    get_active_product,
    get_cart_for_user,
    get_cart_item,
    get_or_create_cart,
    update_cart_item_quantity,
)
from app.extensions import db


class CartError(Exception):
    """Base error for shopping-cart operations."""


class CartProductNotFoundError(CartError):
    """Raised when a product is missing or unavailable."""


class CartItemNotFoundError(CartError):
    """Raised when a cart item cannot be found for the user."""


class CartStockError(CartError):
    """Raised when requested quantity exceeds available stock."""


def _positive_integer(value, field_name):
    """Validate a positive whole-number ID or quantity."""
    try:
        normalized = int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise CartError(
            f"{field_name} must be a whole number."
        ) from error

    if normalized < 1:
        raise CartError(
            f"{field_name} must be greater than zero."
        )

    return normalized


def get_user_cart(user_id):
    """Return the user's persistent cart, creating it if necessary."""
    try:
        user_id = _positive_integer(user_id, "User ID")

        get_or_create_cart(user_id)
        db.session.commit()

        return get_cart_for_user(user_id)

    except CartError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to load or create a shopping cart."
        )
        raise CartError(
            "Your shopping cart could not be loaded. Please try again."
        ) from error


def add_product_to_cart(user_id, product_id, quantity=1):
    """Add a product or increase its existing cart-line quantity."""
    user_id = _positive_integer(user_id, "User ID")
    product_id = _positive_integer(product_id, "Product ID")
    quantity = _positive_integer(quantity, "Quantity")

    try:
        cart = get_or_create_cart(user_id)

        product = get_active_product(product_id)

        if product is None:
            raise CartProductNotFoundError(
                "This product does not exist or is no longer available."
            )

        existing_item = get_cart_item(cart.id, product.id)

        new_quantity = quantity
        if existing_item is not None:
            new_quantity += existing_item.quantity

        if new_quantity > product.stock:
            raise CartStockError(
                f"Only {product.stock} item(s) are currently in stock."
            )

        if existing_item is not None:
            item = update_cart_item_quantity(
                existing_item,
                new_quantity,
            )
        else:
            item = create_cart_item(
                cart.id,
                product.id,
                quantity,
            )

        db.session.commit()
        return item

    except CartError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to add a product to the shopping cart."
        )
        raise CartError(
            "The product could not be added to your cart. Please try again."
        ) from error


def update_cart_quantity(user_id, item_id, quantity):
    """Set a cart item's quantity without exceeding available stock."""
    user_id = _positive_integer(user_id, "User ID")
    item_id = _positive_integer(item_id, "Cart item ID")
    quantity = _positive_integer(quantity, "Quantity")

    try:
        cart = get_cart_for_user(user_id)

        if cart is None:
            raise CartItemNotFoundError(
                "This cart item could not be found."
            )

        # Search only the current user's cart to prevent cross-user changes.
        item = next(
            (entry for entry in cart.items if entry.id == item_id),
            None,
        )

        if item is None:
            raise CartItemNotFoundError(
                "This cart item could not be found."
            )

        product = get_active_product(item.product_id)

        if product is None:
            raise CartProductNotFoundError(
                "This product is no longer available."
            )

        if quantity > product.stock:
            raise CartStockError(
                f"Only {product.stock} item(s) are currently in stock."
            )

        update_cart_item_quantity(item, quantity)
        db.session.commit()

        return item

    except CartError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to update a shopping-cart item."
        )
        raise CartError(
            "The cart quantity could not be updated. Please try again."
        ) from error


def remove_cart_item(user_id, item_id):
    """Remove an item from the current user's cart."""
    user_id = _positive_integer(user_id, "User ID")
    item_id = _positive_integer(item_id, "Cart item ID")

    try:
        cart = get_cart_for_user(user_id)

        if cart is None:
            raise CartItemNotFoundError(
                "This cart item could not be found."
            )

        item = next(
            (entry for entry in cart.items if entry.id == item_id),
            None,
        )

        if item is None:
            raise CartItemNotFoundError(
                "This cart item could not be found."
            )

        delete_cart_item(item)
        db.session.commit()

    except CartError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to remove an item from the shopping cart."
        )
        raise CartError(
            "The cart item could not be removed. Please try again."
        ) from error


def calculate_cart_total(cart):
    """Calculate the cart total using decimal arithmetic."""
    from decimal import Decimal

    total = Decimal("0.00")

    for item in cart.items:
        if item.product is not None:
            total += Decimal(str(item.product.price)) * item.quantity

    return total
