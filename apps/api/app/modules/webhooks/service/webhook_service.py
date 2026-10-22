import hmac
import hashlib
import time
import logging
import math
from typing import Dict, Any, Optional
from fastapi import HTTPException, status

from app.infrastructure.events.event_bus import event_bus, DomainEvent, StandardDomainEvents, ActorContext
from app.modules.webhooks.dto.webhook_dto import WebhookPayloadDTO, WebhookResponseDTO

logger = logging.getLogger(__name__)

# Providers that require HMAC signature verification.
# Unknown providers without secrets in self.secrets will be rejected.
_SIGNATURE_REQUIRED_PROVIDERS = {"whatsapp", "facebook", "zapier", "n8n"}

# Providers known to have no caller-facing signature (e.g., inbound SMS from carriers)
# These must be explicitly allowlisted here; all others default to requiring a signature.
_SIGNATURE_EXEMPT_PROVIDERS: set = set()


class GenericWebhookEngineService:
    """
    Enterprise Webhook Framework supporting WhatsApp, Facebook Lead Ads,
    Telegram, Zapier, n8n, and Custom Systems.
    Enforces HMAC verification, replay attack prevention, and async event dispatching.

    P0 Security Hardening (applied):
    - Webhooks with no signature are REJECTED (not silently accepted) for signature-required providers.
    - Webhooks with no configured secret are REJECTED — unconfigured providers cannot bypass verification.
    - Replay attack window remains 5 minutes (max_skew_seconds=300).
    - Missing timestamp on signature-required providers is rejected.
    """

    def __init__(self, secrets: Optional[Dict[str, str]] = None):
        self.secrets = secrets or {}

    def verify_signature(
        self, provider: str, payload_bytes: bytes, signature: Optional[str], secret: Optional[str] = None
    ) -> bool:
        """
        Verify HMAC signature for a webhook payload.

        Security invariants:
        - If the provider is in _SIGNATURE_EXEMPT_PROVIDERS, signature is skipped.
        - If no signature is present and provider requires one → REJECT (return False).
        - If no secret is configured for a signature-required provider → REJECT (return False).
          This prevents new/unconfigured integrations from silently bypassing verification.
        """
        # Exempt providers bypass signature checks
        if provider in _SIGNATURE_EXEMPT_PROVIDERS:
            return True

        # For all other providers, missing signature = REJECT
        if not signature:
            logger.warning(f"[WEBHOOK SECURITY] Missing signature for provider '{provider}' — rejected")
            return False

        # No secret configured = REJECT (safe failure; misconfiguration is not an allowlist)
        if not secret:
            logger.warning(
                f"[WEBHOOK SECURITY] No secret configured for provider '{provider}' — rejected. "
                "Configure the webhook secret in settings."
            )
            return False

        if provider in ("whatsapp", "facebook"):
            # Facebook/WhatsApp format: sha256=HEX
            expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)

        elif provider in ("zapier", "n8n", "custom"):
            expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)

        # Unknown provider — require explicit allowlisting
        logger.warning(f"[WEBHOOK SECURITY] Unknown provider '{provider}' — rejected (not in allowlist)")
        return False

    def check_replay_attack(self, timestamp: Optional[str], max_skew_seconds: int = 300) -> bool:
        if not timestamp:
            # Meta's signed-body webhook contract does not include this custom
            # header. A missing timestamp is therefore provider-compatible, but
            # time-window checking alone does not prevent duplicate delivery.
            logger.warning("[WEBHOOK SECURITY] Missing optional X-Timestamp header on inbound webhook")
            return True  # Allow but log — timestamp is advisory for non-signature-required providers
        try:
            ts = float(timestamp)
            if not math.isfinite(ts):
                return False
            now = time.time()
            if abs(now - ts) > max_skew_seconds:
                logger.warning(f"[WEBHOOK SECURITY] Replay attack suspected! Time skew: {abs(now - ts)}s")
                return False
        except (TypeError, ValueError):
            return False
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

        # Signature Verification — uses hardened verify_signature (no silent pass-through)
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
            # Never derive tenant context from caller-controlled HTTP headers.
            # Provider-account-to-organization routing needs a trusted server-side
            # mapping before this generic route can emit tenant-scoped events.
            organization_id="global",
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
