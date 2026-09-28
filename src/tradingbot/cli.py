"""
Command-line interface for the Mathematical Trading Bot.

Usage:
    python -m tradingbot --help
    python -m tradingbot calculate --a 100 --b 150 --c 125
    python -m tradingbot validate-data --file data/sample/sample.csv
    python -m tradingbot detect --file data/sample/sample.csv
    python -m tradingbot backtest --file data/sample/sample.csv
    python -m tradingbot report --file data/sample/sample.csv
"""

import argparse
import json
import sys
from typing import List, Optional

from .exceptions import TradingBotError
from .logging import get_logger

logger = get_logger("tradingbot.cli")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m tradingbot",
        description=(
            "Mathematical Trading Bot — research and backtesting system. "
            "Core formula: TARGET = (B + C) / A. No live trading."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {_get_version()}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- calculate ------------------------------------------------------
    p_calc = sub.add_parser(
        "calculate",
        help="Calculate TARGET = (B + C) / A for given A, B, C values.",
    )
    p_calc.add_argument("--a", required=True, type=str, help="Point A (must be > 0)")
    p_calc.add_argument("--b", required=True, type=str, help="Point B (must be > 0)")
    p_calc.add_argument("--c", required=True, type=str, help="Point C (must be > 0)")
    p_calc.add_argument("--json", action="store_true", help="Output as JSON")

    # --- validate-data ---------------------------------------------------
    p_val = sub.add_parser(
        "validate-data",
        help="Validate a historical CSV dataset (strict, no silent repair).",
    )
    p_val.add_argument("--file", required=True, type=str, help="Path to CSV file")
    p_val.add_argument(
        "--allow-duplicates", action="store_true",
        help="Drop duplicate timestamps with a warning instead of failing",
    )

    # --- detect -----------------------------------------------------------
    p_detect = sub.add_parser(
        "detect",
        help="Run A/B/C detection on a CSV dataset and print found setups.",
    )
    p_detect.add_argument("--file", required=True, type=str, help="Path to CSV file")
    _add_common_backtest_args(p_detect)

    # --- backtest -----------------------------------------------------------
    p_bt = sub.add_parser(
        "backtest",
        help="Run a full historical backtest on a CSV dataset.",
    )
    p_bt.add_argument("--file", required=True, type=str, help="Path to CSV file")
    _add_common_backtest_args(p_bt)
    p_bt.add_argument("--json", action="store_true", help="Print result summary as JSON")
    p_bt.add_argument(
        "--no-charts", action="store_true", help="Skip chart generation"
    )

    # --- report -----------------------------------------------------------
    p_rep = sub.add_parser(
        "report",
        help="Run a backtest and export JSON/CSV/Markdown reports and charts.",
    )
    p_rep.add_argument("--file", required=True, type=str, help="Path to CSV file")
    _add_common_backtest_args(p_rep)
    p_rep.add_argument(
        "--reports-dir", default="reports", help="Directory for reports (default: reports)"
    )
    p_rep.add_argument(
        "--charts-dir", default="charts", help="Directory for charts (default: charts)"
    )
    p_rep.add_argument("--base-name", default="backtest", help="Base file name")

    return parser


def _add_common_backtest_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--target-mode",
        choices=["high_low_reach", "close_reach"],
        default="high_low_reach",
        help="Target evaluation interpretation (default: high_low_reach)",
    )
    p.add_argument(
        "--invalidation",
        choices=["reference", "none"],
        default="reference",
        help="Invalidation rule (default: reference)",
    )
    p.add_argument(
        "--left-window", type=int, default=3, help="Swing left window (default 3)"
    )
    p.add_argument(
        "--right-window", type=int, default=3, help="Swing right/confirmation window (default 3)"
    )
    p.add_argument(
        "--min-separation", type=int, default=1,
        help="Minimum candle separation between same-role swings (default 1)",
    )
    p.add_argument(
        "--min-distance", type=float, default=0.0,
        help="Minimum price distance between structural points (default 0)",
    )
    p.add_argument(
        "--max-candles-active", type=int, default=200,
        help="Expire setups after this many active candles (default 200)",
    )
    p.add_argument(
        "--target-projection",
        choices=["c_anchored_ratio", "identity"],
        default="c_anchored_ratio",
        help=(
            "How the dimensionless mathematical target maps to a price level "
            "(interpretation; default: c_anchored_ratio)"
        ),
    )
    p.add_argument(
        "--direction", choices=["both", "long", "short"], default="both",
        help="Restrict detection to one direction (default: both)",
    )


def _get_version() -> str:
    from . import __version__
    return __version__


# ----------------------------------------------------------------------
# Command handlers
# ----------------------------------------------------------------------
def cmd_calculate(args: argparse.Namespace) -> int:
    from .mathematical_engine import MathematicalEngine

    engine = MathematicalEngine()
    try:
        result = engine.calculate_target(args.a, args.b, args.c)
    except TradingBotError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print("Mathematical Strategy Calculation")
    print("Formula: TARGET = (B + C) / A")
    print()
    print(f"A      = {result.a}")
    print(f"B      = {result.b}")
    print(f"C      = {result.c}")
    print(f"B + C  = {result.sum}")
    print(f"TARGET = {result.target}")
    return 0


def _load_candles(file: str, allow_duplicates: bool = False):
    from .data.csv_data_provider import CSVDataProvider

    provider = CSVDataProvider(file, config={"allow_duplicates": allow_duplicates})
    report = provider.validate()
    return provider, report


def cmd_validate_data(args: argparse.Namespace) -> int:
    try:
        _, report = _load_candles(args.file, args.allow_duplicates)
    except TradingBotError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1

    print("Dataset validation PASSED")
    print(f"  File:               {report.path}")
    print(f"  Data rows:          {report.row_count}")
    print(f"  Candles:            {report.candle_count}")
    print(f"  Chronologically sorted: {report.sorted}")
    if report.duplicates_removed:
        print(f"  Duplicates removed: {report.duplicates_removed}")
    for w in report.warnings:
        print(f"  Warning: {w}")
    return 0


def _resolve_direction(value: str) -> Optional[str]:
    return None if value == "both" else value


def cmd_detect(args: argparse.Namespace) -> int:
    from decimal import Decimal

    from .detection.abc_detector import ABCDetectorConfig, ReferenceABCDetector
    from .detection.swing_detector import SwingDetectorConfig

    try:
        provider, report = _load_candles(args.file)
        candles = provider.get_candles()
    except TradingBotError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    swing_cfg = SwingDetectorConfig(
        left_window=args.left_window,
        right_window=args.right_window,
        min_separation=args.min_separation,
    )
    detector_cfg = ABCDetectorConfig(
        swing_config=swing_cfg,
        min_distance=Decimal(str(args.min_distance)),
    )
    detector = ReferenceABCDetector(detector_cfg)
    wanted = _resolve_direction(args.direction)
    from .strategy.mathematical_strategy import MathematicalStrategy

    strategy = MathematicalStrategy(detector=detector)
    setups = []
    for candle in candles:
        for s in strategy.feed(candle):
            if wanted is None or s.direction.value == wanted:
                setups.append(s)

    print("A/B/C Detection (reference detector — see docs/strategy.md)")
    print(f"  File: {args.file}")
    print(f"  Candles: {report.candle_count}")
    print(f"  Swing config: left={args.left_window}, right={args.right_window}, "
          f"min_separation={args.min_separation}")
    print(f"  Setups found: {len(setups)}")
    print()
    for i, setup in enumerate(setups, start=1):
        print(f"Setup {i}: [{setup.direction.value.upper()}]")
        print(f"  A = {setup.a.value} (ts={setup.a.timestamp}, idx={setup.a.candle_index})")
        print(f"  B = {setup.b.value} (ts={setup.b.timestamp}, idx={setup.b.candle_index})")
        print(f"  C = {setup.c.value} (ts={setup.c.timestamp}, idx={setup.c.candle_index})")
        print(f"  TARGET = {setup.target}  [= ({setup.b.value} + {setup.c.value}) / {setup.a.value}]")
        print()
    return 0


def _run_backtest_with_options(args: argparse.Namespace):

    from .backtesting.backtest_engine import BacktestConfig, BacktestEngine
    from .strategy.mathematical_strategy import MathematicalStrategy

    provider, report = _load_candles(args.file)
    candles = provider.get_candles()

    config = BacktestConfig(
        target_mode=args.target_mode,
        invalidation_rule=args.invalidation,
        max_candles_active=args.max_candles_active,
        target_projection=args.target_projection,
    )
    strategy = MathematicalStrategy()
    engine = BacktestEngine(strategy=strategy, config=config)
    result = engine.run(candles)
    return result, report


def cmd_backtest(args: argparse.Namespace) -> int:
    from .reporting.charts import ChartGenerator

    try:
        result, report = _run_backtest_with_options(args)
    except TradingBotError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        m = result.metrics
        print("Backtest completed")
        print(f"  Candles:            {result.dataset['candle_count']}")
        print(f"  Total setups:       {m['total_setups']}")
        print(f"  Target reached:     {m['target_reached']}")
        print(f"  Invalidated:        {m['invalidated_setups']}")
        print(f"  Expired:            {m['expired_setups']}")
        print(f"  Target hit rate:    {m['target_hit_rate_pct']}%")
        print(f"  Completion rate:    {m['completion_rate_pct']}%")
        print(f"  Warnings:           {len(result.warnings)}")

    if not args.no_charts:
        try:
            chart = ChartGenerator(config={"charts_dir": "charts"})
            provider, _ = _load_candles(args.file)
            candles = provider.get_candles()
            path = chart.generate_backtest_chart(
                candles, result.setup_results, file_name="backtest"
            )
            print(f"  Chart:              {path}")
        except TradingBotError as e:
            print(f"  Chart error: {e}", file=sys.stderr)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from .reporting.charts import ChartGenerator
    from .reporting.reporter import Reporter

    try:
        result, report = _run_backtest_with_options(args)
    except TradingBotError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    data = result.to_dict()
    data["dataset"]["path"] = args.file
    data["dataset"]["validation"] = report.to_dict()

    reporter = Reporter(config={"reports_dir": args.reports_dir})
    paths = reporter.export_all(data, base_name=args.base_name)

    provider, _ = _load_candles(args.file)
    chart = ChartGenerator(config={"charts_dir": args.charts_dir})
    chart_path = chart.generate_backtest_chart(
        provider.get_candles(), result.setup_results, file_name=args.base_name
    )

    print("Report generated")
    print(f"  JSON:     {paths['json']}")
    print(f"  CSV:      {paths['csv']}")
    print(f"  Markdown: {paths['markdown']}")
    print(f"  Chart:    {chart_path}")
    print()
    print(f"Setups: {data['setup_count']}, "
          f"target hit rate: {data['metrics']['target_hit_rate_pct']}%")
    return 0


HANDLERS = {
    "calculate": cmd_calculate,
    "validate-data": cmd_validate_data,
    "detect": cmd_detect,
    "backtest": cmd_backtest,
    "report": cmd_report,
}


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = HANDLERS[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
