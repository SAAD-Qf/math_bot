"""
PricePoint data model for reusable price/value points.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from ..exceptions import InvalidPriceError

EMPTY: Mapping[str, Any] = {}


@dataclass(frozen=True)
class PricePoint:
    """Represents a single price/value point.

    Attributes:
        value: The price value (must be finite and >= 0).
        timestamp: Unix timestamp in milliseconds (optional).
        source: Source identifier for the price (optional).
        candle_index: Index of the candle this point was derived from (optional).
        role: Role of the point in an ABC structure (optional 'A'/'B'/'C'/swing role).
        metadata: Additional context about how the point was derived.
    """
    value: Decimal
    timestamp: Optional[int] = None
    source: Optional[str] = None
    candle_index: Optional[int] = None
    role: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate price point."""
        if not isinstance(self.value, Decimal):
            raise InvalidPriceError(
                f"PricePoint.value must be a Decimal, got {type(self.value).__name__}"
            )
        if self.value.is_nan() or self.value.is_infinite():
            raise InvalidPriceError(
                f"PricePoint value must be finite, got: {self.value}"
            )
        if self.value < Decimal('0'):
            raise InvalidPriceError(f"Negative price value not allowed: {self.value}")

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"PricePoint(value={self.value}, timestamp={self.timestamp}, source={self.source})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert the point to a plain dictionary (JSON friendly)."""
        return {
            'value': str(self.value),
            'timestamp': self.timestamp,
            'source': self.source,
            'candle_index': self.candle_index,
            'role': self.role,
            'metadata': dict(self.metadata),
        }

    @classmethod
    def from_float(cls, value: float, timestamp: Optional[int] = None,
                   source: Optional[str] = None) -> 'PricePoint':
        """Create a PricePoint from a float value."""
        return cls(value=Decimal(str(value)), timestamp=timestamp, source=source)

    @classmethod
    def from_str(cls, value: str, timestamp: Optional[int] = None,
                 source: Optional[str] = None) -> 'PricePoint':
        """Create a PricePoint from a string value."""
        return cls(value=Decimal(value), timestamp=timestamp, source=source)
