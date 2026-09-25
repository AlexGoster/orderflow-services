"""Шина событий: интерфейс + in-memory реализация + Redis pub/sub."""

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub, Redis

logger = logging.getLogger(__name__)

EventHandler = Callable[[Mapping[str, Any]], Awaitable[None]]


class EventBus(Protocol):
    """Минимальный контракт шины: публикация и подписка на топик."""

    async def publish(self, topic: str, payload: Mapping[str, Any]) -> None: ...

    async def subscribe(self, topic: str, handler: EventHandler) -> None: ...

    async def close(self) -> None: ...


class InMemoryEventBus:
    """Бус внутри одного процесса: подписчики вызываются синхронно в publish.

    Использается в тестах и при локальном запуске без Redis — публикация
    детерминирована: когда POST /orders вернулся, уведомление уже создано.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self.published: list[tuple[str, Mapping[str, Any]]] = []

    async def publish(self, topic: str, payload: Mapping[str, Any]) -> None:
        self.published.append((topic, payload))
        for handler in self._subscribers.get(topic, []):
            await handler(payload)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    async def close(self) -> None:
        self._subscribers.clear()


class RedisEventBus:
    """Prod-реализация на Redis pub/sub: один канал на топик."""

    def __init__(self, client: Redis, *, channel_prefix: str = "orderflow") -> None:
        self._client = client
        self._channel_prefix = channel_prefix
        self._tasks: list[asyncio.Task[None]] = []
        self._pubsubs: list[PubSub] = []

    def _channel(self, topic: str) -> str:
        return f"{self._channel_prefix}:{topic}"

    async def publish(self, topic: str, payload: Mapping[str, Any]) -> None:
        message = json.dumps(payload, default=str)
        await self._client.publish(self._channel(topic), message)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(self._channel(topic))
        self._pubsubs.append(pubsub)
        self._tasks.append(asyncio.create_task(self._consume(pubsub, handler)))

    async def _consume(self, pubsub: PubSub, handler: EventHandler) -> None:
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                text = data.decode() if isinstance(data, bytes | bytearray) else str(data)
                await handler(json.loads(text))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("event consumer failed")

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        for pubsub in self._pubsubs:
            await pubsub.aclose()  # type: ignore[no-untyped-call]  # redis-py без аннотаций
        self._pubsubs.clear()
        await self._client.aclose()


def create_event_bus(*, backend: str, redis_url: str) -> EventBus:
    """Фабрика по конфигурации: ``memory`` для дев-окружения, ``redis`` для прода."""
    if backend == "redis":
        return RedisEventBus(aioredis.from_url(redis_url))
    return InMemoryEventBus()
