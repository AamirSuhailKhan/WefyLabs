import pytest
import uuid
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.infrastructure.events.event_bus import (
    DomainEventBus, DomainEvent, StandardDomainEvents, ActorContext
)
from app.infrastructure.cache.query_cache import AsyncQueryCacheService, CacheTTL
from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService
from app.modules.webhooks.dto.webhook_dto import WebhookPayloadDTO
from app.common.response import create_success_response, create_error_response

@pytest.mark.asyncio
async def test_domain_event_bus_publishing_and_subscribers():
    bus = DomainEventBus()
    received_events = []

    async def sample_handler(event: DomainEvent):
        received_events.append(event)

    bus.subscribe(StandardDomainEvents.LEAD_CREATED, sample_handler)

    test_event = DomainEvent(
        event_type=StandardDomainEvents.LEAD_CREATED,
        organization_id="org_test_123",
        actor=ActorContext(user_id="user_123", role="broker", actor_type="user"),
        payload={"lead_id": "lead_999", "name": "John Doe"}
    )

    await bus.publish(test_event)

    assert len(received_events) >= 1
    matched = [e for e in received_events if e.event_id == test_event.event_id]
    assert len(matched) == 1
    assert matched[0].payload["name"] == "John Doe"

def test_cache_service_tag_invalidation():
    AsyncQueryCacheService.clear()
    AsyncQueryCacheService.set("key_1", {"data": "val1"}, ttl_seconds=60, tags=["org_1"])
    AsyncQueryCacheService.set("key_2", {"data": "val2"}, ttl_seconds=60, tags=["org_1"])
    AsyncQueryCacheService.set("key_3", {"data": "val3"}, ttl_seconds=60, tags=["org_2"])

    assert AsyncQueryCacheService.get("key_1") == {"data": "val1"}
    assert AsyncQueryCacheService.get("key_3") == {"data": "val3"}

    # Invalidate org_1 tag
    AsyncQueryCacheService.invalidate_tag("org_1")

    assert AsyncQueryCacheService.get("key_1") is None
    assert AsyncQueryCacheService.get("key_2") is None
    assert AsyncQueryCacheService.get("key_3") == {"data": "val3"}

@pytest.mark.asyncio
async def test_webhook_engine_signature_and_replay():
    service = GenericWebhookEngineService(secrets={"whatsapp": "test_secret_123"})
    
    # Test valid replay timestamp
    assert service.check_replay_attack(str(time.time())) is True
    # Test expired replay timestamp
    assert service.check_replay_attack(str(time.time() - 1000)) is False

    dto = WebhookPayloadDTO(
        provider="whatsapp",
        event_type="message_received",
        payload={"phone": "+1234567890", "message": "Hi"},
        timestamp=str(time.time())
    )

    response = await service.ingest_webhook(dto, b'{"message": "Hi"}', {"x-organization-id": "org_test"})
    assert response.received is True
    assert response.status == "processed"

def test_api_envelope_formatting():
    success_resp = create_success_response(data={"id": 123}, meta={"page": 1}, request_id="req_001")
    assert success_resp.success is True
    assert success_resp.data == {"id": 123}
    assert success_resp.requestId == "req_001"

    error_resp = create_error_response(code="NOT_FOUND", message="Item missing", request_id="req_002")
    assert error_resp.success is False
    assert error_resp.error.code == "NOT_FOUND"
    assert error_resp.requestId == "req_002"
