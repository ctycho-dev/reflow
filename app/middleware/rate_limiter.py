# app/middleware/rate_limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import (
    Request,
    status
)
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import get_logger


logger = get_logger()


# Create a custom key function if needed (e.g., user-based limits)
def rate_limit_key(request: Request):

    wallet = getattr(request.state, "wallet", None)
    if wallet:
        return f"wallet:{wallet}"
    return get_remote_address(request)


# Initialize limiter with Redis storage
limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["200/minute", "20/second"],
    storage_uri=settings.redis.url,
)


async def rate_limit_exceeded_handler(request: Request, exc: Exception):
    """
    Custom handler for RateLimitExceeded exceptions.
    Safely ignores non-RateLimitExceeded exceptions.
    """
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "Rate limit exceeded. Please try again later."},
        )

    logger.warning(
        "Unexpected exception passed to rate_limit_exceeded_handler: %s",
        exc,
        exc_info=True
    )
    raise exc
