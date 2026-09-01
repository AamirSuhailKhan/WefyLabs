"""
PART 6 — Enterprise Infrastructure Architecture Tests
======================================================
Tests for: Audit, Notifications, Feature Flags, Settings,
API Keys, Integration Framework, Event History, System Health.
"""
import pytest
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.infrastructure.events.event_bus import (
    DomainEvent, StandardDomainEvents, ActorContext, DomainEventBus
)
from app.infrastructure.cache.query_cache import AsyncQueryCacheService, CacheTTL
from app.modules.notifications.channels.notification_channels import (
    NotificationPayload, InAppChannelAdapter, EmailChannelAdapter,
    WhatsAppChannelAdapter, TelegramChannelAdapter, SMSChannelAdapter
)
from app.modules.integrations.interfaces.provider_interface import (
    get_provider, INTEGRATION_PROVIDER_REGISTRY, GoogleCalendarProvider, HubSpotProvider
)
from app.common.response import create_success_response, create_error_response


# ─── Audit Module Tests ────────────────────────────────────────────────────────

def test_audit_dto_construction():
    from app.modules.audit.dto.audit_dto import AuditCreateDTO
    dto = AuditCreateDTO(
        action="lead.create",
        resource_type="lead",
        resource_id="lead-001",
        actor_type="user",
        ip_address="127.0.0.1",
        request_id="req_abc123",
    )
    assert dto.action == "lead.create"
    assert dto.resource_type == "lead"
    assert dto.request_id == "req_abc123"


# ─── Notification Channel Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_notification_channels_send():
    """All channel adapters must implement send() and return True."""
    payload = NotificationPayload(
        recipient_id="broker-001",
        title="Test Notification",
        body="Hello World",
        channel="in_app",
    )
    channels = [
        InAppChannelAdapter(),
        EmailChannelAdapter(),
        WhatsAppChannelAdapter(),
        TelegramChannelAdapter(),
        SMSChannelAdapter(),
    ]
    for channel in channels:
        result = await channel.send(payload)
        assert result is True, f"Channel {channel.channel_name} did not return True"


def test_notification_dto_defaults():
    from app.modules.notifications.dto.notification_dto import NotificationSendDTO
    dto = NotificationSendDTO(
        recipient_id="broker-001",
        title="Lead Assigned",
        channels=["in_app", "email"],
    )
    assert dto.priority == "normal"
    assert "in_app" in dto.channels
    assert "email" in dto.channels


# ─── Feature Flag Tests ────────────────────────────────────────────────────────

def test_feature_flag_cache_isolation():
    """Feature flag cache keys are properly scoped."""
    from app.modules.feature_flags.service.feature_flag_service import FeatureFlagService

    # Test cache key generation via direct method call (no DB needed)
    class _Svc(FeatureFlagService):
        def __init__(self): pass  # skip DB init

    svc = _Svc()
    key1 = svc._cache_key("ai_scoring", "global", None)
    key2 = svc._cache_key("ai_scoring", "organization", "org-001")
    key3 = svc._cache_key("ai_scoring", "user", "user-001")

    assert key1 != key2
    assert key2 != key3
    assert "global" in key1
    assert "org-001" in key2


# ─── Settings Tests ────────────────────────────────────────────────────────────

def test_settings_cache_key_uniqueness():
    """Settings cache keys must differ by scope and scope_id."""
    from app.modules.settings.service.settings_service import SettingsService

    class MockSettingsService(SettingsService):
        def __init__(self):
            pass

    svc = MockSettingsService()
    k1 = svc._cache_key("timezone", "global", None)
    k2 = svc._cache_key("timezone", "organization", "org-001")
    k3 = svc._cache_key("timezone", "user", "user-abc")

    assert k1 != k2 != k3


def test_settings_dto_validation():
    from app.modules.settings.dto.settings_dto import SettingUpsertDTO
    dto = SettingUpsertDTO(key="timezone", value="Asia/Kolkata", scope="organization")
    assert dto.key == "timezone"
    assert dto.value == "Asia/Kolkata"
    assert dto.is_sensitive is False


# ─── API Key Tests ─────────────────────────────────────────────────────────────

def test_api_key_hash_is_deterministic():
    """SHA-256 hash of the same key always yields same digest."""
    raw_key = "bl_test_key_12345"
    h1 = hashlib.sha256(raw_key.encode()).hexdigest()
    h2 = hashlib.sha256(raw_key.encode()).hexdigest()
    assert h1 == h2
    assert len(h1) == 64


def test_api_key_prefix_format():
    """API keys must start with 'bl_' prefix."""
    from app.modules.api_keys.service.api_key_service import ApiKeyService

    class MockApiKeyService(ApiKeyService):
        def __init__(self):
            pass

    svc = MockApiKeyService()
    raw_key, key_hash, prefix = svc._generate_key()

    assert raw_key.startswith("bl_")
    assert len(key_hash) == 64
    assert prefix == raw_key[:10]


# ─── Integration Framework Tests ───────────────────────────────────────────────

def test_integration_registry_contains_expected_providers():
    """Provider registry must include core integrations."""
    assert "google_calendar" in INTEGRATION_PROVIDER_REGISTRY
    assert "hubspot" in INTEGRATION_PROVIDER_REGISTRY
    assert "stripe" in INTEGRATION_PROVIDER_REGISTRY


def test_get_provider_returns_correct_adapter():
    provider = get_provider("google_calendar")
    assert isinstance(provider, GoogleCalendarProvider)
    assert provider.provider_name == "google_calendar"


def test_get_provider_returns_none_for_unknown():
    provider = get_provider("unknown_provider_xyz")
    assert provider is None


@pytest.mark.asyncio
async def test_google_calendar_provider_connect():
    provider = GoogleCalendarProvider()
    result = await provider.connect(credentials={"token": "test"})
    assert result is True


@pytest.mark.asyncio
async def test_hubspot_provider_sync():
    provider = HubSpotProvider()
    result = await provider.sync("integration-id-001")
    assert "synced_contacts" in result


# ─── Event History Tests ────────────────────────────────────────────────────────

def test_event_history_dto_fields():
    """Event history records must carry all required fields."""
    event = DomainEvent(
        event_type=StandardDomainEvents.LEAD_CREATED,
        organization_id="org-001",
        actor=ActorContext(user_id="user-001", actor_type="user"),
        payload={"lead_id": "lead-123"},
    )
    assert event.event_id.startswith("evt_")
    assert event.version == "1.0"
    assert event.actor.actor_type == "user"
    assert "lead_id" in event.payload


# ─── System Health Tests ────────────────────────────────────────────────────────

def test_health_service_check_structure():
    """Deep health check response must include all required keys."""
    from app.modules.system_health.service.health_service import SystemHealthService

    class MockHealthService(SystemHealthService):
        def __init__(self):
            pass
        async def _check_db(self):
            return True
        async def _check_redis(self):
            return True
        def _check_queues(self):
            return True

    import asyncio
    svc = MockHealthService()
    result = asyncio.run(svc.deep_check())
    assert "status" in result
    assert "checks" in result
    assert "latency_ms" in result
    assert "version" in result
    assert result["status"] == "healthy"
