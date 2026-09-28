"""
Unit tests for swing detection, including explicit no-look-ahead proofs.
"""

import pytest

from conftest import make_candle, zigzag_candles
from tradingbot.detection.swing_detector import (
    SwingDetector,
    SwingDetectorConfig,
)


def test_config_validation():
    with pytest.raises(ValueError):
        SwingDetectorConfig(left_window=0)
    with pytest.raises(ValueError):
        SwingDetectorConfig(right_window=0)
    with pytest.raises(ValueError):
        SwingDetectorConfig(min_separation=-1)


def test_swing_high_detection():
    # Rise 0..3 (peak high at 3), fall 4..7
    candles = zigzag_candles([(1, 4, 1.0), (-1, 4, 1.0)])
    detector = SwingDetector(SwingDetectorConfig(left_window=3, right_window=3))
    swings = detector.process_all(candles)
    highs = [s for s in swings if s.is_high]
    assert len(highs) == 1
    assert highs[0].point_index == 3
    assert highs[0].value == candles[3].high


def test_swing_low_detection():
    # Fall 0..3 (trough low at 3), rise 4..7
    candles = zigzag_candles([(-1, 4, 1.0), (1, 4, 1.0)])
    detector = SwingDetector(SwingDetectorConfig(left_window=3, right_window=3))
    swings = detector.process_all(candles)
    lows = [s for s in swings if s.is_low]
    assert len(lows) == 1
    assert lows[0].point_index == 3
    assert lows[0].value == candles[3].low


def test_confirmation_delay_equals_right_window():
    """A swing at index p is only returned when candle p+right_window arrives."""
    candles = zigzag_candles([(1, 4, 1.0), (-1, 4, 1.0)])
    detector = SwingDetector(SwingDetectorConfig(left_window=3, right_window=3))
    seen = []
    for i, candle in enumerate(candles):
        for s in detector.on_candle(candle):
            seen.append((i, s))
    assert len(seen) == 1
    arrival_index, swing = seen[0]
    assert swing.point_index == 3
    assert arrival_index == swing.confirmed_at_index == 6
    assert swing.confirmed_at_timestamp == candles[6].timestamp
    assert swing.point_timestamp == candles[3].timestamp


def test_no_lookahead_swing_unavailable_before_confirmation():
    """CRITICAL: before p+right_window candles exist, the swing MUST NOT appear."""
    candles = zigzag_candles([(1, 4, 1.0), (-1, 4, 1.0)])
    detector = SwingDetector(SwingDetectorConfig(left_window=3, right_window=3))
    early = []
    for i, candle in enumerate(candles):
        early.extend(detector.on_candle(candle))
        if i < 6:
            assert early == [], f"swing leaked at candle {i} (needs confirmation at 6)"
    assert len(early) == 1


def test_no_lookahead_on_partial_history():
    """Truncating the same series must never produce extra swings."""
    full = zigzag_candles([(1, 4, 1.0), (-1, 4, 1.0), (1, 4, 1.0), (-1, 4, 1.0)])
    for cutoff in range(1, len(full)):
        partial_swings = SwingDetector(
            SwingDetectorConfig(left_window=3, right_window=3)
        ).process_all(full[:cutoff])
        for s in partial_swings:
            assert s.confirmed_at_index < cutoff, (
                f"look-ahead: swing confirmed at {s.confirmed_at_index} "
                f"produced from only {cutoff} candles"
            )


def test_ties_are_deterministic_first_max_wins():
    """Plateau: the FIRST candle of the plateau is the swing high."""
    candles = [
        make_candle(0, 100, 101, 99, 100),
        make_candle(1, 100, 105, 99, 100),
        make_candle(2, 100, 105, 99, 100),  # tie with index 1
        make_candle(3, 100, 103, 99, 100),
        make_candle(4, 100, 101, 99, 100),
        make_candle(5, 100, 100, 99, 100),
        make_candle(6, 100, 100, 99, 100),
        make_candle(7, 100, 100, 99, 100),
    ]
    detector = SwingDetector(SwingDetectorConfig(left_window=1, right_window=3))
    swings = detector.process_all(candles)
    highs = [s for s in swings if s.is_high]
    assert len(highs) == 1
    assert highs[0].point_index == 1


def test_min_separation_suppresses_close_swings():
    """Large min_separation keeps at most one swing per role; zero allows all."""
    candles = zigzag_candles(
        [(1, 4, 1.0), (-1, 4, 1.0), (1, 4, 1.0), (-1, 4, 1.0)]
    )
    relaxed = SwingDetector(
        SwingDetectorConfig(left_window=3, right_window=3, min_separation=0)
    ).process_all(candles)
    strict = SwingDetector(
        SwingDetectorConfig(left_window=3, right_window=3, min_separation=100)
    ).process_all(candles)
    assert len(relaxed) >= 2
    assert len(strict) == 2  # exactly one high and one low


def test_reset_clears_state():
    candles = zigzag_candles([(1, 4, 1.0), (-1, 4, 1.0)])
    detector = SwingDetector(SwingDetectorConfig(left_window=3, right_window=3))
    detector.process_all(candles)
    detector.reset()
    assert detector.candles_seen == 0
    assert detector.process_all(candles[:5]) == []


def test_flat_market_no_swings():
    candles = [make_candle(i, 100, 100.2, 99.8, 100) for i in range(20)]
    detector = SwingDetector(SwingDetectorConfig(left_window=3, right_window=3))
    assert detector.process_all(candles) == []
