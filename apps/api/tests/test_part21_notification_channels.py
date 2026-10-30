"""
Test Suite: Notification Channel Truthfulness & Fallback Behavior
Verifies that notification channels (Email, WhatsApp, Telegram, SMS)
truthfully report failure when unconfigured rather than returning false-success (True).
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.modules.notifications.channels.notification_channels import (
    NotificationPayload,
    InAppChannelAdapter,
    EmailChannelAdapter,
    WhatsAppChannelAdapter,
    TelegramChannelAdapter,
    SMSChannelAdapter,
)
from app.modules.communication.provider_adapters.base_provider import ProviderResponse, ProviderDeliveryStatus


@pytest.mark.asyncio
async def test_in_app_channel_adapter_success():
    adapter = InAppChannelAdapter()
    payload = NotificationPayload(
        recipient_id="broker-123",
        title="New Lead Assigned",
        body="Lead John Doe has been assigned to you.",
        channel="in_app",
    )
    result = await adapter.send(payload)
    assert result is True


@pytest.mark.asyncio
async def test_email_channel_adapter_returns_false_when_unconfigured():
    adapter = EmailChannelAdapter()
    payload = NotificationPayload(
        recipient_id="user@example.com",
        title="Invoice Overdue",
        body="Please pay your outstanding invoice.",
        channel="email",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = False
    mock_provider.provider_name = "smtp"

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is False, "Unconfigured Email provider must return False, not True"
        mock_provider.send.assert_not_called()


@pytest.mark.asyncio
async def test_email_channel_adapter_success_when_configured():
    adapter = EmailChannelAdapter()
    payload = NotificationPayload(
        recipient_id="user@example.com",
        title="Welcome",
        body="Welcome to WefyLabs CRM.",
        channel="email",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = True
    mock_provider.provider_name = "smtp"
    mock_provider.send = AsyncMock(return_value=ProviderResponse(
        success=True,
        provider_message_id="msg-123",
        status="sent",
    ))

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is True
        mock_provider.send.assert_called_once()


@pytest.mark.asyncio
async def test_whatsapp_channel_adapter_returns_false_when_unconfigured():
    adapter = WhatsAppChannelAdapter()
    payload = NotificationPayload(
        recipient_id="+971501234567",
        title="Viewing Confirmed",
        body="Your property viewing is confirmed for 3:00 PM.",
        channel="whatsapp",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = False
    mock_provider.provider_name = "whatsapp_cloud"

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is False, "Unconfigured WhatsApp provider must return False, not True"
        mock_provider.send.assert_not_called()


@pytest.mark.asyncio
async def test_whatsapp_channel_adapter_success_when_configured():
    adapter = WhatsAppChannelAdapter()
    payload = NotificationPayload(
        recipient_id="+971501234567",
        title="Viewing Confirmed",
        body="Your property viewing is confirmed for 3:00 PM.",
        channel="whatsapp",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = True
    mock_provider.provider_name = "whatsapp_cloud"
    mock_provider.send = AsyncMock(return_value=ProviderResponse(
        success=True,
        provider_message_id="wa-msg-123",
        status="delivered",
    ))

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is True
        mock_provider.send.assert_called_once()


@pytest.mark.asyncio
async def test_telegram_channel_adapter_returns_false_when_unconfigured():
    adapter = TelegramChannelAdapter()
    payload = NotificationPayload(
        recipient_id="tg_user_999",
        title="Offer Received",
        body="A buyer submitted an offer on Unit 402.",
        channel="telegram",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = False
    mock_provider.provider_name = "telegram"

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is False, "Unconfigured Telegram provider must return False, not True"
        mock_provider.send.assert_not_called()


@pytest.mark.asyncio
async def test_sms_channel_adapter_returns_false_when_unconfigured():
    adapter = SMSChannelAdapter()
    payload = NotificationPayload(
        recipient_id="+971509998877",
        title="Security Code",
        body="Your verification code is 849201.",
        channel="sms",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = False
    mock_provider.provider_name = "sms_twilio"

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is False, "Unconfigured SMS provider must return False, not True"
        mock_provider.send.assert_not_called()


@pytest.mark.asyncio
async def test_adapter_exception_handling_returns_false():
    """Verify that any network/internal exception during send returns False rather than crashing."""
    adapter = WhatsAppChannelAdapter()
    payload = NotificationPayload(
        recipient_id="+971501234567",
        title="Test Crash",
        body="Test error handling",
        channel="whatsapp",
    )
    mock_provider = MagicMock()
    mock_provider.is_configured.return_value = True
    mock_provider.send = AsyncMock(side_effect=RuntimeError("Simulated network connection reset"))

    mock_mgr = MagicMock()
    mock_mgr.get_provider.return_value = mock_provider

    with patch("app.modules.communication.channel_manager.manager.get_channel_manager", return_value=mock_mgr):
        result = await adapter.send(payload)
        assert result is False
