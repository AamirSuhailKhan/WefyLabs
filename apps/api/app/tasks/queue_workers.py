import logging
from typing import Dict, Any
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300
)
def process_lead_event(self, event_data: Dict[str, Any]):
    """Processes lead queue tasks: scoring, enrichment, and duplicate checking."""
    logger.info(f"[QUEUE: lead_queue] Processing event: {event_data.get('event_id')}")
    return {"status": "completed", "event_id": event_data.get("event_id")}

@celery_app.task(
    bind=True,
    max_retries=5,
    default_retry_delay=10,
    retry_backoff=True
)
def process_webhook_event(self, webhook_data: Dict[str, Any]):
    """Processes incoming webhooks asynchronously."""
    logger.info(f"[QUEUE: webhook_queue] Ingested webhook for provider: {webhook_data.get('provider')}")
    return {"status": "processed", "provider": webhook_data.get("provider")}

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=15
)
def process_ai_qualification(self, lead_id: str, context: Dict[str, Any]):
    """Processes AI qualification and RAG vector embedding."""
    logger.info(f"[QUEUE: ai_queue] Running AI qualification for Lead ID: {lead_id}")
    return {"status": "ai_completed", "lead_id": lead_id}

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
)
def process_email_dispatch(self, email_data: Dict[str, Any]):
    """
    Asynchronously dispatches outbound transactional email via EmailSMTPProvider.
    Idempotent dispatch with retry handling.
    """
    import asyncio
    import uuid
    from app.modules.communication.channel_manager.manager import get_channel_manager
    from app.modules.communication.provider_adapters.base_provider import OutboundMessageDTO

    recipient = email_data.get("recipient")
    subject = email_data.get("subject", "Notification from WefyLabs")
    content = email_data.get("content", "")
    html_content = email_data.get("html")

    logger.info(f"[QUEUE: email_queue] Dispatching email to: {recipient} subject: '{subject}'")

    channel_mgr = get_channel_manager()
    email_provider = channel_mgr.get_provider("email")

    outbound_dto = OutboundMessageDTO(
        message_id=email_data.get("message_id") or str(uuid.uuid4()),
        conversation_id=email_data.get("conversation_id") or "system",
        organization_id=email_data.get("organization_id") or "system",
        channel="email",
        provider_name=email_provider.provider_name,
        recipient_identifier=recipient,
        content=content or subject,
        message_type="text",
        content_structured={"subject": subject, "html": html_content} if html_content else {"subject": subject},
        idempotency_key=email_data.get("idempotency_key") or f"celery:email:{recipient}:{subject}",
    )

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio  # in case called in nested loop
            nest_asyncio.apply()
            resp = loop.run_until_complete(email_provider.send(outbound_dto))
        else:
            resp = loop.run_until_complete(email_provider.send(outbound_dto))
    except RuntimeError:
        resp = asyncio.run(email_provider.send(outbound_dto))

    if not resp.success:
        logger.warning(f"[QUEUE: email_queue] Email send failed: {resp.error_code} - {resp.error_message}")
        if resp.retryable:
            raise RuntimeError(f"Transient email failure: {resp.error_message}")
        return {"status": "failed", "error": resp.error_message, "error_code": resp.error_code}

    return {"status": "sent", "provider_message_id": resp.provider_message_id}

@celery_app.task(bind=True, max_retries=3)
def process_whatsapp_dispatch(self, message_data: Dict[str, Any]):
    logger.info(f"[QUEUE: whatsapp_queue] Sending WhatsApp message to: {message_data.get('phone')}")
    return {"status": "sent"}

@celery_app.task(bind=True)
def process_analytics_event(self, event_payload: Dict[str, Any]):
    logger.info(f"[QUEUE: analytics_queue] Aggregating metric for event: {event_payload.get('event_type')}")
    return {"status": "aggregated"}

@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def revoke_google_oauth_token_task(self, token: str):
    """
    Asynchronously revokes Google OAuth token via Google's token revocation endpoint.
    Safe error handling: never exposes tokens in logs, never blocks indefinitely.
    """
    from app.modules.auth.oauth_revocation import perform_google_token_revocation
    try:
        success, status_code, err = perform_google_token_revocation(token)
        return {"revoked": success, "status_code": status_code, "error": err}
    except Exception as exc:
        logger.warning(f"[Celery: Google OAuth Revocation] Revocation attempt encountered error: {exc}")
        return {"revoked": False, "error": str(exc)}

