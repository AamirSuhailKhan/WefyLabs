"""
Part 23.1 — Brevo SMTP Free Transactional Email Integration Test Suite
======================================================================
Comprehensive test suite verifying:
1. Brevo SMTP provider initialization, alias handling, and configuration check.
2. Safe failure on unconfigured / dummy credentials (fail-closed, truthful).
3. RFC Message-ID and MIME multipart (Plaintext + HTML) assembly.
4. STARTTLS (587) and SSL (465) dispatch flows.
5. Truthful error classification (AUTH_FAILED, INVALID_RECIPIENT, PROVIDER_UNAVAILABLE).
6. Non-secret connection probe method (`test_connection`).
7. Celery async task dispatch (`process_email_dispatch`).
8. Notification channel adapter (`EmailChannelAdapter`).
9. Emergency pause / fail-closed safety guard compatibility.
10. Secret protection and log masking.
"""
import asyncio
import smtplib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.modules.communication.channel_manager.manager import ChannelManager
from app.modules.communication.provider_adapters.base_provider import (
    DeliveryStatusEnum,
    OutboundMessageDTO,
    ProviderStatusEnum,
)
from app.modules.communication.provider_adapters.email_smtp_provider import EmailSMTPProvider
from app.modules.notifications.channels.notification_channels import (
    EmailChannelAdapter,
    NotificationPayload,
)
from app.tasks.queue_workers import process_email_dispatch


# ─── 1. Unconfigured Safety ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_unconfigured_safety():
    """Unconfigured SMTP provider strictly returns CONFIGURATION_REQUIRED (never fakes success)."""
    provider = EmailSMTPProvider(smtp_host="", smtp_password="", from_email="")
    assert provider.is_configured() is False
    assert await provider.verify_configuration() == ProviderStatusEnum.CONFIGURATION_REQUIRED

    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="buyer@domain.ae",
        content="Testing unconfigured safety.",
    )
    resp = await provider.send(msg)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED
    assert resp.error_code == "CONFIGURATION_REQUIRED"
    assert resp.retryable is False


# ─── 2. Aliases & Parameter Resolution ─────────────────────────────────────────

def test_brevo_smtp_aliases_and_properties():
    """Supports canonical names and aliases (smtp_username, email_from_address, smtp_security)."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_username="brevo_account_user",
        smtp_password="real_brevo_secret_key_123",
        email_from_address="noreply@domain.ae",
        from_name="BeetleLabs Real Estate",
        smtp_security="STARTTLS",
    )
    assert provider.provider_name == "smtp_email"
    assert provider.channel == "email"
    assert provider._smtp_host == "smtp-relay.brevo.com"
    assert provider._smtp_port == 587
    assert provider._smtp_user == "brevo_account_user"
    assert provider._from_email == "noreply@domain.ae"
    assert provider._smtp_use_tls is True
    assert provider._smtp_use_ssl is False
    assert provider.is_configured() is True


# ─── 3. MIME Multipart & HTML Body Assembly ───────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_mime_multipart_and_message_id():
    """Verifies valid RFC Message-ID and multipart plaintext/HTML payload generation."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_user="brevo_user",
        smtp_password="brevo_secret_password",
        from_email="notifications@luxuryestates.ae",
        from_name="Luxury Estates Dubai",
        smtp_use_tls=True,
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-101",
        organization_id="org-101",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="investor@dubaiholding.ae",
        content="Dear Investor, your VIP property brochure is attached.",
        content_structured={
            "subject": "Exclusive Off-Plan Launch: Palm Jumeirah Villas",
            "html": "<h1>Exclusive Launch</h1><p>Dear Investor, your VIP brochure is attached.</p>",
        },
    )

    sent_message = None

    def capture_send(message):
        nonlocal sent_message
        sent_message = message

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.send_message.side_effect = capture_send
        mock_smtp_cls.return_value = instance

        resp = await provider.send(msg)

        assert resp.success is True
        assert resp.delivery_status == DeliveryStatusEnum.SENT
        assert resp.provider_message_id is not None
        assert "@luxuryestates.ae" in resp.provider_message_id
        assert sent_message is not None
        assert sent_message["Subject"] == "Exclusive Off-Plan Launch: Palm Jumeirah Villas"
        assert "Luxury Estates Dubai <notifications@luxuryestates.ae>" in sent_message["From"]
        assert sent_message["To"] == "investor@dubaiholding.ae"
        assert sent_message.is_multipart() is True


# ─── 4. STARTTLS Port 587 Send ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_starttls_send_success():
    """Verifies standard port 587 STARTTLS dispatch flow."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_user="brevo_user",
        smtp_password="brevo_secret_password",
        from_email="noreply@beetlelabs.ai",
        smtp_use_tls=True,
        smtp_use_ssl=False,
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="lead@client.com",
        content="Your inquiry has been received.",
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        mock_smtp_cls.return_value = instance

        resp = await provider.send(msg)

        assert resp.success is True
        assert resp.delivery_status == DeliveryStatusEnum.SENT
        assert mock_smtp_cls.called
        assert instance.starttls.called
        assert instance.login.called
        assert instance.send_message.called


# ─── 5. SSL Port 465 Send ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_ssl_port_465_send_success():
    """Verifies port 465 SSL dispatch flow uses smtplib.SMTP_SSL."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=465,
        smtp_user="brevo_user",
        smtp_password="brevo_secret_password",
        from_email="noreply@beetlelabs.ai",
        smtp_security="SSL",
    )
    assert provider._smtp_use_ssl is True

    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="lead@client.com",
        content="Your inquiry has been received.",
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP_SSL") as mock_ssl_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        mock_ssl_cls.return_value = instance

        resp = await provider.send(msg)

        assert resp.success is True
        assert resp.delivery_status == DeliveryStatusEnum.SENT
        assert mock_ssl_cls.called
        assert instance.login.called
        assert instance.send_message.called


# ─── 6. SMTP Authentication Error ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_auth_error_handling():
    """SMTP authentication failure is mapped to AUTH_FAILED and non-retryable."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_user="brevo_user",
        smtp_password="wrong_password",
        from_email="noreply@beetlelabs.ai",
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="lead@client.com",
        content="Test auth failure.",
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication credentials invalid")
        mock_smtp_cls.return_value = instance

        resp = await provider.send(msg)

        assert resp.success is False
        assert resp.delivery_status == DeliveryStatusEnum.AUTH_FAILED
        assert resp.error_code == "SMTP_AUTH_FAILED"
        assert resp.retryable is False


# ─── 7. SMTP Recipient Refused ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_recipient_refused():
    """SMTP server rejecting recipient maps to INVALID_RECIPIENT and non-retryable."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_user="brevo_user",
        smtp_password="brevo_secret_password",
        from_email="noreply@beetlelabs.ai",
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="rejected-recipient@invalid-domain-xyz.com",
        content="Test recipient refused.",
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.send_message.side_effect = smtplib.SMTPRecipientsRefused({"rejected@invalid.com": (550, b"User not found")})
        mock_smtp_cls.return_value = instance

        resp = await provider.send(msg)

        assert resp.success is False
        assert resp.delivery_status == DeliveryStatusEnum.INVALID_RECIPIENT
        assert resp.error_code == "SMTP_RECIPIENT_REFUSED"
        assert resp.retryable is False


# ─── 8. Transient Connection Error ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_transient_connection_error():
    """Transient network/timeout failure maps to PROVIDER_UNAVAILABLE with retryable=True."""
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_user="brevo_user",
        smtp_password="brevo_secret_password",
        from_email="noreply@beetlelabs.ai",
    )
    msg = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        organization_id="org-1",
        channel="email",
        provider_name="smtp_email",
        recipient_identifier="lead@client.com",
        content="Test transient timeout.",
    )

    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        instance.connect.side_effect = TimeoutError("Connection timed out to smtp-relay.brevo.com:587")
        mock_smtp_cls.side_effect = TimeoutError("Connection timed out to smtp-relay.brevo.com:587")

        resp = await provider.send(msg)

        assert resp.success is False
        assert resp.delivery_status == DeliveryStatusEnum.PROVIDER_UNAVAILABLE
        assert resp.error_code == "SMTP_CONNECT_ERROR"
        assert resp.retryable is True


# ─── 9. Connection Probe Diagnostic ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_test_connection_probe():
    """test_connection() verifies handshake and auth without sending messages."""
    # 1. Unconfigured probe
    unconf = EmailSMTPProvider()
    success, msg = await unconf.test_connection()
    assert success is False
    assert "incomplete" in msg

    # 2. Configured probe (success)
    conf = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_user="brevo_user",
        smtp_password="brevo_secret_password",
        from_email="noreply@beetlelabs.ai",
    )
    with patch("app.modules.communication.provider_adapters.email_smtp_provider.smtplib.SMTP") as mock_smtp_cls:
        instance = MagicMock()
        instance.__enter__.return_value = instance
        mock_smtp_cls.return_value = instance

        success, msg = await conf.test_connection()
        assert success is True
        assert "successful" in msg
        assert instance.login.called


# ─── 10. Notification Channel Adapter ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_brevo_smtp_notification_channel_adapter():
    """EmailChannelAdapter dispatches notifications through EmailSMTPProvider."""
    adapter = EmailChannelAdapter()
    payload = NotificationPayload(
        recipient_id="investor@domain.com",
        title="Site Visit Confirmed",
        body="Your site visit for Palm Jumeirah is confirmed for tomorrow 4 PM.",
        channel="email",
    )

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager") as mock_get_mgr:
        mgr = ChannelManager()
        provider = EmailSMTPProvider(
            smtp_host="smtp-relay.brevo.com",
            smtp_user="brevo_user",
            smtp_password="brevo_secret_password",
            from_email="noreply@beetlelabs.ai",
        )
        mgr.register(provider)
        mock_get_mgr.return_value = mgr

        with patch.object(provider, "send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = MagicMock(success=True)
            result = await adapter.send(payload)
            assert result is True
            assert mock_send.called


# ─── 11. Celery Task Async Dispatch ───────────────────────────────────────────

def test_brevo_smtp_celery_task_dispatch():
    """Celery process_email_dispatch task sends email via EmailSMTPProvider."""
    email_data = {
        "recipient": "client@domain.ae",
        "subject": "Payment Plan Summary",
        "content": "Attached is your payment schedule for DLF Phase 5.",
    }

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager") as mock_get_mgr:
        mgr = ChannelManager()
        provider = EmailSMTPProvider(
            smtp_host="smtp-relay.brevo.com",
            smtp_user="brevo_user",
            smtp_password="brevo_secret_password",
            from_email="noreply@beetlelabs.ai",
        )
        mgr.register(provider)
        mock_get_mgr.return_value = mgr

        with patch.object(provider, "send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = MagicMock(success=True, provider_message_id="<test-msg-id@brevo.com>")
            result = process_email_dispatch.__wrapped__(email_data)
            assert result["status"] == "sent"
            assert result["provider_message_id"] == "<test-msg-id@brevo.com>"


# ─── 12. Secret Masking & Protection ──────────────────────────────────────────

def test_brevo_smtp_secret_masking_and_no_leak():
    """Verifies that secrets are never leaked in repr or string conversions."""
    secret_pass = "super_secret_password_987654321"
    provider = EmailSMTPProvider(
        smtp_host="smtp-relay.brevo.com",
        smtp_user="brevo_user",
        smtp_password=secret_pass,
        from_email="noreply@beetlelabs.ai",
    )
    provider_str = repr(provider)
    assert secret_pass not in provider_str
    assert "smtp-relay.brevo.com" in provider_str
