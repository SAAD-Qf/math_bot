"""
Unit tests for the PricePoint domain model.
"""

from decimal import Decimal

import pytest

from tradingbot.domain.price_point import PricePoint
from tradingbot.exceptions import InvalidPriceError


def test_valid_price_point():
    """Test creating a valid PricePoint."""
    p = PricePoint(value=Decimal("150.50"), timestamp=1609459200000, source="test")
    assert p.value == Decimal("150.50")
    assert p.timestamp == 1609459200000
    assert p.source == "test"
    assert str(p) == "150.50"


def test_negative_price_point_raises_error():
    """Test that a negative price point raises InvalidPriceError."""
    with pytest.raises(InvalidPriceError):
        PricePoint(value=Decimal("-10.0"))


def test_from_float():
    """Test factory from float."""
    p = PricePoint.from_float(123.45)
    assert p.value == Decimal("123.45")


def test_from_str():
    """Test factory from str."""
    p = PricePoint.from_str("123.45")
    assert p.value == Decimal("123.45")
