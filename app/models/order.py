
from datetime import datetime, timezone

from ..extensions import db


class Order(db.Model):
    """Store a customer's completed or recorded order."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="completed")
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="orders")
    items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(db.Model):
    """Store the sale price and historical cost of a purchased product."""

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=True,
    )
    quantity = db.Column(db.Integer, nullable=False)

    # Final per-unit selling price, including discounts.
    price_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)

    # Per-unit cost when the order was placed; NULL means unknown.
    cost_at_purchase = db.Column(db.Numeric(10, 2), nullable=True)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")

    __table_args__ = (
        db.CheckConstraint(
            "cost_at_purchase IS NULL OR cost_at_purchase >= 0",
            name="check_order_item_cost_at_purchase_non_negative",
        ),
    )
