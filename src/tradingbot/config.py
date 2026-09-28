"""
Configuration management for the trading bot.

This module provides configuration management for the trading bot,
enabling different settings for development, testing, and production.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from .exceptions import ConfigurationError

load_dotenv()

@dataclass
class LoggingConfig:
    """Configuration for logging settings."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_size: int = 10485760  # 10MB
    backup_count: int = 5

    @classmethod
    def from_env(cls) -> 'LoggingConfig':
        """Create logging configuration from environment variables."""
        return cls(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file=os.getenv("LOG_FILE"),
            max_size=int(os.getenv("LOG_MAX_SIZE", "10485760")),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5"))
        )

@dataclass
class DataProviderConfig:
    """Configuration for data providers."""
    csv_file_path: str = "data/sample.csv"
    default_symbol: str = "BTCUSDT"
    default_timeframe: str = "1h"

    @classmethod
    def from_env(cls) -> 'DataProviderConfig':
        """Create data provider configuration from environment variables."""
        return cls(
            csv_file_path=os.getenv("CSV_FILE_PATH", "data/sample.csv"),
            default_symbol=os.getenv("DEFAULT_SYMBOL", "BTCUSDT"),
            default_timeframe=os.getenv("DEFAULT_TIMEFRAME", "1h")
        )

@dataclass
class StrategyConfig:
    """Configuration for the mathematical strategy and its detection pipeline.

    All detection-related values are REFERENCE INTERPRETATIONS (see
    docs/strategy.md); the confirmed rule is only TARGET = (B + C) / A.
    """
    default_config: Dict[str, Any] = field(default_factory=dict)
    swing_left_window: int = 3
    swing_right_window: int = 3
    swing_min_separation: int = 1
    min_distance: float = 0.0
    target_mode: str = "high_low_reach"
    target_projection: str = "c_anchored_ratio"
    invalidation_rule: str = "reference"
    max_candles_active: int = 200
    allow_overlapping: bool = True
    direction: str = "both"

    @classmethod
    def from_env(cls) -> 'StrategyConfig':
        """Create strategy configuration from environment variables."""
        return cls(
            default_config={
                "min_setup_quality": float(os.getenv("MIN_SETUP_QUALITY", "0.7")),
                "min_price_movement": float(os.getenv("MIN_PRICE_MOVEMENT", "0.01")),
                "max_position_size": float(os.getenv("MAX_POSITION_SIZE", "1.0")),
            },
            swing_left_window=int(os.getenv("SWING_LEFT_WINDOW", "3")),
            swing_right_window=int(os.getenv("SWING_RIGHT_WINDOW", "3")),
            swing_min_separation=int(os.getenv("SWING_MIN_SEPARATION", "1")),
            min_distance=float(os.getenv("MIN_DISTANCE", "0.0")),
            target_mode=os.getenv("TARGET_MODE", "high_low_reach"),
            target_projection=os.getenv("TARGET_PROJECTION", "c_anchored_ratio"),
            invalidation_rule=os.getenv("INVALIDATION_RULE", "reference"),
            max_candles_active=int(os.getenv("MAX_CANDLES_ACTIVE", "200")),
            allow_overlapping=os.getenv("ALLOW_OVERLAPPING", "true").lower() == "true",
            direction=os.getenv("DIRECTION", "both"),
        )

@dataclass
class BacktestConfig:
    """Configuration for backtesting."""
    initial_capital: float = 100000.0
    transaction_cost: float = 0.0
    slippage: float = 0.0
    spread: float = 0.0
    max_drawdown: float = 0.2
    max_position_size: float = 1.0
    enable_logging: bool = True
    reports_dir: str = "reports"
    charts_dir: str = "charts"

    @classmethod
    def from_env(cls) -> 'BacktestConfig':
        """Create backtest configuration from environment variables."""
        return cls(
            initial_capital=float(os.getenv("INITIAL_CAPITAL", "100000.0")),
            transaction_cost=float(os.getenv("TRANSACTION_COST", "0.0")),
            slippage=float(os.getenv("SLIPPAGE", "0.0")),
            spread=float(os.getenv("SPREAD", "0.0")),
            max_drawdown=float(os.getenv("MAX_DRAWDOWN", "0.2")),
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "1.0")),
            enable_logging=os.getenv("ENABLE_LOGGING", "true").lower() == "true",
            reports_dir=os.getenv("REPORTS_DIR", "reports"),
            charts_dir=os.getenv("CHARTS_DIR", "charts"),
        )

@dataclass
class Config:
    """Main configuration class for the trading bot."""
    environment: str = "development"
    logging: LoggingConfig = field(default_factory=LoggingConfig.from_env)
    data_provider: DataProviderConfig = field(default_factory=DataProviderConfig.from_env)
    strategy: StrategyConfig = field(default_factory=StrategyConfig.from_env)
    backtest: BacktestConfig = field(default_factory=BacktestConfig.from_env)

    @classmethod
    def from_env(cls, environment: Optional[str] = None) -> 'Config':
        """Create configuration from environment variables and .env file.

        Args:
            environment: Environment to load configuration for
            (development, testing, production)

        Returns:
            Config object

        Raises:
            ConfigurationError: If configuration is invalid or missing
        """
        env = environment or os.getenv("ENVIRONMENT", "development")

        # Validate environment
        if env not in ["development", "testing", "production"]:
            raise ConfigurationError(f"Invalid environment: {env}")

        # Load environment-specific .env file
        env_file = f".env.{env}"
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)

        # Load global .env file
        load_dotenv(override=True)

        return cls(environment=env)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "data_provider.csv_file_path")
            default: Default value if key is not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self

        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "environment": self.environment,
            "logging": self.logging.__dict__,
            "data_provider": self.data_provider.__dict__,
            "strategy": self.strategy.__dict__,
            "backtest": self.backtest.__dict__,
        }
