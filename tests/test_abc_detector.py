"""
Unit tests for the A/B/C detector (reference implementation) and ABCSetup.
"""

from decimal import Decimal

import pytest

from conftest import zigzag_candles
from tradingbot.detection.abc_detector import (
    ABCDetectorConfig,
    ReferenceABCDetector,
)
from tradingbot.detection.swing_detector import SwingDetectorConfig
from tradingbot.domain import ABCSetup, PricePoint
from tradingbot.domain.enums import SetupDirection
from tradingbot.exceptions import InvalidPriceError, InvalidStrategyInputError


def _detect(candles, **kwargs):
    defaults = dict(swing_config=SwingDetectorConfig(left_window=3, right_window=3))
    defaults.update(kwargs)
    detector = ReferenceABCDetector(ABCDetectorConfig(**defaults))
    from tradingbot import MathematicalStrategy

    strategy = MathematicalStrategy(detector=detector)
    setups = []
    for candle in candles:
        setups.extend(strategy.feed(candle))  # strategy attaches the target
    return setups


def test_config_validation():
    with pytest.raises(ValueError):
        ABCDetectorConfig(min_distance=Decimal(-1))
    with pytest.raises(ValueError):
        ABCDetectorConfig(max_setups_per_combination=0)


def test_long_setup_detected_from_zigzag():
    # up 0..5, down 6..11 (A low), up 12..17 (B high), down 18..23 (C low),
    # up 24..27 tail so C can be confirmed (needs 3 candles after index 23).
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0)]
    )
    setups = _detect(candles)
    longs = [s for s in setups if s.direction == SetupDirection.LONG]
    assert len(longs) >= 1
    s = longs[0]
    assert s.a.role == "A" and s.b.role == "B" and s.c.role == "C"
    assert s.a.metadata["swing_role"] == "swing_low"
    assert s.b.metadata["swing_role"] == "swing_high"
    assert s.c.metadata["swing_role"] == "swing_low"
    assert s.a.candle_index < s.b.candle_index < s.c.candle_index
    assert s.a.timestamp <= s.b.timestamp <= s.c.timestamp
    # mathematical target present
    assert s.target is not None
    assert s.target == (s.b.value + s.c.value) / s.a.value


def test_short_setup_detected_from_zigzag():
    # down 0..5, up 6..11 (A high), down 12..17 (B low), up 18..23 (C high),
    # down 24..27 tail so C can be confirmed.
    candles = zigzag_candles(
        [(-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 4, 1.0)]
    )
    setups = _detect(candles)
    shorts = [s for s in setups if s.direction == SetupDirection.SHORT]
    assert len(shorts) >= 1
    s = shorts[0]
    assert s.a.metadata["swing_role"] == "swing_high"
    assert s.b.metadata["swing_role"] == "swing_low"
    assert s.c.metadata["swing_role"] == "swing_high"
    assert s.a.candle_index < s.b.candle_index < s.c.candle_index


def test_setup_availability_no_lookahead():
    """A setup must only appear when C is CONFIRMED, never before."""
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0)]
    )
    detector = ReferenceABCDetector(
        ABCDetectorConfig(swing_config=SwingDetectorConfig(3, 3))
    )
    c_swing = None
    # Find where the C low (last leg) gets confirmed by scanning.
    for i, candle in enumerate(candles):
        new = detector.on_candle(candle)
        for s in new:
            conf = s.metadata["c_confirmed_at_index"]
            assert conf <= i, (
                f"look-ahead: setup produced at candle {i} but C confirmed at {conf}"
            )
            if c_swing is None:
                c_swing = conf
    assert c_swing is not None


def test_min_distance_filters_small_structures():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0)]
    )
    without = _detect(candles, min_distance=Decimal("0"))
    with_strict = _detect(candles, min_distance=Decimal("1000"))
    assert len(without) >= 1
    assert with_strict == []


def test_duplicate_prevention_same_c_not_twice():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0)]
    )
    setups = _detect(candles)
    keys = [(s.direction.value, s.c.candle_index) for s in setups]
    assert len(keys) == len(set(keys))


def test_detector_reset():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 4, 1.0)]
    )
    detector = ReferenceABCDetector()
    assert detector.on_candle(candles[0]) == []
    detector.reset()
    # after reset, replaying a prefix must not produce setups from old state
    assert all(detector.on_candle(c) == [] for c in candles[:8])


def test_config_summary_reports_assumptions():
    detector = ReferenceABCDetector()
    summary = detector.config_summary
    assert summary["detector_class"] == "ReferenceABCDetector"
    assert "left_window" in summary and "right_window" in summary


def test_abc_setup_requires_chronology():
    a = PricePoint(value=Decimal(10), timestamp=1000, candle_index=0, role="A")
    b = PricePoint(value=Decimal(20), timestamp=2000, candle_index=5, role="B")
    c = PricePoint(value=Decimal(15), timestamp=3000, candle_index=9, role="C")
    setup = ABCSetup(a=a, b=b, c=c)
    assert setup.calculate_target() == Decimal(35) / Decimal(10)

    bad_c = PricePoint(value=Decimal(15), timestamp=500, candle_index=9, role="C")
    with pytest.raises(InvalidStrategyInputError, match="chronological"):
        ABCSetup(a=a, b=b, c=bad_c)


def test_abc_setup_rejects_bad_indices():
    a = PricePoint(value=Decimal(10), timestamp=1000, candle_index=4, role="A")
    b = PricePoint(value=Decimal(20), timestamp=2000, candle_index=2, role="B")
    c = PricePoint(value=Decimal(15), timestamp=3000, candle_index=9, role="C")
    with pytest.raises(InvalidStrategyInputError, match="indices"):
        ABCSetup(a=a, b=b, c=c)


def test_abc_setup_rejects_zero_or_negative():
    p_ok = PricePoint(value=Decimal(10), timestamp=1000, candle_index=0)
    with pytest.raises(InvalidStrategyInputError, match="A"):
        ABCSetup(
            a=PricePoint(value=Decimal(0), timestamp=0, candle_index=0),
            b=p_ok, c=p_ok,
        )
    # Negative values are rejected by PricePoint itself.
    with pytest.raises(InvalidPriceError):
        PricePoint(value=Decimal(-1))
    # Zero B/C values are rejected by ABCSetup.
    with pytest.raises(InvalidStrategyInputError, match="B"):
        ABCSetup(
            a=PricePoint(value=Decimal(10), timestamp=0, candle_index=0),
            b=PricePoint(value=Decimal(0), timestamp=1, candle_index=1),
            c=PricePoint(value=Decimal(5), timestamp=2, candle_index=2),
        )
    with pytest.raises(InvalidStrategyInputError, match="C"):
        ABCSetup(
            a=PricePoint(value=Decimal(10), timestamp=0, candle_index=0),
            b=PricePoint(value=Decimal(5), timestamp=1, candle_index=1),
            c=PricePoint(value=Decimal(0), timestamp=2, candle_index=2),
        )


def test_direction_must_be_enum():
    p = PricePoint(value=Decimal(10), timestamp=0, candle_index=0)
    with pytest.raises(InvalidStrategyInputError, match="SetupDirection"):
        ABCSetup(a=p, b=p, c=p, direction="long")
