# app/api/dependencies/integrations.py
from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """Return the app-wide Redis client attached during lifespan."""
    return request.app.state.redis.client
