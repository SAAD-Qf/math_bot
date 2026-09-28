"""
Target evaluation for ABC setups.

INTERPRETATION NOTE (NOT a confirmed strategy rule):
The formula TARGET = (B + C) / A is confirmed; *how* a target level is checked
against candles is an interpretation. Two configurable modes are provided:

* HIGH_LOW_REACH: a long setup reaches its target when a candle's high touches
  or exceeds the target; a short setup when the low touches or undercuts it.
* CLOSE_REACH: a long setup reaches its target when the close >= target; a
  short when close <= target.

Both modes only use candle data from AFTER the setup became active, so they
never leak future information.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict

from ..domain import Candle
from ..domain.enums import SetupDirection, TargetEvaluationMode


class TargetEvaluator(ABC):
    """Interface for target reachability evaluation."""

    @abstractmethod
    def evaluate(self, target: Decimal, direction: SetupDirection, candle: Candle) -> bool:
        """Return True if this candle reaches the target for the given direction."""
        raise NotImplementedError

    @property
    @abstractmethod
    def mode(self) -> TargetEvaluationMode:
        """The evaluation mode identifier."""
        raise NotImplementedError

    @property
    @abstractmethod
    def interpretation(self) -> str:
        """Human-readable interpretation, used in reports."""
        raise NotImplementedError

    def describe(self) -> Dict[str, str]:
        """Human-readable description used in reports."""
        return {
            "evaluator_class": type(self).__name__,
            "mode": self.mode.value,
            "interpretation": self.interpretation,
        }


class HighLowReachEvaluator(TargetEvaluator):
    """Target counts as reached when the candle's extreme touches the level.

    Long: candle.high >= target. Short: candle.low <= target.
    """

    @property
    def mode(self) -> TargetEvaluationMode:
        return TargetEvaluationMode.HIGH_LOW_REACH

    @property
    def interpretation(self) -> str:
        return (
            "Long: candle.high >= target. Short: candle.low <= target. "
            "Intrabar extreme touch counts as a reach."
        )

    def evaluate(self, target: Decimal, direction: SetupDirection, candle: Candle) -> bool:
        if direction == SetupDirection.LONG:
            return candle.high >= target
        return candle.low <= target


class CloseReachEvaluator(TargetEvaluator):
    """Target counts as reached only when the candle closes beyond the level.

    Long: candle.close >= target. Short: candle.close <= target.
    """

    @property
    def mode(self) -> TargetEvaluationMode:
        return TargetEvaluationMode.CLOSE_REACH

    @property
    def interpretation(self) -> str:
        return (
            "Long: candle.close >= target. Short: candle.close <= target. "
            "Only candle closes count; intrabar touches do not."
        )

    def evaluate(self, target: Decimal, direction: SetupDirection, candle: Candle) -> bool:
        if direction == SetupDirection.LONG:
            return candle.close >= target
        return candle.close <= target


def build_target_evaluator(mode: TargetEvaluationMode) -> TargetEvaluator:
    """Factory: build the evaluator for a configured mode."""
    if mode == TargetEvaluationMode.HIGH_LOW_REACH:
        return HighLowReachEvaluator()
    if mode == TargetEvaluationMode.CLOSE_REACH:
        return CloseReachEvaluator()
    raise ValueError(f"Unknown target evaluation mode: {mode}")
