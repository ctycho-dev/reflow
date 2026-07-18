# app/core/decorators.py
import time
import logging
import functools
import inspect

logger = logging.getLogger("app.timing")


def log_timing(message: str | None = None):
    """
    Decorator that logs execution time for sync/async functions.

    Usage:
        @log_timing()
        @log_timing("Get all chats")
    """

    def decorator(func):
        is_coroutine = inspect.iscoroutinefunction(func)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                logger.info(
                    message or f"{func.__name__}_duration",
                    extra={
                        "func": func.__qualname__,
                        "duration_s": round(duration, 3),
                    },
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                logger.info(
                    message or f"{func.__name__}_duration",
                    extra={
                        "func": func.__qualname__,
                        "duration_s": round(duration, 3),
                        "duration_ms": int(duration * 1000),
                    },
                )

        return async_wrapper if is_coroutine else sync_wrapper

    return decorator