from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.core.integrations.provider_interface import IntegrationRegistry

router = APIRouter(prefix="/integrations", tags=["WefyLabs Integration Platform Engine"])

# --- Schemas ---
class IntegrationProviderInfo(BaseModel):
    provider_id: str
    category: str

class CreateCalendarEventRequest(BaseModel):
    provider_id: str = "google_calendar" # google_calendar | microsoft_outlook
    title: str
    start_time: str
    end_time: str
    attendees: List[str]

class CreateSignatureRequest(BaseModel):
    provider_id: str = "docusign" # docusign | adobe_sign
    document_name: str
    signer_email: str

class PublishPortalRequest(BaseModel):
    provider_id: str = "property_finder" # property_finder | zillow | magicbricks
    property_id: str
    title: str
    price: float
    location: str


# --- Endpoints ---

@router.get("/providers", response_model=List[IntegrationProviderInfo])
async def list_integration_providers():
    """Lists all available integration providers decoupled by vendor abstraction."""
    return IntegrationRegistry.list_active_providers()

@router.post("/calendar/events")
async def create_calendar_event_endpoint(
    req: CreateCalendarEventRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Dispatches calendar event creation via abstract CalendarProvider (Google Calendar / Outlook)."""
    try:
        provider = IntegrationRegistry.get_provider(req.provider_id)
        if provider.category != "calendar":
            raise HTTPException(status_code=400, detail=f"Provider {req.provider_id} is not a calendar provider")
        
        return await provider.create_event(
            title=req.title,
            start_time=req.start_time,
            end_time=req.end_time,
            attendees=req.attendees
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/signature/request")
async def create_signature_request_endpoint(
    req: CreateSignatureRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Dispatches E-Signature request via abstract SignatureProvider (DocuSign / Adobe Sign)."""
    try:
        provider = IntegrationRegistry.get_provider(req.provider_id)
        if provider.category != "e_signature":
            raise HTTPException(status_code=400, detail=f"Provider {req.provider_id} is not an e-signature provider")

        return await provider.create_signature_request(
            document_name=req.document_name,
            signer_email=req.signer_email
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/portal/publish")
async def publish_portal_listing_endpoint(
    req: PublishPortalRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Publishes property listing via abstract PortalSyndicationProvider (Property Finder / Zillow / MagicBricks)."""
    try:
        provider = IntegrationRegistry.get_provider(req.provider_id)
        if provider.category != "portal_syndication":
            raise HTTPException(status_code=400, detail=f"Provider {req.provider_id} is not a portal syndication provider")

        return await provider.publish_listing(
            property_id=req.property_id,
            title=req.title,
            price=req.price,
            location=req.location
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
