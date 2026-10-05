from datetime import datetime, timezone

from app.extensions import db


class BalanceTransaction(db.Model):
    __tablename__ = "balance_transactions"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    amount = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )

    transaction_type = db.Column(
        db.String(30),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        back_populates="balance_transactions",
    )