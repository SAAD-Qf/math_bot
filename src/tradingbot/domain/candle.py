"""
Candle data model for OHLCV price data.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ..exceptions import InvalidCandleError

_ZERO = Decimal('0')


def _to_decimal(field_name: str, value: Any) -> Decimal:
    """Coerce a raw value to Decimal with explicit error handling."""
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, bool):
        raise InvalidCandleError(f"Candle {field_name} must be numeric, got bool")
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(str(value))
    elif isinstance(value, str):
        try:
            d = Decimal(value.strip())
        except InvalidOperation as e:
            raise InvalidCandleError(
                f"Candle {field_name} is not a valid number: {value!r}"
            ) from e
    else:
        raise InvalidCandleError(
            f"Candle {field_name} must be numeric, got {type(value).__name__}"
        )
    if d.is_nan():
        raise InvalidCandleError(f"Candle {field_name} cannot be NaN")
    if d.is_infinite():
        raise InvalidCandleError(f"Candle {field_name} cannot be infinite")
    return d


@dataclass(frozen=True)
class Candle:
    """Represents a single candlestick bar with OHLCV data.

    Attributes:
        timestamp: Unix timestamp in milliseconds
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume (non-negative)
    """
    timestamp: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self):
        """Validate candle data after initialization."""
        if not isinstance(self.timestamp, int) or isinstance(self.timestamp, bool):
            raise InvalidCandleError(
                f"Candle timestamp must be an integer (ms), got {type(self.timestamp).__name__}"
            )
        # Coerce numeric fields so construction from mixed types is safe.
        try:
            object.__setattr__(self, 'open', _to_decimal('open', self.open))
            object.__setattr__(self, 'high', _to_decimal('high', self.high))
            object.__setattr__(self, 'low', _to_decimal('low', self.low))
            object.__setattr__(self, 'close', _to_decimal('close', self.close))
            object.__setattr__(self, 'volume', _to_decimal('volume', self.volume))
        except InvalidCandleError:
            raise
        except (InvalidOperation, ValueError, TypeError) as e:
            raise InvalidCandleError(f"Invalid candle numeric value: {e}") from e

        if self.open < _ZERO or self.high < _ZERO or self.low < _ZERO or self.close < _ZERO:
            raise InvalidCandleError("Candle prices cannot be negative")
        if self.volume < _ZERO:
            raise InvalidCandleError(f"Candle volume cannot be negative: {self.volume}")
        if self.low > self.open or self.low > self.high or self.low > self.close:
            raise InvalidCandleError(f"Invalid low price: {self.low}")
        if self.high < self.open or self.high < self.low or self.high < self.close:
            raise InvalidCandleError(f"Invalid high price: {self.high}")
        if not (self.low <= self.open <= self.high):
            raise InvalidCandleError(f"Price levels inconsistent: {self.open}, {self.high}, {self.low}")
        if not (self.low <= self.close <= self.high):
            raise InvalidCandleError(f"Price levels inconsistent: {self.close}, {self.high}, {self.low}")

    @property
    def range(self) -> Decimal:
        """Calculate the price range (high - low)."""
        return self.high - self.low

    @property
    def mid_price(self) -> Decimal:
        """Calculate the midpoint price."""
        return (self.high + self.low) / Decimal('2')

    def is_bullish(self) -> bool:
        """Check if the candle is bullish (close > open)."""
        return self.close > self.open

    def is_bearish(self) -> bool:
        """Check if the candle is bearish (close < open)."""
        return self.close < self.open

    @classmethod
    def from_dict(cls, data: dict) -> 'Candle':
        """Create a Candle from a dictionary."""
        try:
            return cls(
                timestamp=int(data['timestamp']),
                open=Decimal(str(data['open'])),
                high=Decimal(str(data['high'])),
                low=Decimal(str(data['low'])),
                close=Decimal(str(data['close'])),
                volume=Decimal(str(data['volume']))
            )
        except (KeyError, ValueError, TypeError, InvalidOperation, InvalidCandleError) as e:
            raise InvalidCandleError(f"Failed to create Candle from dict: {e}") from e

    def to_dict(self) -> dict:
        """Convert Candle to dictionary."""
        return {
            'timestamp': self.timestamp,
            'open': str(self.open),
            'high': str(self.high),
            'low': str(self.low),
            'close': str(self.close),
            'volume': str(self.volume)
        }
