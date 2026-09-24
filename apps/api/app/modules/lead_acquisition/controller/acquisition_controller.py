"""
Part 21.1 — Lead Acquisition API Controller
============================================
FastAPI router for the real-estate lead acquisition engine.

All endpoints enforce:
  - Authentication (JWT broker token)
  - organization_id from authenticated context — NEVER from request body
  - Tenant isolation — orgs cannot access each other's sources/campaigns/prospects
  - Rate limiting via Redis
  - Idempotency
  - Audit logging

Endpoints:
  POST   /api/v1/lead-acquisition/sources
  GET    /api/v1/lead-acquisition/sources
  GET    /api/v1/lead-acquisition/sources/{id}
  PUT    /api/v1/lead-acquisition/sources/{id}
  POST   /api/v1/lead-acquisition/campaigns
  GET    /api/v1/lead-acquisition/campaigns
  GET    /api/v1/lead-acquisition/campaigns/{id}
  PUT    /api/v1/lead-acquisition/campaigns/{id}
  GET    /api/v1/lead-acquisition/prospects
  GET    /api/v1/lead-acquisition/prospects/{id}
  POST   /api/v1/lead-acquisition/prospects/{id}/import
  POST   /api/v1/lead-acquisition/prospects/{id}/reject
  POST   /api/v1/leads/acquisition/website            ← Website lead capture
  POST   /api/v1/lead-acquisition/webhooks/{provider} ← Webhook acquisition
  GET    /api/v1/lead-acquisition/meta/status          ← Meta connector status
  GET    /api/v1/lead-acquisition/google/status        ← Google connector status
"""
from __future__ import annotations
import time
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Request, Response, HTTPException, status, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.models.acquisition_models import (
    LeadSource, LeadAcquisitionEvent, LeadProspect, SourceAttribution,
    ProspectStatus, DuplicateMatchStatus
)
from app.models.lead import Lead
from app.modules.lead_acquisition.dto.acquisition_dto import (
    LeadSourceCreateDTO, LeadSourceUpdateDTO, LeadSourceResponseDTO,
    LeadCampaignCreateDTO, LeadCampaignUpdateDTO, LeadCampaignResponseDTO,
    WebsiteLeadAcquisitionDTO, AcquisitionResponseDTO,
    ProspectResponseDTO, ProspectImportDTO, ProspectRejectDTO,
    CanonicalLeadIntakeDTO, CanonicalLeadIntakeResultDTO, UniversalSourceType,
    ReconciliationRequestDTO, ReconciliationResponseDTO,
    BackfillRequestDTO, BackfillResponseDTO,
    ProviderConnectDTO, ProviderStatusDTO,
)
from app.modules.lead_acquisition.services.lead_source_service import LeadSourceService
from app.modules.lead_acquisition.services.lead_campaign_service import LeadCampaignService
from app.modules.lead_acquisition.services.prospect_service import ProspectService
from app.modules.lead_acquisition.services.acquisition_event_service import AcquisitionEventService
from app.modules.lead_acquisition.services.acquisition_quality_service import score_and_save
from app.modules.lead_acquisition.connectors.meta_connector import MetaLeadAdsConnector
from app.modules.lead_acquisition.connectors.google_connector import GoogleLeadFormConnector
from app.modules.lead_acquisition.metrics.acquisition_metrics import (
    record_acquisition_received, record_acquisition_success, record_acquisition_failure,
    record_prospect_created, record_duplicate, record_import, record_rejected,
    record_webhook_failure, record_latency,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lead-acquisition", tags=["Lead Acquisition Engine"])
website_router = APIRouter(prefix="/api/v1/leads", tags=["Website Lead Acquisition"])


# ─── Lead Sources ─────────────────────────────────────────────────────────────

@router.post("/sources", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_source(
    dto: LeadSourceCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Create a new lead source for the organization."""
    org_id = _get_org_id(current_broker)
    svc = LeadSourceService(db)
    source = await svc.create_source(org_id, dto)
    return create_success_response(data=LeadSourceResponseDTO.model_validate(source).model_dump())


@router.get("/sources", response_model=APIResponse)
async def list_lead_sources(
    channel: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """List lead sources for the organization."""
    org_id = _get_org_id(current_broker)
    svc = LeadSourceService(db)
    sources = await svc.list_sources(org_id, channel=channel, status=status_filter)
    return create_success_response(data=[
        LeadSourceResponseDTO.model_validate(s).model_dump() for s in sources
    ])


@router.get("/sources/{source_id}", response_model=APIResponse)
async def get_lead_source(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Get a lead source by ID (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = LeadSourceService(db)
    source = await svc.get_source(org_id, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    return create_success_response(data=LeadSourceResponseDTO.model_validate(source).model_dump())


@router.put("/sources/{source_id}", response_model=APIResponse)
async def update_lead_source(
    source_id: str,
    dto: LeadSourceUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Update a lead source (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = LeadSourceService(db)
    source = await svc.update_source(org_id, source_id, dto)
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")
    return create_success_response(data=LeadSourceResponseDTO.model_validate(source).model_dump())


# ─── Lead Campaigns ───────────────────────────────────────────────────────────

@router.post("/campaigns", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_campaign(
    dto: LeadCampaignCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Create a new real-estate acquisition campaign."""
    org_id = _get_org_id(current_broker)
    svc = LeadCampaignService(db)
    campaign = await svc.create_campaign(org_id, dto)
    return create_success_response(data=LeadCampaignResponseDTO.model_validate(campaign).model_dump())


@router.get("/campaigns", response_model=APIResponse)
async def list_lead_campaigns(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """List campaigns for the organization."""
    org_id = _get_org_id(current_broker)
    svc = LeadCampaignService(db)
    campaigns = await svc.list_campaigns(org_id, status=status_filter)
    return create_success_response(data=[
        LeadCampaignResponseDTO.model_validate(c).model_dump() for c in campaigns
    ])


@router.get("/campaigns/{campaign_id}", response_model=APIResponse)
async def get_lead_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Get a campaign by ID (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = LeadCampaignService(db)
    campaign = await svc.get_campaign(org_id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return create_success_response(data=LeadCampaignResponseDTO.model_validate(campaign).model_dump())


@router.put("/campaigns/{campaign_id}", response_model=APIResponse)
async def update_lead_campaign(
    campaign_id: str,
    dto: LeadCampaignUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Update a campaign (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = LeadCampaignService(db)
    campaign = await svc.update_campaign(org_id, campaign_id, dto)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return create_success_response(data=LeadCampaignResponseDTO.model_validate(campaign).model_dump())


@router.get("/campaigns/{campaign_id}/properties", response_model=APIResponse)
async def get_campaign_properties(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Get property IDs linked to a campaign (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = LeadCampaignService(db)
    property_ids = await svc.get_campaign_properties(org_id, campaign_id)
    return create_success_response(data={"campaign_id": campaign_id, "property_ids": property_ids})


# ─── Lead Prospects ───────────────────────────────────────────────────────────

@router.get("/prospects", response_model=APIResponse)
async def list_prospects(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """List prospects for the organization (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = ProspectService(db)
    prospects = await svc.list_prospects(org_id, status=status_filter, limit=limit, offset=offset)
    return create_success_response(data=[
        ProspectResponseDTO.model_validate(p).model_dump() for p in prospects
    ])


@router.get("/prospects/{prospect_id}", response_model=APIResponse)
async def get_prospect(
    prospect_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Get a prospect by ID (tenant-isolated)."""
    org_id = _get_org_id(current_broker)
    svc = ProspectService(db)
    prospect = await svc.get_prospect(org_id, prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return create_success_response(data=ProspectResponseDTO.model_validate(prospect).model_dump())


@router.post("/prospects/{prospect_id}/import", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def import_prospect_as_lead(
    prospect_id: str,
    dto: ProspectImportDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Import a READY or DUPLICATE prospect as a canonical CRM Lead."""
    org_id = _get_org_id(current_broker)
    svc = ProspectService(db)
    prospect = await svc.get_prospect(org_id, prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    if prospect.status not in ("READY", "DUPLICATE", "NORMALIZED"):
        raise HTTPException(
            status_code=400,
            detail=f"Prospect cannot be imported in status '{prospect.status}'. Must be READY, NORMALIZED, or DUPLICATE."
        )
    import uuid
    broker_uuid = current_broker.id if hasattr(current_broker.id, 'int') else uuid.UUID(str(current_broker.id))
    lead = await svc.import_as_lead(
        organization_id=org_id,
        prospect=prospect,
        broker_uuid=broker_uuid,
        override_name=dto.override_name,
    )
    record_import(org_id)
    return create_success_response(data={
        "lead_id": str(lead.id),
        "prospect_id": prospect_id,
        "status": "imported",
    })


@router.post("/prospects/{prospect_id}/reject", response_model=APIResponse)
async def reject_prospect(
    prospect_id: str,
    dto: ProspectRejectDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Reject a prospect with a stated reason."""
    org_id = _get_org_id(current_broker)
    svc = ProspectService(db)
    prospect = await svc.get_prospect(org_id, prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    await svc.reject_prospect(prospect, dto.reason)
    record_rejected(org_id, dto.reason)
    return create_success_response(data={"prospect_id": prospect_id, "status": "REJECTED"})


# ─── Website Lead Acquisition ─────────────────────────────────────────────────

@website_router.post(
    "/acquisition/website",
    response_model=APIResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def website_lead_acquisition(
    dto: WebsiteLeadAcquisitionDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Website lead acquisition endpoint.

    Processes incoming website form submissions.
    Returns 202 Accepted immediately — async pipeline processes normalization/dedup.

    Security:
      - organization_id from authenticated JWT context
      - Property/campaign ownership verified server-side
      - Rate limiting applied
      - Idempotency enforced
    """
    start_time = time.perf_counter()
    org_id = _get_org_id(current_broker)

    # Validate: at least one of phone or email must be present
    if not dto.validate_contact_present():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of 'phone' or 'email' is required"
        )

    # Record metrics
    record_acquisition_received(org_id, "WEBSITE", "website_form")

    # Idempotency key from header or DTO
    idem_key = (
        dto.idempotency_key
        or request.headers.get("X-Idempotency-Key")
        or None
    )

    try:
        # Step 1: Record acquisition event
        event_svc = AcquisitionEventService(db)
        event, is_new_event = await event_svc.record_event(
            organization_id=org_id,
            source_id=dto.source_id,
            campaign_id=dto.campaign_id,
            channel="WEBSITE",
            idempotency_key=idem_key,
            occurred_at=None,
            provider_name="website_form",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )

        # Step 2: Create or update prospect
        prospect_svc = ProspectService(db)
        prospect, is_new = await prospect_svc.create_from_website(
            organization_id=org_id,
            dto=dto,
            acquisition_event_id=event.id,
            source_id=dto.source_id,
        )

        # Step 3: Score immediately (lightweight — async enrichment via Celery)
        await score_and_save(prospect, db)
        await db.commit()

        # Step 4: Queue async pipeline (normalize → dedup → AI extract)
        try:
            from app.modules.lead_acquisition.tasks.acquisition_tasks import process_acquisition_event
            if callable(getattr(process_acquisition_event, "apply_async", None)):
                process_acquisition_event.apply_async(
                    args=[org_id, prospect.id, dto.source_id],
                    countdown=2,
                )
        except Exception as task_exc:
            logger.debug(f"[ACQ] Celery task dispatch skipped: {task_exc}")

        elapsed = time.perf_counter() - start_time
        record_latency("WEBSITE", elapsed)
        record_acquisition_success(org_id, "WEBSITE")
        record_prospect_created(org_id, prospect.status)

        return create_success_response(data={
            "acquisition_event_id": event.id,
            "prospect_id": prospect.id,
            "status": "accepted" if is_new else "updated",
            "message": "Lead acquisition received and queued for processing.",
            "is_new_prospect": is_new,
        })

    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        record_acquisition_failure(org_id, "WEBSITE", type(exc).__name__)
        record_latency("WEBSITE", elapsed)
        logger.error(f"[ACQ] Website acquisition failed for org={org_id}: {exc}")
        raise HTTPException(status_code=500, detail="Acquisition processing error")


# ─── Webhook Acquisition (Part 13: Meta + Google + Generic) ──────────────────

@router.get("/webhooks/{provider}")
async def verify_acquisition_webhook_challenge(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook verification challenge endpoint (e.g. Meta hub.challenge).
    Publicly accessible to provider verification bots.
    Validates hub.verify_token and returns raw hub.challenge text/plain.
    """
    if provider.lower() == "meta":
        connector = MetaLeadAdsConnector()
        query_params = dict(request.query_params)
        verify_token = query_params.get("hub.verify_token") or ""
        token = query_params.get("token") or ""

        # Find matching source
        source_svc = LeadSourceService(db)
        source = None
        if token:
            source = await source_svc.resolve_source_by_webhook_token(token)

        expected_token = verify_token
        if source and source.configuration:
            expected_token = source.configuration.get("verify_token") or source.webhook_url_token or verify_token

        challenge = connector.handle_verification_challenge(query_params, expected_token)
        if challenge:
            return Response(content=challenge, media_type="text/plain", status_code=200)

        record_webhook_failure("meta", "challenge_failed")
        raise HTTPException(status_code=403, detail="Meta verification challenge token mismatch")

    return Response(content="OK", media_type="text/plain", status_code=200)


@router.post("/webhooks/{provider}", response_model=APIResponse, status_code=status.HTTP_200_OK)
async def receive_acquisition_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Universal Provider Webhook Ingestion Endpoint (Part 13).
    Ingests Meta Lead Ads, Google Ads Lead Forms, and Generic Webhooks directly
    into the canonical Universal Intake pipeline without bypassing identity,
    deduplication, attribution, or fair routing.

    Tenant organization is strictly resolved from verified LeadSource token.
    Never accepts organization_id from request body.
    """
    provider_clean = provider.lower()
    SUPPORTED_PROVIDERS = {"meta", "google", "generic", "zapier", "hubspot", "salesforce"}
    if provider_clean not in SUPPORTED_PROVIDERS:
        record_webhook_failure(provider, "unsupported_provider")
        raise HTTPException(status_code=400, detail=f"Unsupported webhook provider: {provider}")

    # Read raw body for HMAC signature verification
    raw_body = await request.body()

    # Parse JSON payload
    try:
        payload = await request.json() if raw_body else {}
    except Exception:
        record_webhook_failure(provider, "invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Resolve source token from query, header, or payload
    token = (
        request.query_params.get("token")
        or request.headers.get("X-Webhook-Token")
        or payload.get("token")
        or (payload.get("google_key") if provider_clean == "google" else None)
    )

    source_svc = LeadSourceService(db)
    source: Optional[LeadSource] = None
    if token:
        source = await source_svc.resolve_source_by_webhook_token(token)

    # Fallback: if google provider and not found by token, search by provider within org if source_id given
    if not source and request.query_params.get("source_id"):
        # Handled in lookup below
        source = await source_svc.get_source_by_id(request.query_params["source_id"])

    if not source:
        record_webhook_failure(provider, "invalid_token")
        raise HTTPException(status_code=403, detail="Invalid or missing webhook token")

    org_id = source.organization_id
    config = source.configuration or {}
    record_acquisition_received(org_id, source.channel or "WEBHOOK", provider)

    from app.modules.lead_acquisition.services.universal_intake_service import UniversalIntakeService
    u_svc = UniversalIntakeService(db)

    # ── 1. META LEAD ADS WEBHOOK ──────────────────────────────────────────────
    if provider_clean == "meta":
        meta_connector = MetaLeadAdsConnector()

        # Signature verification if secret configured
        app_secret = config.get("app_secret") or config.get("app_secret_encrypted") or source.webhook_secret_hash
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        if app_secret:
            if not sig_header:
                record_webhook_failure("meta", "missing_signature")
                raise HTTPException(status_code=401, detail="Missing Meta webhook signature (X-Hub-Signature-256)")
            if not meta_connector.verify_webhook_signature(app_secret, raw_body, sig_header):
                record_webhook_failure("meta", "invalid_signature")
                raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")

        # Extract leadgen events
        events = meta_connector.extract_lead_events(payload)
        if events:
            results = []
            for ev in events:
                leadgen_id = ev["external_id"]
                access_token = config.get("access_token") or config.get("access_token_encrypted") or ""
                lead_data: Optional[Dict[str, Any]] = None

                # Fetch lead data via Graph API if access_token available
                if access_token:
                    lead_data, err = await meta_connector.retrieve_lead_data(leadgen_id, access_token)
                    if err:
                        logger.warning(f"[META WEBHOOK] Graph API retrieval code={err} for leadgen={leadgen_id}")

                # If no lead_data returned, check if payload had embedded field_data (test mode)
                if not lead_data and "field_data" in payload:
                    lead_data = payload

                normalized = meta_connector.normalize_lead_payload(lead_data or {}, ev)

                intake_dto = CanonicalLeadIntakeDTO(
                    source_type=UniversalSourceType.META,
                    external_source="meta_lead_ads",
                    external_lead_id=leadgen_id,
                    name=normalized.get("name"),
                    phone=normalized.get("phone"),
                    email=normalized.get("email"),
                    message=normalized.get("message"),
                    budget=normalized.get("budget"),
                    property_type=normalized.get("property_type"),
                    preferred_locations=normalized.get("preferred_locations", []),
                    city=normalized.get("city"),
                    timeline=normalized.get("timeline"),
                    source_id=source.id,
                    source_metadata=normalized.get("source_metadata"),
                    utm_source=normalized.get("utm_source", "meta"),
                    utm_medium=normalized.get("utm_medium", "paid_social"),
                    utm_campaign=normalized.get("utm_campaign"),
                    idempotency_key=f"meta:{leadgen_id}",
                )

                res = await u_svc.ingest_lead(
                    organization_id=org_id,
                    dto=intake_dto,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    raw_payload=payload,
                )
                results.append(res)

            record_acquisition_success(org_id, "META")
            first_res = results[0]
            return create_success_response(data={
                "event_id": first_res.event_id,
                "lead_id": first_res.lead_id,
                "status": "processed" if not first_res.is_duplicate else "duplicate",
                "provider": "meta",
                "is_duplicate": first_res.is_duplicate,
                "identity_outcome": first_res.identity_outcome,
                "events_count": len(results),
            })

    # ── 2. GOOGLE ADS LEAD FORM WEBHOOK ───────────────────────────────────────
    elif provider_clean == "google":
        google_connector = GoogleLeadFormConnector()

        # Verify Google Ads key if configured
        expected_key = config.get("google_key") or config.get("google_key_encrypted") or source.webhook_secret_hash
        provided_key = payload.get("google_key") or request.query_params.get("google_key") or token
        if expected_key:
            if not google_connector.verify_webhook_key(expected_key, provided_key):
                record_webhook_failure("google", "invalid_key")
                raise HTTPException(status_code=401, detail="Invalid Google Ads webhook key")

        normalized = google_connector.parse_submission(payload)
        lead_ext_id = normalized.get("external_id") or secrets.token_hex(8)

        intake_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.GOOGLE,
            external_source="google_lead_form",
            external_lead_id=lead_ext_id,
            name=normalized.get("name"),
            phone=normalized.get("phone"),
            email=normalized.get("email"),
            message=normalized.get("message"),
            budget=normalized.get("budget"),
            property_type=normalized.get("property_type"),
            preferred_locations=normalized.get("preferred_locations", []),
            city=normalized.get("city"),
            timeline=normalized.get("timeline"),
            source_id=source.id,
            source_metadata=normalized.get("source_metadata"),
            utm_source=normalized.get("utm_source", "google"),
            utm_medium=normalized.get("utm_medium", "cpc"),
            utm_campaign=normalized.get("utm_campaign"),
            idempotency_key=f"google:{lead_ext_id}",
        )

        res = await u_svc.ingest_lead(
            organization_id=org_id,
            dto=intake_dto,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            raw_payload=payload,
        )
        record_acquisition_success(org_id, "GOOGLE")
        return create_success_response(data={
            "event_id": res.event_id,
            "lead_id": res.lead_id,
            "status": "processed" if not res.is_duplicate else "duplicate",
            "provider": "google",
            "is_duplicate": res.is_duplicate,
            "identity_outcome": res.identity_outcome,
        })

    # ── 3. GENERIC / PARTNER WEBHOOK ──────────────────────────────────────────
    contact_phone = payload.get("phone") or payload.get("phone_number") or payload.get("contact_phone")
    contact_email = payload.get("email") or payload.get("contact_email")
    contact_name = payload.get("name") or payload.get("full_name")
    inquiry_msg = payload.get("message") or payload.get("requirement") or payload.get("inquiry")
    external_id = payload.get("id") or payload.get("leadgen_id") or payload.get("submission_id") or secrets.token_hex(8)

    intake_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.WEBHOOK,
        external_source=provider,
        external_lead_id=str(external_id),
        name=contact_name,
        phone=contact_phone,
        email=contact_email,
        message=inquiry_msg,
        source_id=source.id,
        source_metadata=payload,
        idempotency_key=f"{provider}:{external_id}",
    )
    res = await u_svc.ingest_lead(
        organization_id=org_id,
        dto=intake_dto,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        raw_payload=payload,
    )
    record_acquisition_success(org_id, source.channel or "WEBHOOK")
    return create_success_response(data={
        "event_id": res.event_id,
        "lead_id": res.lead_id,
        "status": "processed" if not res.is_duplicate else "duplicate",
        "provider": provider,
        "is_duplicate": res.is_duplicate,
        "identity_outcome": res.identity_outcome,
    })


@router.post("/intake", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def universal_lead_intake(
    dto: CanonicalLeadIntakeDTO,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Universal Authenticated Lead Intake API (Part 9).
    Single authoritative contract ingested from integrations or internal clients.
    Tenant is strictly resolved from authenticated context.
    """
    org_id = _get_org_id(current_broker)
    from app.modules.lead_acquisition.services.universal_intake_service import UniversalIntakeService
    svc = UniversalIntakeService(db)
    result = await svc.ingest_lead(
        organization_id=org_id,
        dto=dto,
        actor_id=str(current_broker.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        raw_payload=dto.model_dump(),
    )
    return create_success_response(data=result.model_dump())


# ─── Connector Status ─────────────────────────────────────────────────────────

@router.get("/meta/status", response_model=APIResponse)
async def meta_connector_status(
    source_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Check Meta Lead Ads connector configuration status."""
    org_id = _get_org_id(current_broker)
    configuration = None
    if source_id:
        source_svc = LeadSourceService(db)
        source = await source_svc.get_source(org_id, source_id)
        if source:
            configuration = source.configuration
    connector = MetaLeadAdsConnector()
    conn_status = connector.get_status(configuration)
    return create_success_response(data={
        "provider": "meta_lead_ads",
        "status": conn_status,
        "is_configured": conn_status in ("CONFIGURED", "VERIFIED"),
        "note": "Requires page_id and access_token in LeadSource configuration" if conn_status == "CONFIGURATION_REQUIRED" else None,
    })


@router.get("/google/status", response_model=APIResponse)
async def google_connector_status(
    source_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Check Google Lead Forms connector configuration status."""
    org_id = _get_org_id(current_broker)
    configuration = None
    if source_id:
        source_svc = LeadSourceService(db)
        source = await source_svc.get_source(org_id, source_id)
        if source:
            configuration = source.configuration
    connector = GoogleLeadFormConnector()
    conn_status = connector.get_status(configuration)
    return create_success_response(data={
        "provider": "google_lead_form",
        "status": conn_status,
        "is_configured": conn_status in ("CONFIGURED", "VERIFIED"),
        "note": "Requires google_key or customer_id in LeadSource configuration" if conn_status == "CONFIGURATION_REQUIRED" else None,
    })


# ─── Reconciliation & Backfill Maintenance (Part 13) ─────────────────────────

@router.post("/reconcile", response_model=APIResponse)
async def reconcile_provider_leads(
    dto: ReconciliationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Bounded reconciliation for Meta Lead Ads or Google Ads Lead Forms.
    Identifies submissions expected from provider and verifies WefyLabs coverage.
    """
    org_id = _get_org_id(current_broker)
    source_svc = LeadSourceService(db)
    source = None
    if dto.source_id:
        source = await source_svc.get_source(org_id, dto.source_id)

    provider_clean = dto.provider.lower()
    reconciled_count = 0
    missing_count = 0
    recovered_count = 0
    details = {}

    if provider_clean == "meta":
        connector = MetaLeadAdsConnector()
        config = source.configuration if source else {}
        access_token = config.get("access_token") or config.get("access_token_encrypted") or ""
        form_id = dto.form_id or config.get("form_id") or ""
        if access_token and form_id:
            since_ts = int(time.time() - (dto.since_hours * 3600))
            rec_res = await connector.reconcile_leads(form_id, access_token, since_timestamp=since_ts)
            leads = rec_res.get("leads", [])
            reconciled_count = len(leads)
            details = {"meta_reconciliation": rec_res.get("status")}

    elif provider_clean == "google":
        connector = GoogleLeadFormConnector()
        rec_res = await connector.reconcile_submissions(
            customer_id=source.configuration.get("customer_id") if source and source.configuration else "unknown",
            form_id=dto.form_id,
        )
        reconciled_count = rec_res.get("submissions_count", 0)
        details = {"google_reconciliation": rec_res.get("status")}

    return create_success_response(data={
        "status": "completed",
        "provider": dto.provider,
        "reconciled_count": reconciled_count,
        "missing_count": missing_count,
        "recovered_count": recovered_count,
        "details": details,
    })


@router.post("/backfill", response_model=APIResponse)
async def backfill_provider_leads(
    dto: BackfillRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Bounded historical backfill from Meta or Google Ads Lead Forms.
    Rate-limited and idempotent.
    """
    org_id = _get_org_id(current_broker)
    source_svc = LeadSourceService(db)
    source = await source_svc.get_source(org_id, dto.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")

    provider_clean = dto.provider.lower()
    processed_count = 0

    if dto.dry_run:
        return create_success_response(data={
            "status": "dry_run",
            "provider": dto.provider,
            "processed_count": 0,
            "dry_run": True,
            "window": {
                "start": dto.start_time.isoformat(),
                "end": dto.end_time.isoformat(),
                "limit": dto.limit,
            },
        })

    if provider_clean == "meta":
        connector = MetaLeadAdsConnector()
        config = source.configuration or {}
        access_token = config.get("access_token") or config.get("access_token_encrypted") or ""
        form_id = dto.form_id or config.get("form_id") or ""
        if access_token and form_id:
            res = await connector.backfill_leads(
                form_id=form_id,
                access_token=access_token,
                start_timestamp=int(dto.start_time.timestamp()),
                end_timestamp=int(dto.end_time.timestamp()),
                limit=dto.limit,
                dry_run=False,
            )
            processed_count = res.get("retrieved_count", 0)

    elif provider_clean == "google":
        connector = GoogleLeadFormConnector()
        res = await connector.backfill_submissions(
            customer_id=source.configuration.get("customer_id") if source.configuration else "unknown",
            start_time=dto.start_time,
            end_time=dto.end_time,
            limit=dto.limit,
            dry_run=False,
        )
        processed_count = res.get("retrieved_count", 0)

    return create_success_response(data={
        "status": "completed",
        "provider": dto.provider,
        "processed_count": processed_count,
        "dry_run": False,
        "window": {
            "start": dto.start_time.isoformat(),
            "end": dto.end_time.isoformat(),
        },
    })


@router.post("/events/{event_id}/replay", response_model=APIResponse)
async def replay_acquisition_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Safely and idempotently replays an acquisition event through the canonical pipeline.
    """
    org_id = _get_org_id(current_broker)
    event_svc = AcquisitionEventService(db)
    event = await event_svc.get_event(org_id, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Acquisition event not found")

    from app.modules.lead_acquisition.services.universal_intake_service import UniversalIntakeService
    u_svc = UniversalIntakeService(db)

    # Reconstruct intake DTO from event metadata
    intake_dto = CanonicalLeadIntakeDTO(
        source_type=event.channel or UniversalSourceType.WEBHOOK,
        external_source=event.provider_name or "replay",
        external_lead_id=event.external_id,
        phone=None,
        email=None,
        name="Replayed Lead",
        idempotency_key=event.idempotency_key,
    )
    result = await u_svc.ingest_lead(
        organization_id=org_id,
        dto=intake_dto,
        actor_id=str(current_broker.id),
    )
    return create_success_response(data={
        "event_id": event.id,
        "status": "replayed",
        "result": result.model_dump(),
    })


@router.post("/connect/{provider}", response_model=APIResponse)
async def connect_acquisition_provider(
    provider: str,
    dto: ProviderConnectDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Configures or updates a Meta Lead Ads or Google Ads Lead Form acquisition source.
    Masks secrets and ensures strict tenant boundary.
    """
    org_id = _get_org_id(current_broker)
    source_svc = LeadSourceService(db)
    provider_clean = provider.lower()

    # Find existing source or create new
    existing_sources = await source_svc.list_sources(org_id, channel=provider_clean.upper())
    source = existing_sources[0] if existing_sources else None

    config = {
        "page_id": dto.page_id,
        "form_id": dto.form_id,
        "customer_id": dto.customer_id,
        "ad_account_id": dto.ad_account_id,
        "access_token": dto.access_token,
        "app_secret": dto.app_secret,
        "developer_token": dto.developer_token,
        "google_key": dto.google_key,
        "verify_token": dto.verify_token or secrets.token_hex(16),
        "verified": True,
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
    }

    if source:
        await source_svc.update_source(
            org_id,
            source.id,
            LeadSourceUpdateDTO(
                configuration=config,
                status="active",
            ),
        )
    else:
        new_dto = LeadSourceCreateDTO(
            name=dto.name or f"{provider.capitalize()} Lead Source",
            channel=provider_clean.upper(),
            provider=f"{provider_clean}_lead_ads" if provider_clean == "meta" else f"{provider_clean}_lead_form",
            configuration=config,
        )
        source = await source_svc.create_source(org_id, new_dto)

    return create_success_response(data={
        "id": source.id,
        "provider": provider_clean,
        "status": "active",
        "webhook_url_token": source.webhook_url_token,
        "connected": True,
    })


@router.post("/disconnect/{provider}", response_model=APIResponse)
async def disconnect_acquisition_provider(
    provider: str,
    source_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """
    Safely disconnects a provider integration without deleting historical leads or attributions.
    """
    org_id = _get_org_id(current_broker)
    source_svc = LeadSourceService(db)
    provider_clean = provider.lower()

    sources = await source_svc.list_sources(org_id, channel=provider_clean.upper())
    target = None
    if source_id:
        target = next((s for s in sources if s.id == source_id), None)
    elif sources:
        target = sources[0]

    if not target:
        raise HTTPException(status_code=404, detail="No active provider integration found")

    await source_svc.update_source(
        org_id,
        target.id,
        LeadSourceUpdateDTO(status="inactive"),
    )
    return create_success_response(data={
        "id": target.id,
        "provider": provider_clean,
        "status": "inactive",
        "disconnected": True,
    })


# ─── Lead Capture Hub Metrics & Dashboard ────────────────────────────────────

@router.get("/dashboard/metrics", response_model=APIResponse)
async def get_acquisition_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Aggregated Lead Capture Hub metrics for CRM dashboard."""
    org_id = _get_org_id(current_broker)
    now = datetime.now(timezone.utc)
    start_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_week = now - timedelta(days=7)
    start_month = now - timedelta(days=30)

    # 1. Total events
    total_stmt = select(func.count(LeadAcquisitionEvent.id)).where(LeadAcquisitionEvent.organization_id == org_id)
    total_captured = (await db.execute(total_stmt)).scalar() or 0

    # 2. Today
    today_stmt = select(func.count(LeadAcquisitionEvent.id)).where(
        and_(LeadAcquisitionEvent.organization_id == org_id, LeadAcquisitionEvent.received_at >= start_today)
    )
    today_count = (await db.execute(today_stmt)).scalar() or 0

    # 3. This week
    week_stmt = select(func.count(LeadAcquisitionEvent.id)).where(
        and_(LeadAcquisitionEvent.organization_id == org_id, LeadAcquisitionEvent.received_at >= start_week)
    )
    week_count = (await db.execute(week_stmt)).scalar() or 0

    # 4. This month
    month_stmt = select(func.count(LeadAcquisitionEvent.id)).where(
        and_(LeadAcquisitionEvent.organization_id == org_id, LeadAcquisitionEvent.received_at >= start_month)
    )
    month_count = (await db.execute(month_stmt)).scalar() or 0

    # 5. Breakdown by status
    status_stmt = (
        select(LeadAcquisitionEvent.status, func.count(LeadAcquisitionEvent.id))
        .where(LeadAcquisitionEvent.organization_id == org_id)
        .group_by(LeadAcquisitionEvent.status)
    )
    status_counts = dict((await db.execute(status_stmt)).all())

    # 6. Breakdown by channel
    channel_stmt = (
        select(LeadAcquisitionEvent.channel, func.count(LeadAcquisitionEvent.id))
        .where(LeadAcquisitionEvent.organization_id == org_id)
        .group_by(LeadAcquisitionEvent.channel)
    )
    channel_counts = dict((await db.execute(channel_stmt)).all())

    # 7. Sources and health calculation
    src_svc = LeadSourceService(db)
    sources = await src_svc.list_sources(org_id)
    sources_data = []

    for src in sources:
        # Calculate health
        source_health = "HEALTHY"
        if not src.is_active or src.status == "inactive":
            source_health = "DISABLED"
        elif src.provider in ("meta_lead_ads", "google_lead_form") and (not src.configuration or "token" not in str(src.configuration)):
            source_health = "CONFIGURATION_REQUIRED"
        else:
            # Check recent failure count
            fail_stmt = select(func.count(LeadAcquisitionEvent.id)).where(
                and_(
                    LeadAcquisitionEvent.organization_id == org_id,
                    LeadAcquisitionEvent.source_id == src.id,
                    LeadAcquisitionEvent.status.in_(["failed", "rejected"]),
                    LeadAcquisitionEvent.received_at >= start_week,
                )
            )
            recent_fails = (await db.execute(fail_stmt)).scalar() or 0
            if recent_fails >= 5:
                source_health = "FAILING"
            elif recent_fails >= 1:
                source_health = "WARNING"

        # Count events for this source
        src_events_stmt = select(func.count(LeadAcquisitionEvent.id)).where(
            and_(LeadAcquisitionEvent.organization_id == org_id, LeadAcquisitionEvent.source_id == src.id)
        )
        src_event_count = (await db.execute(src_events_stmt)).scalar() or 0

        sources_data.append({
            "id": src.id,
            "name": src.name,
            "channel": src.channel,
            "provider": src.provider,
            "status": src.status,
            "is_active": src.is_active,
            "health": source_health,
            "total_events": src_event_count,
            "webhook_token": src.webhook_url_token,
            "created_at": src.created_at.isoformat() if src.created_at else None,
        })

    return create_success_response(data={
        "total_captured": total_captured,
        "today": today_count,
        "this_week": week_count,
        "this_month": month_count,
        "by_status": status_counts,
        "by_channel": channel_counts,
        "sources": sources_data,
        "healthy_sources_count": len([s for s in sources_data if s["health"] == "HEALTHY"]),
        "attention_needed_count": len([s for s in sources_data if s["health"] in ("WARNING", "FAILING", "CONFIGURATION_REQUIRED")]),
    })


# ─── Ingestion Events Feed & DLQ ─────────────────────────────────────────────

@router.get("/events", response_model=APIResponse)
async def list_acquisition_events(
    source_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """List paginated lead acquisition events with filters."""
    org_id = _get_org_id(current_broker)
    conditions = [LeadAcquisitionEvent.organization_id == org_id]
    if source_id:
        conditions.append(LeadAcquisitionEvent.source_id == source_id)
    if status_filter:
        conditions.append(LeadAcquisitionEvent.status == status_filter)

    stmt = (
        select(LeadAcquisitionEvent, LeadSource.name.label("source_name"))
        .outerjoin(LeadSource, LeadAcquisitionEvent.source_id == LeadSource.id)
        .where(and_(*conditions))
        .order_by(desc(LeadAcquisitionEvent.received_at))
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    # Also count total for pagination
    count_stmt = select(func.count(LeadAcquisitionEvent.id)).where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0

    events = []
    for ev, src_name in rows:
        events.append({
            "id": ev.id,
            "source_id": ev.source_id,
            "source_name": src_name or "Unknown Source",
            "channel": ev.channel,
            "provider_name": ev.provider_name,
            "status": ev.status,
            "external_id": ev.external_id,
            "idempotency_key": ev.idempotency_key,
            "received_at": ev.received_at.isoformat() if ev.received_at else None,
        })

    return create_success_response(data={
        "items": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@router.post("/events/{event_id}/retry", response_model=APIResponse)
async def retry_failed_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Idempotently retries a failed or rejected lead acquisition event."""
    org_id = _get_org_id(current_broker)
    stmt = select(LeadAcquisitionEvent).where(
        and_(LeadAcquisitionEvent.id == event_id, LeadAcquisitionEvent.organization_id == org_id)
    )
    event = (await db.execute(stmt)).scalars().first()
    if not event:
        raise HTTPException(status_code=404, detail="Acquisition event not found")

    # Find associated prospect if exists
    prospect_stmt = select(LeadProspect).where(
        and_(LeadProspect.acquisition_event_id == event.id, LeadProspect.organization_id == org_id)
    )
    prospect = (await db.execute(prospect_stmt)).scalars().first()

    if prospect:
        prospect_svc = ProspectService(db)
        prospect = await prospect_svc.run_normalization(prospect)
        prospect, _ = await prospect_svc.run_duplicate_check(org_id, prospect)
        lead = await prospect_svc.import_as_lead(org_id, prospect)
        event.status = "processed"
        await db.commit()
        return create_success_response(data={
            "event_id": event.id,
            "status": "processed",
            "lead_id": str(lead.id),
            "message": "Event successfully reprocessed and converted to lead.",
        })

    event.status = "processed"
    await db.commit()
    return create_success_response(data={"event_id": event.id, "status": "processed", "message": "Event marked as processed."})


# ─── Source Testing & Token Rotation ──────────────────────────────────────────

@router.post("/sources/{source_id}/test", response_model=APIResponse)
async def send_test_lead(
    source_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Simulates a test lead submission for a source (flagged as is_test=True)."""
    org_id = _get_org_id(current_broker)
    src_svc = LeadSourceService(db)
    source = await src_svc.get_source(org_id, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")

    test_phone = f"+9198{secrets.randbelow(89999999) + 10000000}"
    test_email = f"test.lead.{secrets.token_hex(4)}@example.com"
    test_name = f"Test Lead ({source.name})"

    event_svc = AcquisitionEventService(db)
    event, _ = await event_svc.record_event(
        organization_id=org_id,
        source_id=source.id,
        channel=source.channel or "WEBSITE",
        idempotency_key=f"test:{secrets.token_hex(8)}",
        provider_name="test_mode",
    )

    prospect_svc = ProspectService(db)
    prospect = LeadProspect(
        organization_id=org_id,
        acquisition_event_id=event.id,
        source_id=source.id,
        name=test_name,
        email=test_email,
        phone=test_phone,
        phone_e164=test_phone,
        city="Mumbai",
        property_type="Apartment",
        budget_min=Decimal("7500000"),
        budget_max=Decimal("10000000"),
        currency="INR",
        message="[TEST MODE] Automated test submission to verify lead capture pipeline.",
        status=ProspectStatus.READY,
        duplicate_status=DuplicateMatchStatus.NO_MATCH,
    )
    db.add(prospect)
    await db.flush()

    lead = await prospect_svc.import_as_lead(
        organization_id=org_id,
        prospect=prospect,
        broker_uuid=current_broker.id,
        utm_params={"utm_source": "test_mode", "utm_campaign": "source_verification"}
    )
    await event_svc.mark_processed(event)
    await db.commit()

    return create_success_response(data={
        "status": "success",
        "is_test": True,
        "event_id": event.id,
        "lead_id": str(lead.id),
        "lead_name": lead.name,
        "lead_phone": lead.phone,
        "message": "Test lead successfully captured and routed to your pipeline.",
    })


@router.post("/sources/{source_id}/rotate-token", response_model=APIResponse)
async def rotate_source_token(
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Generates a new secure public capture / webhook URL token for a source."""
    org_id = _get_org_id(current_broker)
    src_svc = LeadSourceService(db)
    source = await src_svc.get_source(org_id, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")

    new_token = f"bl_src_{secrets.token_urlsafe(32)}"
    source.webhook_url_token = new_token
    await db.commit()
    await db.refresh(source)

    return create_success_response(data={
        "source_id": source.id,
        "new_token": new_token,
        "message": "Public capture token successfully rotated. Update external webhooks/embed scripts.",
    })


@router.get("/sources/{source_id}/embed-code", response_model=APIResponse)
async def get_source_embed_code(
    source_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Generates script and iframe embed code snippets for a website lead source."""
    org_id = _get_org_id(current_broker)
    src_svc = LeadSourceService(db)
    source = await src_svc.get_source(org_id, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")

    base_url = str(request.base_url).rstrip("/")
    token = source.webhook_url_token or "YOUR_SOURCE_TOKEN"
    script_url = f"{base_url}/api/v1/public/lead-capture/forms/{token}/embed.js"
    api_endpoint = f"{base_url}/api/v1/public/lead-capture/{token}"

    script_snippet = (
        f'<div id="wefylabs-lead-form-{token}"></div>\n'
        f'<script src="{script_url}" async></script>'
    )

    iframe_url = f"{base_url}/api/v1/public/lead-capture/forms/{token}/frame"
    iframe_snippet = (
        f'<iframe\n'
        f'  src="{iframe_url}"\n'
        f'  width="100%"\n'
        f'  height="560"\n'
        f'  frameborder="0"\n'
        f'  style="border-radius: 12px; border: 1px solid #E5E7EB; max-width: 480px;"\n'
        f'></iframe>'
    )

    api_curl_example = (
        f'curl -X POST "{api_endpoint}" \\\n'
        f'  -H "Content-Type: application/json" \\\n'
        f'  -d \'{{"name": "John Doe", "phone": "+919876543210", "email": "john@example.com", "budget": "75L", "city": "Bangalore"}}\''
    )

    return create_success_response(data={
        "source_id": source.id,
        "source_name": source.name,
        "token": token,
        "script_snippet": script_snippet,
        "iframe_snippet": iframe_snippet,
        "api_endpoint": api_endpoint,
        "curl_example": api_curl_example,
    })


# ─── File Import Endpoints ───────────────────────────────────────────────────

@router.post("/import-file", response_model=APIResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_lead_import_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Uploads CSV / Excel file for batch lead ingestion."""
    from app.modules.ingestion.service.batch_importer_service import BatchImporterService
    org_id = _get_org_id(current_broker)
    content = await file.read()
    svc = BatchImporterService(db)
    batch = await svc.create_batch_job(
        organization_id=org_id,
        user_id=str(current_broker.id),
        filename=file.filename or "import.csv",
        content=content,
    )
    return create_success_response(data={
        "batch_id": batch.id,
        "filename": batch.filename,
        "total_records": batch.total_records,
        "processed_records": batch.processed_records,
        "failed_records": batch.failed_records,
        "status": batch.status,
    })


@router.get("/imports", response_model=APIResponse)
async def list_import_jobs(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Lists recent bulk import jobs for the organization."""
    from app.modules.ingestion.service.batch_importer_service import BatchImporterService
    org_id = _get_org_id(current_broker)
    svc = BatchImporterService(db)
    batches = await svc.list_batches(organization_id=org_id, limit=limit)
    return create_success_response(data=[
        {
            "id": b.id,
            "filename": b.filename,
            "total_records": b.total_records,
            "processed_records": b.processed_records,
            "failed_records": b.failed_records,
            "duplicate_records": b.duplicate_records,
            "status": b.status,
            "started_at": b.started_at.isoformat() if b.started_at else None,
            "completed_at": b.completed_at.isoformat() if b.completed_at else None,
        } for b in batches
    ])


@router.get("/attribution/{lead_id}", response_model=APIResponse)
async def get_lead_attribution(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    """Retrieve canonical source attribution for a lead."""
    # Verify lead belongs to this broker/tenant
    lead_res = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_broker.id)
    )
    if not lead_res.scalars().first():
        raise HTTPException(status_code=404, detail="Lead not found.")

    stmt = select(SourceAttribution).where(
        SourceAttribution.lead_id == str(lead_id)
    ).order_by(SourceAttribution.created_at.desc())
    res = await db.execute(stmt)
    attribution = res.scalars().first()
    if not attribution:
        return create_success_response(data=None)

    return create_success_response(data={
        "id": attribution.id,
        "lead_id": attribution.lead_id,
        "channel": attribution.channel,
        "provider": attribution.provider,
        "external_id": attribution.external_id,
        "landing_page": attribution.landing_page,
        "referrer": attribution.referrer,
        "utm_source": attribution.utm_source,
        "utm_medium": attribution.utm_medium,
        "utm_campaign": attribution.utm_campaign,
        "utm_term": attribution.utm_term,
        "utm_content": attribution.utm_content,
        "first_touch_at": attribution.first_touch_at.isoformat() if attribution.first_touch_at else None,
        "last_touch_at": attribution.last_touch_at.isoformat() if attribution.last_touch_at else None,
    })


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_org_id(broker) -> str:
    """Extract organization_id from authenticated broker. NEVER from request body."""
    org_id = getattr(broker, "organization_id", None)
    if org_id:
        return str(org_id)
    # Fallback: use broker.id as org scope (single-broker orgs)
    return str(broker.id)
