"""
Tests for event middleware (Kafka + Redis stubs).
"""

from __future__ import annotations

import pytest

from middleware.events import EventMiddleware, StubKafkaConsumer, StubRedisCache
from offchain.services import audit


class TestKafkaStubs:
    """Tests for the Kafka producer/consumer stubs."""

    @pytest.mark.asyncio
    async def test_publish_and_retrieve(self):
        audit.clear_log()
        mw = EventMiddleware()
        await mw.startup()

        event = await mw.publish(
            topic="cari.transactions",
            event_type="MINT_COMPLETED",
            payload={"amount": 1000},
            correlation_id="test-123",
        )
        assert event.event_type == "MINT_COMPLETED"

        messages = mw.producer.get_messages("cari.transactions")
        assert len(messages) == 1
        assert messages[0].event_id == event.event_id

        await mw.shutdown()

    @pytest.mark.asyncio
    async def test_consumer_dispatch(self):
        audit.clear_log()
        consumer = StubKafkaConsumer()
        await consumer.connect()

        received = []

        async def handler(event):
            received.append(event)

        consumer.subscribe("test.topic", handler)

        from middleware.events import Event
        test_event = Event(topic="test.topic", event_type="TEST", payload={"x": 1})
        await consumer.process_event(test_event)

        assert len(received) == 1
        assert received[0].event_type == "TEST"


class TestRedisStub:
    """Tests for the Redis cache stub."""

    @pytest.mark.asyncio
    async def test_set_get(self):
        cache = StubRedisCache()
        await cache.connect()

        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing(self):
        cache = StubRedisCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_operations(self):
        cache = StubRedisCache()
        await cache.set_json("data", {"foo": "bar", "num": 42})
        result = await cache.get_json("data")
        assert result == {"foo": "bar", "num": 42}

    @pytest.mark.asyncio
    async def test_increment(self):
        cache = StubRedisCache()
        val1 = await cache.increment("counter")
        val2 = await cache.increment("counter")
        assert val1 == 1
        assert val2 == 2

    @pytest.mark.asyncio
    async def test_delete(self):
        cache = StubRedisCache()
        await cache.set("to_delete", "exists")
        await cache.delete("to_delete")
        assert await cache.get("to_delete") is None


class TestEventMiddleware:
    """Tests for the unified event middleware."""

    @pytest.mark.asyncio
    async def test_cached_status(self):
        audit.clear_log()
        mw = EventMiddleware()
        await mw.startup()

        await mw.publish(
            topic="test",
            event_type="STATUS_UPDATE",
            payload={"status": "confirmed"},
            correlation_id="corr-abc",
        )

        cached = await mw.get_cached_status("corr-abc")
        assert cached is not None
        assert cached["event_type"] == "STATUS_UPDATE"

        await mw.shutdown()
