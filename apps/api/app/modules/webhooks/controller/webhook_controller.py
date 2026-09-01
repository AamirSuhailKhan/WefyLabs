from fastapi import APIRouter, Request, Header, HTTPException, status
from typing import Optional, Dict
import json

from app.common.response import APIResponse, create_success_response
from app.modules.webhooks.service.webhook_service import GenericWebhookEngineService
from app.modules.webhooks.dto.webhook_dto import WebhookPayloadDTO

router = APIRouter(prefix="/v1/webhooks", tags=["Webhooks Framework V1"])

webhook_service = GenericWebhookEngineService()

@router.post("/{provider}", response_model=APIResponse)
async def receive_webhook(
    provider: str,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_timestamp: Optional[str] = Header(None, alias="X-Timestamp"),
    x_nonce: Optional[str] = Header(None, alias="X-Nonce")
):
    raw_body = await request.body()
    try:
        json_payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        json_payload = {}

    dto = WebhookPayloadDTO(
        provider=provider,
        event_type=json_payload.get("event", "generic_webhook"),
        payload=json_payload,
        signature=x_signature or request.headers.get("x-hub-signature-256"),
        timestamp=x_timestamp,
        nonce=x_nonce
    )

    headers_dict = dict(request.headers)
    result = await webhook_service.ingest_webhook(dto, raw_body, headers_dict)
    
    return create_success_response(
        data=result,
        request_id=getattr(request.state, "correlation_id", "")
    )
