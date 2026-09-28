"""
Tests for backtest metrics.
"""

from decimal import Decimal

from conftest import zigzag_candles
from tradingbot.backtesting.backtest_engine import BacktestConfig, BacktestEngine


def _run(candles, **cfg):
    return BacktestEngine(config=BacktestConfig(**cfg)).run(candles)


def test_metrics_keys_present():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 3, 0.5), (1, 8, 1.5)]
    )
    metrics = _run(candles).metrics
    for key in (
        "total_setups", "valid_setups", "invalidated_setups", "expired_setups",
        "target_reached", "target_not_reached", "target_hit_rate_pct",
        "invalidation_rate_pct", "completion_rate_pct", "still_active_at_end",
        "duration", "long", "short", "setup_frequency_per_100_candles",
        "max_favorable_excursion_avg", "max_adverse_excursion_avg",
    ):
        assert key in metrics, f"missing metric: {key}"


def test_counts_are_consistent():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 3, 0.5), (1, 8, 1.5)]
    )
    m = _run(candles).metrics
    assert m["target_reached"] + m["target_not_reached"] == m["valid_setups"]
    assert (
        m["target_reached"] + m["invalidated_setups"] + m["expired_setups"]
        == m["valid_setups"]
    )
    assert m["valid_setups"] + m["still_active_at_end"] == m["total_setups"]


def test_rates_in_zero_to_hundred():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 4, 1.0)]
    )
    m = _run(candles).metrics
    for rate in ("target_hit_rate_pct", "invalidation_rate_pct", "completion_rate_pct"):
        assert 0.0 <= m[rate] <= 100.0


def test_directional_statistics():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 4, 1.0),
         (-1, 6, 1.0), (1, 6, 1.0), (-1, 6, 1.0), (1, 4, 1.0)]
    )
    m = _run(candles).metrics
    assert m["long"]["total"] + m["short"]["total"] == m["total_setups"]
    assert m["long"]["target_reached"] <= m["long"]["total"]
    assert m["short"]["target_reached"] <= m["short"]["total"]


def test_duration_stats_sane():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 3, 0.5), (1, 8, 1.5)]
    )
    d = _run(candles).metrics["duration"]
    assert d["min_ms"] <= d["median_ms"] <= d["max_ms"]
    assert d["min_ms"] <= d["avg_ms"] <= d["max_ms"]


def test_setup_frequency():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 4, 1.0)]
    )
    m = _run(candles).metrics
    assert m["setup_frequency_per_100_candles"] == round(
        m["total_setups"] / len(candles) * 100.0, 4
    )


def test_mfe_mae_non_negative():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 3, 0.5), (1, 8, 1.5)]
    )
    m = _run(candles).metrics
    assert m["max_favorable_excursion_avg"] >= 0
    assert m["max_adverse_excursion_avg"] >= 0


def test_zero_setups_metrics_safe():
    from tradingbot.domain import Candle

    candles = [
        Candle(
            timestamp=1609459200000 + i * 3_600_000,
            open=Decimal(100), high=Decimal("100.2"),
            low=Decimal("99.8"), close=Decimal(100), volume=Decimal(1),
        )
        for i in range(15)
    ]
    m = _run(candles).metrics
    assert m["total_setups"] == 0
    assert m["target_hit_rate_pct"] == 0.0
    assert m["duration"]["avg_ms"] == 0.0
