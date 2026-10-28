from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db
from app.models import Order, User
from app.services.loyalty_service import (
    LoyaltyDiscountError,
    apply_loyalty_discount,
    get_completed_order_count,
    get_completed_order_spending,
    get_loyalty_discount_percent,
)


class TestConfig:
    TESTING = True
    SECRET_KEY = "loyalty-test-secret"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture
def app():
    application = create_app(TestConfig)

    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def customer(app):
    """Create an isolated customer for loyalty tests."""
    with app.app_context():
        user = User(
            username="loyaltycustomer",
            email="loyaltycustomer@example.com",
            password_hash="test-only-password-hash",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        return user.id


@pytest.mark.parametrize(
    ("orders", "spending", "expected"),
    [
        (0, Decimal("0.00"), Decimal("0.00")),
        (3, Decimal("0.00"), Decimal("0.00")),
        (4, Decimal("0.00"), Decimal("5.00")),
        (5, Decimal("0.00"), Decimal("5.00")),
        (9, Decimal("0.00"), Decimal("5.00")),
        (10, Decimal("0.00"), Decimal("10.00")),
        (3, Decimal("500.00"), Decimal("0.00")),
        (3, Decimal("500.01"), Decimal("5.00")),
        (4, Decimal("500.01"), Decimal("5.00")),
        (10, Decimal("600.00"), Decimal("10.00")),
    ],
)
def test_loyalty_discount_eligibility(orders, spending, expected):
    """Apply the purchase-count and spending eligibility rules."""
    assert get_loyalty_discount_percent(orders, spending) == expected


@pytest.mark.parametrize("orders", [-1, 1.5, True, None])
def test_invalid_completed_order_count_is_rejected(orders):
    with pytest.raises(LoyaltyDiscountError):
        get_loyalty_discount_percent(orders)


@pytest.mark.parametrize(
    "spending",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
        "not-a-number",
        None,
    ],
)
def test_invalid_completed_order_spending_is_rejected(spending):
    with pytest.raises(LoyaltyDiscountError):
        get_loyalty_discount_percent(0, spending)


@pytest.mark.parametrize(
    ("amount", "percent", "expected"),
    [
        ("80.00", "5.00", "76.00"),
        ("80.00", "10.00", "72.00"),
        ("19.99", "0.00", "19.99"),
        ("50.00", "100.00", "0.00"),
        ("10.00", "5.00", "9.50"),
    ],
)
def test_loyalty_discount_calculations(amount, percent, expected):
    result = apply_loyalty_discount(
        Decimal(amount),
        Decimal(percent),
    )

    assert result == Decimal(expected)


@pytest.mark.parametrize(
    ("amount", "percent"),
    [
        ("-1.00", "5.00"),
        ("invalid", "5.00"),
        ("10.00", "-1.00"),
        ("10.00", "100.01"),
    ],
)
def test_invalid_loyalty_discount_inputs_are_rejected(amount, percent):
    with pytest.raises(LoyaltyDiscountError):
        apply_loyalty_discount(amount, percent)


@pytest.mark.parametrize(
    "user_id",
    [-1, 0, 1.5, True, None, "1"],
)
def test_invalid_customer_id_is_rejected(user_id):
    with pytest.raises(LoyaltyDiscountError):
        get_completed_order_count(user_id)

    with pytest.raises(LoyaltyDiscountError):
        get_completed_order_spending(user_id)


def test_completed_order_count_only_includes_last_90_days(
    app,
    customer,
):
    """Count completed orders in the rolling 90-day purchase window."""
    with app.app_context():
        now = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)

        orders = [
            # Included: exactly on the cutoff.
            Order(
                user_id=customer,
                total_price=Decimal("20.00"),
                status="completed",
                created_at=now - timedelta(days=90),
            ),
            # Included: inside the window.
            Order(
                user_id=customer,
                total_price=Decimal("30.00"),
                status="completed",
                created_at=now - timedelta(days=30),
            ),
            # Excluded: too old.
            Order(
                user_id=customer,
                total_price=Decimal("40.00"),
                status="completed",
                created_at=now - timedelta(days=91),
            ),
            # Excluded: future-dated.
            Order(
                user_id=customer,
                total_price=Decimal("50.00"),
                status="completed",
                created_at=now + timedelta(minutes=1),
            ),
            # Non-completed orders never count.
            Order(
                user_id=customer,
                total_price=Decimal("60.00"),
                status="pending",
                created_at=now,
            ),
            Order(
                user_id=customer,
                total_price=Decimal("70.00"),
                status="failed",
                created_at=now,
            ),
            Order(
                user_id=customer,
                total_price=Decimal("80.00"),
                status="cancelled",
                created_at=now,
            ),
        ]

        db.session.add_all(orders)
        db.session.commit()

        assert get_completed_order_count(customer, now=now) == 2


def test_completed_order_spending_includes_only_completed_orders(
    app,
    customer,
):
    """Sum historical completed orders, excluding other statuses."""
    with app.app_context():
        now = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)

        db.session.add_all([
            # Historical spending still qualifies after 90 days.
            Order(
                user_id=customer,
                total_price=Decimal("300.00"),
                status="completed",
                created_at=now - timedelta(days=180),
            ),
            Order(
                user_id=customer,
                total_price=Decimal("210.00"),
                status="completed",
                created_at=now - timedelta(days=10),
            ),
            Order(
                user_id=customer,
                total_price=Decimal("100.00"),
                status="pending",
                created_at=now,
            ),
            Order(
                user_id=customer,
                total_price=Decimal("200.00"),
                status="failed",
                created_at=now,
            ),
            Order(
                user_id=customer,
                total_price=Decimal("400.00"),
                status="cancelled",
                created_at=now,
            ),
        ])

        db.session.commit()

        spending = get_completed_order_spending(customer)

        assert spending == Decimal("510.00")
        assert (
            get_loyalty_discount_percent(
                completed_order_count=0,
                completed_order_spending=spending,
            )
            == Decimal("5.00")
        )


def test_no_completed_orders_means_zero_spending(app, customer):
    with app.app_context():
        assert get_completed_order_count(
            customer,
        ) == 0

        assert get_completed_order_spending(
            customer,
        ) == Decimal("0.00")


def test_customer_needs_neither_four_recent_orders_nor_over_500_spending():
    """Neither threshold means no loyalty discount."""
    assert get_loyalty_discount_percent(
        completed_order_count=3,
        completed_order_spending=Decimal("500.00"),
    ) == Decimal("0.00")