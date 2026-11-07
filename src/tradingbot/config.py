"""
Runtime configuration for the research/backtesting CLI.

The *strategy/backtest* configuration has exactly one source of truth:
``tradingbot.backtesting.backtest_engine.BacktestConfig`` (built by the CLI
flags and by the web UI's Pydantic schema). This module intentionally does not
duplicate those fields. It only holds environment-level settings that are not
part of a run: the environment label and logging configuration.
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
    def from_env(cls) -> "LoggingConfig":
        """Create logging configuration from environment variables."""
        return cls(
            level=os.getenv("LOG_LEVEL", "INFO"),
            file=os.getenv("LOG_FILE"),
            max_size=int(os.getenv("LOG_MAX_SIZE", "10485760")),
            backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
        )


@dataclass
class Config:
    """Environment-level configuration (no strategy parameters)."""

    environment: str = "development"
    logging: LoggingConfig = field(default_factory=LoggingConfig.from_env)

    @classmethod
    def from_env(cls, environment: Optional[str] = None) -> "Config":
        """Create configuration from environment variables and .env files.

        Raises:
            ConfigurationError: If the environment label is invalid.
        """
        env = environment or os.getenv("ENVIRONMENT", "development")
        if env not in ["development", "testing", "production"]:
            raise ConfigurationError(f"Invalid environment: {env}")

        # Load environment-specific .env file, then the global .env file.
        env_file = f".env.{env}"
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
        load_dotenv(override=True)

        return cls(environment=env)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        value: Any = self
        for part in key.split("."):
            if hasattr(value, part):
                value = getattr(value, part)
            elif isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary."""
        return {
            "environment": self.environment,
            "logging": self.logging.__dict__,
        }
