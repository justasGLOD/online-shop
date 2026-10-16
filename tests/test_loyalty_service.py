
from decimal import Decimal

import pytest

from app.services.loyalty_service import (
    LoyaltyDiscountError,
    apply_loyalty_discount,
    get_loyalty_discount_percent,
)


@pytest.mark.parametrize(
    ("orders", "expected"),
    [
        (0, Decimal("0.00")),
        (4, Decimal("0.00")),
        (5, Decimal("5.00")),
        (9, Decimal("5.00")),
        (10, Decimal("10.00")),
        (100, Decimal("10.00")),
    ],
)
def test_loyalty_discount_tiers(orders, expected):
    assert get_loyalty_discount_percent(orders) == expected


@pytest.mark.parametrize("orders", [-1, 1.5, True, None])
def test_invalid_completed_order_count_is_rejected(orders):
    with pytest.raises(LoyaltyDiscountError):
        get_loyalty_discount_percent(orders)


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
