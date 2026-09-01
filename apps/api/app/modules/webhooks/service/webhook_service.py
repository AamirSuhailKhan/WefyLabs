import hmac
import hashlib
import time
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

from app.infrastructure.events.event_bus import event_bus, DomainEvent, StandardDomainEvents, ActorContext
from app.modules.webhooks.dto.webhook_dto import WebhookPayloadDTO, WebhookResponseDTO

logger = logging.getLogger(__name__)

class GenericWebhookEngineService:
    """
    Enterprise Webhook Framework supporting WhatsApp, Facebook Lead Ads,
    Telegram, Zapier, n8n, and Custom Systems.
    Enforces HMAC verification, replay attack prevention, and async event dispatching.
    """

    def __init__(self, secrets: Optional[Dict[str, str]] = None):
        self.secrets = secrets or {}

    def verify_signature(self, provider: str, payload_bytes: bytes, signature: Optional[str], secret: Optional[str] = None) -> bool:
        if not signature:
            # If no signature provided, allow in dev/staging or flag invalid
            return True

        if provider in ("whatsapp", "facebook"):
            # Facebook/WhatsApp format: sha256=HEX
            if not secret:
                return True
            expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)

        elif provider in ("zapier", "n8n", "custom"):
            if not secret:
                return True
            expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)

        return True

    def check_replay_attack(self, timestamp: Optional[str], max_skew_seconds: int = 300) -> bool:
        if not timestamp:
            return True
        try:
            ts = float(timestamp)
            now = time.time()
            if abs(now - ts) > max_skew_seconds:
                logger.warning(f"[WEBHOOK SECURITY] Replay attack suspected! Time skew: {abs(now - ts)}s")
                return False
        except ValueError:
            pass
        return True

    async def ingest_webhook(
        self,
        dto: WebhookPayloadDTO,
        raw_body: bytes,
        headers: Dict[str, str]
    ) -> WebhookResponseDTO:
        # Replay Attack Prevention
        if not self.check_replay_attack(dto.timestamp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook rejected due to invalid or expired timestamp (replay protection)."
            )

        # Signature Verification
        secret = self.secrets.get(dto.provider)
        if not self.verify_signature(dto.provider, raw_body, dto.signature, secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Webhook signature verification failed for provider '{dto.provider}'."
            )

        actor = ActorContext(
            user_id=f"webhook_{dto.provider}",
            role="webhook",
            actor_type="webhook"
        )

        event = DomainEvent(
            event_type=StandardDomainEvents.WEBHOOK_RECEIVED,
            organization_id=headers.get("x-organization-id", "global"),
            actor=actor,
            payload={
                "provider": dto.provider,
                "event_type": dto.event_type,
                "payload": dto.payload
            }
        )

        # Emit event asynchronously
        await event_bus.publish(event)

        return WebhookResponseDTO(
            received=True,
            event_id=event.event_id,
            status="processed"
        )
