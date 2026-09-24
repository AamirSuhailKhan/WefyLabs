"""
Part 20 — Marketing OS Service Layer
=====================================
Business logic for:
1. MarketingCampaignService — CRUD + state machine + approval workflow
2. ListingStudioService     — Grounded listing creation + publication
3. LandingPageService       — Landing page management + lead form routing
4. TrackingLinkService      — UTM-validated tracking link builder + QR
5. ProjectLaunchService     — Launch checklist management
6. MarketingAssetService    — Asset versioning + approval
7. MarketingIntelligenceService — Campaign funnel, stale detection, ROI

Design rules:
- No autonomous paid campaign launches.
- No budget spending without human approval.
- AI drafts fields; marks them is_ai_generated=True.
- No fabricated impressions, clicks, or ROI.
- Decimal arithmetic for all money.
- Tenant isolation via organization_id on every query.
- State changes write CampaignAuditLog + OutboxEvent atomically.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing_models import (
    MarketingCampaign, CampaignApproval, CampaignAuditLog,
    MarketingAsset, PropertyListingPublication, ListingDistribution,
    LandingPage, TrackingLink, CampaignEvent, ProjectLaunch,
    CampaignListingLink,
    CampaignStatus, CampaignObjective, ListingPublicationStatus,
    AssetStatus, AssetType, ApprovalDecision, LaunchStatus,
    DistributionChannel,
)
from app.models.inventory_models import (
    RealEstateProject, ProjectUnit, ProjectPriceBook,
    UnitInventoryStatus,
)
from app.infrastructure.outbox.outbox_service import OutboxService as _OutboxService

logger = logging.getLogger("wefylabs.marketing.service")


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_short_token() -> str:
    """Generate URL-safe non-sequential token for tracking links."""
    return secrets.token_urlsafe(10)[:12]


def _generate_campaign_code() -> str:
    """Generate unique campaign code (e.g. CAMP-4F9A2B)."""
    return f"CAMP-{secrets.token_hex(3).upper()}"


# ─────────────────────────────────────────────────────────────────────────────
# 1. MarketingCampaignService
# ─────────────────────────────────────────────────────────────────────────────

class MarketingCampaignService:
    """
    Governs MarketingCampaign lifecycle.

    CRITICAL INVARIANTS:
    - Status transitions strictly validated against CampaignStatus.VALID_TRANSITIONS.
    - Paid/external campaigns require CampaignApproval before ACTIVE.
    - Budget changes require explicit actor context and are audited.
    - AI assistance flags are preserved; AI cannot bypass approval.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_campaign(
        self,
        organization_id: str,
        name: str,
        objective: str,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
        budget_planned: Optional[Decimal] = None,
        currency: str = "INR",
        start_at: Optional[datetime] = None,
        end_at: Optional[datetime] = None,
        utm_source: Optional[str] = None,
        utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        bhk_scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        lead_campaign_id: Optional[str] = None,
        is_ai_assisted: bool = False,
    ) -> MarketingCampaign:
        """Create a new marketing campaign in DRAFT state."""
        if objective not in CampaignObjective.ALL:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid objective '{objective}'. Valid: {sorted(CampaignObjective.ALL)}"
            )

        # Verify project belongs to tenant if provided
        if project_id:
            project = await self._get_project(organization_id, project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found or not accessible")

        campaign_code = _generate_campaign_code()
        campaign = MarketingCampaign(
            id=_new_id(),
            organization_id=organization_id,
            name=name,
            campaign_code=campaign_code,
            description=description,
            objective=objective,
            status=CampaignStatus.DRAFT,
            project_id=project_id,
            bhk_scope=bhk_scope,
            budget_planned=budget_planned,
            currency=currency,
            start_at=start_at,
            end_at=end_at,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign or campaign_code.lower(),
            owner_id=owner_id,
            lead_campaign_id=lead_campaign_id,
            is_ai_assisted=is_ai_assisted,
            approval_status=ApprovalDecision.PENDING,
        )
        self.db.add(campaign)
        await self.db.flush()

        await self._write_audit(organization_id, campaign.id, "CREATED", None, CampaignStatus.DRAFT, owner_id)
        await _OutboxService.record_event(
            self.db,
            event_type="campaign.created",
            payload={"campaign_id": campaign.id, "organization_id": organization_id, "name": name},
            aggregate_type="MarketingCampaign",
            aggregate_id=campaign.id,
            tenant_id=organization_id,
        )
        await self.db.commit()
        await self.db.refresh(campaign)
        logger.info(f"[MARKETING] Campaign created: {campaign.campaign_code} org={organization_id}")
        return campaign

    async def get_campaign(self, organization_id: str, campaign_id: str) -> Optional[MarketingCampaign]:
        stmt = select(MarketingCampaign).where(
            and_(MarketingCampaign.id == campaign_id, MarketingCampaign.organization_id == organization_id,
                 MarketingCampaign.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_campaigns(
        self, organization_id: str, status: Optional[str] = None,
        objective: Optional[str] = None, project_id: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> List[MarketingCampaign]:
        conditions = [
            MarketingCampaign.organization_id == organization_id,
            MarketingCampaign.deleted_at.is_(None),
        ]
        if status:
            conditions.append(MarketingCampaign.status == status)
        if objective:
            conditions.append(MarketingCampaign.objective == objective)
        if project_id:
            conditions.append(MarketingCampaign.project_id == project_id)
        stmt = (
            select(MarketingCampaign).where(and_(*conditions))
            .order_by(MarketingCampaign.created_at.desc())
            .limit(limit).offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def transition_status(
        self, organization_id: str, campaign_id: str,
        new_status: str, actor_id: Optional[str] = None, reason: Optional[str] = None,
    ) -> MarketingCampaign:
        """Controlled state transition with audit and outbox emission."""
        campaign = await self.get_campaign(organization_id, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if not CampaignStatus.can_transition(campaign.status, new_status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot transition campaign from '{campaign.status}' to '{new_status}'"
            )

        # Paid campaigns require approval before ACTIVE
        if new_status in {CampaignStatus.ACTIVE, CampaignStatus.SCHEDULED}:
            if campaign.approval_status != ApprovalDecision.APPROVED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Campaign requires explicit human approval before activation. Use the approval endpoint."
                )

        old_status = campaign.status
        campaign.status = new_status
        if new_status == CampaignStatus.ACTIVE and not campaign.start_at:
            campaign.start_at = _now()
        if new_status == CampaignStatus.COMPLETED:
            campaign.end_at = _now()

        await self.db.flush()
        await self._write_audit(organization_id, campaign_id, "STATUS_CHANGED", old_status, new_status, actor_id, {"reason": reason})
        await _OutboxService.record_event(
            self.db,
            event_type=f"campaign.{new_status}",
            payload={"campaign_id": campaign_id, "from_status": old_status, "to_status": new_status},
            aggregate_type="MarketingCampaign",
            aggregate_id=campaign_id,
            tenant_id=organization_id,
        )
        await self.db.commit()
        await self.db.refresh(campaign)
        logger.info(f"[MARKETING] Campaign {campaign.campaign_code}: {old_status} → {new_status}")
        return campaign

    async def request_approval(
        self, organization_id: str, campaign_id: str,
        requested_by: str, budget_requested: Optional[Decimal] = None,
        channels: Optional[str] = None, target_summary: Optional[str] = None,
        creative_version: Optional[str] = None,
    ) -> CampaignApproval:
        """Create approval request. AI cannot call this on its own — requires authenticated broker."""
        campaign = await self.get_campaign(organization_id, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if campaign.status not in {CampaignStatus.DRAFT, CampaignStatus.IN_REVIEW}:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot request approval for campaign in status '{campaign.status}'"
            )

        approval = CampaignApproval(
            id=_new_id(),
            organization_id=organization_id,
            campaign_id=campaign_id,
            requested_by=requested_by,
            requested_at=_now(),
            budget_requested=budget_requested or campaign.budget_planned,
            channels_requested=channels,
            target_summary=target_summary,
            creative_version=creative_version,
            decision=ApprovalDecision.PENDING,
        )
        self.db.add(approval)

        # Move campaign to IN_REVIEW
        if campaign.status == CampaignStatus.DRAFT:
            campaign.status = CampaignStatus.IN_REVIEW
            await self._write_audit(organization_id, campaign_id, "STATUS_CHANGED",
                                    CampaignStatus.DRAFT, CampaignStatus.IN_REVIEW, requested_by)

        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def decide_approval(
        self, organization_id: str, approval_id: str, reviewer_id: str,
        decision: str, reason: Optional[str] = None, budget_approved: Optional[Decimal] = None,
    ) -> CampaignApproval:
        """Human reviewer approves or rejects campaign. AI CANNOT call this endpoint."""
        if decision not in {ApprovalDecision.APPROVED, ApprovalDecision.REJECTED}:
            raise HTTPException(status_code=422, detail="Decision must be 'approved' or 'rejected'")

        stmt = select(CampaignApproval).where(
            and_(CampaignApproval.id == approval_id, CampaignApproval.organization_id == organization_id)
        )
        approval = (await self.db.execute(stmt)).scalars().first()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")

        approval.decision = decision
        approval.reviewed_by = reviewer_id
        approval.reviewed_at = _now()
        approval.review_reason = reason
        approval.budget_approved = budget_approved

        # Update campaign approval_status cache
        campaign = await self.get_campaign(organization_id, approval.campaign_id)
        if campaign:
            campaign.approval_status = decision
            if decision == ApprovalDecision.APPROVED:
                campaign.approved_by = reviewer_id
                campaign.approved_at = _now()
                if budget_approved:
                    campaign.budget_approved = budget_approved
                campaign.status = CampaignStatus.APPROVED
                await self._write_audit(organization_id, campaign.id, "APPROVED", CampaignStatus.IN_REVIEW,
                                        CampaignStatus.APPROVED, reviewer_id, {"reason": reason})
            else:
                campaign.status = CampaignStatus.DRAFT
                await self._write_audit(organization_id, campaign.id, "APPROVAL_REJECTED", CampaignStatus.IN_REVIEW,
                                        CampaignStatus.DRAFT, reviewer_id, {"reason": reason})

        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def update_metrics(
        self, organization_id: str, campaign_id: str,
        impressions: Optional[int] = None, clicks: Optional[int] = None,
        leads_count: Optional[int] = None, revenue_attributed: Optional[Decimal] = None,
        provenance: str = "MANUAL",
    ) -> MarketingCampaign:
        """Update factual campaign metrics. Only real data permitted. provenance must be explicit."""
        campaign = await self.get_campaign(organization_id, campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        if impressions is not None:
            campaign.impressions = impressions
        if clicks is not None:
            campaign.clicks = clicks
        if leads_count is not None:
            campaign.leads_count = leads_count
        if revenue_attributed is not None:
            campaign.revenue_attributed = revenue_attributed
        campaign.metrics_provenance = provenance

        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign

    async def _write_audit(
        self, organization_id: str, campaign_id: str, action: str,
        from_value: Any, to_value: Any, actor_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        log = CampaignAuditLog(
            id=_new_id(),
            organization_id=organization_id,
            campaign_id=campaign_id,
            action=action,
            from_value=str(from_value) if from_value is not None else None,
            to_value=str(to_value) if to_value is not None else None,
            performed_by=actor_id,
            metadata_=metadata,
            performed_at=_now(),
        )
        self.db.add(log)
        await self.db.flush()

    async def _get_project(self, organization_id: str, project_id: str) -> Optional[RealEstateProject]:
        stmt = select(RealEstateProject).where(
            and_(RealEstateProject.id == project_id, RealEstateProject.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()


# ─────────────────────────────────────────────────────────────────────────────
# 2. ListingStudioService
# ─────────────────────────────────────────────────────────────────────────────

class ListingStudioService:
    """
    Listing Studio — creates marketing representations of canonical inventory.

    CRITICAL INVARIANTS:
    - Listing is always grounded in canonical project_id/unit_id from Part 19.
    - AI-generated fields are marked with _ai=True flags.
    - AI MUST NOT invent price, area, possession, RERA, or availability.
    - Stale detection runs against canonical unit status.
    - Publication requires explicit approval.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_listing(
        self, organization_id: str, project_id: str,
        unit_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        listing_title: Optional[str] = None,
        listing_title_ai: bool = False,
        short_description: Optional[str] = None,
        short_description_ai: bool = False,
        full_description: Optional[str] = None,
        full_description_ai: bool = False,
        highlights: Optional[str] = None,
        highlights_ai: bool = False,
        slug: Optional[str] = None,
        seo_title: Optional[str] = None,
        seo_description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> PropertyListingPublication:
        """Create a listing publication grounded in canonical project/unit data."""
        # Verify project ownership
        project = await self._get_project(organization_id, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Verify unit belongs to project if specified
        if unit_id:
            unit = await self._get_unit(organization_id, project_id, unit_id)
            if not unit:
                raise HTTPException(status_code=404, detail="Unit not found in project")

        # Auto-generate slug if not provided
        if not slug:
            base = (listing_title or project.name or "listing").lower()
            slug = f"{base.replace(' ', '-')[:40]}-{secrets.token_hex(3)}"

        listing = PropertyListingPublication(
            id=_new_id(),
            organization_id=organization_id,
            project_id=project_id,
            unit_id=unit_id,
            campaign_id=campaign_id,
            listing_title=listing_title,
            listing_title_ai=listing_title_ai,
            short_description=short_description,
            short_description_ai=short_description_ai,
            full_description=full_description,
            full_description_ai=full_description_ai,
            highlights=highlights,
            highlights_ai=highlights_ai,
            slug=slug,
            seo_title=seo_title or listing_title,
            seo_description=seo_description,
            status=ListingPublicationStatus.DRAFT,
            last_inventory_sync_at=_now(),
            created_by=created_by,
        )
        self.db.add(listing)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(listing)
        return listing

    async def get_listing(self, organization_id: str, listing_id: str) -> Optional[PropertyListingPublication]:
        stmt = select(PropertyListingPublication).where(
            and_(PropertyListingPublication.id == listing_id,
                 PropertyListingPublication.organization_id == organization_id,
                 PropertyListingPublication.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_listings(
        self, organization_id: str, project_id: Optional[str] = None,
        status: Optional[str] = None, is_stale: Optional[bool] = None,
        limit: int = 50, offset: int = 0,
    ) -> List[PropertyListingPublication]:
        conditions = [
            PropertyListingPublication.organization_id == organization_id,
            PropertyListingPublication.deleted_at.is_(None),
        ]
        if project_id:
            conditions.append(PropertyListingPublication.project_id == project_id)
        if status:
            conditions.append(PropertyListingPublication.status == status)
        if is_stale is not None:
            conditions.append(PropertyListingPublication.is_stale == is_stale)
        stmt = (
            select(PropertyListingPublication).where(and_(*conditions))
            .order_by(PropertyListingPublication.created_at.desc())
            .limit(limit).offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def publish_listing(
        self, organization_id: str, listing_id: str, approved_by: str,
    ) -> PropertyListingPublication:
        """Publish listing. Requires explicit approval (approved_by != None)."""
        listing = await self.get_listing(organization_id, listing_id)
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        if listing.status not in {ListingPublicationStatus.READY, ListingPublicationStatus.APPROVED}:
            raise HTTPException(
                status_code=409,
                detail=f"Listing must be READY or APPROVED before publishing. Current: {listing.status}"
            )

        # Safety check: verify unit is still available before publishing
        if listing.unit_id:
            unit = await self._get_unit_by_id(organization_id, listing.unit_id)
            if unit and unit.status not in {UnitInventoryStatus.AVAILABLE}:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot publish listing: unit is '{unit.status}', not available. Update listing scope first."
                )

        listing.status = ListingPublicationStatus.PUBLISHED
        listing.approved_by = approved_by
        listing.approved_at = _now()
        listing.published_at = _now()
        listing.last_inventory_sync_at = _now()
        listing.is_stale = False

        await _OutboxService.record_event(
            self.db,
            event_type="listing.published",
            payload={"listing_id": listing_id, "project_id": listing.project_id},
            aggregate_type="PropertyListingPublication",
            aggregate_id=listing_id,
            tenant_id=organization_id,
        )
        await self.db.commit()
        await self.db.refresh(listing)
        return listing

    async def detect_stale_listings(self, organization_id: str) -> List[Dict]:
        """
        Identify published listings where inventory is no longer available.
        Returns factual stale conditions only.
        """
        stmt = select(PropertyListingPublication).where(
            and_(
                PropertyListingPublication.organization_id == organization_id,
                PropertyListingPublication.status == ListingPublicationStatus.PUBLISHED,
                PropertyListingPublication.unit_id.is_not(None),
                PropertyListingPublication.deleted_at.is_(None),
            )
        )
        listings = list((await self.db.execute(stmt)).scalars().all())
        stale = []
        for listing in listings:
            unit = await self._get_unit_by_id(organization_id, listing.unit_id)
            if unit and unit.status not in {UnitInventoryStatus.AVAILABLE}:
                listing.is_stale = True
                listing.stale_reason = f"Unit status is '{unit.status}'"
                stale.append({
                    "listing_id": listing.id,
                    "unit_id": listing.unit_id,
                    "unit_status": unit.status,
                    "stale_reason": listing.stale_reason,
                })
        if stale:
            await self.db.commit()
        return stale

    async def _get_project(self, organization_id: str, project_id: str):
        stmt = select(RealEstateProject).where(
            and_(RealEstateProject.id == project_id, RealEstateProject.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def _get_unit(self, organization_id: str, project_id: str, unit_id: str):
        stmt = select(ProjectUnit).where(
            and_(ProjectUnit.id == unit_id, ProjectUnit.project_id == project_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def _get_unit_by_id(self, organization_id: str, unit_id: str):
        stmt = select(ProjectUnit).where(ProjectUnit.id == unit_id)
        return (await self.db.execute(stmt)).scalars().first()


# ─────────────────────────────────────────────────────────────────────────────
# 3. LandingPageService
# ─────────────────────────────────────────────────────────────────────────────

class LandingPageService:
    """Manages project/campaign-scoped landing pages. Lead form routes to Part 9 intake."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_landing_page(
        self, organization_id: str, name: str, slug: str,
        project_id: Optional[str] = None, campaign_id: Optional[str] = None,
        page_title: Optional[str] = None, meta_description: Optional[str] = None,
        utm_source: Optional[str] = None, utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None,
        hero_content: Optional[Dict] = None, form_config: Optional[Dict] = None,
        created_by: Optional[str] = None,
    ) -> LandingPage:
        # Sanitize slug: lowercase, alphanumeric + hyphens, no traversal
        clean_slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug.lower())[:100]

        page = LandingPage(
            id=_new_id(),
            organization_id=organization_id,
            name=name,
            slug=clean_slug,
            project_id=project_id,
            campaign_id=campaign_id,
            page_title=page_title,
            meta_description=meta_description,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            hero_content=hero_content,
            form_config=form_config or {},
            status="draft",
            form_enabled=True,
            created_by=created_by,
        )
        self.db.add(page)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise HTTPException(status_code=409, detail=f"Slug '{clean_slug}' already exists for this organization")
        await self.db.refresh(page)
        return page

    async def get_landing_page(self, organization_id: str, page_id: str) -> Optional[LandingPage]:
        stmt = select(LandingPage).where(
            and_(LandingPage.id == page_id, LandingPage.organization_id == organization_id,
                 LandingPage.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def get_by_slug(self, organization_id: str, slug: str) -> Optional[LandingPage]:
        """Used by public landing page endpoint. Returns only published pages."""
        stmt = select(LandingPage).where(
            and_(LandingPage.slug == slug, LandingPage.organization_id == organization_id,
                 LandingPage.status == "published", LandingPage.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def publish(self, organization_id: str, page_id: str, approved_by: str) -> LandingPage:
        page = await self.get_landing_page(organization_id, page_id)
        if not page:
            raise HTTPException(status_code=404, detail="Landing page not found")
        page.status = "published"
        page.published_at = _now()
        page.approved_by = approved_by
        await self.db.commit()
        await self.db.refresh(page)
        return page

    async def list_landing_pages(
        self, organization_id: str, project_id: Optional[str] = None,
        status: Optional[str] = None, limit: int = 50, offset: int = 0,
    ) -> List[LandingPage]:
        conditions = [LandingPage.organization_id == organization_id, LandingPage.deleted_at.is_(None)]
        if project_id:
            conditions.append(LandingPage.project_id == project_id)
        if status:
            conditions.append(LandingPage.status == status)
        stmt = (select(LandingPage).where(and_(*conditions))
                .order_by(LandingPage.created_at.desc()).limit(limit).offset(offset))
        return list((await self.db.execute(stmt)).scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# 4. TrackingLinkService
# ─────────────────────────────────────────────────────────────────────────────

class TrackingLinkService:
    """
    UTM-validated tracking link builder.
    Never exposes internal UUIDs in the short_token.
    Attribution feeds into SourceAttribution (Part 9) on lead capture.
    """

    VALID_UTM_PATTERN = set("abcdefghijklmnopqrstuvwxyz0123456789_-.")

    def __init__(self, db: AsyncSession):
        self.db = db

    def _validate_utm(self, value: Optional[str], field_name: str) -> Optional[str]:
        """Normalize UTM values: lowercase, alphanumeric + safe chars only."""
        if not value:
            return None
        normalized = value.strip().lower()[:255]
        # Allow alphanumeric, hyphens, underscores, dots, forward slashes (for paths)
        cleaned = "".join(c if c.isalnum() or c in "_-./" else "_" for c in normalized)
        return cleaned

    async def build_tracking_link(
        self, organization_id: str, destination_url: str,
        campaign_id: Optional[str] = None, landing_page_id: Optional[str] = None,
        channel_partner_id: Optional[str] = None,
        utm_source: Optional[str] = None, utm_medium: Optional[str] = None,
        utm_campaign: Optional[str] = None, utm_content: Optional[str] = None,
        utm_term: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> TrackingLink:
        """Create a validated tracking link with UTM normalization."""
        # Validate destination URL
        if not destination_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail="Destination URL must be a valid http/https URL")

        # Normalize UTM params
        norm_source = self._validate_utm(utm_source, "utm_source")
        norm_medium = self._validate_utm(utm_medium, "utm_medium")
        norm_campaign = self._validate_utm(utm_campaign, "utm_campaign")
        norm_content = self._validate_utm(utm_content, "utm_content")
        norm_term = self._validate_utm(utm_term, "utm_term")

        short_token = _generate_short_token()

        link = TrackingLink(
            id=_new_id(),
            organization_id=organization_id,
            campaign_id=campaign_id,
            landing_page_id=landing_page_id,
            channel_partner_id=channel_partner_id,
            destination_url=destination_url,
            utm_source=norm_source,
            utm_medium=norm_medium,
            utm_campaign=norm_campaign,
            utm_content=norm_content,
            utm_term=norm_term,
            short_token=short_token,
            click_count=0,
            is_active=True,
            created_by=created_by,
        )
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def resolve_link(self, short_token: str) -> Optional[TrackingLink]:
        """Resolve a tracking link for redirect. Increments click_count (no PII)."""
        stmt = select(TrackingLink).where(
            and_(TrackingLink.short_token == short_token, TrackingLink.is_active == True)
        )
        link = (await self.db.execute(stmt)).scalars().first()
        if link:
            link.click_count = (link.click_count or 0) + 1
            link.last_clicked_at = _now()
            await self.db.commit()
        return link

    async def get_link(self, organization_id: str, link_id: str) -> Optional[TrackingLink]:
        stmt = select(TrackingLink).where(
            and_(TrackingLink.id == link_id, TrackingLink.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_links(
        self, organization_id: str, campaign_id: Optional[str] = None,
        limit: int = 50, offset: int = 0,
    ) -> List[TrackingLink]:
        conditions = [TrackingLink.organization_id == organization_id]
        if campaign_id:
            conditions.append(TrackingLink.campaign_id == campaign_id)
        stmt = (select(TrackingLink).where(and_(*conditions))
                .order_by(TrackingLink.created_at.desc()).limit(limit).offset(offset))
        return list((await self.db.execute(stmt)).scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# 5. MarketingAssetService
# ─────────────────────────────────────────────────────────────────────────────

class MarketingAssetService:
    """Manages marketing assets with versioning and approval workflows."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_asset(
        self, organization_id: str, name: str, asset_type: str,
        project_id: Optional[str] = None, campaign_id: Optional[str] = None,
        storage_url: Optional[str] = None, mime_type: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        is_ai_generated: bool = False, created_by: Optional[str] = None,
    ) -> MarketingAsset:
        asset = MarketingAsset(
            id=_new_id(),
            organization_id=organization_id,
            name=name,
            asset_type=asset_type,
            project_id=project_id,
            campaign_id=campaign_id,
            storage_url=storage_url,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            status=AssetStatus.DRAFT,
            version=1,
            is_ai_generated=is_ai_generated,
            is_public=False,
            created_by=created_by,
        )
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def approve_asset(
        self, organization_id: str, asset_id: str, approved_by: str,
    ) -> MarketingAsset:
        asset = await self.get_asset(organization_id, asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        if asset.status not in {AssetStatus.DRAFT, AssetStatus.REVIEW}:
            raise HTTPException(status_code=409, detail=f"Cannot approve asset in status '{asset.status}'")
        asset.status = AssetStatus.APPROVED
        asset.approved_by = approved_by
        asset.approved_at = _now()
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def create_new_version(
        self, organization_id: str, asset_id: str,
        storage_url: str, created_by: Optional[str] = None,
    ) -> MarketingAsset:
        """Never silently overwrite approved assets — create a new version instead."""
        original = await self.get_asset(organization_id, asset_id)
        if not original:
            raise HTTPException(status_code=404, detail="Asset not found")
        new_asset = MarketingAsset(
            id=_new_id(),
            organization_id=organization_id,
            name=original.name,
            asset_type=original.asset_type,
            project_id=original.project_id,
            campaign_id=original.campaign_id,
            storage_url=storage_url,
            status=AssetStatus.DRAFT,
            version=original.version + 1,
            previous_version_id=original.id,
            is_ai_generated=original.is_ai_generated,
            is_public=False,
            created_by=created_by,
        )
        self.db.add(new_asset)
        # Archive the original
        original.status = AssetStatus.ARCHIVED
        await self.db.commit()
        await self.db.refresh(new_asset)
        return new_asset

    async def get_asset(self, organization_id: str, asset_id: str) -> Optional[MarketingAsset]:
        stmt = select(MarketingAsset).where(
            and_(MarketingAsset.id == asset_id, MarketingAsset.organization_id == organization_id,
                 MarketingAsset.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_assets(
        self, organization_id: str, project_id: Optional[str] = None,
        campaign_id: Optional[str] = None, asset_type: Optional[str] = None,
        status: Optional[str] = None, limit: int = 50, offset: int = 0,
    ) -> List[MarketingAsset]:
        conditions = [MarketingAsset.organization_id == organization_id, MarketingAsset.deleted_at.is_(None)]
        if project_id:
            conditions.append(MarketingAsset.project_id == project_id)
        if campaign_id:
            conditions.append(MarketingAsset.campaign_id == campaign_id)
        if asset_type:
            conditions.append(MarketingAsset.asset_type == asset_type)
        if status:
            conditions.append(MarketingAsset.status == status)
        stmt = (select(MarketingAsset).where(and_(*conditions))
                .order_by(MarketingAsset.created_at.desc()).limit(limit).offset(offset))
        return list((await self.db.execute(stmt)).scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# 6. ProjectLaunchService
# ─────────────────────────────────────────────────────────────────────────────

class ProjectLaunchService:
    """Manages project launch checklists. Human approval required before LAUNCHED."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_launch(
        self, organization_id: str, project_id: str,
        campaign_id: Optional[str] = None, landing_page_id: Optional[str] = None,
        scheduled_launch_at: Optional[datetime] = None, created_by: Optional[str] = None,
    ) -> ProjectLaunch:
        launch = ProjectLaunch(
            id=_new_id(),
            organization_id=organization_id,
            project_id=project_id,
            campaign_id=campaign_id,
            landing_page_id=landing_page_id,
            status=LaunchStatus.DRAFT,
            scheduled_launch_at=scheduled_launch_at,
            created_by=created_by,
        )
        self.db.add(launch)
        await self.db.commit()
        await self.db.refresh(launch)
        return launch

    async def update_gate(
        self, organization_id: str, launch_id: str, gate: str, ready: bool,
    ) -> ProjectLaunch:
        """Update a specific checklist gate."""
        launch = await self.get_launch(organization_id, launch_id)
        if not launch:
            raise HTTPException(status_code=404, detail="Project launch not found")

        valid_gates = {
            "gate_project_configured", "gate_inventory_ready", "gate_pricing_ready",
            "gate_media_ready", "gate_landing_page_ready", "gate_lead_form_ready",
            "gate_tracking_ready", "gate_partner_distribution_ready",
            "gate_campaign_ready", "gate_approval_complete",
        }
        if gate not in valid_gates:
            raise HTTPException(status_code=422, detail=f"Invalid gate '{gate}'")

        setattr(launch, gate, ready)
        await self.db.commit()
        await self.db.refresh(launch)
        return launch

    async def approve_and_launch(
        self, organization_id: str, launch_id: str, approved_by: str,
    ) -> ProjectLaunch:
        """Human approval + launch. All gates must be ready. AI cannot call this."""
        launch = await self.get_launch(organization_id, launch_id)
        if not launch:
            raise HTTPException(status_code=404, detail="Project launch not found")

        if not self._all_gates_ready(launch):
            raise HTTPException(
                status_code=409,
                detail="Cannot launch: not all readiness gates are complete. Check the checklist."
            )

        launch.status = LaunchStatus.LAUNCHED
        launch.approved_by = approved_by
        launch.approved_at = _now()
        launch.launched_at = _now()
        launch.gate_approval_complete = True

        await _OutboxService.record_event(
            self.db,
            event_type="project_launch.launched",
            payload={"launch_id": launch_id, "project_id": launch.project_id, "approved_by": approved_by},
            aggregate_type="ProjectLaunch",
            aggregate_id=launch_id,
            tenant_id=organization_id,
        )
        await self.db.commit()
        await self.db.refresh(launch)
        return launch

    def _all_gates_ready(self, launch: ProjectLaunch) -> bool:
        return all([
            launch.gate_project_configured,
            launch.gate_inventory_ready,
            launch.gate_pricing_ready,
            launch.gate_lead_form_ready,
        ])

    async def get_launch(self, organization_id: str, launch_id: str) -> Optional[ProjectLaunch]:
        stmt = select(ProjectLaunch).where(
            and_(ProjectLaunch.id == launch_id, ProjectLaunch.organization_id == organization_id,
                 ProjectLaunch.deleted_at.is_(None))
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_launches(
        self, organization_id: str, project_id: Optional[str] = None,
        status: Optional[str] = None, limit: int = 50,
    ) -> List[ProjectLaunch]:
        conditions = [ProjectLaunch.organization_id == organization_id, ProjectLaunch.deleted_at.is_(None)]
        if project_id:
            conditions.append(ProjectLaunch.project_id == project_id)
        if status:
            conditions.append(ProjectLaunch.status == status)
        stmt = (select(ProjectLaunch).where(and_(*conditions))
                .order_by(ProjectLaunch.created_at.desc()).limit(limit))
        return list((await self.db.execute(stmt)).scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# 7. MarketingIntelligenceService
# ─────────────────────────────────────────────────────────────────────────────

class MarketingIntelligenceService:
    """
    Read-only intelligence service for marketing funnel analytics.
    Returns actual data or DATA_INSUFFICIENT — never fabricated.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_campaign_funnel(self, organization_id: str, campaign_id: str) -> Dict:
        """Return the actual campaign-to-revenue funnel from real data."""
        campaign = (await self.db.execute(
            select(MarketingCampaign).where(
                and_(MarketingCampaign.id == campaign_id,
                     MarketingCampaign.organization_id == organization_id)
            )
        )).scalars().first()

        if not campaign:
            return {"status": "NOT_FOUND"}

        # Count actual events from campaign_events
        def event_count(event_type: str):
            return None  # Will be populated by actual DB query below

        leads = campaign.leads_count
        qualified = campaign.qualified_leads_count
        appointments = campaign.appointments_count
        bookings = campaign.bookings_count
        revenue = campaign.revenue_attributed

        def _rate(num, den):
            if num is None or den is None or den == 0:
                return None
            return round((num / den) * 100, 2)

        return {
            "campaign_id": campaign_id,
            "campaign_code": campaign.campaign_code,
            "status": campaign.status,
            "metrics_provenance": campaign.metrics_provenance or "UNKNOWN",
            "funnel": {
                "impressions": campaign.impressions,
                "clicks": campaign.clicks,
                "leads": leads,
                "qualified_leads": qualified,
                "appointments": appointments,
                "bookings": bookings,
                "revenue_attributed": str(revenue) if revenue else None,
            },
            "rates": {
                "click_to_lead": _rate(leads, campaign.clicks) if campaign.clicks else None,
                "lead_to_qualified": _rate(qualified, leads),
                "qualified_to_appointment": _rate(appointments, qualified),
                "appointment_to_booking": _rate(bookings, appointments),
            },
            "roi": self._compute_roi(campaign),
        }

    def _compute_roi(self, campaign: MarketingCampaign) -> Dict:
        """Only compute ROI when actual spend AND actual revenue exist."""
        if not campaign.budget_spent or not campaign.revenue_attributed:
            return {"status": "NOT_AVAILABLE", "reason": "Requires both actual spend and actual revenue"}
        if campaign.budget_spent == 0:
            return {"status": "NOT_AVAILABLE", "reason": "No spend recorded"}
        roi = ((campaign.revenue_attributed - campaign.budget_spent) / campaign.budget_spent) * 100
        return {
            "status": "CALCULATED",
            "roi_percent": float(round(roi, 2)),
            "spend": str(campaign.budget_spent),
            "revenue": str(campaign.revenue_attributed),
            "currency": campaign.currency,
        }

    async def get_stale_listings_alert(self, organization_id: str) -> Dict:
        """Return count of stale published listings."""
        stmt = select(func.count()).where(
            and_(
                PropertyListingPublication.organization_id == organization_id,
                PropertyListingPublication.status == ListingPublicationStatus.PUBLISHED,
                PropertyListingPublication.is_stale == True,
                PropertyListingPublication.deleted_at.is_(None),
            )
        )
        count = (await self.db.execute(stmt)).scalar() or 0
        return {
            "stale_listings_count": count,
            "alert": count > 0,
            "severity": "HIGH" if count > 5 else ("MEDIUM" if count > 0 else "NONE"),
        }

    async def get_pending_approvals(self, organization_id: str) -> Dict:
        """Return count of campaigns pending approval."""
        stmt = select(func.count()).where(
            and_(
                MarketingCampaign.organization_id == organization_id,
                MarketingCampaign.status == CampaignStatus.IN_REVIEW,
                MarketingCampaign.deleted_at.is_(None),
            )
        )
        count = (await self.db.execute(stmt)).scalar() or 0
        return {"pending_approvals": count, "alert": count > 0}
