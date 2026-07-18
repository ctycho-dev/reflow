from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from app.middleware.logging import AccessLogMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.database.connection import DatabaseManager
from app.api.v1 import router as api_router
from app.infrastructure.redis.client import RedisClient
from app.exceptions.exceptions import add_exception_handlers
from app.core.logger import (
    get_logger,
    setup_logging
)
from app.middleware.rate_limiter import (
    limiter,
    rate_limit_exceeded_handler
)
from app.middleware.cors import add_cors_middleware
from app.core.config import settings


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI application lifecycle."""
    try:
        setup_logging()
        db_manager = DatabaseManager(settings.postgres)
        db_manager.init_engine(application_name="reflow-api")
        app.state.db = db_manager
        app.state.redis = RedisClient()
        await app.state.redis.ping()
        logger.info("Application startup complete")
        yield
    except Exception as e:
        logger.error("lifespan error: %s", e)
        raise
    finally:
        logger.info("Application shutting down")
        await db_manager.close()
        await app.state.redis.close()


app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    rate_limit_exceeded_handler
)


add_cors_middleware(app)

add_exception_handlers(app)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AccessLogMiddleware)

app.include_router(api_router)


@app.get("/health")
@limiter.limit("5/minute")
async def health_check(request: Request):
    return {"status": "healthy"}
