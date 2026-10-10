
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Cart, CartItem, Product


def get_cart_for_user(user_id):
    """Return a user's cart with its items and products."""
    statement = (
        select(Cart)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product)
        )
        .where(Cart.user_id == user_id)
    )

    return db.session.scalar(statement)


def get_or_create_cart(user_id):
    """Get the user's existing cart or create a new one."""
    cart = get_cart_for_user(user_id)

    if cart is None:
        cart = Cart(user_id=user_id)
        db.session.add(cart)
        db.session.flush()

    return cart


def get_active_product(product_id):
    """Return an active product, or None if unavailable."""
    statement = select(Product).where(
        Product.id == product_id,
        Product.is_active.is_(True),
    )

    return db.session.scalar(statement)


def get_cart_item(cart_id, product_id):
    """Find a product's existing line in a cart."""
    statement = select(CartItem).where(
        CartItem.cart_id == cart_id,
        CartItem.product_id == product_id,
    )

    return db.session.scalar(statement)


def create_cart_item(cart_id, product_id, quantity):
    """Add a new product line to a cart."""
    item = CartItem(
        cart_id=cart_id,
        product_id=product_id,
        quantity=quantity,
    )

    db.session.add(item)
    db.session.flush()

    return item


def update_cart_item_quantity(cart_item, quantity):
    """Set the quantity of an existing cart item."""
    cart_item.quantity = quantity
    db.session.flush()

    return cart_item


def delete_cart_item(cart_item):
    """Remove a product line from a cart."""
    db.session.delete(cart_item)
    db.session.flush()
