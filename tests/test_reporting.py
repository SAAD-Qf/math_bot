"""
Tests for reporting (JSON/CSV/Markdown) and chart generation.
"""

import json
import os

import pytest

from conftest import zigzag_candles
from tradingbot.backtesting.backtest_engine import BacktestConfig, BacktestEngine
from tradingbot.exceptions import TradingBotError
from tradingbot.reporting.charts import ChartGenerator
from tradingbot.reporting.reporter import Reporter

CANDLES = None  # populated lazily


def _result():
    candles = zigzag_candles(
        [(1, 6, 1.0), (-1, 6, 1.0), (1, 6, 1.0), (-1, 3, 0.5), (1, 8, 1.5)]
    )
    return BacktestEngine(config=BacktestConfig()).run(candles), candles


def _data(tmp_path):
    result, _ = _result()
    data = result.to_dict()
    data["dataset"]["path"] = "synthetic.csv"
    return data


class TestReporter:
    def test_json_roundtrip(self, tmp_path):
        data = _data(tmp_path)
        reporter = Reporter(config={"reports_dir": str(tmp_path)})
        parsed = json.loads(reporter.to_json(data))
        assert parsed["metrics"]["total_setups"] == data["metrics"]["total_setups"]

    def test_csv_content(self, tmp_path):
        data = _data(tmp_path)
        reporter = Reporter(config={"reports_dir": str(tmp_path)})
        csv_text = reporter.to_csv(data)
        assert "Metric,Value" in csv_text
        assert "metrics.total_setups" in csv_text

    def test_markdown_sections(self, tmp_path):
        data = _data(tmp_path)
        reporter = Reporter(config={"reports_dir": str(tmp_path)})
        md = reporter.to_markdown(data)
        for section in (
            "# Mathematical Trading Bot — Backtest Report",
            "## Dataset", "## Configuration", "## Metrics", "## Setups",
            "## Warnings", "## Errors", "## Assumptions",
        ):
            assert section in md

    def test_export_all_formats(self, tmp_path):
        data = _data(tmp_path)
        reporter = Reporter(config={"reports_dir": str(tmp_path)})
        paths = reporter.export_all(data, base_name="bt")
        assert set(paths) == {"json", "csv", "markdown"}
        for path in paths.values():
            assert os.path.exists(path), path
            assert os.path.getsize(path) > 0
        assert paths["json"].endswith(".json")
        assert paths["csv"].endswith(".csv")
        assert paths["markdown"].endswith(".md")

    def test_json_file_is_valid_json(self, tmp_path):
        data = _data(tmp_path)
        reporter = Reporter(config={"reports_dir": str(tmp_path)})
        paths = reporter.export_all(data, base_name="bt2")
        with open(paths["json"], encoding="utf-8") as f:
            parsed = json.load(f)
        assert "setup_results" in parsed

    def test_unsupported_format(self, tmp_path):
        reporter = Reporter()
        with pytest.raises(TradingBotError, match="Unsupported"):
            reporter.get_report({}, "xml")

    def test_reports_based_on_actual_backtest_data(self, tmp_path):
        data = _data(tmp_path)
        md = Reporter().to_markdown(data)
        # The setup count in the table must match the data.
        assert f"## Setups ({data['setup_count']})" in md


class TestCharts:
    def test_chart_generated(self, tmp_path):
        result, candles = _result()
        gen = ChartGenerator(config={"charts_dir": str(tmp_path)})
        path = gen.generate_backtest_chart(candles, result.setup_results)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 10_000  # a real PNG, not an empty file

    def test_chart_without_candles_raises(self, tmp_path):
        gen = ChartGenerator(config={"charts_dir": str(tmp_path)})
        with pytest.raises(TradingBotError):
            gen.generate_backtest_chart([], [])

    def test_chart_with_dict_results(self, tmp_path):
        result, candles = _result()
        gen = ChartGenerator(config={"charts_dir": str(tmp_path)})
        dicts = [r.to_dict() for r in result.setup_results]
        path = gen.generate_backtest_chart(candles, dicts)
        assert os.path.exists(path)

    def test_no_equity_curve_by_design(self):
        """There is no execution model, so no equity chart API may exist."""
        gen = ChartGenerator()
        assert not any(
            name.startswith("generate_equity") for name in dir(gen)
        )
