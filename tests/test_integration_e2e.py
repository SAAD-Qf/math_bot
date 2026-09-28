"""
End-to-end integration test.

CSV -> Data Validation -> Swing Detection -> A/B/C Detection ->
Mathematical Calculation -> Target Evaluation -> Invalidation -> Backtest ->
Metrics -> Reports -> Charts

Everything must work together using only public entry points.
"""

import json
import os
from decimal import Decimal

from tradingbot import (
    ABCDetectorConfig,
    BacktestConfig,
    BacktestEngine,
    MathematicalEngine,
    MathematicalStrategy,
    ReferenceABCDetector,
    SwingDetector,
    SwingDetectorConfig,
)
from tradingbot.data.csv_data_provider import CSVDataProvider
from tradingbot.reporting.charts import ChartGenerator
from tradingbot.reporting.reporter import Reporter


def test_full_pipeline_end_to_end(tmp_path):
    # ---- 1. CSV + Data Validation -------------------------------------
    provider = CSVDataProvider("data/sample/sample_sinus_1h.csv")
    report = provider.validate()
    assert report.is_valid
    assert report.candle_count == 300
    assert report.sorted

    candles = provider.get_candles()
    assert len(candles) == 300

    # ---- 2. Swing Detection (no look-ahead helper check) ---------------
    swings = SwingDetector(
        SwingDetectorConfig(left_window=3, right_window=3)
    ).process_all(candles)
    assert len(swings) > 0
    for s in swings:
        assert s.confirmed_at_index == s.point_index + 3

    # ---- 3. A/B/C Detection --------------------------------------------
    # (Via MathematicalStrategy so setups carry their calculated targets.)
    strategy = MathematicalStrategy(
        detector=ReferenceABCDetector(
            config=ABCDetectorConfig(
                swing_config=SwingDetectorConfig(left_window=3, right_window=3)
            )
        )
    )
    setups = []
    for candle in candles:
        setups.extend(strategy.feed(candle))
    assert len(setups) > 0
    for s in setups:
        assert s.a.candle_index < s.b.candle_index < s.c.candle_index

    # ---- 4. Mathematical Calculation (confirmed formula) ----------------
    for s in setups:
        expected = (s.b.value + s.c.value) / s.a.value
        assert s.target == expected
    canonical = MathematicalEngine().calculate_target(100, 150, 125)
    assert canonical.target == Decimal("2.75")

    # ---- 5-8. Backtest with Target Evaluation + Invalidation ------------
    engine = BacktestEngine(config=BacktestConfig(target_mode="high_low_reach"))
    result = engine.run(candles)

    assert result.dataset["candle_count"] == 300
    assert result.metrics["total_setups"] == len(result.setup_results)
    # Chronology invariants across every recorded setup.
    for r in result.setup_results:
        assert r.activated_at is not None
        if r.completed_at is not None:
            assert r.completed_at >= r.activated_at
        for t in r.state_transitions:
            assert t.timestamp is not None

    # ---- 9. Metrics ------------------------------------------------------
    m = result.metrics
    assert m["total_setups"] > 0
    assert (
        m["target_reached"] + m["invalidated_setups"] + m["expired_setups"]
        == m["valid_setups"]
    )
    assert 0.0 <= m["target_hit_rate_pct"] <= 100.0

    # ---- 10. Reports (JSON / CSV / Markdown) ----------------------------
    data = result.to_dict()
    data["dataset"]["path"] = "data/sample/sample_sinus_1h.csv"
    data["dataset"]["validation"] = report.to_dict()

    reporter = Reporter(config={"reports_dir": str(tmp_path / "reports")})
    paths = reporter.export_all(data, base_name="e2e")
    for path in paths.values():
        assert os.path.exists(path) and os.path.getsize(path) > 0
    with open(paths["json"], encoding="utf-8") as f:
        parsed = json.load(f)
    assert parsed["metrics"]["total_setups"] == m["total_setups"]
    assert "TARGET = (B + C) / A (confirmed)" in parsed["assumptions"]["formula"]

    # ---- 11. Charts -------------------------------------------------------
    chart_gen = ChartGenerator(config={"charts_dir": str(tmp_path / "charts")})
    chart_path = chart_gen.generate_backtest_chart(candles, result.setup_results)
    assert os.path.exists(chart_path) and os.path.getsize(chart_path) > 10_000


def test_second_dataset_without_code_changes(tmp_path):
    """The system must work on another CSV dataset with zero code changes."""
    other = tmp_path / "other_dataset.csv"
    rows = []
    for i in range(400):
        # Deterministic zig-zag with valid OHLC (open/close within [low, high]).
        base = 50 + (15 if (i // 20) % 2 == 0 else 5) + (i % 20) * 0.25
        o = base
        c = base + (0.8 if (i // 20) % 2 == 0 else -0.8)
        hi = max(o, c) + 0.5
        lo = min(o, c) - 0.5
        rows.append(
            f"{1700000000000 + i * 60000},{o},{hi},{lo},{c},10"
        )
    other.write_text(
        "timestamp,open,high,low,close,volume\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    provider = CSVDataProvider(str(other))
    assert provider.validate().is_valid
    result = BacktestEngine().run(provider.get_candles())
    assert result.dataset["candle_count"] == 400
    assert "metrics" in result.to_dict()


def test_determinism_same_inputs_same_outputs():
    provider = CSVDataProvider("data/sample/sample_sinus_1h.csv")
    candles = provider.get_candles()
    r1 = BacktestEngine().run(candles)
    r2 = BacktestEngine().run(candles)
    assert r1.metrics == r2.metrics
    assert len(r1.setup_results) == len(r2.setup_results)
    for a, b in zip(r1.setup_results, r2.setup_results, strict=False):
        assert a.target == b.target
        assert a.final_status == b.final_status
