"""
Target projection: mapping the mathematical target to a comparable price level.

WHY THIS EXISTS (documented interpretation — NOT a confirmed strategy rule):
    The formula TARGET = (B + C) / A is CONFIRMED and produces a
    *dimensionless* number whenever A is expressed in the same price units as
    B and C. Candles, however, trade in *price units*. Before a target can be
    evaluated against candle highs/lows/closes, a projection rule from the
    mathematical value to a price level is REQUIRED — and that rule is NOT
    part of the confirmed strategy.

    Two configurable projectors are provided:

    * CAnchoredRatioTargetProjector (default):
        long:  price_target = C * TARGET  (C anchors the projection)
        short: price_target = C / TARGET
        Rationale (reference interpretation only): the target fraction is
        scaled by the last structural point C.

    * IdentityTargetProjector:
        price_target = TARGET
        Only meaningful when the instrument's price scale already equals the
        mathematical value scale.

    Both projectors are pure functions of already-known values (A, B, C,
    TARGET) — no market data, no look-ahead. Replace with the exact rule when
    it is defined.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict

from ..domain.enums import SetupDirection

ONE = Decimal('1')


class TargetProjector(ABC):
    """Interface for projecting the mathematical target onto the price scale."""

    @abstractmethod
    def project(self, target: Decimal, direction: SetupDirection,
                a: Decimal, b: Decimal, c: Decimal) -> Decimal:
        """Return the price level that will be compared against candles."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    def describe(self) -> Dict[str, str]:
        """Description used in reports."""
        return {
            "projector_class": type(self).__name__,
            "name": self.name,
            "interpretation": self.interpretation,
        }

    @property
    @abstractmethod
    def interpretation(self) -> str:
        raise NotImplementedError


class IdentityTargetProjector(TargetProjector):
    """Use the mathematical target directly as the price level."""

    @property
    def name(self) -> str:
        return "identity"

    @property
    def interpretation(self) -> str:
        return (
            "price_target = TARGET. Use only when the instrument's price scale "
            "equals the mathematical value scale."
        )

    def project(self, target: Decimal, direction: SetupDirection,
                a: Decimal, b: Decimal, c: Decimal) -> Decimal:
        return target


class CAnchoredRatioTargetProjector(TargetProjector):
    """Project around the C structural point using the target ratio.

    long:  price_target = C * TARGET
    short: price_target = C / TARGET  (guarding against division by zero)
    """

    @property
    def name(self) -> str:
        return "c_anchored_ratio"

    @property
    def interpretation(self) -> str:
        return (
            "REFERENCE INTERPRETATION (not confirmed): long price_target = "
            "C * TARGET; short price_target = C / TARGET. C is the anchor of "
            "the projection."
        )

    def project(self, target: Decimal, direction: SetupDirection,
                a: Decimal, b: Decimal, c: Decimal) -> Decimal:
        if direction == SetupDirection.SHORT:
            if c == 0:
                raise ValueError("C must be non-zero for short projection")
            return c / target
        return c * target


def build_target_projector(name: str) -> TargetProjector:
    """Factory for target projectors by name."""
    if name == "identity":
        return IdentityTargetProjector()
    if name == "c_anchored_ratio":
        return CAnchoredRatioTargetProjector()
    raise ValueError(
        f"Unknown target projector: {name!r} (use 'identity' or 'c_anchored_ratio')"
    )
