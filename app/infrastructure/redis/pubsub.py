# app/infrastructure/redis/pubsub.py
from redis.asyncio import Redis
from typing import AsyncGenerator


class RedisPubSub:
    def __init__(self, client: Redis, channel: str, object_id: str, client_id: str):
        self._client = client
        self._channel = f"{channel}:{object_id}"
        self._client_id = client_id
        self._pubsub = None

    async def publish(self, message: str):
        await self._client.publish(self._channel, message)

    async def subscribe(self):
        self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)
        await self._pubsub.subscribe(self._channel)

    async def unsubscribe(self):
        if self._pubsub:
            await self._pubsub.unsubscribe(self._channel)
            await self._pubsub.close()

    async def listen(self) -> AsyncGenerator[str, None]:
        if not self._pubsub:
            raise RuntimeError("You must call subscribe() before listen()")

        async for message in self._pubsub.listen():
            if message["type"] == "message":
                yield message["data"].decode()
