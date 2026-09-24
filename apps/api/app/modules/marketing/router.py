"""
Part 20 — Marketing OS: FastAPI Router
=======================================
Endpoints for:
 - Campaigns (CRUD + state machine + approval)
 - Listings (Listing Studio)
 - Landing Pages
 - Tracking Links
 - Marketing Assets
 - Project Launches
 - Intelligence (funnel, stale, ROI)

Security: Every endpoint enforces organization_id via get_current_broker.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.marketing.service import (
    MarketingCampaignService, ListingStudioService, LandingPageService,
    TrackingLinkService, MarketingAssetService, ProjectLaunchService,
    MarketingIntelligenceService,
)

marketing_router = APIRouter(prefix="/marketing", tags=["Part 20 — Marketing & Listing Distribution OS"])
router = marketing_router


def _org(broker: Broker) -> str:
    return str(broker.organization_id or broker.id)


def _bid(broker: Broker) -> str:
    return str(broker.id)


# ═══════════════════════════════════════════════════════════════════════════
# CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.post("/campaigns", status_code=201, summary="Create a marketing campaign")
async def create_campaign(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a marketing campaign. Starts in DRAFT state.
    AI-assisted campaigns must declare is_ai_assisted=True.
    Budget spending/activation requires human approval first.
    """
    svc = MarketingCampaignService(db)
    campaign = await svc.create_campaign(
        organization_id=_org(broker),
        name=data.get("name", ""),
        objective=data.get("objective", "lead_generation"),
        description=data.get("description"),
        project_id=data.get("project_id"),
        budget_planned=Decimal(str(data["budget_planned"])) if data.get("budget_planned") else None,
        currency=data.get("currency", "INR"),
        start_at=datetime.fromisoformat(data["start_at"]) if data.get("start_at") else None,
        end_at=datetime.fromisoformat(data["end_at"]) if data.get("end_at") else None,
        utm_source=data.get("utm_source"),
        utm_medium=data.get("utm_medium"),
        utm_campaign=data.get("utm_campaign"),
        bhk_scope=data.get("bhk_scope"),
        owner_id=_bid(broker),
        lead_campaign_id=data.get("lead_campaign_id"),
        is_ai_assisted=data.get("is_ai_assisted", False),
    )
    return {
        "id": campaign.id,
        "campaign_code": campaign.campaign_code,
        "status": campaign.status,
        "objective": campaign.objective,
    }


@marketing_router.get("/campaigns", summary="List marketing campaigns")
async def list_campaigns(
    status: Optional[str] = Query(None),
    objective: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingCampaignService(db)
    campaigns = await svc.list_campaigns(
        organization_id=_org(broker),
        status=status, objective=objective, project_id=project_id,
        limit=limit, offset=offset,
    )
    return {
        "campaigns": [
            {
                "id": c.id, "campaign_code": c.campaign_code, "name": c.name,
                "objective": c.objective, "status": c.status,
                "project_id": c.project_id, "approval_status": c.approval_status,
                "budget_planned": str(c.budget_planned) if c.budget_planned else None,
                "currency": c.currency,
            }
            for c in campaigns
        ],
        "total": len(campaigns),
    }


@marketing_router.get("/campaigns/{campaign_id}", summary="Get campaign detail")
async def get_campaign(
    campaign_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingCampaignService(db)
    campaign = await svc.get_campaign(_org(broker), campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {
        "id": campaign.id, "campaign_code": campaign.campaign_code, "name": campaign.name,
        "objective": campaign.objective, "status": campaign.status,
        "project_id": campaign.project_id, "bhk_scope": campaign.bhk_scope,
        "approval_status": campaign.approval_status,
        "budget_planned": str(campaign.budget_planned) if campaign.budget_planned else None,
        "budget_approved": str(campaign.budget_approved) if campaign.budget_approved else None,
        "budget_spent": str(campaign.budget_spent) if campaign.budget_spent else None,
        "currency": campaign.currency,
        "start_at": campaign.start_at.isoformat() if campaign.start_at else None,
        "end_at": campaign.end_at.isoformat() if campaign.end_at else None,
        "utm_source": campaign.utm_source, "utm_medium": campaign.utm_medium,
        "utm_campaign": campaign.utm_campaign,
        "impressions": campaign.impressions, "clicks": campaign.clicks,
        "leads_count": campaign.leads_count,
        "is_ai_assisted": campaign.is_ai_assisted,
    }


@marketing_router.post("/campaigns/{campaign_id}/status", summary="Transition campaign status")
async def transition_campaign_status(
    campaign_id: str = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Controlled state transition. Requires approval before ACTIVE/SCHEDULED."""
    svc = MarketingCampaignService(db)
    campaign = await svc.transition_status(
        organization_id=_org(broker),
        campaign_id=campaign_id,
        new_status=data.get("status", ""),
        actor_id=_bid(broker),
        reason=data.get("reason"),
    )
    return {"id": campaign.id, "status": campaign.status}


@marketing_router.post("/campaigns/{campaign_id}/approval-request", summary="Request campaign approval")
async def request_campaign_approval(
    campaign_id: str = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Submit campaign for human approval. Required before activation."""
    svc = MarketingCampaignService(db)
    approval = await svc.request_approval(
        organization_id=_org(broker),
        campaign_id=campaign_id,
        requested_by=_bid(broker),
        budget_requested=Decimal(str(data["budget"])) if data.get("budget") else None,
        channels=data.get("channels"),
        target_summary=data.get("target_summary"),
        creative_version=data.get("creative_version"),
    )
    return {
        "approval_id": approval.id,
        "campaign_id": approval.campaign_id,
        "decision": approval.decision,
        "requested_at": approval.requested_at.isoformat(),
    }


@marketing_router.post("/approvals/{approval_id}/decide", summary="Decide on campaign approval (human only)")
async def decide_campaign_approval(
    approval_id: str = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Human approval decision endpoint.
    AI agents must NOT be permitted to call this endpoint.
    """
    svc = MarketingCampaignService(db)
    approval = await svc.decide_approval(
        organization_id=_org(broker),
        approval_id=approval_id,
        reviewer_id=_bid(broker),
        decision=data.get("decision", ""),
        reason=data.get("reason"),
        budget_approved=Decimal(str(data["budget_approved"])) if data.get("budget_approved") else None,
    )
    return {
        "approval_id": approval.id,
        "campaign_id": approval.campaign_id,
        "decision": approval.decision,
        "reviewed_by": approval.reviewed_by,
        "reviewed_at": approval.reviewed_at.isoformat() if approval.reviewed_at else None,
    }


@marketing_router.put("/campaigns/{campaign_id}/metrics", summary="Update campaign metrics (factual data only)")
async def update_campaign_metrics(
    campaign_id: str = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Update factual performance metrics. Data provenance must be declared."""
    svc = MarketingCampaignService(db)
    campaign = await svc.update_metrics(
        organization_id=_org(broker),
        campaign_id=campaign_id,
        impressions=data.get("impressions"),
        clicks=data.get("clicks"),
        leads_count=data.get("leads_count"),
        revenue_attributed=Decimal(str(data["revenue_attributed"])) if data.get("revenue_attributed") else None,
        provenance=data.get("provenance", "MANUAL"),
    )
    return {"id": campaign.id, "metrics_provenance": campaign.metrics_provenance}


# ═══════════════════════════════════════════════════════════════════════════
# LISTING STUDIO
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.post("/listings", status_code=201, summary="Create a property listing publication")
async def create_listing(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a marketing listing grounded in canonical inventory.
    AI-generated fields must declare *_ai=True flags.
    Price/area/possession sourced from canonical project/unit — never overridden here.
    """
    svc = ListingStudioService(db)
    listing = await svc.create_listing(
        organization_id=_org(broker),
        project_id=data.get("project_id", ""),
        unit_id=data.get("unit_id"),
        campaign_id=data.get("campaign_id"),
        listing_title=data.get("listing_title"),
        listing_title_ai=data.get("listing_title_ai", False),
        short_description=data.get("short_description"),
        short_description_ai=data.get("short_description_ai", False),
        full_description=data.get("full_description"),
        full_description_ai=data.get("full_description_ai", False),
        highlights=data.get("highlights"),
        highlights_ai=data.get("highlights_ai", False),
        slug=data.get("slug"),
        seo_title=data.get("seo_title"),
        seo_description=data.get("seo_description"),
        created_by=_bid(broker),
    )
    return {
        "id": listing.id, "slug": listing.slug,
        "status": listing.status, "project_id": listing.project_id,
        "unit_id": listing.unit_id,
    }


@marketing_router.get("/listings", summary="List property listing publications")
async def list_listings(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_stale: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ListingStudioService(db)
    listings = await svc.list_listings(
        organization_id=_org(broker), project_id=project_id,
        status=status, is_stale=is_stale, limit=limit, offset=offset,
    )
    return {
        "listings": [
            {
                "id": l.id, "slug": l.slug, "listing_title": l.listing_title,
                "status": l.status, "is_stale": l.is_stale,
                "project_id": l.project_id, "unit_id": l.unit_id,
                "stale_reason": l.stale_reason,
            }
            for l in listings
        ],
        "total": len(listings),
    }


@marketing_router.get("/listings/{listing_id}", summary="Get listing publication detail")
async def get_listing(
    listing_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ListingStudioService(db)
    listing = await svc.get_listing(_org(broker), listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return {
        "id": listing.id, "slug": listing.slug, "status": listing.status,
        "project_id": listing.project_id, "unit_id": listing.unit_id,
        "listing_title": listing.listing_title, "listing_title_ai": listing.listing_title_ai,
        "short_description": listing.short_description, "short_description_ai": listing.short_description_ai,
        "full_description": listing.full_description, "full_description_ai": listing.full_description_ai,
        "highlights": listing.highlights, "highlights_ai": listing.highlights_ai,
        "seo_title": listing.seo_title, "seo_description": listing.seo_description,
        "is_stale": listing.is_stale, "stale_reason": listing.stale_reason,
        "published_at": listing.published_at.isoformat() if listing.published_at else None,
        "version": listing.version,
    }


@marketing_router.post("/listings/{listing_id}/publish", summary="Publish a listing (requires approval)")
async def publish_listing(
    listing_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ListingStudioService(db)
    listing = await svc.publish_listing(
        organization_id=_org(broker),
        listing_id=listing_id,
        approved_by=_bid(broker),
    )
    return {"id": listing.id, "status": listing.status, "published_at": listing.published_at.isoformat()}


@marketing_router.get("/listings/diagnostics/stale", summary="Detect stale published listings")
async def detect_stale_listings(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ListingStudioService(db)
    stale = await svc.detect_stale_listings(_org(broker))
    return {"stale_count": len(stale), "stale_listings": stale}


# ═══════════════════════════════════════════════════════════════════════════
# LANDING PAGES
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.post("/landing-pages", status_code=201, summary="Create a landing page")
async def create_landing_page(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = LandingPageService(db)
    page = await svc.create_landing_page(
        organization_id=_org(broker),
        name=data.get("name", ""),
        slug=data.get("slug", ""),
        project_id=data.get("project_id"),
        campaign_id=data.get("campaign_id"),
        page_title=data.get("page_title"),
        meta_description=data.get("meta_description"),
        utm_source=data.get("utm_source"),
        utm_medium=data.get("utm_medium"),
        utm_campaign=data.get("utm_campaign"),
        hero_content=data.get("hero_content"),
        form_config=data.get("form_config"),
        created_by=_bid(broker),
    )
    return {"id": page.id, "slug": page.slug, "status": page.status}


@marketing_router.get("/landing-pages", summary="List landing pages")
async def list_landing_pages(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = LandingPageService(db)
    pages = await svc.list_landing_pages(
        organization_id=_org(broker), project_id=project_id,
        status=status, limit=limit, offset=offset,
    )
    return {"pages": [{"id": p.id, "name": p.name, "slug": p.slug, "status": p.status} for p in pages]}


@marketing_router.post("/landing-pages/{page_id}/publish", summary="Publish landing page")
async def publish_landing_page(
    page_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = LandingPageService(db)
    page = await svc.publish(organization_id=_org(broker), page_id=page_id, approved_by=_bid(broker))
    return {"id": page.id, "status": page.status}


# ═══════════════════════════════════════════════════════════════════════════
# TRACKING LINKS
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.post("/tracking-links", status_code=201, summary="Build a validated tracking link")
async def create_tracking_link(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = TrackingLinkService(db)
    link = await svc.build_tracking_link(
        organization_id=_org(broker),
        destination_url=data.get("destination_url", ""),
        campaign_id=data.get("campaign_id"),
        landing_page_id=data.get("landing_page_id"),
        channel_partner_id=data.get("channel_partner_id"),
        utm_source=data.get("utm_source"),
        utm_medium=data.get("utm_medium"),
        utm_campaign=data.get("utm_campaign"),
        utm_content=data.get("utm_content"),
        utm_term=data.get("utm_term"),
        created_by=_bid(broker),
    )
    return {
        "id": link.id,
        "short_token": link.short_token,
        "utm_source": link.utm_source, "utm_medium": link.utm_medium,
        "utm_campaign": link.utm_campaign,
        "destination_url": link.destination_url,
    }


@marketing_router.get("/tracking-links", summary="List tracking links")
async def list_tracking_links(
    campaign_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = TrackingLinkService(db)
    links = await svc.list_links(organization_id=_org(broker), campaign_id=campaign_id, limit=limit, offset=offset)
    return {
        "links": [
            {"id": l.id, "short_token": l.short_token, "click_count": l.click_count,
             "utm_source": l.utm_source, "utm_medium": l.utm_medium, "campaign_id": l.campaign_id}
            for l in links
        ]
    }


@marketing_router.get("/t/{short_token}", include_in_schema=False, summary="Resolve tracking link redirect")
async def resolve_tracking_link(
    short_token: str = Path(..., max_length=16),
    db: AsyncSession = Depends(get_db),
):
    """Public redirect endpoint. Does not expose any PII or internal IDs."""
    svc = TrackingLinkService(db)
    link = await svc.resolve_link(short_token)
    if not link:
        raise HTTPException(status_code=404, detail="Tracking link not found or inactive")
    from fastapi.responses import RedirectResponse
    dest = link.destination_url
    params = []
    if link.utm_source: params.append(f"utm_source={link.utm_source}")
    if link.utm_medium: params.append(f"utm_medium={link.utm_medium}")
    if link.utm_campaign: params.append(f"utm_campaign={link.utm_campaign}")
    if link.utm_content: params.append(f"utm_content={link.utm_content}")
    if params:
        sep = "&" if "?" in dest else "?"
        dest = dest + sep + "&".join(params)
    return RedirectResponse(url=dest, status_code=302)


# ═══════════════════════════════════════════════════════════════════════════
# MARKETING ASSETS
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.post("/assets", status_code=201, summary="Create a marketing asset")
async def create_asset(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingAssetService(db)
    asset = await svc.create_asset(
        organization_id=_org(broker),
        name=data.get("name", ""),
        asset_type=data.get("asset_type", "image"),
        project_id=data.get("project_id"),
        campaign_id=data.get("campaign_id"),
        storage_url=data.get("storage_url"),
        mime_type=data.get("mime_type"),
        file_size_bytes=data.get("file_size_bytes"),
        is_ai_generated=data.get("is_ai_generated", False),
        created_by=_bid(broker),
    )
    return {"id": asset.id, "status": asset.status, "version": asset.version}


@marketing_router.post("/assets/{asset_id}/approve", summary="Approve a marketing asset")
async def approve_asset(
    asset_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingAssetService(db)
    asset = await svc.approve_asset(_org(broker), asset_id, _bid(broker))
    return {"id": asset.id, "status": asset.status, "approved_at": asset.approved_at.isoformat() if asset.approved_at else None}


@marketing_router.get("/assets", summary="List marketing assets")
async def list_assets(
    project_id: Optional[str] = Query(None),
    campaign_id: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingAssetService(db)
    assets = await svc.list_assets(
        organization_id=_org(broker), project_id=project_id, campaign_id=campaign_id,
        asset_type=asset_type, status=status, limit=limit, offset=offset,
    )
    return {
        "assets": [
            {"id": a.id, "name": a.name, "asset_type": a.asset_type, "status": a.status,
             "version": a.version, "is_ai_generated": a.is_ai_generated}
            for a in assets
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# PROJECT LAUNCHES
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.post("/launches", status_code=201, summary="Create a project launch workflow")
async def create_launch(
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectLaunchService(db)
    launch = await svc.create_launch(
        organization_id=_org(broker),
        project_id=data.get("project_id", ""),
        campaign_id=data.get("campaign_id"),
        landing_page_id=data.get("landing_page_id"),
        created_by=_bid(broker),
    )
    return {"id": launch.id, "project_id": launch.project_id, "status": launch.status}


@marketing_router.patch("/launches/{launch_id}/gate", summary="Update a launch readiness gate")
async def update_launch_gate(
    launch_id: str = Path(...),
    data: Dict[str, Any] = Body(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectLaunchService(db)
    launch = await svc.update_gate(_org(broker), launch_id, data.get("gate", ""), data.get("ready", False))
    return {
        "id": launch.id, "status": launch.status,
        "gates": {
            "project_configured": launch.gate_project_configured,
            "inventory_ready": launch.gate_inventory_ready,
            "pricing_ready": launch.gate_pricing_ready,
            "media_ready": launch.gate_media_ready,
            "landing_page_ready": launch.gate_landing_page_ready,
            "lead_form_ready": launch.gate_lead_form_ready,
            "tracking_ready": launch.gate_tracking_ready,
            "partner_distribution_ready": launch.gate_partner_distribution_ready,
            "campaign_ready": launch.gate_campaign_ready,
            "approval_complete": launch.gate_approval_complete,
        }
    }


@marketing_router.post("/launches/{launch_id}/approve-and-launch", summary="Approve and launch project (human action)")
async def approve_and_launch(
    launch_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """Human-only endpoint. All readiness gates must be complete. AI may not call this."""
    svc = ProjectLaunchService(db)
    launch = await svc.approve_and_launch(_org(broker), launch_id, _bid(broker))
    return {"id": launch.id, "status": launch.status, "launched_at": launch.launched_at.isoformat() if launch.launched_at else None}


@marketing_router.get("/launches", summary="List project launches")
async def list_launches(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = ProjectLaunchService(db)
    launches = await svc.list_launches(organization_id=_org(broker), project_id=project_id, status=status)
    return {
        "launches": [
            {"id": l.id, "project_id": l.project_id, "status": l.status,
             "launched_at": l.launched_at.isoformat() if l.launched_at else None}
            for l in launches
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════
# INTELLIGENCE — Campaign Funnel & Analytics
# ═══════════════════════════════════════════════════════════════════════════

@marketing_router.get("/intelligence/campaigns/{campaign_id}/funnel", summary="Get campaign marketing funnel")
async def get_campaign_funnel(
    campaign_id: str = Path(...),
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the actual campaign-to-revenue funnel.
    Values are NULL when data is not available — never fabricated.
    ROI is NOT_AVAILABLE unless both actual spend and revenue are recorded.
    """
    svc = MarketingIntelligenceService(db)
    return await svc.get_campaign_funnel(_org(broker), campaign_id)


@marketing_router.get("/intelligence/stale-listings", summary="Get stale listing alert summary")
async def stale_listings_alert(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingIntelligenceService(db)
    return await svc.get_stale_listings_alert(_org(broker))


@marketing_router.get("/intelligence/pending-approvals", summary="Get pending campaign approval count")
async def pending_approvals(
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketingIntelligenceService(db)
    return await svc.get_pending_approvals(_org(broker))
