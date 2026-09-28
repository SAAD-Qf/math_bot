"""
Abstract base class for trading strategies.

This defines the interface that all strategies must implement,
enabling consistent strategy execution across different approaches.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..domain import ABCSetup, Candle, PricePoint


class Strategy(ABC):
    """Abstract base class for trading strategies.

    All trading strategies must implement this interface to ensure consistency
    across different strategy approaches (mathematical, pattern-based, etc.).

    Args:
        config: Strategy configuration (optional)
    """

    def __init__(self, config: Optional[dict] = None):
        """Initialize strategy with configuration."""
        self.config = config or {}

    @abstractmethod
    def analyze(self, candles: List[Candle]) -> Optional[ABCSetup]:
        """Analyze market data and identify potential trading setups.

        This is the core method that must be implemented by concrete strategies.

        Args:
            candles: List of historical candle data

        Returns:
            ABCSetup object if a valid setup is found, None otherwise

        Raises:
            InvalidStrategyInputError: If analysis fails due to invalid input
        """
        pass

    @abstractmethod
    def calculate_target(self, abc_setup: ABCSetup) -> PricePoint:
        """Calculate the target price for a given ABC setup.

        This method implements the specific mathematical formula for the
        strategy. For our placeholder strategy: TARGET = (B + C) / A

        Args:
            abc_setup: Validated ABC setup containing points A, B, and C

        Returns:
            PricePoint representing the calculated target

        Raises:
            InvalidStrategyInputError: If calculation fails
        """
        pass

    def validate_setup(self, abc_setup: ABCSetup) -> bool:
        """Validate a candidate ABC setup.

        This helper method provides basic validation of ABC setups.
        Concrete strategies can override this with more sophisticated validation.

        Args:
            abc_setup: ABC setup to validate

        Returns:
            True if setup is valid, False otherwise
        """
        if not abc_setup:
            return False

        # Basic validation: all points must have valid values
        if not all([
            abc_setup.a and abc_setup.a.value is not None,
            abc_setup.b and abc_setup.b.value is not None,
            abc_setup.c and abc_setup.c.value is not None
        ]):
            return False

        # Basic validation: point A cannot be zero (division by zero)
        if abc_setup.a.value == 0:
            return False

        return True

    def is_compatible(self, candles: List[Candle]) -> bool:
        """Check if strategy is compatible with the given data.

        This can be used to determine if a strategy should be applied
        based on data characteristics (e.g., minimum number of candles,
        data quality, etc.).

        Args:
            candles: List of candles to check

        Returns:
            True if strategy is compatible, False otherwise
        """
        # Default implementation: require at least 2 candles
        return len(candles) >= 2
