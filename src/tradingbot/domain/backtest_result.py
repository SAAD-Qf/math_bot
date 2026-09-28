"""
BacktestResult: aggregated output of a complete backtest run.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import SetupDirection
from .setup_result import SetupResult


@dataclass
class BacktestResult:
    """Complete result of a backtest run.

    Attributes:
        dataset: Information about the dataset used (path, symbol, counts).
        config: The effective configuration (detector, evaluator, invalidation, costs).
        setup_results: Per-setup outcome records.
        metrics: Computed statistics (see backtesting.metrics).
        warnings: Non-fatal issues observed during the run.
        errors: Fatal errors encountered (usually empty if the run completed).
        assumptions: Documented strategy assumptions in effect.
        duration_ms: Wall-clock duration of the run in milliseconds.
    """
    dataset: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    setup_results: List[SetupResult] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    assumptions: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None

    @property
    def total_setups(self) -> int:
        return len(self.setup_results)

    def setups_in_direction(self, direction: SetupDirection) -> List[SetupResult]:
        """Return setup results filtered by direction."""
        return [r for r in self.setup_results if r.setup.direction == direction]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "dataset": dict(self.dataset),
            "config": dict(self.config),
            "setup_count": len(self.setup_results),
            "setup_results": [r.to_dict() for r in self.setup_results],
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "assumptions": dict(self.assumptions),
            "duration_ms": self.duration_ms,
        }
