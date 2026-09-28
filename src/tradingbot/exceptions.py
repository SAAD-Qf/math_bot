"""
Custom exception hierarchy for the trading bot.

All domain and infrastructure errors derive from TradingBotError so callers
can catch any project-specific failure with a single except clause.
"""


class TradingBotError(Exception):
    """Base class for all trading bot errors."""


class InvalidCandleError(TradingBotError):
    """Raised when a Candle fails validation (bad OHLCV values)."""


class InvalidPriceError(TradingBotError):
    """Raised when a price value is invalid (negative, NaN, etc.)."""


class InvalidStrategyInputError(TradingBotError):
    """Raised when a strategy receives input it cannot process."""


class DataProviderError(TradingBotError):
    """Raised when a data provider fails to retrieve or parse market data."""


class DataValidationError(DataProviderError):
    """Raised when historical data fails strict validation."""


class ConfigurationError(TradingBotError):
    """Raised when configuration is missing, invalid, or inconsistent."""


class BacktestError(TradingBotError):
    """Raised when a backtest cannot run (bad data, bad parameters, etc.)."""


class DetectorError(TradingBotError):
    """Raised when swing/A-B-C detection cannot proceed."""


class InvalidStateTransitionError(BacktestError):
    """Raised when an invalid lifecycle state transition is attempted."""
