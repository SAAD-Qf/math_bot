"""
Mathematical engine for trading strategy calculations.

This module implements the core mathematical calculations for the trading strategy,
including the ABC setup target formula and validation.

STRATEGY BOUNDARY:
    The formula TARGET = (B + C) / A is the ONLY confirmed part of the strategy.
    No detection or interpretation logic lives here.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Dict, Optional

from .exceptions import TradingBotError

FORMULA = "(B + C) / A"

# Valid contexts for passing an A/B/C input into the engine.
_VALID_POINT_TYPES = (Decimal, int, float, str)


def _coerce(value: Any, name: str) -> Decimal:
    """Coerce an input value to a Decimal with strict validation."""
    if isinstance(value, bool):
        raise TradingBotError(f"Point {name} must be numeric, got bool")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(str(value))
    elif isinstance(value, str):
        try:
            d = Decimal(value.strip())
        except InvalidOperation as e:
            raise TradingBotError(f"Point {name} is not a valid number: {value!r}") from e
    else:
        raise TradingBotError(
            f"Point {name} must be numeric (Decimal/int/float/str), got {type(value).__name__}"
        )
    if d.is_nan():
        raise TradingBotError("Points A, B, and C cannot be NaN")
    if d.is_infinite():
        raise TradingBotError("Points A, B, and C cannot be infinite")
    return d


@dataclass
class MathematicalCalculationResult:
    """Result of mathematical calculations for ABC setups.

    Attributes:
        a: Point A value
        b: Point B value
        c: Point C value
        sum: B + C sum
        target: (B + C) / A target value
        formula: The mathematical formula used
        timestamp: Optional timestamp for the calculation
        metadata: Additional metadata about the calculation
    """
    a: Decimal
    b: Decimal
    c: Decimal
    sum: Decimal
    target: Decimal
    formula: str = FORMULA
    timestamp: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate calculation result."""
        if self.a == 0:
            raise TradingBotError("Point A cannot be zero (division by zero)")
        if self.b < 0 or self.c < 0:
            raise TradingBotError("Points B and C cannot be negative")
        if self.b == 0 or self.c == 0:
            raise TradingBotError("Points B and C cannot be zero")

    def to_dict(self) -> Dict[str, Any]:
        """Convert calculation result to dictionary."""
        return {
            "a": str(self.a),
            "b": str(self.b),
            "c": str(self.c),
            "sum": str(self.sum),
            "target": str(self.target),
            "formula": self.formula,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata or {}),
        }

    def __str__(self) -> str:
        return (f"MathematicalCalculationResult(a={self.a}, b={self.b}, c={self.c}, "
                f"sum={self.sum}, target={self.target})")


class MathematicalEngine:
    """Engine for mathematical calculations in trading strategies.

    This engine implements the core mathematical formula for the trading strategy:
    TARGET = (B + C) / A

    It provides methods for calculating targets, validating inputs, and formatting
    results in a structured way.

    Args:
        strict_mode: Whether to enforce strict validation (default: True).
            When True, A must be strictly positive and B, C must be > 0.
            When False, only A != 0 and B, C >= 0 are enforced.
        precision: Number of significant digits used for division (default 28).
        config: Optional configuration for the engine
    """

    def __init__(self, strict_mode: bool = True, precision: int = 28,
                 config: Optional[Dict[str, Any]] = None):
        self.strict_mode = strict_mode
        self.precision = precision
        self.config = config or {}

    def calculate_target(self, a: Any, b: Any, c: Any) -> MathematicalCalculationResult:
        """Calculate the target using the formula: TARGET = (B + C) / A.

        This is the core mathematical formula for the trading strategy.
        The formula is preserved exactly as specified: TARGET = (B + C) / A.

        Args:
            a: Point A value (denominator)
            b: Point B value (numerator component 1)
            c: Point C value (numerator component 2)

        Returns:
            MathematicalCalculationResult with the calculated target

        Raises:
            TradingBotError: If validation fails
        """
        a_d = _coerce(a, "A")
        b_d = _coerce(b, "B")
        c_d = _coerce(c, "C")
        self._validate_inputs(a_d, b_d, c_d)

        sum_result = b_d + c_d
        with localcontext() as ctx:
            ctx.prec = self.precision
            target = sum_result / a_d

        return MathematicalCalculationResult(
            a=a_d, b=b_d, c=c_d, sum=sum_result, target=target
        )

    def calculate_from_points(self, point_a: Any, point_b: Any, point_c: Any) -> MathematicalCalculationResult:
        """Calculate target from PricePoint-like objects (requires `.value`).

        Args:
            point_a: PricePoint for point A
            point_b: PricePoint for point B
            point_c: PricePoint for point C

        Returns:
            MathematicalCalculationResult with the calculated target

        Raises:
            TradingBotError: If validation fails or points are invalid
        """
        try:
            a = point_a.value
            b = point_b.value
            c = point_c.value
        except AttributeError as e:
            raise TradingBotError(f"Invalid PricePoint objects: {e}") from e
        return self.calculate_target(a, b, c)

    def validate_inputs(self, a: Any, b: Any, c: Any) -> bool:
        """Validate inputs for mathematical calculations.

        Args:
            a: Point A value
            b: Point B value
            c: Point C value

        Returns:
            True if inputs are valid, False otherwise
        """
        try:
            a_d, b_d, c_d = _coerce(a, "A"), _coerce(b, "B"), _coerce(c, "C")
            self._validate_inputs(a_d, b_d, c_d)
            return True
        except TradingBotError:
            return False

    def _validate_inputs(self, a: Decimal, b: Decimal, c: Decimal) -> None:
        """Validate already-coerced Decimals (no NaN/infinity at this point)."""
        # Check for zero denominator
        if a == 0:
            raise TradingBotError("Point A cannot be zero (division by zero)")

        if self.strict_mode:
            if a < 0:
                raise TradingBotError("Point A cannot be negative")
            if b <= 0:
                raise TradingBotError("Point B must be positive")
            if c <= 0:
                raise TradingBotError("Point C must be positive")
        else:
            if b < 0:
                raise TradingBotError("Points B and C cannot be negative")
            if c < 0:
                raise TradingBotError("Points B and C cannot be negative")

    def get_example_calculation(self) -> MathematicalCalculationResult:
        """Get an example calculation for documentation and testing.

        Uses the canonical example: A=100, B=150, C=125 -> TARGET = 2.75
        """
        return self.calculate_target(Decimal("100"), Decimal("150"), Decimal("125"))

    def validate_calculation_result(self, result: MathematicalCalculationResult) -> bool:
        """Validate a calculation result by re-deriving sum and target."""
        try:
            if result.a == 0:
                return False
            if result.b < 0 or result.c < 0:
                return False
            expected_sum = result.b + result.c
            if result.sum != expected_sum:
                return False
            expected_target = expected_sum / result.a
            if result.target != expected_target:
                return False
            return True
        except Exception:
            return False
