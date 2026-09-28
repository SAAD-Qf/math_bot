"""
Test imports and project package initialization.
"""

def test_imports():
    """Verify that all core components can be imported without error."""
    import tradingbot
    from tradingbot import (
        ABCSetup,
        BacktestError,
        BacktestStatus,
        Candle,
        Config,
        ConfigurationError,
        CSVDataProvider,
        DataProviderError,
        HistoricalDataProvider,
        InvalidCandleError,
        InvalidPriceError,
        InvalidStrategyInputError,
        MathematicalEngine,
        PricePoint,
        Strategy,
        get_logger,
    )
    assert tradingbot.__version__ == "0.1.0"
    assert Candle is not None
    assert PricePoint is not None
    assert ABCSetup is not None
    assert BacktestStatus is not None
    assert Strategy is not None
    assert HistoricalDataProvider is not None
    assert CSVDataProvider is not None
    assert InvalidCandleError is not None
    assert InvalidPriceError is not None
    assert InvalidStrategyInputError is not None
    assert DataProviderError is not None
    assert ConfigurationError is not None
    assert BacktestError is not None
    assert Config is not None
    assert MathematicalEngine is not None
    assert get_logger is not None
