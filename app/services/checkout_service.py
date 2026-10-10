
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import (
    BalanceTransaction,
    Cart,
    Order,
    OrderItem,
    Product,
    User,
)


class CheckoutError(Exception):
    """Base exception for checkout failures."""


class EmptyCartError(CheckoutError):
    """Raised when a customer attempts to buy an empty cart."""


class CheckoutUserNotFoundError(CheckoutError):
    """Raised when the customer no longer exists."""


class CheckoutProductUnavailableError(CheckoutError):
    """Raised when a product is missing or inactive."""


class InsufficientStockError(CheckoutError):
    """Raised when the requested quantity exceeds stock."""


class InsufficientBalanceError(CheckoutError):
    """Raised when the customer's balance is insufficient."""


def checkout_cart(user_id):
    """
    Purchase everything in the customer's cart in one transaction.

    The balance, stock, order, transaction history and cart are updated
    together. If checkout fails, the database transaction is rolled back.
    """
    try:
        # Lock the customer row where the database supports row-level locks.
        user_statement = (
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        user = db.session.scalar(user_statement)

        if user is None:
            raise CheckoutUserNotFoundError(
                "Your account could not be found."
            )

        # Load the cart and its items.
        cart_statement = (
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.user_id == user.id)
        )

        cart = db.session.scalar(cart_statement)

        if cart is None or not cart.items:
            raise EmptyCartError(
                "Your shopping cart is empty."
            )

        # Validate every product before changing any balances or stock.
        purchase_lines = []
        total = Decimal("0.00")

        for item in cart.items:
            product_statement = (
                select(Product)
                .where(Product.id == item.product_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )

            product = db.session.scalar(product_statement)

            if product is None or not product.is_active:
                raise CheckoutProductUnavailableError(
                    "A product in your cart is no longer available. "
                    "Please review your cart."
                )

            if (
                not isinstance(item.quantity, int)
                or isinstance(item.quantity, bool)
                or item.quantity < 1
            ):
                raise CheckoutError(
                    "Your cart contains an invalid quantity."
                )

            try:
                price = Decimal(str(product.price))
            except (InvalidOperation, TypeError, ValueError) as error:
                raise CheckoutError(
                    "A product has an invalid price."
                ) from error

            if not price.is_finite() or price <= 0:
                raise CheckoutError(
                    "A product has an invalid price."
                )

            if item.quantity > product.stock:
                raise InsufficientStockError(
                    f"Not enough stock for {product.name}. "
                    f"Available quantity: {product.stock}."
                )

            line_total = price * item.quantity
            total += line_total

            purchase_lines.append(
                (item, product, item.quantity, price)
            )

        # Recheck the account balance using decimal arithmetic.
        balance = Decimal(str(user.balance))

        if balance < total:
            raise InsufficientBalanceError(
                f"Insufficient balance. Your order costs "
                f"€{total:.2f}, but your balance is €{balance:.2f}."
            )

        # Create the order after all business validations have passed.
        order = Order(
            user_id=user.id,
            total_price=total,
            status="completed",
        )

        db.session.add(order)
        db.session.flush()

        # Save purchase-time prices and reduce inventory.
        for item, product, quantity, price in purchase_lines:
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                price_at_purchase=price,
            )

            db.session.add(order_item)
            product.stock -= quantity

        # Deduct the purchase total from the customer's balance.
        user.balance = balance - total

        # Purchases are recorded as negative balance transactions.
        balance_transaction = BalanceTransaction(
            user_id=user.id,
            amount=-total,
            transaction_type="purchase",
        )

        db.session.add(balance_transaction)

        # Clear the cart only as part of this same transaction.
        for item in list(cart.items):
            db.session.delete(item)

        # This is the sole commit for the entire checkout operation.
        db.session.commit()

        return order

    except CheckoutError:
        db.session.rollback()
        raise

    except SQLAlchemyError as error:
        db.session.rollback()

        current_app.logger.exception(
            "Database error during checkout for user %s.",
            user_id,
        )

        raise CheckoutError(
            "Your purchase could not be completed. "
            "No changes were saved. Please try again."
        ) from error

    except Exception as error:
        db.session.rollback()

        current_app.logger.exception(
            "Unexpected error during checkout for user %s.",
            user_id,
        )

        raise CheckoutError(
            "An unexpected error prevented checkout. "
            "Please try again."
        ) from error
