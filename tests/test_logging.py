"""Logging configuration tests."""

import logging

from tradingbot.config import LoggingConfig
from tradingbot.logging import configure_root_logger, get_logger


def _close_logger(logger):
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
    logger.handlers = []


def test_get_logger_writes_to_configured_file(tmp_path):
    log_file = tmp_path / "test.log"
    config = LoggingConfig(level="DEBUG", file=str(log_file))
    logger = get_logger("tradingbot.tests.file", config)
    logger.debug("hello-file")
    _close_logger(logger)
    assert "hello-file" in log_file.read_text(encoding="utf-8")


def test_get_logger_defaults_to_caller_name():
    logger = get_logger()
    assert logger.name
    _close_logger(logger)


def test_get_logger_is_cached():
    first = get_logger("tradingbot.tests.cached")
    second = get_logger("tradingbot.tests.cached")
    assert first is second
    _close_logger(first)


def test_configure_root_logger(tmp_path):
    log_file = tmp_path / "root.log"
    config = LoggingConfig(level="INFO", file=str(log_file))
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    try:
        configure_root_logger(config=config)
        root.info("root-message")
        for handler in list(root.handlers):
            handler.flush()
            handler.close()
        assert "root-message" in log_file.read_text(encoding="utf-8")
    finally:
        root.handlers = previous_handlers
        root.setLevel(previous_level)
