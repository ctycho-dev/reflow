# app/core/logger.py
import sys
import logging
from pythonjsonlogger.json import JsonFormatter

from app.core.config import settings


def setup_logging() -> None:
    """Initialize logging based on environment and settings."""
    log_level = settings.app.log_level.upper()

    json_formatter = JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(user_email)s %(module)s %(funcName)s %(lineno)d',
        datefmt='%Y-%m-%dT%H:%M:%S%z'
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(json_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    app_logger = logging.getLogger("app")
    app_logger.setLevel(log_level)
    app_logger.propagate = False
    app_logger.handlers.clear()
    app_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get logger instance. Call setup_logging() first in app startup.

    Usage:
        logger = get_logger(__name__)
        logger.info("Message")
    """
    if name is None:
        name = "app"
    return logging.getLogger(name)