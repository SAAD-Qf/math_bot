"""Enums for the tradingbot domain."""

from enum import Enum


class SetupDirection(str, Enum):
    """Direction of an ABC setup.

    The direction only affects *which price side* the target is evaluated on;
    the target value itself is always computed as TARGET = (B + C) / A.
    """

    LONG = "long"
    SHORT = "short"


class SetupStatus(str, Enum):
    """Lifecycle status of an ABC setup."""

    PENDING = "pending"          # detected, not yet active
    ACTIVE = "active"            # active; target evaluation running
    TARGET_REACHED = "target_reached"  # terminal: target was reached
    INVALIDATED = "invalidated"  # terminal: invalidation rule triggered
    EXPIRED = "expired"          # terminal: max duration exceeded


class TargetStatus(str, Enum):
    """Status of the target evaluation of a setup."""

    NOT_EVALUATED = "not_evaluated"
    PENDING = "pending"
    REACHED = "reached"
    NOT_REACHED = "not_reached"


class InvalidationStatus(str, Enum):
    """Status of the invalidation evaluation of a setup."""

    NOT_EVALUATED = "not_evaluated"
    NONE = "none"                # evaluated: no invalidation
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class TargetEvaluationMode(str, Enum):
    """How a target level is checked against candles.

    Both modes are CONFIGURABLE INTERPRETATIONS; the confirmed part of the
    strategy is only the formula TARGET = (B + C) / A (see docs/strategy.md).
    """

    HIGH_LOW_REACH = "high_low_reach"  # long: high >= target; short: low <= target
    CLOSE_REACH = "close_reach"        # long: close >= target; short: close <= target


class PointRole(str, Enum):
    """Role of a PricePoint in an ABC structure."""

    A = "A"
    B = "B"
    C = "C"
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
