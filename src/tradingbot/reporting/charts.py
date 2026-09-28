"""
Matplotlib-based research charts.

Charts are pure visualizations of ACTUAL backtest data (no fabricated equity
curves — there is no execution model in this project). Saved under charts/.
"""

import os
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")  # headless-safe backend
import matplotlib.pyplot as plt

from ..domain import Candle
from ..exceptions import TradingBotError

TARGET_COLOR = "#d62728"
REACHED_COLOR = "#2ca02c"
INVALIDATED_COLOR = "#7f7f7f"
EXPIRED_COLOR = "#bcbd22"


class ChartGenerator:
    """Generates research charts for a backtest run."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.charts_dir = self.config.get("charts_dir", "charts")

    def generate_backtest_chart(
        self,
        candles: List[Candle],
        setup_results: List[Any],
        file_name: str = "backtest",
        title: str = "ABC Setups — Mathematical Strategy Research Chart",
    ) -> str:
        """Render price chart with A/B/C markers, targets and outcomes.

        Returns the written file path.

        Args:
            candles: chronological candle list used in the backtest.
            setup_results: SetupResult objects (or dicts) from a run.
        """
        if not candles:
            raise TradingBotError("Cannot generate chart without candles")

        try:
            os.makedirs(self.charts_dir, exist_ok=True)
        except OSError as e:
            raise TradingBotError(f"Cannot create charts directory: {e}") from e

        x = list(range(len(candles)))
        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]

        fig, ax = plt.subplots(figsize=(14, 7))

        ax.fill_between(x, lows, highs, alpha=0.15, color="#1f77b4", label="Candle range")
        ax.plot(x, closes, color="#1f77b4", linewidth=1.2, label="Close")

        results = [self._coerce_result(r) for r in setup_results]

        # --- A / B / C structural markers --------------------------------
        marker_specs = [
            ("A", "^", "#9467bd"),
            ("B", "v", "#ff7f0e"),
            ("C", "o", "#8c564b"),
        ]
        for role, marker, color in marker_specs:
            xs, ys = [], []
            for r in results:
                point = r.get(role.lower(), {})
                idx = point.get("candle_index")
                value = point.get("value")
                if idx is None or value is None:
                    continue
                if 0 <= int(idx) < len(candles):
                    xs.append(int(idx))
                    ys.append(float(value))
            if xs:
                ax.scatter(
                    xs, ys, marker=marker, color=color, s=70, zorder=5,
                    edgecolors="black", linewidths=0.5, label=f"{role} point",
                )

        # --- Target levels while a setup is active ------------------------
        for r in results:
            target = r.get("target")
            a_idx = r.get("a", {}).get("candle_index")
            if not target or a_idx is None:
                continue
            start = max(int(a_idx), 0)
            end_idx = None
            for field in ("reached_at", "invalidated_at", "expiry_at", "completed_at"):
                ts = r.get(field)
                if ts is not None:
                    end_idx = self._ts_to_index(candles, ts)
                    break
            end = (end_idx if end_idx is not None else len(candles) - 1)
            if end <= start:
                end = min(start + 1, len(candles) - 1)
            ax.hlines(
                float(target), start, end, colors=TARGET_COLOR,
                linestyles="dashed", linewidth=1.0,
            )

        # --- Outcome markers ----------------------------------------------
        plotted = set()
        for r in results:
            for field, color, label in (
                ("reached_at", REACHED_COLOR, "Target reached"),
                ("invalidated_at", INVALIDATED_COLOR, "Invalidated"),
                ("expiry_at", EXPIRED_COLOR, "Expired"),
            ):
                ts = r.get(field)
                if ts is None or ts in plotted:
                    continue
                idx = self._ts_to_index(candles, ts)
                if idx is None:
                    continue
                plotted.add(ts)
                ax.scatter(
                    [idx], [closes[idx]], marker="*", s=160, color=color,
                    zorder=6, edgecolors="black", linewidths=0.5,
                    label=label if label not in plotted else None,
                )

        # Deduplicate legend entries while keeping order.
        handles, labels = ax.get_legend_handles_labels()
        seen = {}
        for h, lab in zip(handles, labels, strict=False):
            if lab and lab not in seen:
                seen[lab] = h
        ax.legend(seen.values(), seen.keys(), loc="best", fontsize=9)

        ax.set_title(title)
        ax.set_xlabel("Candle index")
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3)

        out_path = os.path.join(self.charts_dir, f"{file_name}.png")
        try:
            fig.tight_layout()
            fig.savefig(out_path, dpi=150)
        except OSError as e:
            raise TradingBotError(f"Failed to save chart: {e}") from e
        finally:
            plt.close(fig)

        return out_path

    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_result(result: Any) -> Dict[str, Any]:
        """Accept SetupResult objects or pre-serialized dicts."""
        if isinstance(result, dict):
            return result
        if hasattr(result, "to_dict"):
            return result.to_dict()
        raise TradingBotError("setup_results must be SetupResult or dict")

    @staticmethod
    def _ts_to_index(candles: List[Candle], timestamp: int) -> Optional[int]:
        """Map a candle timestamp to its index (first match)."""
        for i, c in enumerate(candles):
            if c.timestamp == timestamp:
                return i
        return None
