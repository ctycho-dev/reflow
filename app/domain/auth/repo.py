# app/domain/auth/repository.py
from redis.asyncio import Redis

from app.exceptions.exceptions import DatabaseError


NONCE_KEY_PREFIX = "siwe:nonce:"


def _key(address: str) -> str:
    return f"{NONCE_KEY_PREFIX}{address.lower()}"


class AuthRepository:
    """Stateless. Redis client passed per-method."""

    async def store_nonce(
        self,
        redis: Redis,
        *,
        address: str,
        nonce: str,
        ttl_seconds: int,
    ) -> None:
        try:
            await redis.set(_key(address), nonce, ex=ttl_seconds)
        except Exception as e:
            raise DatabaseError(f"Failed to store nonce for {address}: {e}") from e

    async def consume_nonce(
        self,
        redis: Redis,
        *,
        address: str,
    ) -> str | None:
        """
        Atomic get-and-delete. Single-use enforcement: two concurrent calls
        can't both return the same value — exactly one gets the nonce.
        """
        try:
            result = await redis.getdel(_key(address))
        except Exception as e:
            raise DatabaseError(f"Failed to consume nonce for {address}: {e}") from e
        if result is None:
            return None
        return result.decode() if isinstance(result, bytes) else result
