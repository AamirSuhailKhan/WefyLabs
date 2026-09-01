import uuid
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.developer_models import DeveloperApiKey, WebhookSubscription
from app.core.events.event_bus import DomainEventBus, DomainEvent

router = APIRouter(prefix="/developer", tags=["Developer Platform & Webhook Framework"])

# --- Schemas ---
class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., max_length=100)
    scopes: List[str] = Field(default_factory=lambda: ["leads:read", "leads:write"])

class CreateApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    raw_api_key: str # Returned ONCE upon creation
    scopes: List[str]
    created_at: str

class ApiKeyInfoResponse(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    is_active: bool
    created_at: str

class CreateWebhookRequest(BaseModel):
    target_url: str = Field(..., max_length=500)
    events: List[str] = Field(default_factory=lambda: ["LeadCreated", "LeadQualified", "DealWon"])

class WebhookResponse(BaseModel):
    id: str
    target_url: str
    secret: str
    events: List[str]
    is_active: bool

class PublishEventRequest(BaseModel):
    event_name: str # e.g. LeadCreated, LeadQualified, DealWon
    payload: Dict[str, Any]

class PublishEventResponse(BaseModel):
    event_id: str
    event_name: str
    subscribers_notified: int


# --- Endpoints ---

@router.post("/api-keys", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_developer_api_key(
    req: CreateApiKeyRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a new secure Developer API Key with custom scopes (Stripe / Shopify grade).
    """
    random_secret = secrets.token_hex(20)
    raw_key = f"btl_live_{random_secret}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:12]

    key_record = DeveloperApiKey(
        broker_id=current_broker.id,
        name=req.name,
        api_key_hash=key_hash,
        prefix=prefix,
        scopes=req.scopes,
        is_active=True
    )

    db.add(key_record)
    await db.commit()
    await db.refresh(key_record)

    return CreateApiKeyResponse(
        id=str(key_record.id),
        name=key_record.name,
        prefix=key_record.prefix,
        raw_api_key=raw_key,
        scopes=key_record.scopes,
        created_at=key_record.created_at.isoformat() if key_record.created_at else ""
    )


@router.get("/api-keys", response_model=List[ApiKeyInfoResponse])
async def list_developer_api_keys(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists all active developer API keys for the current workspace."""
    stmt = select(DeveloperApiKey).where(DeveloperApiKey.broker_id == current_broker.id, DeveloperApiKey.is_active.is_(True))
    res = await db.execute(stmt)
    keys = res.scalars().all()

    return [
        ApiKeyInfoResponse(
            id=str(k.id),
            name=k.name,
            prefix=k.prefix,
            scopes=k.scopes,
            is_active=k.is_active,
            created_at=k.created_at.isoformat() if k.created_at else ""
        )
        for k in keys
    ]


@router.post("/webhooks", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def register_webhook_subscription(
    req: CreateWebhookRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Registers a real-time HTTP Webhook Endpoint for CRM domain events."""
    webhook_secret = f"whsec_{secrets.token_hex(16)}"

    sub = WebhookSubscription(
        broker_id=current_broker.id,
        target_url=req.target_url,
        secret=webhook_secret,
        events=[e.strip() for e in req.events],
        is_active=True
    )

    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return WebhookResponse(
        id=str(sub.id),
        target_url=sub.target_url,
        secret=sub.secret,
        events=sub.events,
        is_active=sub.is_active
    )


@router.get("/webhooks", response_model=List[WebhookResponse])
async def list_webhook_subscriptions(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists all active webhook subscriptions for the current broker."""
    stmt = select(WebhookSubscription).where(WebhookSubscription.broker_id == current_broker.id, WebhookSubscription.is_active.is_(True))
    res = await db.execute(stmt)
    subs = res.scalars().all()

    return [
        WebhookResponse(
            id=str(s.id),
            target_url=s.target_url,
            secret=s.secret,
            events=s.events,
            is_active=s.is_active
        )
        for s in subs
    ]


@router.post("/events/publish", response_model=PublishEventResponse)
async def publish_domain_event_endpoint(
    req: PublishEventRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Dispatches a domain event through the DomainEventBus to notify all active subscribers and plugins."""
    evt = DomainEvent(
        event_id=f"evt_{secrets.token_hex(8)}",
        event_name=req.event_name,
        tenant_id=str(current_broker.id),
        payload=req.payload
    )

    notified = await DomainEventBus.publish(evt)

    return PublishEventResponse(
        event_id=evt.event_id,
        event_name=evt.event_name,
        subscribers_notified=notified
    )
