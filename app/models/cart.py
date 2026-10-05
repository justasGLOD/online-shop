from datetime import datetime, timezone

from app.extensions import db


class Cart(db.Model):
    __tablename__ = "carts"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        back_populates="cart",
    )

    items = db.relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    cart_id = db.Column(
        db.Integer,
        db.ForeignKey("carts.id"),
        nullable=False,
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=1,
    )

    cart = db.relationship(
        "Cart",
        back_populates="items",
    )

    product = db.relationship(
        "Product",
        back_populates="cart_items",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "cart_id",
            "product_id",
            name="unique_cart_product",
        ),
    )