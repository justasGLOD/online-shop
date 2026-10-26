
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from ..extensions import db


class Product(db.Model):
    """Store product details, pricing, stock, costs, and reviews."""

    __tablename__ = "products"

    # Basic product information
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    # Nullable because existing products may not have a recorded cost yet.
    cost_price = db.Column(db.Numeric(10, 2), nullable=True)

    # Discounts and inventory
    discount_percent = db.Column(
        db.Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )
    stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Product creation timestamp
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="check_product_discount_percent_range",
        ),
        db.CheckConstraint(
            "cost_price IS NULL OR cost_price >= 0",
            name="check_product_cost_price_non_negative",
        ),
    )

    @property
    def discounted_price(self):
        """Calculate the final selling price after the discount."""
        price = Decimal(str(self.price))
        discount = Decimal(
            str(self.discount_percent or Decimal("0.00"))
        )
        final_price = price * (Decimal("100") - discount) / Decimal("100")

        return final_price.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @property
    def discount_amount(self):
        """Calculate the amount saved through the discount."""
        return (
            Decimal(str(self.price)) - self.discounted_price
        ).quantize(Decimal("0.01"))

    # Relationships with other database records
    cart_items = db.relationship("CartItem", back_populates="product")
    order_items = db.relationship("OrderItem", back_populates="product")
    reviews = db.relationship(
        "Review",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Product {self.name}>"
