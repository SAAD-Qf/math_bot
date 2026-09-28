"""
Abstract base class for historical market data providers.

This defines the interface that all data providers must implement,
enabling dependency injection and testability.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from ..domain import Candle
from ..exceptions import DataProviderError, InvalidCandleError


class HistoricalDataProvider(ABC):
    """Abstract base class for historical market data providers.

    All data providers must implement this interface to ensure consistency
    across different data sources (CSV, exchanges, etc.).

    Args:
        config: Configuration object for the data provider (optional)
    """

    def __init__(self, config: Optional[dict] = None):
        """Initialize the data provider with optional configuration."""
        self.config = config or {}

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        timeframe: str = "1h"
    ) -> List[Candle]:
        """Retrieve historical candles for a given symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            start_time: Start timestamp for data retrieval (optional, defaults to earliest available)
            end_time: End timestamp for data retrieval (optional, defaults to latest available)
            timeframe: Timeframe for candles (e.g., "1m", "5m", "1h", "1d")

        Returns:
            List of Candle objects

        Raises:
            DataProviderError: If data retrieval fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the data provider is available and properly configured.

        Returns:
            True if the provider is available, False otherwise
        """
        pass

    def validate_candle_data(self, data: List[dict]) -> List[Candle]:
        """Validate and convert raw candle data to Candle objects.

        This is a helper method that can be used by concrete providers
        to validate data before returning it.

        Args:
            data: Raw candle data (list of dictionaries)

        Returns:
            List of validated Candle objects

        Raises:
            DataProviderError: If data validation fails
        """
        candles = []
        for candle_data in data:
            try:
                candles.append(Candle.from_dict(candle_data))
            except (InvalidCandleError, KeyError, ValueError) as e:
                raise DataProviderError(f"Invalid candle data: {e}") from e
        return candles
