"""Environment-level configuration tests (logging/environment only)."""

import pytest

from tradingbot.config import Config, LoggingConfig
from tradingbot.exceptions import ConfigurationError


def test_logging_config_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FILE", "logs/test.log")
    monkeypatch.setenv("LOG_MAX_SIZE", "1234")
    monkeypatch.setenv("LOG_BACKUP_COUNT", "2")
    config = LoggingConfig.from_env()
    assert config.level == "DEBUG"
    assert config.file == "logs/test.log"
    assert config.max_size == 1234
    assert config.backup_count == 2


def test_config_from_env_get_and_to_dict(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "testing")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    config = Config.from_env()
    assert config.environment == "testing"
    assert config.logging.level == "WARNING"
    assert config.get("logging.level") == "WARNING"
    assert config.get("logging.missing", "fallback") == "fallback"
    assert config.get("does.not.exist") is None
    data = config.to_dict()
    assert data["environment"] == "testing"
    assert data["logging"]["level"] == "WARNING"


def test_config_rejects_invalid_environment():
    with pytest.raises(ConfigurationError, match="Invalid environment"):
        Config.from_env("staging")
