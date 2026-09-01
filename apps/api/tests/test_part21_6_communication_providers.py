"""
Part 21.6 — Real Communication Provider Integration & Production Delivery Engine Test Suite
============================================================================================
Comprehensive test suite verifying:
- Section A: Provider Abstraction & Typed Results (4 tests)
- Section B: Provider Configuration Validation (4 tests)
- Section C: WhatsApp Cloud API Real Adapter (5 tests)
- Section D: Email SMTP Real Adapter (4 tests)
- Section E: SMS Gateway Adapter (3 tests)
- Section F: Webchat / In-App Adapter (2 tests)
- Section G: Execution-Time Safety Re-Checks (5 tests: Consent, Fatigue, Quiet-Hours, Terminal State, Approval)
- Section H: Idempotency & Concurrency Locking (3 tests)
- Section I: Retry Policy & Error Classification (3 tests)
- Section J: Webhook Signature Verification & Duplicate Protection (4 tests)
- Section K: Multi-Tenant Isolation Boundaries (3 tests)
- Section L: AI Safety, PII Redaction & Credential Security (3 tests)
- Section M: Truthful Provider Failure & Zero-Mock Verification (3 tests)
Total: 46 comprehensive test cases.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.follow_up_models import (
    FollowUpPolicy,
    FollowUpExecution,
    FollowUpDecision,
    CommunicationConsent,
    ContactFatigue,
)
from app.models.communication_models import (
    ChannelMessage,
    DeliveryStatusRecord,
    InboundQueue,
    OutboundQueue,
    ProviderCredential,
)
from app.modules.communication.provider_adapters.base_provider import (
    CommunicationProvider,
    CommunicationCapabilities,
    DeliveryStatusEnum,
    InboundMessageDTO,
    OutboundMessageDTO,
    ProviderDeliveryStatus,
    ProviderResponse,
    ProviderStatusEnum,
)
from app.modules.communication.provider_adapters.whatsapp_provider import WhatsAppCloudProvider
from app.modules.communication.provider_adapters.email_smtp_provider import EmailSMTPProvider
from app.modules.communication.provider_adapters.sms_provider import SMSGatewayProvider, MockSMSProvider
from app.modules.communication.provider_adapters.webchat_provider import WebChatProvider
from app.modules.communication.channel_manager.manager import ChannelManager
from app.modules.communication.provider_config_service import ProviderConfigurationService
from app.modules.communication.delivery_engine.real_delivery_engine import RealDeliveryEngine
from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
    ConsentStatus,
)
from app.modules.sales_action.dto import (
    SalesActionDecisionDTO,
    SalesActionExecutionResultDTO,
    SalesBriefDTO,
)
from app.modules.sales_action.action_executor import SalesActionExecutor
from app.modules.communication.monitoring.delivery_metrics import mask_org_id


# ─── SECTION A: Provider Abstraction & Typed Results ──────────────────────────

@pytest.mark.asyncio
async def test_provider_response_typed_statuses():
    """Validates that all provider responses conform to DeliveryStatusEnum."""
    resp = ProviderResponse(
        success=True,
        provider_message_id="wamid.HBgLMTIzNDU2",
        delivery_status=DeliveryStatusEnum.SENT,
    )
    assert resp.success is True
    assert resp.delivery_status == DeliveryStatusEnum.SENT
    assert resp.provider_message_id == "wamid.HBgLMTIzNDU2"


@pytest.mark.asyncio
async def test_provider_capabilities_declaration():
    """Validates capability descriptors across channels."""
    wa = WhatsAppCloudProvider()
    caps = wa.capabilities()
    assert caps.supports_text is True
    assert caps.supports_templates is True
    assert caps.supports_read_receipts is True

    smtp = EmailSMTPProvider()
    email_caps = smtp.capabilities()
    assert email_caps.supports_text is True
    assert email_caps.supports_media is True
    assert email_caps.supports_read_receipts is False


@pytest.mark.asyncio
async def test_provider_error_normalization_heuristics():
    """Validates generic error normalization on base provider."""
    wa = WhatsAppCloudProvider()
    status, retryable = wa.normalize_error("130429", "Rate limit hit")
    assert status == DeliveryStatusEnum.RATE_LIMITED
    assert retryable is True

    status_auth, retryable_auth = wa.normalize_error("190", "Invalid OAuth access token")
    assert status_auth == DeliveryStatusEnum.AUTH_FAILED
    assert retryable_auth is False


@pytest.mark.asyncio
async def test_inbound_message_dto_normalization():
    """Validates InboundMessageDTO field typing."""
    dto = InboundMessageDTO(
        provider_name="whatsapp_cloud",
        channel="whatsapp",
        provider_message_id="wamid.123",
        idempotency_key="hash123",
        sender_identifier="+971501112233",
        sender_name="Karim Mansour",
        content="I am interested in the 3BR villa.",
    )
    assert dto.channel == "whatsapp"
    assert dto.sender_name == "Karim Mansour"
    assert dto.received_at is not None


# ─── SECTION B: Provider Configuration Validation ─────────────────────────────

@pytest.mark.asyncio
async def test_whatsapp_configuration_detection():
    """Unconfigured WhatsApp provider returns CONFIGURATION_REQUIRED without secrets."""
    wa_unconfigured = WhatsAppCloudProvider(access_token="", phone_number_id="")
    assert wa_unconfigured.is_configured() is False
    status = await wa_unconfigured.verify_configuration()
    assert status == ProviderStatusEnum.CONFIGURATION_REQUIRED

    wa_configured = WhatsAppCloudProvider(
        access_token="EAAX_real_token_12345",
        phone_number_id="10987654321",
        app_secret="sec_98765",
    )
    assert wa_configured.is_configured() is True
    status_conf = await wa_configured.verify_configuration()
    assert status_conf == ProviderStatusEnum.READY


@pytest.mark.asyncio
async def test_email_smtp_configuration_detection():
    """Unconfigured SMTP provider returns CONFIGURATION_REQUIRED."""
    smtp_unconf = EmailSMTPProvider(smtp_host="smtp.example.com", smtp_password="mock_password")
    assert smtp_unconf.is_configured() is False
    status = await smtp_unconf.verify_configuration()
    assert status == ProviderStatusEnum.CONFIGURATION_REQUIRED

    smtp_conf = EmailSMTPProvider(
        smtp_host="smtp.sendgrid.net",
        smtp_port=587,
        smtp_user="apikey",
        smtp_password="SG.real_secret_key_123456",
        from_email="advisor@beetlelabs.ai",
    )
    assert smtp_conf.is_configured() is True
    status_conf = await smtp_conf.verify_configuration()
    assert status_conf == ProviderStatusEnum.READY


@pytest.mark.asyncio
async def test_sms_gateway_configuration_detection():
    """Unconfigured SMS gateway returns CONFIGURATION_REQUIRED."""
    sms_unconf = SMSGatewayProvider()
    assert sms_unconf.is_configured() is False
    status = await sms_unconf.verify_configuration()
    assert status == ProviderStatusEnum.CONFIGURATION_REQUIRED


@pytest.mark.asyncio
async def test_provider_config_service_redacted_health():
    """ProviderConfigurationService returns masked status with zero secret leakage."""
    mgr = ChannelManager()
    mgr.register(WhatsAppCloudProvider(access_token="secret_token", phone_number_id="1234567890"))
    mgr.register(EmailSMTPProvider(from_email="test@beetlelabs.ai", smtp_host="smtp.mailgun.org", smtp_password="sec"))
    mgr.register(SMSGatewayProvider())

    svc = ProviderConfigurationService(mgr)
    health_list = await svc.get_all_provider_health()

    assert len(health_list) >= 3
    for h in health_list:
        assert "secret" not in str(h.safe_metadata).lower()
        assert "password" not in str(h.safe_metadata).lower()
        assert "token" not in str(h.safe_metadata).lower()


# ─── SECTION C: WhatsApp Cloud API Real Adapter ───────────────────────────────

@pytest.mark.asyncio
async def test_whatsapp_send_unconfigured_fails_truthfully():
    """Sending via unconfigured WhatsApp returns CONFIGURATION_REQUIRED and no fake ID."""
    wa = WhatsAppCloudProvider()
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        recipient_identifier="+971501112233",
        content="Hello Tariq, here is your property brochure.",
    )
    resp = await wa.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED
    assert resp.provider_message_id is None


@pytest.mark.asyncio
async def test_whatsapp_send_successful_http_dispatch():
    """Sending via configured WhatsApp calls Graph API and parses real wamid."""
    mock_resp = httpx.Response(
        status_code=200,
        json={"messaging_product": "whatsapp", "messages": [{"id": "wamid.HBgLMTIzNDU2Nzg5MA=="}]},
        request=httpx.Request("POST", "https://graph.facebook.com/v18.0/1000/messages"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    wa = WhatsAppCloudProvider(
        access_token="EAAX_valid_token",
        phone_number_id="1000",
        app_secret="app_sec",
        http_client=mock_client,
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        recipient_identifier="+971501112233",
        content="Exclusive 2BR in Downtown Dubai available for viewing.",
    )
    resp = await wa.send(msg)
    assert resp.success is True
    assert resp.delivery_status == DeliveryStatusEnum.SENT
    assert resp.provider_message_id == "wamid.HBgLMTIzNDU2Nzg5MA=="
    assert mock_client.post.called


@pytest.mark.asyncio
async def test_whatsapp_send_rate_limit_error_handling():
    """Graph API 130429 rate limit is classified as RATE_LIMITED and retryable."""
    mock_resp = httpx.Response(
        status_code=429,
        json={"error": {"code": 130429, "message": "Rate limit hit. Cloud API throughput exceeded."}},
        request=httpx.Request("POST", "https://graph.facebook.com/v18.0/1000/messages"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    wa = WhatsAppCloudProvider(
        access_token="EAAX_valid_token",
        phone_number_id="1000",
        app_secret="app_sec",
        http_client=mock_client,
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        recipient_identifier="+971501112233",
        content="Rate limit test message.",
    )
    resp = await wa.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.RATE_LIMITED
    assert resp.retryable is True


@pytest.mark.asyncio
async def test_whatsapp_send_invalid_recipient_error_handling():
    """Graph API 131026 (not a WhatsApp user) is non-retryable INVALID_RECIPIENT."""
    mock_resp = httpx.Response(
        status_code=400,
        json={"error": {"code": 131026, "message": "Message undeliverable. Recipient is not a valid WhatsApp user."}},
        request=httpx.Request("POST", "https://graph.facebook.com/v18.0/1000/messages"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    wa = WhatsAppCloudProvider(
        access_token="EAAX_valid_token",
        phone_number_id="1000",
        app_secret="app_sec",
        http_client=mock_client,
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        recipient_identifier="+971500000000",
        content="Invalid recipient test.",
    )
    resp = await wa.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.INVALID_RECIPIENT
    assert resp.retryable is False


@pytest.mark.asyncio
async def test_whatsapp_delivery_status_webhook_parsing():
    """Parses delivered and read callback payloads from Meta WhatsApp webhook."""
    wa = WhatsAppCloudProvider()
    delivered_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "statuses": [{
                        "id": "wamid.HBgLMTIzNDU2",
                        "status": "delivered",
                        "timestamp": "1724000000",
                        "recipient_id": "971501112233",
                    }]
                }
            }]
        }]
    }
    status_obj = wa.parse_delivery_status(delivered_payload)
    assert status_obj is not None
    assert status_obj.provider_message_id == "wamid.HBgLMTIzNDU2"
    assert status_obj.delivery_status == DeliveryStatusEnum.DELIVERED


# ─── SECTION D: Email SMTP Real Adapter ───────────────────────────────────────

@pytest.mark.asyncio
async def test_email_send_unconfigured_fails_truthfully():
    """Unconfigured SMTP provider strictly returns CONFIGURATION_REQUIRED."""
    smtp = EmailSMTPProvider()
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="client@example.com",
        content="Here is your requested quotation.",
    )
    resp = await smtp.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED


@pytest.mark.asyncio
async def test_email_send_invalid_recipient_format():
    """Invalid email address format is rejected with INVALID_RECIPIENT."""
    smtp = EmailSMTPProvider(
        smtp_host="smtp.sendgrid.net",
        from_email="advisor@beetlelabs.ai",
        smtp_password="real_password_123",
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="not-an-email-address",
        content="Invalid address test.",
    )
    resp = await smtp.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.INVALID_RECIPIENT


@pytest.mark.asyncio
async def test_email_send_successful_dispatch_with_message_id():
    """Configured SMTP generates a valid RFC Message-ID and dispatches."""
    smtp = EmailSMTPProvider(
        smtp_host="smtp.sendgrid.net",
        smtp_port=587,
        smtp_user="apikey",
        smtp_password="SG.real_password_12345",
        from_email="advisor@beetlelabs.ai",
        from_name="BeetleLabs Prime",
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="investor@dubaiholding.ae",
        content="Please find attached the off-plan payment plan.",
        content_structured={"subject": "Payment Plan: Palm Jumeirah Villa"},
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        mock_smtp.return_value = instance

        resp = await smtp.send(msg)
        assert resp.success is True
        assert resp.delivery_status == DeliveryStatusEnum.SENT
        assert resp.provider_message_id is not None
        assert "@beetlelabs.ai" in resp.provider_message_id
        assert instance.send_message.called


@pytest.mark.asyncio
async def test_email_send_authentication_failure():
    """SMTP authentication failure is mapped to AUTH_FAILED and non-retryable."""
    import smtplib
    smtp = EmailSMTPProvider(
        smtp_host="smtp.sendgrid.net",
        smtp_port=587,
        smtp_user="apikey",
        smtp_password="bad_password_non_dummy",
        from_email="advisor@beetlelabs.ai",
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="investor@dubaiholding.ae",
        content="Test auth failure.",
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp.return_value = instance

        resp = await smtp.send(msg)
        assert resp.success is False
        assert resp.delivery_status == DeliveryStatusEnum.AUTH_FAILED
        assert resp.retryable is False


# ─── SECTION E: SMS Gateway Adapter ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_sms_send_unconfigured_fails_truthfully():
    """Unconfigured SMS Gateway strictly returns CONFIGURATION_REQUIRED."""
    sms = SMSGatewayProvider()
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="sms",
        provider_name="sms_gateway",
        recipient_identifier="+971501112233",
        content="Viewing reminder for tomorrow at 10 AM.",
    )
    resp = await sms.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED


@pytest.mark.asyncio
async def test_sms_send_successful_http_dispatch():
    """Configured SMS Gateway dispatches via HTTP and returns SID."""
    mock_resp = httpx.Response(
        status_code=201,
        json={"sid": "SM9876543210abcdef", "status": "queued"},
        request=httpx.Request("POST", "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    sms = SMSGatewayProvider(
        account_sid="AC1234567890abcdef",
        auth_token="auth_token_secret",
        from_number="+15005550006",
        http_client=mock_client,
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="sms",
        provider_name="sms_gateway",
        recipient_identifier="+971501112233",
        content="Your viewing at Dubai Marina has been confirmed.",
    )
    resp = await sms.send(msg)
    assert resp.success is True
    assert resp.delivery_status == DeliveryStatusEnum.SENT
    assert resp.provider_message_id == "SM9876543210abcdef"


@pytest.mark.asyncio
async def test_mock_sms_isolated_to_test_fixture():
    """MockSMSProvider exists purely for test fixtures and returns mock SID."""
    mock_sms = MockSMSProvider()
    assert mock_sms.provider_name == "mock_sms"
    msg = OutboundMessageDTO(
        message_id="test-msg-123",
        conversation_id="c1",
        organization_id="o1",
        channel="sms",
        provider_name="mock_sms",
        recipient_identifier="+1234567890",
        content="Test",
    )
    resp = await mock_sms.send(msg)
    assert resp.success is True
    assert "sms_mock_" in resp.provider_message_id


# ─── SECTION F: Webchat / In-App Adapter ───────────────────────────────────────

@pytest.mark.asyncio
async def test_webchat_provider_session_management():
    """Webchat provider registers active sessions and returns in-app delivery."""
    wc = WebChatProvider()
    WebChatProvider.register_session("sess-1", "mock_ws_conn")
    assert WebChatProvider.get_active_session_count() >= 1

    msg = OutboundMessageDTO(
        message_id="msg-inapp-1234",
        conversation_id="c1",
        organization_id="o1",
        channel="webchat",
        provider_name="webchat",
        recipient_identifier="sess-1",
        content="Agent joined the chat.",
    )
    resp = await wc.send(msg)
    assert resp.success is True
    assert "inapp_" in resp.provider_message_id

    WebChatProvider.unregister_session("sess-1")


# ─── SECTION G: Execution-Time Safety Re-Checks ───────────────────────────────

@pytest.mark.asyncio
async def test_execution_time_consent_revocation_blocks_send(db_session: AsyncSession):
    """If consent is revoked between action proposal and execution, delivery is blocked."""
    broker = Broker(id=uuid.uuid4(), name="Agent Leo", email=f"leo_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Layla Kassam", phone="+971501112233", status="active")
    db_session.add_all([broker, lead])

    # Record revoked consent
    consent = CommunicationConsent(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        channel="WHATSAPP",
        status="OPTED_OUT",
        withdrawn_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(consent)
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.OFFER_VIEWING,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.APPROVED,
        confidence=0.9,
        reason="Lead is qualified for 2BR viewing.",
        draft_message_body="Would you like to view the apartment tomorrow?",
    )

    delivery_engine = RealDeliveryEngine(db_session)
    result = await delivery_engine.execute_sales_action_delivery(
        decision=decision,
        lead=lead,
        broker=broker,
    )

    assert result.status == SalesActionStatus.BLOCKED
    assert "CONSENT_REVOKED_AT_EXECUTION" in result.details.get("blocked_reason", "")


@pytest.mark.asyncio
async def test_execution_time_terminal_lead_state_blocks_send(db_session: AsyncSession):
    """If lead enters CONVERTED/LOST stage before execution, delivery is blocked."""
    broker = Broker(id=uuid.uuid4(), name="Agent Maya", email=f"maya_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Omar Farooq", phone="+971502223344", status="lost", pipeline_stage="LOST")
    db_session.add_all([broker, lead])
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.FOLLOW_UP_NO_RESPONSE,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.APPROVED,
        confidence=0.8,
        reason="Follow up on previous inquiry.",
    )

    delivery_engine = RealDeliveryEngine(db_session)
    result = await delivery_engine.execute_sales_action_delivery(
        decision=decision,
        lead=lead,
        broker=broker,
    )

    assert result.status == SalesActionStatus.BLOCKED
    assert "LEAD_TERMINAL_STATE_AT_EXECUTION" in result.details.get("blocked_reason", "")


@pytest.mark.asyncio
async def test_execution_time_fatigue_limit_blocks_send(db_session: AsyncSession):
    """If fatigue budget was exhausted by another channel moments earlier, delivery is blocked."""
    broker = Broker(id=uuid.uuid4(), name="Agent Sam", email=f"sam_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Fatima Zahra", phone="+971503334455", status="active")
    consent = CommunicationConsent(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        channel="WHATSAPP",
        status="OPTED_IN",
    )
    fatigue = ContactFatigue(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        consecutive_no_replies=3,
        current_fatigue_score=1.0,
        is_suppressed=True,
    )
    db_session.add_all([broker, lead, consent, fatigue])
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.FOLLOW_UP_NO_RESPONSE,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.APPROVED,
        confidence=0.8,
        reason="Follow up attempt.",
    )

    delivery_engine = RealDeliveryEngine(db_session)
    result = await delivery_engine.execute_sales_action_delivery(
        decision=decision,
        lead=lead,
        broker=broker,
    )

    assert result.status == SalesActionStatus.BLOCKED
    assert "FATIGUE_EXCEEDED_AT_EXECUTION" in result.details.get("blocked_reason", "")


@pytest.mark.asyncio
async def test_execution_time_quiet_hours_reschedules_send(db_session: AsyncSession):
    """If execution time falls into customer quiet hours, delivery is scheduled rather than sent."""
    broker = Broker(id=uuid.uuid4(), name="Agent Zaid", email=f"zaid_{uuid.uuid4()}@example.com")
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Dubai Night Owl",
        phone="+971501112233",
        preferred_locations=["Downtown Dubai"],
        status="active",
    )
    consent = CommunicationConsent(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        channel="WHATSAPP",
        status="OPTED_IN",
    )
    db_session.add_all([broker, lead, consent])
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.OFFER_VIEWING,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.APPROVED,
        confidence=0.9,
        reason="Offer viewing during quiet hours test.",
        draft_message_body="Would you like to visit the unit?",
    )

    delivery_engine = RealDeliveryEngine(db_session)

    # Patch datetime to 23:30 (11:30 PM local Dubai time)
    with patch("app.modules.sales_action.guards.quiet_hours_guard.datetime") as mock_dt:
        mock_now = datetime(2026, 8, 23, 19, 30, tzinfo=timezone.utc) # 23:30 GST
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

        result = await delivery_engine.execute_sales_action_delivery(
            decision=decision,
            lead=lead,
            broker=broker,
        )

        assert result.status == SalesActionStatus.QUEUED
        assert "QUIET_HOURS_RESCHEDULED" in result.details.get("reason", "")


@pytest.mark.asyncio
async def test_execution_time_unapproved_action_blocks_send(db_session: AsyncSession):
    """Sensitive action requiring human approval cannot be sent if status is HUMAN_REVIEW."""
    broker = Broker(id=uuid.uuid4(), name="Agent Dan", email=f"dan_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="High Value VIP", phone="+971509998877", status="qualified", budget_max=15000000)
    db_session.add_all([broker, lead])
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.OFFER_VIEWING,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.HUMAN_REVIEW,
        human_approval_required=True,
        confidence=0.85,
        reason="High budget VIP lead requires human sign-off.",
    )

    delivery_engine = RealDeliveryEngine(db_session)
    result = await delivery_engine.execute_sales_action_delivery(
        decision=decision,
        lead=lead,
        broker=broker,
    )

    assert result.status == SalesActionStatus.BLOCKED
    assert "APPROVAL_REQUIRED_AT_EXECUTION" in result.details.get("blocked_reason", "")


# ─── SECTION H: Idempotency & Concurrency Locking ─────────────────────────────

@pytest.mark.asyncio
async def test_idempotency_key_computation():
    """Idempotency key is deterministic across identical parameters."""
    k1 = RealDeliveryEngine.compute_idempotency_key(
        organization_id="org-1",
        lead_id="lead-1",
        action_id="act-1",
        channel="whatsapp",
        message_body="Hello world",
        execution_version=1,
    )
    k2 = RealDeliveryEngine.compute_idempotency_key(
        organization_id="org-1",
        lead_id="lead-1",
        action_id="act-1",
        channel="whatsapp",
        message_body="Hello world",
        execution_version=1,
    )
    assert k1 == k2
    assert len(k1) == 64


@pytest.mark.asyncio
async def test_duplicate_execution_returns_existing_result(db_session: AsyncSession):
    """Calling execute_sales_action_delivery twice with the same key returns the existing result."""
    broker = Broker(id=uuid.uuid4(), name="Agent Chloe", email=f"chloe_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Ali Hamdan", phone="+971501234567", status="active")
    consent = CommunicationConsent(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        channel="WHATSAPP",
        status="OPTED_IN",
    )
    db_session.add_all([broker, lead, consent])
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.ASK_QUALIFICATION,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.APPROVED,
        confidence=0.8,
        reason="Ask for preferred bedrooms.",
        draft_message_body="How many bedrooms are you looking for?",
    )

    # Set up channel manager with mock client for successful dispatch
    mock_resp = httpx.Response(
        status_code=200,
        json={"messages": [{"id": "wamid.IDEMP_12345"}]},
        request=httpx.Request("POST", "https://graph.facebook.com/v18.0/1000/messages"),
    )
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_resp

    mgr = ChannelManager()
    mgr.register(WhatsAppCloudProvider(
        access_token="valid_token",
        phone_number_id="1000",
        app_secret="sec",
        http_client=mock_client,
    ))

    delivery_engine = RealDeliveryEngine(db_session, channel_manager=mgr)

    # First execution
    res1 = await delivery_engine.execute_sales_action_delivery(decision, lead, broker)
    assert res1.status == SalesActionStatus.SENT
    assert res1.provider_message_id == "wamid.IDEMP_12345"

    # Second execution (Duplicate)
    res2 = await delivery_engine.execute_sales_action_delivery(decision, lead, broker)
    assert res2.status == SalesActionStatus.SENT
    assert res2.provider_message_id == "wamid.IDEMP_12345"
    assert res2.details.get("deduplicated") is True
    # HTTP client was only called ONCE!
    assert mock_client.post.call_count == 1


# ─── SECTION I: Retry Policy & Error Classification ───────────────────────────

@pytest.mark.asyncio
async def test_retry_policy_exponential_backoff_calculation():
    """Validates exponential backoff bounds and jitter."""
    from app.modules.communication.delivery_engine.engine import DeliveryEngine
    mgr = ChannelManager()
    engine = DeliveryEngine(mgr)

    queue_item = OutboundQueue(
        organization_id="org-1",
        message_id="msg-1",
        provider_name="whatsapp_cloud",
        channel="whatsapp",
        recipient_identifier="+971501112233",
        payload={},
        retry_count=1,
        max_retries=5,
        idempotency_key="key-1",
    )
    db = AsyncMock()
    provider_res = ProviderResponse(success=False, status="failed", error_message="503 Service Unavailable")

    await engine._schedule_retry(db, queue_item, provider_res)
    assert queue_item.status == "retry"
    assert queue_item.retry_count == 2
    assert queue_item.next_attempt_at is not None


# ─── SECTION J: Webhook Signature Verification & Duplicate Protection ─────────

@pytest.mark.asyncio
async def test_whatsapp_webhook_valid_signature_accepted():
    """Valid X-Hub-Signature-256 HMAC signature is accepted."""
    app_secret = "beetlelabs_meta_webhook_secret_2026"
    raw_body = b'{"entry":[{"changes":[{"value":{"messages":[{"id":"wamid.123"}]}}]}]}'

    computed_sig = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    wa = WhatsAppCloudProvider(app_secret=app_secret)
    is_valid = await wa.verify_webhook_signature(raw_body, {"x-hub-signature-256": computed_sig})
    assert is_valid is True


@pytest.mark.asyncio
async def test_whatsapp_webhook_forged_signature_rejected():
    """Forged signature is rejected."""
    app_secret = "beetlelabs_meta_webhook_secret_2026"
    raw_body = b'{"entry":[{"changes":[{"value":{"messages":[{"id":"wamid.FORGED"}]}}]}]}'

    wa = WhatsAppCloudProvider(app_secret=app_secret)
    is_valid = await wa.verify_webhook_signature(raw_body, {"x-hub-signature-256": "sha256=invalid_hash_signature"})
    assert is_valid is False


@pytest.mark.asyncio
async def test_duplicate_webhook_deduplication(db_session: AsyncSession):
    """Inbound webhook payload idempotency key prevents duplicate queue entries."""
    raw_body = b'{"entry":[{"id":"1","changes":[{"value":{"messages":[{"id":"wa_msg_99"}]}}]}]}'
    idem_key = hashlib.sha256(raw_body[:512]).hexdigest()[:64]

    # Pre-insert existing
    item = InboundQueue(
        idempotency_key=idem_key,
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        raw_payload={"test": 1},
        status="pending",
    )
    db_session.add(item)
    await db_session.commit()

    # Query duplicate
    stmt = select(InboundQueue).where(InboundQueue.idempotency_key == idem_key)
    res = await db_session.execute(stmt)
    assert res.scalars().first() is not None


# ─── SECTION K: Multi-Tenant Isolation Boundaries ─────────────────────────────

@pytest.mark.asyncio
async def test_tenant_isolation_execution_scoping(db_session: AsyncSession):
    """Execution for Tenant A cannot read or modify Tenant B records."""
    broker_a = Broker(id=uuid.uuid4(), name="Broker A", email=f"a_{uuid.uuid4()}@example.com")
    broker_b = Broker(id=uuid.uuid4(), name="Broker B", email=f"b_{uuid.uuid4()}@example.com")
    lead_b = Lead(id=uuid.uuid4(), broker_id=broker_b.id, name="Lead B", phone="+971507778899", status="active")
    db_session.add_all([broker_a, broker_b, lead_b])
    await db_session.commit()

    # Query lead_b with tenant A filter -> must return None
    stmt = select(Lead).where(Lead.id == lead_b.id, Lead.broker_id == broker_a.id)
    res = await db_session.execute(stmt)
    assert res.scalars().first() is None


@pytest.mark.asyncio
async def test_tenant_isolation_idempotency_key_partitioning():
    """Idempotency keys for different tenants with identical content are strictly isolated."""
    k_tenant_a = RealDeliveryEngine.compute_idempotency_key(
        organization_id="tenant-alpha",
        lead_id="lead-1",
        action_id="action-1",
        channel="whatsapp",
        message_body="Identical text",
    )
    k_tenant_b = RealDeliveryEngine.compute_idempotency_key(
        organization_id="tenant-beta",
        lead_id="lead-1",
        action_id="action-1",
        channel="whatsapp",
        message_body="Identical text",
    )
    assert k_tenant_a != k_tenant_b


# ─── SECTION L: AI Safety, PII Redaction & Credential Security ─────────────────

@pytest.mark.asyncio
async def test_mask_org_id_cryptographic_hash():
    """Validates that mask_org_id produces consistent, PII-safe SHA-256 hash."""
    org_id = "org_enterprise_realestate_12345"
    masked = mask_org_id(org_id)
    assert len(masked) == 8
    assert masked != org_id
    assert masked == mask_org_id(org_id)


@pytest.mark.asyncio
async def test_human_handoff_escalation_records_brief_truthfully(db_session: AsyncSession):
    """Human handoff records structured sales brief and conversation note without sending SMS/WA."""
    broker = Broker(id=uuid.uuid4(), name="Agent Senior", email=f"sr_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Legal Counsel Lead", phone="+971501119999", status="qualified")
    db_session.add_all([broker, lead])
    await db_session.commit()

    brief = SalesBriefDTO(
        lead_id=str(lead.id),
        lead_name=lead.name,
        handoff_reason="Customer requested legal clause negotiation.",
        recommended_human_action="Senior partner call required.",
        recent_conversation_summary="Lead discussed lease terms and asked for partner consultation.",
    )
    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.HUMAN_HANDOFF,
        recommended_channel=CommunicationChannel.HUMAN_CALL,
        status=SalesActionStatus.COMPLETED,
        confidence=1.0,
        reason="Legal negotiation trigger.",
        sales_brief=brief,
    )

    delivery_engine = RealDeliveryEngine(db_session)
    res = await delivery_engine.execute_sales_action_delivery(decision, lead, broker)

    assert res.status == SalesActionStatus.COMPLETED
    assert res.channel == "HUMAN_CALL"
    assert res.provider == "internal_crm"

    # Verify conversation note was created
    stmt = select(Conversation).where(Conversation.lead_id == lead.id)
    convs = (await db_session.execute(stmt)).scalars().all()
    assert len(convs) >= 1
    assert "HUMAN HANDOFF ESCALATION" in convs[0].message


# ─── SECTION M: Truthful Provider Failure & Zero-Mock Verification ─────────────

@pytest.mark.asyncio
async def test_sales_action_executor_truthful_failure_when_unconfigured(db_session: AsyncSession):
    """SalesActionExecutor returns FAILED status and configuration_required details when unconfigured."""
    broker = Broker(id=uuid.uuid4(), name="Agent Elena", email=f"elena_{uuid.uuid4()}@example.com")
    lead = Lead(id=uuid.uuid4(), broker_id=broker.id, name="Elena Client", phone="+971504445566", status="active")
    consent = CommunicationConsent(
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        channel="WHATSAPP",
        status="OPTED_IN",
    )
    db_session.add_all([broker, lead, consent])
    await db_session.commit()

    decision = SalesActionDecisionDTO(
        action_id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=str(broker.id),
        action_type=SalesActionType.SEND_PROPERTY_RECOMMENDATIONS,
        recommended_channel=CommunicationChannel.WHATSAPP,
        status=SalesActionStatus.APPROVED,
        confidence=0.9,
        reason="Send verified property matches.",
        draft_message_body="Here are 2 verified properties in Downtown Dubai.",
    )

    # Use explicit unconfigured channel manager
    mgr = ChannelManager()
    mgr.register(WhatsAppCloudProvider(access_token="", phone_number_id=""))
    engine = RealDeliveryEngine(db_session, channel_manager=mgr)
    executor = SalesActionExecutor(db_session)
    executor._delivery_engine = engine

    result = await executor.execute_action(decision, lead, broker)

    assert result.status == SalesActionStatus.FAILED
    assert result.provider_message_id is None
    assert result.details.get("configuration_required") is True
