"""
Logging configuration and utilities for the trading bot.

This module provides configurable logging with support for different levels
and output formats.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional, Union

from .config import LoggingConfig

# Global logger registry
_loggers: Dict[str, logging.Logger] = {}

HandlerType = Union[RotatingFileHandler, logging.StreamHandler]


def get_logger(name: Optional[str] = None, config: Optional[LoggingConfig] = None) -> logging.Logger:
    """Get a logger instance with the specified name and configuration.

    Args:
        name: Logger name (defaults to the calling module's name if None)
        config: Logging configuration (defaults to environment-based config)

    Returns:
        Configured logger instance
    """
    if name is None:
        # Use the caller's module name for the logger
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_module = frame.f_back.f_globals.get('__name__', 'trading_bot')
        else:
            caller_module = 'trading_bot'
        name = caller_module

    # Check if logger already exists
    if name in _loggers:
        return _loggers[name]

    # Create new logger
    logger = logging.getLogger(name)

    # Use default config if none provided
    if config is None:
        config = LoggingConfig.from_env()

    # Set up handler
    if config.file:
        handler: HandlerType = RotatingFileHandler(
            config.file,
            maxBytes=config.max_size,
            backupCount=config.backup_count
        )
    else:
        handler = logging.StreamHandler(sys.stdout)

    # Set up formatter
    formatter = logging.Formatter(config.format)
    handler.setFormatter(formatter)

    # Configure logger
    logger.setLevel(getattr(logging, config.level.upper()))
    logger.addHandler(handler)

    # Remove any existing handlers to prevent duplicate logs
    logger.handlers = [handler]

    # Store logger in registry
    _loggers[name] = logger

    return logger


def configure_root_logger(level: str = "INFO", config: Optional[LoggingConfig] = None) -> None:
    """Configure the root logger for the application.

    Args:
        level: Root logging level
        config: Logging configuration
    """
    if config is None:
        config = LoggingConfig.from_env()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add handler based on configuration
    if config.file:
        root_handler: HandlerType = RotatingFileHandler(
            config.file,
            maxBytes=config.max_size,
            backupCount=config.backup_count
        )
    else:
        root_handler = logging.StreamHandler(sys.stdout)

    # Set up formatter
    formatter = logging.Formatter(config.format)
    root_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(root_handler)
