"""Shared test fixtures and candle builders."""

import math
from decimal import Decimal
from typing import List

import pytest

from tradingbot.domain import Candle

START_MS = 1609459200000  # 2021-01-01T00:00:00Z
STEP_MS = 3_600_000


def make_candle(i: int, open_: float, high: float, low: float, close: float,
                volume: float = 100.0, step_ms: int = STEP_MS,
                start_ms: int = START_MS) -> Candle:
    """Build one Candle at index i with explicit OHLCV floats."""
    return Candle(
        timestamp=start_ms + i * step_ms,
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
    )


def flat_candles(n: int, price: float = 100.0) -> List[Candle]:
    """n candles all at the same price."""
    return [
        make_candle(i, price, price + 0.5, price - 0.5, price) for i in range(n)
    ]


def zigzag_candles(legs: List[tuple], start: float = 100.0) -> List[Candle]:
    """Build a zig-zag path from legs of (direction, length, per_candle_move).

    direction: +1 up, -1 down. Prices are continuous (close == next open).
    On an up candle the HIGH extends beyond the close (high = close + tip) and
    equals the open otherwise; on a down candle the LOW extends beyond the
    close (low = close - tip). Result: highs strictly increase along an up leg
    and strictly decrease along a down leg (mirror for lows), so each turn
    candle is the unique extreme of its neighborhood — clean, unambiguous
    swings.
    """
    candles: List[Candle] = []
    price = start
    i = 0
    tip = 0.1
    for direction, length, move in legs:
        for _ in range(length):
            o = price
            c = price + direction * move
            if direction > 0:
                hi = c + tip * move
                lo = o
            else:
                hi = o
                lo = c - tip * move
            candles.append(make_candle(i, o, hi, lo, c))
            price = c
            i += 1
    return candles


def sinus_candles(n: int, amplitude: float = 10.0, period: float = 30.0,
                  base: float = 100.0) -> List[Candle]:
    """Deterministic sine-wave candles."""
    candles: List[Candle] = []
    for i in range(n):
        mid = base + amplitude * math.sin(2.0 * math.pi * i / period)
        o = mid - 0.3
        c = mid + 0.3
        candles.append(make_candle(i, o, max(o, c) + 0.5, min(o, c) - 0.5, c))
    return candles


@pytest.fixture
def sample_csv(tmp_path):
    """A small valid CSV file."""
    path = tmp_path / "valid.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "1609459200000,100.0,105.0,95.0,102.0,1000.0\n"
        "1609462800000,102.0,108.0,100.0,106.0,1200.0\n"
        "1609466400000,106.0,110.0,104.0,105.0,800.0\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def big_sample_csv(tmp_path):
    """A 300-candle deterministic sine-wave CSV (same generator as scripts/)."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    try:
        from generate_sample_data import generate, write_csv
    finally:
        sys.path.pop(0)
    path = tmp_path / "sine.csv"
    write_csv(str(path), generate(300))
    return str(path)
