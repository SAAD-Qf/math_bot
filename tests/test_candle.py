"""
Unit tests for the Candle domain model and validation.
"""

from decimal import Decimal

import pytest

from tradingbot.domain.candle import Candle
from tradingbot.exceptions import InvalidCandleError


def test_valid_candle_creation():
    candle = Candle(
        timestamp=1609459200000,
        open=Decimal("100.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal("102.0"),
        volume=Decimal("1000.0"),
    )
    assert candle.timestamp == 1609459200000
    assert candle.range == Decimal("10.0")
    assert candle.mid_price == Decimal("100.0")
    assert candle.is_bullish() is True
    assert candle.is_bearish() is False


def test_bearish_candle():
    candle = Candle(
        timestamp=1609459200000,
        open=Decimal("102.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal("98.0"),
        volume=Decimal("1000.0"),
    )
    assert candle.is_bullish() is False
    assert candle.is_bearish() is True


def test_invalid_low_greater_than_open():
    with pytest.raises(InvalidCandleError):
        Candle(
            timestamp=1609459200000,
            open=Decimal("100.0"),
            high=Decimal("105.0"),
            low=Decimal("102.0"),
            close=Decimal("103.0"),
            volume=Decimal("1000.0"),
        )


def test_invalid_high_less_than_close():
    with pytest.raises(InvalidCandleError):
        Candle(
            timestamp=1609459200000,
            open=Decimal("100.0"),
            high=Decimal("101.0"),
            low=Decimal("95.0"),
            close=Decimal("102.0"),
            volume=Decimal("1000.0"),
        )


def test_negative_price_rejected():
    with pytest.raises(InvalidCandleError, match="negative"):
        Candle(timestamp=1, open=-1, high=10, low=-5, close=5, volume=1)


def test_nan_price_rejected():
    with pytest.raises(InvalidCandleError, match="NaN"):
        Candle(timestamp=1, open=Decimal("NaN"), high=10, low=1, close=5, volume=1)


def test_infinite_price_rejected():
    with pytest.raises(InvalidCandleError, match="infinite"):
        Candle(timestamp=1, open=1, high=Decimal("Infinity"), low=1, close=5, volume=1)


def test_negative_volume_rejected():
    with pytest.raises(InvalidCandleError, match="volume"):
        Candle(timestamp=1, open=10, high=11, low=9, close=10, volume=-1)


def test_non_integer_timestamp_rejected():
    with pytest.raises(InvalidCandleError, match="timestamp"):
        Candle(timestamp="1609459200000", open=10, high=11, low=9, close=10, volume=1)


def test_invalid_string_number_rejected():
    with pytest.raises(InvalidCandleError, match="not a valid number"):
        Candle(timestamp=1, open="abc", high=11, low=9, close=10, volume=1)


def test_coercion_from_int_float_str():
    candle = Candle(timestamp=1, open=10, high="11.5", low=9.25, close="10", volume=100)
    assert candle.open == Decimal("10")
    assert candle.high == Decimal("11.5")
    assert candle.low == Decimal("9.25")


def test_candle_from_dict():
    data = {
        "timestamp": 1609459200000,
        "open": "100.0",
        "high": "105.0",
        "low": "95.0",
        "close": "102.0",
        "volume": "1000.0",
    }
    candle = Candle.from_dict(data)
    assert candle.open == Decimal("100.0")
    assert candle.high == Decimal("105.0")
    assert candle.low == Decimal("95.0")
    assert candle.close == Decimal("102.0")


def test_candle_from_dict_missing_key():
    with pytest.raises(InvalidCandleError, match="from dict"):
        Candle.from_dict({"timestamp": 1, "open": "1"})


def test_candle_to_dict():
    candle = Candle(
        timestamp=1609459200000,
        open=Decimal("100.0"),
        high=Decimal("105.0"),
        low=Decimal("95.0"),
        close=Decimal("102.0"),
        volume=Decimal("1000.0"),
    )
    d = candle.to_dict()
    assert d["timestamp"] == 1609459200000
    assert d["open"] == "100.0"
    assert d["volume"] == "1000.0"
