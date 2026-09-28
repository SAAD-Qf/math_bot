"""
Invalidation rules for active ABC setups.

INTERPRETATION NOTE (NOT a confirmed strategy rule):
When a setup is considered "invalidated" is not part of the confirmed strategy.
The reference rule below is a documented, configurable interpretation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from ..domain import ABCSetup, Candle
from ..domain.enums import InvalidationStatus, SetupDirection


class InvalidationRule(ABC):
    """Interface for setup invalidation decisions."""

    @abstractmethod
    def check(
        self,
        setup: ABCSetup,
        candle: Candle,
        candles_since_activation: int,
    ) -> Optional[InvalidationStatus]:
        """Evaluate one candle against an active setup.

        Args:
            setup: The active setup.
            candle: The candle being evaluated (always AFTER activation).
            candles_since_activation: Number of candles evaluated so far
                including this one.

        Returns:
            InvalidationStatus.INVALIDATED, InvalidationStatus.EXPIRED, or
            None when the setup remains valid.
        """
        raise NotImplementedError

    def describe(self) -> Dict[str, str]:
        """Human-readable description used in reports."""
        return {
            "rule_class": type(self).__name__,
            "interpretation": self.interpretation,
        }

    @property
    @abstractmethod
    def interpretation(self) -> str:
        raise NotImplementedError


class ReferenceInvalidationRule(InvalidationRule):
    """Reference invalidation mechanism.

    REFERENCE INTERPRETATION (documented assumption):
    * A LONG setup is invalidated when a candle's low <= C point value
      (price breaks back through the C structural level).
    * A SHORT setup is invalidated when a candle's high >= C point value.
    * A setup expires after ``max_candles_active`` candles of monitoring.

    All inputs come from the setup itself and candles AFTER activation, so no
    future information is used.
    """

    def __init__(self, max_candles_active: int = 200):
        if max_candles_active < 1:
            raise ValueError("max_candles_active must be >= 1")
        self.max_candles_active = max_candles_active

    @property
    def interpretation(self) -> str:
        return (
            "Long invalidated when candle.low <= C value; short invalidated when "
            "candle.high >= C value; setups expire after "
            f"{self.max_candles_active} active candles."
        )

    def describe(self) -> Dict[str, str]:
        return {
            "rule_class": type(self).__name__,
            "max_candles_active": str(self.max_candles_active),
            "interpretation": self.interpretation,
        }

    def check(
        self,
        setup: ABCSetup,
        candle: Candle,
        candles_since_activation: int,
    ) -> Optional[InvalidationStatus]:
        if setup.direction == SetupDirection.LONG:
            if candle.low <= setup.c.value:
                return InvalidationStatus.INVALIDATED
        else:
            if candle.high >= setup.c.value:
                return InvalidationStatus.INVALIDATED
        if candles_since_activation >= self.max_candles_active:
            return InvalidationStatus.EXPIRED
        return None


class NoInvalidationRule(InvalidationRule):
    """Setup never invalidates; only expiry (max_candles_active) applies."""

    def __init__(self, max_candles_active: int = 500):
        if max_candles_active < 1:
            raise ValueError("max_candles_active must be >= 1")
        self.max_candles_active = max_candles_active

    @property
    def interpretation(self) -> str:
        return (
            "No price-based invalidation; setups expire after "
            f"{self.max_candles_active} active candles."
        )

    def describe(self) -> Dict[str, str]:
        return {
            "rule_class": type(self).__name__,
            "max_candles_active": str(self.max_candles_active),
            "interpretation": self.interpretation,
        }

    def check(
        self,
        setup: ABCSetup,
        candle: Candle,
        candles_since_activation: int,
    ) -> Optional[InvalidationStatus]:
        if candles_since_activation >= self.max_candles_active:
            return InvalidationStatus.EXPIRED
        return None


def build_invalidation_rule(kind: str, max_candles_active: int = 200) -> InvalidationRule:
    """Factory for invalidation rules.

    Args:
        kind: "reference" (price-through-C + expiry) or "none" (expiry only).
        max_candles_active: candles a setup may stay active before expiring.
    """
    if kind == "reference":
        return ReferenceInvalidationRule(max_candles_active=max_candles_active)
    if kind == "none":
        return NoInvalidationRule(max_candles_active=max_candles_active)
    raise ValueError(f"Unknown invalidation rule kind: {kind!r} (use 'reference' or 'none')")
