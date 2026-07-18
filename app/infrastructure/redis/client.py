import socket
from redis.asyncio import Redis, ConnectionError
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger()


class RedisClient:
    def __init__(self):

        self._client = Redis.from_url(
            settings.redis.url,
            decode_responses=False
        )
    
    @property
    def client(self):
        """The client property."""
        return self._client

    async def ping(self) -> None:
        try:
            await self._client.ping()  # type: ignore[misc]
        except ConnectionError as e:
            logger.error("Could not connect to Redis: %s", e)
            raise

    async def close(self) -> None:
        await self._client.aclose()
