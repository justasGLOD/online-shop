
from datetime import datetime, timezone

from ..extensions import db


class Payment(db.Model):
    """Record a payment-provider transaction for a balance top-up."""

    __tablename__ = "payments"

    # Payment and customer details
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(
        db.String(3),
        nullable=False,
        default="eur",
    )
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
    )

    # Stripe identifiers
    stripe_checkout_session_id = db.Column(
        db.String(255),
        unique=True,
        nullable=True,
    )
    stripe_payment_intent_id = db.Column(
        db.String(255),
        unique=True,
        nullable=True,
    )

    # Payment timestamps
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User")

    __table_args__ = (
        db.CheckConstraint(
            "amount > 0",
            name="check_payment_amount_positive",
        ),
        db.CheckConstraint(
            "status IN ('pending', 'paid', 'failed', 'cancelled')",
            name="check_payment_status",
        ),
    )

    def __repr__(self):
        return f"<Payment {self.id}: {self.status}>"
