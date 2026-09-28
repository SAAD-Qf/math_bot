"""
ABCSetup domain model.

NOTE ON STRATEGY BOUNDARY:
The confirmed part of the strategy is ONLY the formula TARGET = (B + C) / A.
How A, B and C are identified in market data is NOT confirmed; see
docs/strategy.md and docs/assumptions.md. This model is detection-agnostic.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..exceptions import InvalidStrategyInputError
from .enums import InvalidationStatus, SetupDirection, SetupStatus, TargetStatus
from .price_point import PricePoint


@dataclass(frozen=True)
class ABCSetup:
    """Represents a setup of A, B, and C price points for strategy evaluation.

    Attributes:
        a: Point A (denominator, must be > 0)
        b: Point B (numerator component 1, must be > 0)
        c: Point C (numerator component 2, must be > 0)
        direction: Trade direction (long/short)
        status: Lifecycle status of the setup
        target_status: Status of the target evaluation
        invalidation_status: Status of the invalidation evaluation
        target: Target calculated with TARGET = (B + C) / A (optional until calculated)
        created_at: Timestamp (ms) at which the setup was created/activated
        metadata: Arbitrary detector/strategy metadata
    """
    a: PricePoint
    b: PricePoint
    c: PricePoint
    direction: SetupDirection = SetupDirection.LONG
    status: SetupStatus = SetupStatus.PENDING
    target_status: TargetStatus = TargetStatus.NOT_EVALUATED
    invalidation_status: InvalidationStatus = InvalidationStatus.NOT_EVALUATED
    target: Optional[Decimal] = None
    created_at: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate ABC setup after initialization."""
        for name, point in (("A", self.a), ("B", self.b), ("C", self.c)):
            if not isinstance(point, PricePoint):
                raise InvalidStrategyInputError(
                    f"Point {name} must be a PricePoint, got {type(point).__name__}"
                )
        if self.a.value == Decimal('0'):
            raise InvalidStrategyInputError("Point A cannot have value 0 (division by zero)")
        if self.a.value <= Decimal('0'):
            raise InvalidStrategyInputError("Point A must be positive")
        if self.b.value <= Decimal('0'):
            raise InvalidStrategyInputError("Point B must be positive")
        if self.c.value <= Decimal('0'):
            raise InvalidStrategyInputError("Point C must be positive")
        if not isinstance(self.direction, SetupDirection):
            raise InvalidStrategyInputError(
                f"direction must be a SetupDirection enum, got {type(self.direction).__name__}"
            )
        if not isinstance(self.status, SetupStatus):
            raise InvalidStrategyInputError(
                f"status must be a SetupStatus enum, got {type(self.status).__name__}"
            )
        # Enforce strict chronological ordering of the three points.
        ts = [self.a.timestamp, self.b.timestamp, self.c.timestamp]
        if all(t is not None for t in ts):
            if not (ts[0] <= ts[1] <= ts[2]):
                raise InvalidStrategyInputError(
                    f"A/B/C timestamps must be chronological (A<=B<=C), got {ts}"
                )
        idx = [self.a.candle_index, self.b.candle_index, self.c.candle_index]
        if all(i is not None for i in idx):
            if not (idx[0] < idx[1] < idx[2]):
                raise InvalidStrategyInputError(
                    f"A/B/C candle indices must be strictly increasing, got {idx}"
                )

    def calculate_target(self) -> Decimal:
        """Calculate the target using the formula: TARGET = (B + C) / A.

        Returns:
            The calculated target value.

        Raises:
            InvalidStrategyInputError if A is zero.
        """
        if self.a.value == Decimal('0'):
            raise InvalidStrategyInputError("Cannot calculate target: point A has value 0")
        target = (self.b.value + self.c.value) / self.a.value
        object.__setattr__(self, 'target', target)
        return target

    def get_points(self) -> List[PricePoint]:
        """Get all three points as a list [A, B, C]."""
        return [self.a, self.b, self.c]

    def is_bullish_setup(self) -> bool:
        """Heuristic: B > A and C > B (kept for backwards compatibility)."""
        return self.b.value > self.a.value and self.c.value > self.b.value

    def is_bearish_setup(self) -> bool:
        """Heuristic: B < A and C < B (kept for backwards compatibility)."""
        return self.b.value < self.a.value and self.c.value < self.b.value

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the setup to a JSON-friendly dictionary."""
        return {
            "a": self.a.to_dict(),
            "b": self.b.to_dict(),
            "c": self.c.to_dict(),
            "direction": self.direction.value,
            "status": self.status.value,
            "target_status": self.target_status.value,
            "invalidation_status": self.invalidation_status.value,
            "target": str(self.target) if self.target is not None else None,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }
