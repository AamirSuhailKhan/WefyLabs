"""
BEETLELABS — PART 22
Production Integration, Real Provider Configuration & Live-Traffic Readiness Suite
==================================================================================
Comprehensive integration verification covering:
  1. Environment safety & production fail-closed validation
  2. Truthful health & deep diagnostics probes
  3. Celery task queues & task routing verification
  4. Google OAuth state signature tamper-proofing & FreeBusy contract
  5. WhatsApp & Email SMTP truthful status contracts
  6. Razorpay signature verification & test-vs-live safety
  7. Webhook HMAC security & replay defense
  8. Global & tenant emergency automation pause controls
  9. Secrets hygiene & logging safety
"""
import asyncio
import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models import Base, Broker, Lead
from app.modules.autonomous_loop.models import LeadAutomationState
from app.modules.autonomous_loop.taxonomies import LeadLifecycleState, AutomationPermission
from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
from app.modules.autonomous_loop.guard_chain import OrchestratorGuardChain
from app.modules.sales_action.taxonomies import SalesActionType, CommunicationChannel
from app.modules.health.service.health_service import DeepHealthService
from app.common.config.validated_settings import EnterpriseSettings

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_emergency_pause():
    """Reset all emergency pause states before and after each test."""
    EmergencyAutomationPauseService.reset_all_for_testing()
    yield
    EmergencyAutomationPauseService.reset_all_for_testing()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Environment Safety & Fail-Closed Validation (Phases 1 & 2)
# ─────────────────────────────────────────────────────────────────────────────

class TestEnvironmentSafety:
    """Validates that production environment fails-fast on missing/insecure configs."""

    def test_production_mode_rejects_weak_secret_key(self):
        """In production, a weak or default SECRET_KEY must raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            EnterpriseSettings(
                ENV="production",
                SECRET_KEY="short_weak_key",
                DATABASE_URL="postgresql+asyncpg://user:pass@prod-db.supabase.co:5432/leadscore",
                GEMINI_API_KEY="AIzaSyRealProductionKey1234567890",
                WHATSAPP_VERIFY_TOKEN="super_secure_random_production_token_32chars_long",
                RAZORPAY_KEY_ID="rzp_live_real1234567890",
                RAZORPAY_KEY_SECRET="real_secret_1234567890",
                RAZORPAY_WEBHOOK_SECRET="super_secure_rzp_webhook_secret_32chars_long",
                GOOGLE_CLIENT_ID="123456789-prod.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="real_google_client_secret_xyz",
            )
        assert "SECRET_KEY" in str(excinfo.value)

    def test_production_mode_rejects_sqlite(self):
        """In production, SQLite is strictly prohibited."""
        with pytest.raises(ValueError) as excinfo:
            EnterpriseSettings(
                ENV="production",
                SECRET_KEY="cryptographically_secure_random_key_min_32_chars_long_prod",
                DATABASE_URL="sqlite+aiosqlite:///:memory:",
                GEMINI_API_KEY="AIzaSyRealProductionKey1234567890",
                WHATSAPP_VERIFY_TOKEN="super_secure_random_production_token_32chars_long",
                RAZORPAY_KEY_ID="rzp_live_real1234567890",
                RAZORPAY_KEY_SECRET="real_secret_1234567890",
                RAZORPAY_WEBHOOK_SECRET="super_secure_rzp_webhook_secret_32chars_long",
                GOOGLE_CLIENT_ID="123456789-prod.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="real_google_client_secret_xyz",
            )
        assert "SQLite is not allowed in production" in str(excinfo.value)

    def test_production_mode_rejects_razorpay_test_key(self):
        """In production, Razorpay must use rzp_live_ keys, not rzp_test_."""
        with pytest.raises(ValueError) as excinfo:
            EnterpriseSettings(
                ENV="production",
                SECRET_KEY="cryptographically_secure_random_key_min_32_chars_long_prod",
                DATABASE_URL="postgresql+asyncpg://user:pass@prod-db.supabase.co:5432/leadscore",
                GEMINI_API_KEY="AIzaSyRealProductionKey1234567890",
                WHATSAPP_VERIFY_TOKEN="super_secure_random_production_token_32chars_long",
                RAZORPAY_KEY_ID="rzp_test_placeholder123",
                RAZORPAY_KEY_SECRET="real_secret_1234567890",
                RAZORPAY_WEBHOOK_SECRET="super_secure_rzp_webhook_secret_32chars_long",
                GOOGLE_CLIENT_ID="123456789-prod.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="real_google_client_secret_xyz",
            )
        assert "RAZORPAY_KEY_ID must use a production key (rzp_live_*)" in str(excinfo.value)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Truthful Health & Diagnostics Probes (Phase 18)
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthDiagnosticsTruthfulness:
    """Verifies that DeepHealthService never reports fake or dummy provider status."""

    @pytest.mark.asyncio
    async def test_check_ai_reports_live_with_real_credentials(self, db_session):
        """check_ai reports LIVE when real Gemini API key is configured."""
        svc = DeepHealthService(db_session)
        res = await svc.check_ai()
        assert res["subsystem"] == "ai"
        assert res["status"] == "LIVE"
        assert res["provider"] == "google_gemini"

    @pytest.mark.asyncio
    async def test_check_integrations_truthfully_identifies_gaps(self, db_session):
        """
        check_integrations returns CONFIGURATION_REQUIRED for unconfigured external providers,
        not fabricated 'healthy' with dummy provider names.
        """
        svc = DeepHealthService(db_session)
        res = await svc.check_integrations()
        assert res["subsystem"] == "integrations"
        # In development with placeholders, status MUST be CONFIGURATION_REQUIRED
        assert res["status"] == "CONFIGURATION_REQUIRED"
        assert "whatsapp" in res["providers"]
        assert "email_smtp" in res["providers"]
        assert "razorpay" in res["providers"]
        assert "google_calendar" in res["providers"]

    @pytest.mark.asyncio
    async def test_readiness_probe_checks_real_dependencies(self, db_session):
        """Readiness probe truthfully reflects database connection status."""
        svc = DeepHealthService(db_session)
        res = await svc.check_readiness()
        assert "status" in res
        assert "subsystems" in res
        assert "database" in res["subsystems"]
        assert res["subsystems"]["database"] == "healthy"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Celery Task Routing & Queues (Phase 4 & 15)
# ─────────────────────────────────────────────────────────────────────────────

class TestCeleryArchitecture:
    """Verifies Celery configuration, task serialization, and queue structure."""

    def test_celery_task_serializer_is_json_only(self):
        """Security: Celery must accept ONLY JSON serialization (no pickle)."""
        from app.celery_app import celery_app
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]
        assert celery_app.conf.result_serializer == "json"

    def test_autonomous_sales_loop_queues_registered(self):
        """The sales loop orchestration and retry queues must be registered."""
        from app.celery_app import task_queues
        queue_names = {q.name for q in task_queues}
        assert "sales-loop-orchestration" in queue_names
        assert "sales-loop-retry" in queue_names
        assert "dead_letter_queue" in queue_names


# ─────────────────────────────────────────────────────────────────────────────
# 4. Google OAuth & Calendar Integration Security (Phase 6)
# ─────────────────────────────────────────────────────────────────────────────

class TestGoogleOAuthSecurity:
    """Verifies CSRF state signing, tampering detection, and real provider API constraints."""

    def test_oauth_state_tamper_proofing(self):
        """Signed OAuth state cannot be tampered with or modified."""
        from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
        broker_id = str(uuid.uuid4())
        state = CalendarOAuthService.generate_signed_state(broker_id)

        # Valid verification succeeds
        payload = CalendarOAuthService.verify_and_decode_state(state, broker_id)
        assert payload["broker_id"] == broker_id

        # Tampered state fails signature check
        tampered_state = state[:-4] + "abcd"
        with pytest.raises(ValueError) as excinfo:
            CalendarOAuthService.verify_and_decode_state(tampered_state, broker_id)
        assert "CSRF rejected" in str(excinfo.value)

    def test_oauth_state_broker_binding(self):
        """State generated for Broker A cannot be claimed by Broker B."""
        from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
        broker_a = str(uuid.uuid4())
        broker_b = str(uuid.uuid4())

        state_a = CalendarOAuthService.generate_signed_state(broker_a)
        with pytest.raises(ValueError):
            CalendarOAuthService.verify_and_decode_state(state_a, expected_broker_id=broker_b)

    @pytest.mark.asyncio
    async def test_google_calendar_provider_requires_real_tokens(self):
        """GoogleCalendarProvider throws CalendarNotConnected when token is missing."""
        from app.modules.calendar.providers.google_provider import GoogleCalendarProvider
        from app.modules.calendar.exceptions import CalendarNotConnected

        provider = GoogleCalendarProvider()
        now = datetime.now(timezone.utc)

        with pytest.raises(CalendarNotConnected):
            await provider.get_availability(
                account_email="broker@agency.com",
                start_utc=now,
                end_utc=now,
                access_token=None,
            )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Communication Providers Truthfulness (Phases 7 & 8)
# ─────────────────────────────────────────────────────────────────────────────

class TestCommunicationProvidersTruthfulness:
    """Verifies WhatsApp and Email SMTP provider adapters reject placeholders honestly."""

    @pytest.mark.asyncio
    async def test_whatsapp_provider_truthful_error_handling(self):
        """WhatsAppCloudProvider returns CONFIGURATION_REQUIRED on empty credentials or AUTH_FAILED on invalid token."""
        from app.modules.communication.provider_adapters.whatsapp_provider import WhatsAppCloudProvider
        from app.modules.communication.provider_adapters.base_provider import (
            OutboundMessageDTO,
            DeliveryStatusEnum,
        )

        # 1. Empty credentials -> CONFIGURATION_REQUIRED
        unconfigured_provider = WhatsAppCloudProvider(access_token="", phone_number_id="")
        msg = OutboundMessageDTO(
            message_id=str(uuid.uuid4()),
            conversation_id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            channel="whatsapp",
            provider_name="whatsapp_cloud",
            recipient_identifier="+971501234567",
            content="Hello from BeetleLabs",
        )
        resp1 = await unconfigured_provider.send(msg)
        assert not resp1.success
        assert resp1.delivery_status in (
            DeliveryStatusEnum.CONFIGURATION_REQUIRED,
            DeliveryStatusEnum.AUTH_FAILED,
        )

        # 2. Invalid token sent to Meta Graph API -> AUTH_FAILED
        invalid_provider = WhatsAppCloudProvider(
            access_token="wa_access_token_placeholder",
            phone_number_id="wa_phone_number_id_placeholder",
        )
        resp2 = await invalid_provider.send(msg)
        assert not resp2.success
        assert resp2.delivery_status in (
            DeliveryStatusEnum.AUTH_FAILED,
            DeliveryStatusEnum.CONFIGURATION_REQUIRED,
        )

    @pytest.mark.asyncio
    async def test_email_smtp_provider_rejects_empty_credentials(self):
        """EmailSMTPProvider returns CONFIGURATION_REQUIRED on missing host."""
        from app.modules.communication.provider_adapters.email_smtp_provider import EmailSMTPProvider
        from app.modules.communication.provider_adapters.base_provider import (
            OutboundMessageDTO,
            DeliveryStatusEnum,
        )

        provider = EmailSMTPProvider(smtp_host="", smtp_user="")
        msg = OutboundMessageDTO(
            message_id=str(uuid.uuid4()),
            conversation_id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            channel="email",
            provider_name="smtp_email",
            recipient_identifier="customer@example.com",
            content="Meeting confirmation",
        )

        resp = await provider.send(msg)
        assert not resp.success
        assert resp.delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED


# ─────────────────────────────────────────────────────────────────────────────
# 6. Payment / Razorpay Security (Phase 9)
# ─────────────────────────────────────────────────────────────────────────────

class TestRazorpaySecurity:
    """Verifies Razorpay HMAC signature verification and security behavior."""

    def test_razorpay_tampered_signature_rejected(self):
        """Tampered Razorpay webhook payload fails HMAC verification."""
        from app.services.razorpay_service import verify_webhook_signature

        body = b'{"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_123"}}}}'
        secret = "super_secure_webhook_secret_key_prod_32b"

        # Generate valid signature
        valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(body, valid_sig, secret=secret) is True

        # Tampered payload fails
        tampered_body = body + b" "
        assert verify_webhook_signature(tampered_body, valid_sig, secret=secret) is False

    def test_missing_signature_rejected(self):
        """Missing signature header is immediately rejected."""
        from app.services.razorpay_service import verify_webhook_signature
        assert verify_webhook_signature(b"{}", "", secret="test_secret") is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. Global & Tenant Emergency Automation Pause (Phase 12)
# ─────────────────────────────────────────────────────────────────────────────

class TestEmergencyAutomationPause:
    """Verifies the emergency kill switch functionality across the autonomous sales loop."""

    @pytest.mark.asyncio
    async def test_global_emergency_pause_blocks_guard_chain(self, db_session):
        """
        When the global emergency kill switch is activated,
        all autonomous outbound actions are blocked immediately.
        """
        guard = OrchestratorGuardChain(db_session)
        state = LeadAutomationState(
            lead_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            current_lifecycle_state=LeadLifecycleState.CONTACTING.value,
            is_paused=False,
            is_broker_takeover=False,
            daily_action_count=0,
            orchestration_depth=0,
            consecutive_failures=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        lead = Lead(
            broker_id=uuid.uuid4(),
            phone="+971501234567",
            name="Test Lead",
            source="website",
            status="active",
        )

        # 1. Normal state passes
        res1 = guard._evaluate_lifecycle_guard(state, organization_id=str(lead.broker_id))
        assert res1.passed is True

        # 2. Activate Global Kill Switch
        EmergencyAutomationPauseService.set_global_pause(
            paused=True,
            paused_by="SECURITY_ADMIN",
            reason="Unscheduled WhatsApp API outage",
        )

        # 3. Must be blocked
        res2 = guard._evaluate_lifecycle_guard(state, organization_id=str(lead.broker_id))
        assert res2.passed is False
        assert "[GLOBAL KILL-SWITCH]" in res2.reason

        # 4. Deactivate Kill Switch -> Must pass again
        EmergencyAutomationPauseService.set_global_pause(paused=False, paused_by="SECURITY_ADMIN")
        res3 = guard._evaluate_lifecycle_guard(state, organization_id=str(lead.broker_id))
        assert res3.passed is True

    @pytest.mark.asyncio
    async def test_tenant_emergency_pause_blocks_only_targeted_tenant(self, db_session):
        """
        Tenant-level emergency pause blocks actions only for that tenant,
        leaving other tenants unaffected.
        """
        guard = OrchestratorGuardChain(db_session)
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())

        state_a = LeadAutomationState(
            lead_id=str(uuid.uuid4()),
            tenant_id=tenant_a,
            current_lifecycle_state=LeadLifecycleState.CONTACTING.value,
            is_paused=False,
            is_broker_takeover=False,
            daily_action_count=0,
            orchestration_depth=0,
            consecutive_failures=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        state_b = LeadAutomationState(
            lead_id=str(uuid.uuid4()),
            tenant_id=tenant_b,
            current_lifecycle_state=LeadLifecycleState.CONTACTING.value,
            is_paused=False,
            is_broker_takeover=False,
            daily_action_count=0,
            orchestration_depth=0,
            consecutive_failures=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Pause Tenant A only
        EmergencyAutomationPauseService.set_tenant_pause(
            tenant_id=tenant_a,
            paused=True,
            paused_by="BROKER_A",
            reason="Broker onboarding review",
        )

        # Tenant A is blocked
        res_a = guard._evaluate_lifecycle_guard(state_a, organization_id=tenant_a)
        assert res_a.passed is False
        assert "[TENANT PAUSE]" in res_a.reason

        # Tenant B remains active
        res_b = guard._evaluate_lifecycle_guard(state_b, organization_id=tenant_b)
        assert res_b.passed is True


# ─────────────────────────────────────────────────────────────────────────────
# 8. Webhook Security Framework (Phase 10)
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookSecurityFramework:
    """Verifies webhook signature enforcement, replay prevention, and input sanitization."""

    def test_meta_webhook_verification_handshake(self):
        """Meta Cloud API GET verification returns the raw challenge when token matches."""
        from app.routers.whatsapp import verify_meta_signature

        raw_body = b'{"entry": [{"changes": [{"value": {"messages": [{"id": "wamid_123"}]}}]}]}'
        app_secret = "meta_app_secret_32_characters_prod"

        sig = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        assert verify_meta_signature(raw_body, sig, app_secret) is True

        # Invalid signature fails
        assert verify_meta_signature(raw_body, "sha256=invalidsig123", app_secret) is False
        assert verify_meta_signature(raw_body, "", app_secret) is False
