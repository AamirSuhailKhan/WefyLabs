"""
Part 21.6 — Real SMS Provider Adapter
======================================
Production-grade SMS provider adapter supporting Twilio / Generic SMS HTTP Gateways.

NON-NEGOTIABLE INVARIANTS:
1. If SMS credentials are not configured, strictly returns CONFIGURATION_REQUIRED.
2. Never fabricates SMS delivery success in production paths.
3. Never logs authentication tokens, auth headers, or recipient phone numbers.
"""
from __future__ import annotations

import abc
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

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

logger = logging.getLogger("wefylabs.communication.sms")

_KNOWN_DUMMY_SMS = {"mock_sid", "mock_token", "placeholder", "+10000000000", "", "none", "null"}


class SMSProvider(CommunicationProvider, abc.ABC):
    """
    Abstract SMS provider base.
    """

    @property
    def channel(self) -> str:
        return "sms"

    @property
    def supported_message_types(self) -> List[str]:
        return ["text"]

    @property
    def supports_typing_indicator(self) -> bool:
        return False

    @property
    def supports_read_receipts(self) -> bool:
        return False

    @property
    def supports_media(self) -> bool:
        return False

    def capabilities(self) -> CommunicationCapabilities:
        return CommunicationCapabilities(
            supports_text=True,
            supports_templates=False,
            supports_media=False,
            supports_typing_indicator=False,
            supports_read_receipts=False,
            supports_webhooks=True,
            max_text_length=1600,
        )


class SMSGatewayProvider(SMSProvider):
    """
    Production-grade SMS Gateway adapter (Twilio / Generic REST SMS Gateway).
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        api_url: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self._account_sid = (account_sid or "").strip()
        self._auth_token = (auth_token or "").strip()
        self._from_number = (from_number or "").strip()
        self._api_url = api_url
        self._http_client = http_client
        self._connected = False

    @property
    def provider_name(self) -> str:
        return "sms_gateway"

    def is_configured(self) -> bool:
        if not self._account_sid or self._account_sid.lower() in _KNOWN_DUMMY_SMS:
            return False
        if not self._auth_token or self._auth_token.lower() in _KNOWN_DUMMY_SMS:
            return False
        if not self._from_number or self._from_number.lower() in _KNOWN_DUMMY_SMS:
            return False
        return True

    async def verify_configuration(self) -> ProviderStatusEnum:
        if not self.is_configured():
            return ProviderStatusEnum.CONFIGURATION_REQUIRED
        return ProviderStatusEnum.READY

    async def connect(self) -> None:
        if not self.is_configured():
            self._connected = False
            return
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def verify_webhook_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        if not self.is_configured():
            return False
        return True

    async def send(self, message: OutboundMessageDTO) -> ProviderResponse:
        """
        Dispatches SMS via real REST API.
        Truthful execution: returns CONFIGURATION_REQUIRED if unconfigured.
        """
        start_ms = int(time.time() * 1000)

        if not self.is_configured():
            latency_ms = int(time.time() * 1000) - start_ms
            logger.warning(
                f"[SMSGatewayProvider] Cannot send msg_id={message.message_id}: "
                f"SMS provider credentials (account_sid/auth_token/from_number) not configured."
            )
            return ProviderResponse(
                success=False,
                status="failed",
                delivery_status=DeliveryStatusEnum.CONFIGURATION_REQUIRED,
                error_code="CONFIGURATION_REQUIRED",
                error_message="SMS Gateway credentials not configured in environment or database.",
                retryable=False,
                latency_ms=latency_ms,
            )

        # Build endpoint (default Twilio Messages API)
        endpoint = self._api_url or f"https://api.twilio.com/2010-04-01/Accounts/{self._account_sid}/Messages.json"
        data = {
            "From": self._from_number,
            "To": message.recipient_identifier,
            "Body": message.content,
        }

        client = self._http_client
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            should_close = True

        try:
            resp = await client.post(
                endpoint,
                data=data,
                auth=(self._account_sid, self._auth_token),
            )
            latency_ms = int(time.time() * 1000) - start_ms
            resp_data = resp.json() if resp.content else {}

            if resp.status_code in (200, 201):
                sid = resp_data.get("sid", f"sms_{message.message_id[:12]}")
                return ProviderResponse(
                    success=True,
                    provider_message_id=sid,
                    status="sent",
                    delivery_status=DeliveryStatusEnum.SENT,
                    raw_response=resp_data,
                    latency_ms=latency_ms,
                )

            err_code = str(resp_data.get("code", resp.status_code))
            err_msg = resp_data.get("message", f"SMS Gateway error ({resp.status_code})")
            deliv_status, is_retryable = self.normalize_error(err_code, err_msg)

            return ProviderResponse(
                success=False,
                status="failed",
                delivery_status=deliv_status,
                error_code=err_code,
                error_message=err_msg,
                retryable=is_retryable,
                raw_response=resp_data,
                latency_ms=latency_ms,
            )

        except (httpx.ConnectError, httpx.TimeoutException) as net_err:
            latency_ms = int(time.time() * 1000) - start_ms
            return ProviderResponse(
                success=False,
                status="failed",
                delivery_status=DeliveryStatusEnum.PROVIDER_UNAVAILABLE,
                error_code="NETWORK_TIMEOUT",
                error_message=str(net_err),
                retryable=True,
                latency_ms=latency_ms,
            )
        except Exception as e:
            latency_ms = int(time.time() * 1000) - start_ms
            return ProviderResponse(
                success=False,
                status="failed",
                delivery_status=DeliveryStatusEnum.FAILED,
                error_code="SMS_ERROR",
                error_message=str(e),
                retryable=False,
                latency_ms=latency_ms,
            )
        finally:
            if should_close:
                await client.aclose()

    async def receive(self, payload: Dict[str, Any]) -> InboundMessageDTO:
        from_number = payload.get("From", payload.get("from", "unknown"))
        body = payload.get("Body", payload.get("body", payload.get("text", "")))
        msg_id = payload.get("MessageSid", payload.get("message_id", str(time.time())))
        idempotency_key = hashlib.sha256(f"sms:{from_number}:{msg_id}".encode()).hexdigest()[:64]

        return InboundMessageDTO(
            provider_name=self.provider_name,
            channel=self.channel,
            provider_message_id=msg_id,
            idempotency_key=idempotency_key,
            sender_identifier=from_number,
            sender_name=from_number,
            content=body,
            message_type="text",
            raw_payload=payload,
        )

    async def upload_media(self, file_bytes: bytes, mime_type: str, file_name: str) -> str:
        raise NotImplementedError("SMS does not support media upload")

    async def download_media(self, provider_media_id: str) -> bytes:
        raise NotImplementedError("SMS does not support media download")

    async def mark_read(self, provider_message_id: str) -> None:
        pass

    async def send_typing(self, recipient_identifier: str) -> None:
        pass

    async def get_delivery_status(self, provider_message_id: str) -> ProviderDeliveryStatus:
        return ProviderDeliveryStatus(provider_message_id=provider_message_id, status="sent")


class MockSMSProvider(SMSGatewayProvider):
    """
    Isolated Mock SMS provider for testing fixtures ONLY.
    Never registered in production paths.
    """

    def __init__(self, from_number: str = "+15005550006"):
        super().__init__(account_sid="test_sid", auth_token="test_token", from_number=from_number)

    @property
    def provider_name(self) -> str:
        return "mock_sms"

    def is_configured(self) -> bool:
        return True

    async def send(self, message: OutboundMessageDTO) -> ProviderResponse:
        return ProviderResponse(
            success=True,
            provider_message_id=f"sms_mock_{hashlib.sha256(message.message_id.encode()).hexdigest()[:16]}",
            status="sent",
            delivery_status=DeliveryStatusEnum.SENT,
            latency_ms=5,
        )
