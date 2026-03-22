"""
Event middleware — Kafka producer/consumer stubs + Redis cache/pubsub.
Provides async event streaming for CDA/DDA transaction lifecycle events.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Events track CDA mint/burn/transfer operations for reconciliation and compliance.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Coroutine

from pydantic import BaseModel, Field

from offchain.config import get_settings
from offchain.services import audit

logger = logging.getLogger("cari.middleware")


class Event(BaseModel):
    """Domain event flowing through the middleware."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    topic: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str = ""
    source: str = "cari-orchestrator"


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class StubKafkaProducer:
    """In-memory Kafka producer stub for dev/test.

    In production, replace with aiokafka.AIOKafkaProducer connected
    to the bank's Kafka cluster (Confluent Cloud / MSK).
    """

    def __init__(self) -> None:
        self._messages: dict[str, list[Event]] = defaultdict(list)
        self._connected = False

    async def connect(self) -> None:
        settings = get_settings()
        logger.info("Kafka producer connecting to %s (stub)", settings.kafka_bootstrap_servers)
        self._connected = True

    async def send(self, topic: str, event: Event) -> None:
        if not self._connected:
            await self.connect()
        self._messages[topic].append(event)
        logger.debug("Kafka SEND -> %s: %s (%s)", topic, event.event_type, event.event_id[:8])
        await audit.record(
            actor="KAFKA_PRODUCER",
            action="send",
            resource=f"topic:{topic}",
            details={
                "event_type": event.event_type,
                "event_id": event.event_id,
                "correlation_id": event.correlation_id,
            },
        )

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Kafka producer disconnected (stub)")

    def get_messages(self, topic: str) -> list[Event]:
        """Dev/test helper: return all messages sent to a topic."""
        return list(self._messages.get(topic, []))


class StubKafkaConsumer:
    """In-memory Kafka consumer stub for dev/test.

    In production, replace with aiokafka.AIOKafkaConsumer.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._connected = False

    async def connect(self) -> None:
        settings = get_settings()
        logger.info(
            "Kafka consumer connecting to %s, group=%s (stub)",
            settings.kafka_bootstrap_servers,
            settings.kafka_consumer_group,
        )
        self._connected = True

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register an event handler for a topic."""
        self._handlers[topic].append(handler)
        logger.info("Subscribed handler to topic: %s", topic)

    async def process_event(self, event: Event) -> None:
        """Manually dispatch an event to handlers (for testing)."""
        handlers = self._handlers.get(event.topic, [])
        for handler in handlers:
            await handler(event)
        logger.debug(
            "Dispatched event %s to %d handlers on %s",
            event.event_id[:8], len(handlers), event.topic,
        )

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Kafka consumer disconnected (stub)")


class StubRedisCache:
    """In-memory Redis stub for caching and monitoring.

    In production, replace with aioredis connected to Redis/ElastiCache.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, datetime] = {}
        self._connected = False

    async def connect(self) -> None:
        settings = get_settings()
        logger.info("Redis connecting to %s (stub)", settings.redis_url)
        self._connected = True

    async def get(self, key: str) -> str | None:
        val = self._store.get(key)
        if val is not None:
            logger.debug("Redis GET %s -> hit", key)
        return val

    async def set(self, key: str, value: str, ttl_seconds: int = 0) -> None:
        self._store[key] = value
        if ttl_seconds > 0:
            from datetime import timedelta
            self._ttls[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        logger.debug("Redis SET %s (ttl=%ds)", key, ttl_seconds)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._ttls.pop(key, None)

    async def get_json(self, key: str) -> dict | None:
        val = await self.get(key)
        if val is not None:
            return json.loads(val)
        return None

    async def set_json(self, key: str, data: dict, ttl_seconds: int = 0) -> None:
        await self.set(key, json.dumps(data, default=str), ttl_seconds)

    async def increment(self, key: str) -> int:
        """Atomic increment (rate limiting / counters)."""
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Redis disconnected (stub)")

    @property
    def connected(self) -> bool:
        return self._connected


class EventMiddleware:
    """Unified event middleware combining Kafka + Redis."""

    def __init__(self) -> None:
        self.producer = StubKafkaProducer()
        self.consumer = StubKafkaConsumer()
        self.cache = StubRedisCache()

    async def startup(self) -> None:
        """Initialize all middleware connections."""
        await self.producer.connect()
        await self.consumer.connect()
        await self.cache.connect()
        logger.info("Event middleware started")

    async def shutdown(self) -> None:
        """Gracefully disconnect all middleware."""
        await self.producer.disconnect()
        await self.consumer.disconnect()
        await self.cache.disconnect()
        logger.info("Event middleware shut down")

    async def publish(
        self,
        *,
        topic: str,
        event_type: str,
        payload: dict[str, Any],
        correlation_id: str = "",
    ) -> Event:
        """Publish a domain event to Kafka and cache latest state in Redis."""
        event = Event(
            topic=topic,
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
        )
        await self.producer.send(topic, event)
        # Cache latest event per correlation_id for quick lookups
        if correlation_id:
            await self.cache.set_json(
                f"event:{correlation_id}:latest",
                event.model_dump(mode="json"),
                ttl_seconds=3600,
            )
        return event

    async def get_cached_status(self, correlation_id: str) -> dict | None:
        """Retrieve the latest cached event for a given correlation_id."""
        return await self.cache.get_json(f"event:{correlation_id}:latest")


_middleware: EventMiddleware | None = None


def get_event_middleware() -> EventMiddleware:
    global _middleware
    if _middleware is None:
        _middleware = EventMiddleware()
    return _middleware
