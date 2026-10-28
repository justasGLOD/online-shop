
from decimal import Decimal, InvalidOperation

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import BalanceTransaction, Cart, Order, OrderItem, Product, User
from ..services.loyalty_service import (
    LoyaltyDiscountError,
    apply_loyalty_discount,
    get_completed_order_count,
    get_completed_order_spending,
    get_loyalty_discount_percent,
)


class CheckoutError(Exception):
    """Base exception for checkout failures."""


class EmptyCartError(CheckoutError):
    """Raised when the cart is empty."""


class CheckoutUserNotFoundError(CheckoutError):
    """Raised when the customer does not exist."""


class CheckoutProductUnavailableError(CheckoutError):
    """Raised when a product is missing or inactive."""


class InsufficientStockError(CheckoutError):
    """Raised when requested stock is unavailable."""


class InsufficientBalanceError(CheckoutError):
    """Raised when the customer cannot afford the order."""


def checkout_cart(user_id):
    """Complete a purchase and record historical product costs."""
    try:
        user = db.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user is None:
            raise CheckoutUserNotFoundError(
                "Your account could not be found."
            )

        cart = db.session.scalar(
            select(Cart)
            .options(selectinload(Cart.items))
            .where(Cart.user_id == user.id)
        )
        if cart is None or not cart.items:
            raise EmptyCartError("Your shopping cart is empty.")

        purchase_lines = []

        # Validate every item before changing stock or balance.
        for item in cart.items:
            product = db.session.scalar(
                select(Product)
                .where(Product.id == item.product_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )

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
                original_price = Decimal(str(product.price))
                discount = Decimal(
                    str(product.discount_percent or Decimal("0.00"))
                )
                price = Decimal(str(product.discounted_price))

                # Capture cost now; unknown historical costs remain None.
                cost_price = (
                    None
                    if product.cost_price is None
                    else Decimal(str(product.cost_price))
                )
            except (InvalidOperation, TypeError, ValueError) as error:
                raise CheckoutError(
                    "A product has an invalid price, discount, or cost."
                ) from error

            if not original_price.is_finite() or original_price <= 0:
                raise CheckoutError("A product has an invalid price.")

            if (
                not discount.is_finite()
                or discount < Decimal("0.00")
                or discount > Decimal("100.00")
            ):
                raise CheckoutError("A product has an invalid discount.")

            if not price.is_finite() or price < Decimal("0.00"):
                raise CheckoutError(
                    "A product has an invalid discounted price."
                )

            if cost_price is not None and (
                not cost_price.is_finite()
                or cost_price < Decimal("0.00")
            ):
                raise CheckoutError("A product has an invalid cost price.")

            if item.quantity > product.stock:
                raise InsufficientStockError(
                    f"Not enough stock for {product.name}. "
                    f"Available quantity: {product.stock}."
                )

            purchase_lines.append(
                (product, item.quantity, price, cost_price)
            )

        # Determine loyalty eligibility before creating the new order.
        order_count = get_completed_order_count(user.id)
        completed_order_spending = get_completed_order_spending(user.id)

        loyalty_percent = get_loyalty_discount_percent(
            order_count,
            completed_order_spending,
        )

        total = Decimal("0.00")
        final_lines = []

        # Apply loyalty discounts to the discounted selling price.
        for product, quantity, product_price, cost_price in purchase_lines:
            final_price = apply_loyalty_discount(
                product_price,
                loyalty_percent,
            )
            final_lines.append(
                (product, quantity, final_price, cost_price)
            )
            total += final_price * quantity

        balance = Decimal(str(user.balance))
        if balance < total:
            raise InsufficientBalanceError(
                f"Insufficient balance. Your order costs €{total:.2f}, "
                f"but your balance is €{balance:.2f}."
            )

        order = Order(
            user_id=user.id,
            total_price=total,
            status="completed",
        )
        db.session.add(order)
        db.session.flush()

        # Save the selling price and unit cost as they were at purchase.
        for product, quantity, price, cost_price in final_lines:
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    price_at_purchase=price,
                    cost_at_purchase=cost_price,
                )
            )
            product.stock -= quantity

        user.balance = balance - total
        db.session.add(
            BalanceTransaction(
                user_id=user.id,
                amount=-total,
                transaction_type="purchase",
            )
        )

        for item in list(cart.items):
            db.session.delete(item)

        # Save the order, costs, balance, stock, and cart changes together.
        db.session.commit()
        return order

    except CheckoutError:
        db.session.rollback()
        raise

    except LoyaltyDiscountError as error:
        db.session.rollback()
        raise CheckoutError(str(error)) from error

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
            "An unexpected error prevented checkout. Please try again."
        ) from error
