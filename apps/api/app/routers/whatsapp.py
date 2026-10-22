import hmac
import hashlib
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.modules.communication.canonical_service import canonical_communication_service

logger = logging.getLogger("wefylabs.whatsapp")
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

def verify_meta_signature(raw_body: bytes, signature_header: str, app_secret: str) -> bool:
    """Verifies X-Hub-Signature-256 header sent by Meta Cloud API."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_hash = signature_header.split("sha256=")[1]
    calculated_hash = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated_hash, expected_hash)

@router.get("/webhook")
@router.get("/webhook/")
async def whatsapp_webhook_verification(request: Request):
    """
    Meta Cloud API Direct verification handshake endpoint.
    Meta sends query params: hub.mode, hub.verify_token, hub.challenge.
    Returns raw plain-text challenge string when verify_token matches.
    """
    params = request.query_params
    mode = params.get("hub.mode", "").strip() if params.get("hub.mode") else ""
    token = params.get("hub.verify_token", "").strip() if params.get("hub.verify_token") else ""
    challenge = params.get("hub.challenge", "")

    expected_token = (settings.WHATSAPP_VERIFY_TOKEN or "").strip()

    if mode == "subscribe" and token == expected_token and challenge:
        # Meta MUST receive ONLY the raw plain text challenge with HTTP 200 OK
        return Response(content=str(challenge), status_code=status.HTTP_200_OK, media_type="text/plain")

    if mode or token or challenge:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification token mismatch or invalid mode"
        )

    return Response(content="WhatsApp Webhook Active", status_code=status.HTTP_200_OK, media_type="text/plain")

@router.post("/webhook")
@router.post("/webhook/")
async def whatsapp_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Incoming WhatsApp webhook listener for Meta Cloud API Direct and 360dialog.
    Processes webhook via the canonical communication engine:
    1. Authenticates Meta HMAC signature (fail-closed)
    2. Archives raw event to RawCommunicationEvent
    3. Guarantees webhook idempotency
    4. Normalizes phone to E.164 and resolves Identity Graph node
    5. Resolves or creates canonical OmnichannelConversation and ChannelMessage
    6. Processes delivery receipts (sent -> delivered -> read | failed)
    7. Emits transactional OutboxEvent
    """
    raw_body = await request.body()
    headers_dict = dict(request.headers)

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook body must contain valid JSON.",
        )
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook JSON body must be an object.",
        )

    try:
        result = await canonical_communication_service.ingest_inbound_webhook(
            db=db,
            provider_name="whatsapp_cloud",
            raw_body=raw_body,
            headers=headers_dict,
            parsed_payload=data,
            enforce_signature=True,
        )
        return {"status": "ok", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WhatsApp Webhook Error] {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WhatsApp webhook processing failed. The provider may retry delivery.",
        ) from e

