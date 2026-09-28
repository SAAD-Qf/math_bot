from .backtesting import BacktestConfig, BacktestEngine, compute_metrics
from .config import Config
from .data import CSVDataProvider, HistoricalDataProvider
from .detection import (
    ABCDetector,
    ABCDetectorConfig,
    ReferenceABCDetector,
    SwingDetector,
    SwingDetectorConfig,
    SwingPoint,
)
from .domain import (
    ABCSetup,
    BacktestResult,
    BacktestStatus,
    Candle,
    InvalidationStatus,
    PointRole,
    PricePoint,
    SetupDirection,
    SetupResult,
    SetupStatus,
    StateTransition,
    TargetEvaluationMode,
    TargetStatus,
)
from .exceptions import (
    BacktestError,
    ConfigurationError,
    DataProviderError,
    InvalidCandleError,
    InvalidPriceError,
    InvalidStrategyInputError,
    TradingBotError,
)
from .logging import get_logger
from .mathematical_engine import MathematicalCalculationResult, MathematicalEngine
from .reporting import Reporter
from .reporting.charts import ChartGenerator
from .strategy import (
    CloseReachEvaluator,
    CostModel,
    FeeSlippageSpreadModel,
    HighLowReachEvaluator,
    InvalidationRule,
    MathematicalStrategy,
    NoInvalidationRule,
    ReferenceInvalidationRule,
    Strategy,
    TargetEvaluator,
    ZeroCostModel,
    build_cost_model,
    build_invalidation_rule,
    build_target_evaluator,
)

__version__ = "0.1.0"

__all__ = [
    'Candle', 'PricePoint', 'ABCSetup', 'BacktestStatus',
    'SetupDirection', 'SetupStatus', 'TargetStatus', 'InvalidationStatus',
    'TargetEvaluationMode', 'PointRole', 'StateTransition', 'SetupResult', 'BacktestResult',
    'Strategy', 'MathematicalStrategy',
    'TargetEvaluator', 'HighLowReachEvaluator', 'CloseReachEvaluator', 'build_target_evaluator',
    'InvalidationRule', 'ReferenceInvalidationRule', 'NoInvalidationRule', 'build_invalidation_rule',
    'CostModel', 'ZeroCostModel', 'FeeSlippageSpreadModel', 'build_cost_model',
    'HistoricalDataProvider', 'CSVDataProvider',
    'SwingPoint', 'SwingDetector', 'SwingDetectorConfig',
    'ABCDetector', 'ReferenceABCDetector', 'ABCDetectorConfig',
    'BacktestEngine', 'BacktestConfig', 'compute_metrics',
    'Reporter', 'ChartGenerator',
    'TradingBotError', 'InvalidCandleError', 'InvalidPriceError',
    'InvalidStrategyInputError', 'DataProviderError', 'ConfigurationError', 'BacktestError',
    'Config', 'MathematicalEngine', 'MathematicalCalculationResult', 'get_logger',
]
