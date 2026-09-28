"""
MathematicalStrategy: the full strategy pipeline.

Pipeline:
    Candles -> Swing Detection -> A/B/C Detection -> ABC Validation ->
    Mathematical Calculation -> Setup Creation -> (Target Evaluation and
    Invalidation are handled by the backtest engine candle-by-candle).

This module knows nothing about CSV files, exchanges, the CLI, or reports.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..detection.abc_detector import ABCDetector, ReferenceABCDetector
from ..domain import ABCSetup, Candle, PricePoint
from ..domain.enums import SetupStatus, TargetStatus
from ..exceptions import InvalidStrategyInputError
from .strategy import Strategy
from .target_projection import (
    CAnchoredRatioTargetProjector,
    TargetProjector,
)


class MathematicalStrategy(Strategy):
    """Strategy engine implementing the mathematical ABC pipeline.

    The formula TARGET = (B + C) / A is the only confirmed rule; A/B/C
    detection is delegated to a replaceable detector.

    Args:
        detector: An ABCDetector implementation (default ReferenceABCDetector).
        config: Optional dict merged into strategy metadata.
    """

    def __init__(
        self,
        detector: Optional[ABCDetector] = None,
        projector: Optional[TargetProjector] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(config)
        self.detector = detector or ReferenceABCDetector()
        # REFERENCE INTERPRETATION: how the dimensionless mathematical target
        # maps onto the instrument's price scale is NOT confirmed (see
        # docs/strategy.md). The projector makes this mapping explicit and
        # replaceable.
        self.target_projector = projector or CAnchoredRatioTargetProjector()
        self._math_engine = _MathEngineAdapter()

    # ------------------------------------------------------------------
    # Strategy interface
    # ------------------------------------------------------------------
    def analyze(self, candles: List[Candle]) -> Optional[ABCSetup]:
        """Analyze a chronological candle list and return the most recent setup.

        Provided for the Phase 0 Strategy interface; incremental processing is
        preferred via ``feed``.
        """
        if not candles:
            return None
        self.reset()
        setups: List[ABCSetup] = []
        for candle in candles:
            setups.extend(self.feed(candle))
        return setups[-1] if setups else None

    def calculate_target(self, abc_setup: ABCSetup) -> PricePoint:
        """Calculate TARGET = (B + C) / A and return it as a PricePoint.

        The mathematical value is stored on the setup; the projected price
        level is stored separately in ``target_price``.
        """
        result = self._math_engine.calculate_target(
            abc_setup.a.value, abc_setup.b.value, abc_setup.c.value
        )
        return PricePoint(
            value=result.target,
            timestamp=abc_setup.created_at,
            source="mathematical_engine",
            role="TARGET",
            metadata={"formula": result.formula},
        )

    def compute_price_target(self, abc_setup: ABCSetup) -> Decimal:
        """Return the projected price level for a setup.

        mathematical target = (B + C) / A (confirmed formula)
        price target       = projector(target, direction, A, B, C) (interpretation)
        """
        result = self._math_engine.calculate_target(
            abc_setup.a.value, abc_setup.b.value, abc_setup.c.value
        )
        return self.target_projector.project(
            result.target, abc_setup.direction,
            abc_setup.a.value, abc_setup.b.value, abc_setup.c.value,
        )

    def validate_setup(self, abc_setup: ABCSetup) -> bool:
        """Validate chronological order, positivity and A != 0."""
        if abc_setup is None:
            return False
        try:
            ABCSetup(
                a=abc_setup.a, b=abc_setup.b, c=abc_setup.c,
                direction=abc_setup.direction,
            )
        except InvalidStrategyInputError:
            return False
        if abc_setup.c.timestamp is not None and abc_setup.a.timestamp is not None:
            if abc_setup.c.timestamp < abc_setup.a.timestamp:
                return False
        return True

    # ------------------------------------------------------------------
    # Incremental pipeline
    # ------------------------------------------------------------------
    def feed(self, candle: Candle) -> List[ABCSetup]:
        """Feed one candle into the pipeline; return newly created setups
        (mathematical target and projected price target attached)."""
        setups = self.detector.on_candle(candle)
        for setup in setups:
            target = self.calculate_target(setup).value
            price_target = self.compute_price_target(setup)
            object.__setattr__(setup, 'target', target)
            object.__setattr__(setup, 'metadata', {
                **setup.metadata,
                'mathematical_target': str(target),
                'price_target': str(price_target),
                'target_projection': self.target_projector.name,
            })
            object.__setattr__(setup, 'target_status', TargetStatus.PENDING)
            object.__setattr__(setup, 'status', SetupStatus.PENDING)
        return setups

    def reset(self) -> None:
        """Reset detector state."""
        self.detector.reset()

    # ------------------------------------------------------------------
    # Introspection for reporting
    # ------------------------------------------------------------------
    def describe(self) -> Dict[str, Any]:
        """Describe strategy configuration for reports."""
        detector_cfg = (
            self.detector.config_summary
            if hasattr(self.detector, "config_summary")
            else {"detector_class": type(self.detector).__name__}
        )
        return {
            "strategy_class": type(self).__name__,
            "formula": "(B + C) / A",
            "target_projection": self.target_projector.describe(),
            "detector": detector_cfg,
        }


class _MathEngineAdapter:
    """Thin lazy adapter to avoid import cycles at module load time."""

    def __init__(self):
        from ..mathematical_engine import MathematicalEngine
        self._engine = MathematicalEngine()

    def calculate_target(self, a: Decimal, b: Decimal, c: Decimal):
        return self._engine.calculate_target(a, b, c)
