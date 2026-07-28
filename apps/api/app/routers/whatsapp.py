from typing import Dict, Any
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.services.conversation_service import process_incoming_whatsapp_message

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

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
    Always returns 200 OK to prevent infinite webhook retries.
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "ok", "detail": "Invalid or empty JSON body"}

    try:
        result = await process_incoming_whatsapp_message(db, data)
        return {"status": "ok", "result": result}
    except Exception as e:
        print(f"[WhatsApp Webhook Error] {e}")
        return {"status": "ok", "detail": str(e)}
