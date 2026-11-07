"""
Reporter and analytics utilities.

Generates JSON, CSV and Markdown reports from BacktestResult data and exports
them under reports/. All report content derives from actual backtest data.
"""

import csv
import json
import os
from datetime import datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional

from ..exceptions import TradingBotError


class Reporter:
    """Generates reports and statistics from backtest results.

    Args:
        config: Reporter configuration (optional). Supported keys:
            reports_dir (str, default "reports")
    """

    KEY_METRICS = [
        "total_setups", "valid_setups", "target_reached", "target_not_reached",
        "target_hit_rate_pct", "invalidation_rate_pct", "completion_rate_pct",
    ]

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.reports_dir = self.config.get("reports_dir", "reports")

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    def to_json(self, data: Dict[str, Any], indent: int = 2) -> str:
        """Convert backtest results to a JSON string."""
        return json.dumps(data, indent=indent, default=str)

    def to_csv(self, data: Dict[str, Any], include_metadata: bool = True) -> str:
        """Convert backtest results to a CSV string (metric/value rows)."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(['Metric', 'Value'])
        for key, value in data.items():
            if not isinstance(value, (list, dict)):
                writer.writerow([key, value])

        if include_metadata and isinstance(data.get('metrics'), dict):
            writer.writerow([])
            writer.writerow(['Metrics', ''])
            for key, value in data['metrics'].items():
                if not isinstance(value, (list, dict)):
                    writer.writerow([f'metrics.{key}', value])
            for key, value in data['metrics'].items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if not isinstance(sub_value, (list, dict)):
                            writer.writerow([f'metrics.{key}.{sub_key}', sub_value])

        if include_metadata and isinstance(data.get('assumptions'), dict):
            writer.writerow([])
            writer.writerow(['Assumptions', ''])
            for key, value in data['assumptions'].items():
                writer.writerow([f'assumptions.{key}', value])

        return output.getvalue()

    def to_markdown(self, data: Dict[str, Any]) -> str:
        """Convert backtest results to a human-readable Markdown report."""
        lines: List[str] = []
        lines.append("# Mathematical Trading Bot — Backtest Report")
        lines.append("")
        lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_")
        lines.append("")

        dataset = data.get("dataset", {})
        lines.append("## Dataset")
        lines.append("")
        lines.append(f"- Candle count: **{dataset.get('candle_count', 0)}**")
        lines.append(f"- First timestamp: {dataset.get('first_timestamp')}")
        lines.append(f"- Last timestamp: {dataset.get('last_timestamp')}")
        lines.append("")

        cfg = data.get("config", {})
        lines.append("## Configuration")
        lines.append("")
        for key in (
            "target_mode", "invalidation_rule", "max_candles_active",
            "allow_overlapping", "allow_same_candle_activation",
            "fee", "slippage", "spread",
        ):
            if key in cfg:
                lines.append(f"- {key}: `{cfg[key]}`")
        strategy_cfg = cfg.get("strategy", {})
        if strategy_cfg:
            lines.append(f"- strategy: `{strategy_cfg.get('strategy_class', 'n/a')}`")
            detector = strategy_cfg.get("detector", {})
            if detector:
                lines.append(
                    f"- detector: `{detector.get('detector_class', 'n/a')}` "
                    f"(left={detector.get('left_window')}, right={detector.get('right_window')}, "
                    f"min_separation={detector.get('min_separation')}, "
                    f"min_distance={detector.get('min_distance')})"
                )
        lines.append("")

        lines.append("## Metrics")
        lines.append("")
        metrics = data.get("metrics", {})
        for key in self.KEY_METRICS:
            if key in metrics:
                lines.append(f"- {key}: **{metrics[key]}**")
        duration = metrics.get("duration", {})
        if duration:
            lines.append(
                f"- duration (ms): avg={duration.get('avg_ms')}, "
                f"median={duration.get('median_ms')}, min={duration.get('min_ms')}, "
                f"max={duration.get('max_ms')}"
            )
        for direction in ("long", "short"):
            stats = metrics.get(direction, {})
            if stats:
                lines.append(
                    f"- {direction}: total={stats.get('total')}, "
                    f"target_reached={stats.get('target_reached')}, "
                    f"invalidated={stats.get('invalidated')}, "
                    f"expired={stats.get('expired')}, "
                    f"hit_rate={stats.get('target_hit_rate_pct')}%"
                )
        lines.append("")

        setups = data.get("setup_results", [])
        lines.append(f"## Setups ({len(setups)})")
        lines.append("")
        if setups:
            lines.append("| # | Direction | A | B | C | Target | Status | Reached at | Invalidated at | Expired at |")
            lines.append("|---|-----------|---|---|---|--------|--------|------------|----------------|------------|")
            for i, s in enumerate(setups, start=1):
                a = s.get("a", {}).get("value", "?")
                b = s.get("b", {}).get("value", "?")
                c = s.get("c", {}).get("value", "?")
                target = s.get("target", "?")
                lines.append(
                    f"| {i} | {s.get('direction')} | {a} | {b} | {c} | {target} | "
                    f"{s.get('final_status')} | {s.get('reached_at') or '—'} | "
                    f"{s.get('invalidated_at') or '—'} | {s.get('expiry_at') or '—'} |"
                )
        else:
            lines.append("_No setups were detected._")
        lines.append("")

        warnings = data.get("warnings", [])
        lines.append(f"## Warnings ({len(warnings)})")
        lines.append("")
        if warnings:
            for w in warnings[:20]:
                lines.append(f"- {w}")
            if len(warnings) > 20:
                lines.append(f"- ... and {len(warnings) - 20} more")
        else:
            lines.append("_None._")
        lines.append("")

        errors = data.get("errors", [])
        lines.append(f"## Errors ({len(errors)})")
        lines.append("")
        if errors:
            for e in errors:
                lines.append(f"- {e}")
        else:
            lines.append("_None._")
        lines.append("")

        assumptions = data.get("assumptions", {})
        lines.append("## Assumptions")
        lines.append("")
        for key, value in assumptions.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Generic helpers (Phase 0 API preserved)
    # ------------------------------------------------------------------
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a concise summary of backtest results."""
        summary = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'completed',
        }
        metrics = data.get('metrics', {})
        for metric in self.KEY_METRICS:
            if metric in metrics:
                summary[metric] = metrics[metric]
        return summary

    def validate_results(self, data: Dict[str, Any]) -> bool:
        """Validate that results contain expected fields."""
        return 'metrics' in data and 'setup_results' in data

    def get_report(self, data: Dict[str, Any], format_type: str = 'json') -> str:
        """Generate a report string in the specified format."""
        if format_type == 'json':
            return self.to_json(data)
        if format_type == 'csv':
            return self.to_csv(data)
        if format_type in ('markdown', 'md'):
            return self.to_markdown(data)
        if format_type == 'summary':
            return json.dumps(self.generate_summary(data), indent=2, default=str)
        raise TradingBotError(f"Unsupported report format: {format_type}")

    # ------------------------------------------------------------------
    # File export
    # ------------------------------------------------------------------
    def export_to_file(self, data: Dict[str, Any], file_path: str,
                       format_type: str = 'json') -> None:
        """Export a report to a file, creating parent directories."""
        try:
            report = self.get_report(data, format_type)
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
        except TradingBotError:
            raise
        except OSError as e:
            raise TradingBotError(f"Failed to export report to file: {e}") from e

    def export_all(self, data: Dict[str, Any], base_name: str = "backtest",
                   reports_dir: Optional[str] = None) -> Dict[str, str]:
        """Export JSON, CSV and Markdown reports under reports/.

        Returns the mapping of format -> written file path.
        """
        out_dir = reports_dir or self.reports_dir
        os.makedirs(out_dir, exist_ok=True)
        paths = {
            "json": os.path.join(out_dir, f"{base_name}.json"),
            "csv": os.path.join(out_dir, f"{base_name}.csv"),
            "markdown": os.path.join(out_dir, f"{base_name}.md"),
        }
        self.export_to_file(data, paths["json"], "json")
        self.export_to_file(data, paths["csv"], "csv")
        self.export_to_file(data, paths["markdown"], "markdown")
        return paths

    def write_run_index(
        self,
        data: Dict[str, Any],
        base_name: str = "backtest",
        reports_dir: Optional[str] = None,
    ) -> str:
        """Append a compact run entry to ``<reports_dir>/run_index.json``.

        Reports are intentionally overwritten by base name; this index keeps a
        comparable history of the last 100 runs (dataset, config, key metrics).
        """
        out_dir = reports_dir or self.reports_dir
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "run_index.json")
        entries: List[Dict[str, Any]] = []
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    entries = loaded
            except (OSError, ValueError):
                entries = []

        metrics = data.get("metrics", {})
        entry = {
            "run_id": data.get("run_id") or base_name,
            "base_name": base_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset": dict(data.get("dataset", {})),
            "config": dict(data.get("config", {})),
            "metrics": {
                key: metrics[key] for key in self.KEY_METRICS if key in metrics
            },
            "setup_count": data.get("setup_count", len(data.get("setup_results", []))),
            "warning_count": len(data.get("warnings", [])),
        }
        entries.append(entry)
        entries = entries[-100:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, default=str)
        return path
