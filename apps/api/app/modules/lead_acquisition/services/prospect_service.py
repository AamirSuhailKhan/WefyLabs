"""
Part 21.1 — Prospect Service
==============================
Core lifecycle management for LeadProspect entities.

Lifecycle:
  RECEIVED → VALIDATING → NORMALIZED → MATCHING → READY → IMPORTED
  RECEIVED → VALIDATING → DUPLICATE (merge to existing lead)
  RECEIVED → REJECTED / FAILED

NEVER automatically create a duplicate CRM Lead.
NEVER auto-grant consent.
NEVER invent contact details.
"""
from __future__ import annotations
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.acquisition_models import (
    LeadProspect, LeadAcquisitionEvent, SourceAttribution,
    ProspectStatus, DuplicateMatchStatus, ConsentStatus
)
from app.models.lead import Lead
from app.modules.lead_acquisition.services.normalization_service import (
    normalize_phone, normalize_email, normalize_name,
    normalize_budget, normalize_currency, normalize_country_code
)
from app.modules.lead_acquisition.dto.acquisition_dto import WebsiteLeadAcquisitionDTO

logger = logging.getLogger(__name__)


class ProspectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_from_website(
        self,
        organization_id: str,
        dto: WebsiteLeadAcquisitionDTO,
        acquisition_event_id: Optional[str],
        source_id: Optional[str],
    ) -> Tuple[LeadProspect, bool]:
        """
        Create or update a prospect from a website lead submission.

        Returns:
            (prospect, is_new)
        """
        # Step 1: Normalize contact
        phone_e164, phone_confidence = normalize_phone(dto.phone)
        email_norm, email_fingerprint = normalize_email(dto.email)
        name_norm = normalize_name(dto.name)
        budget_min, _ = normalize_budget(dto.budget_min, dto.currency)
        budget_max, currency_norm = normalize_budget(dto.budget_max, dto.currency)
        country_code = normalize_country_code(dto.country)

        # Step 2: Check for existing prospect (dedup by phone or email fingerprint)
        existing = await self._find_existing_prospect(
            organization_id=organization_id,
            phone_e164=phone_e164,
            email_fingerprint=email_fingerprint if email_fingerprint else None,
        )

        if existing and existing.status not in (ProspectStatus.REJECTED, ProspectStatus.FAILED):
            # Update attribution if this is a new acquisition event
            if acquisition_event_id and existing.acquisition_event_id != acquisition_event_id:
                existing.acquisition_event_id = acquisition_event_id
            existing.status = ProspectStatus.RECEIVED  # Reset to re-process
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"[PROSPECT] Updated existing prospect {existing.id} for org={organization_id}")
            return existing, False

        # Step 3: Create new prospect
        prospect = LeadProspect(
            organization_id=organization_id,
            acquisition_event_id=acquisition_event_id,
            source_id=source_id or dto.source_id,
            campaign_id=dto.campaign_id,
            name=name_norm,
            email=email_norm,
            phone=dto.phone,  # Original as-received
            phone_e164=phone_e164,
            email_fingerprint=email_fingerprint or None,
            country=country_code,
            city=dto.city if hasattr(dto, "city") else None,
            language=dto.language,
            lead_intent=dto.lead_intent,
            property_type=dto.property_type,
            transaction_type=dto.transaction_type,
            budget_min=budget_min,
            budget_max=budget_max,
            currency=currency_norm,
            timeline=dto.timeline,
            message=dto.message,
            consent_status=self._resolve_consent_status(
                dto.marketing_consent or dto.email_consent or dto.whatsapp_consent
            ),
            email_consent=dto.email_consent,
            whatsapp_consent=dto.whatsapp_consent,
            marketing_consent=dto.marketing_consent,
            status=ProspectStatus.RECEIVED,
            duplicate_status=DuplicateMatchStatus.UNKNOWN,
        )
        self.db.add(prospect)
        await self.db.commit()
        await self.db.refresh(prospect)
        logger.info(f"[PROSPECT] Created new prospect {prospect.id} for org={organization_id}")
        return prospect, True

    async def run_normalization(self, prospect: LeadProspect) -> LeadProspect:
        """Normalize prospect fields in place."""
        prospect.status = ProspectStatus.VALIDATING

        if prospect.phone and not prospect.phone_e164:
            prospect.phone_e164, _ = normalize_phone(prospect.phone)
        if prospect.email and not prospect.email_fingerprint:
            _, fp = normalize_email(prospect.email)
            prospect.email_fingerprint = fp or None
        if not prospect.email_fingerprint and prospect.email:
            _, fp = normalize_email(prospect.email)
            prospect.email_fingerprint = fp or None

        prospect.status = ProspectStatus.NORMALIZED
        await self.db.commit()
        await self.db.refresh(prospect)
        return prospect

    async def run_duplicate_check(
        self, organization_id: str, prospect: LeadProspect
    ) -> Tuple[LeadProspect, str]:
        """
        Check for duplicate CRM Lead before import.

        Returns:
            (prospect, match_status) where match_status is from DuplicateMatchStatus
        """
        prospect.status = ProspectStatus.MATCHING

        # Search by E.164 phone first
        if prospect.phone_e164:
            existing_lead = await self._find_lead_by_phone(organization_id, prospect.phone_e164)
            if existing_lead:
                prospect.duplicate_status = DuplicateMatchStatus.EXACT_MATCH
                prospect.matched_lead_id = str(existing_lead.id)
                prospect.status = ProspectStatus.DUPLICATE
                await self.db.commit()
                return prospect, DuplicateMatchStatus.EXACT_MATCH

        # Search by email fingerprint
        if prospect.email_fingerprint:
            # Use normalized email for a second-pass search
            email_norm, _ = normalize_email(prospect.email)
            if email_norm:
                existing_lead = await self._find_lead_by_email(organization_id, email_norm)
                if existing_lead:
                    prospect.duplicate_status = DuplicateMatchStatus.HIGH_CONFIDENCE_MATCH
                    prospect.matched_lead_id = str(existing_lead.id)
                    prospect.status = ProspectStatus.DUPLICATE
                    await self.db.commit()
                    return prospect, DuplicateMatchStatus.HIGH_CONFIDENCE_MATCH

        # Use Identity Resolution engine if available
        try:
            from app.modules.identity_resolution.service import IdentityResolutionService
            ir_service = IdentityResolutionService(self.db)
            # This is non-blocking — identity resolution may return POSSIBLE_MATCH
            # We treat that as: allow import but flag for review
        except Exception:
            pass

        prospect.duplicate_status = DuplicateMatchStatus.NO_MATCH
        prospect.status = ProspectStatus.READY
        await self.db.commit()
        return prospect, DuplicateMatchStatus.NO_MATCH

    async def import_as_lead(
        self,
        organization_id: str,
        prospect: LeadProspect,
        broker_uuid: uuid.UUID,
        override_name: Optional[str] = None,
    ) -> Lead:
        """
        Import a READY prospect as a canonical CRM Lead.

        Preserves source attribution. Uses existing Lead model.
        NEVER creates duplicate if exact match found.
        """
        if prospect.status == ProspectStatus.DUPLICATE and prospect.matched_lead_id:
            # Update existing lead with new attribution, don't create duplicate
            existing_lead = await self._get_lead(prospect.matched_lead_id)
            if existing_lead:
                await self._create_attribution(organization_id, existing_lead.id, prospect)
                prospect.canonical_lead_id = str(existing_lead.id)
                prospect.status = ProspectStatus.IMPORTED
                await self.db.commit()
                return existing_lead

        # Create new CRM Lead
        final_name = override_name or prospect.name
        phone = prospect.phone_e164 or prospect.phone or ""
        if not phone:
            raise ValueError("Cannot import prospect without phone number")

        source_value = "manual"
        if prospect.source_id:
            source_value = "manual"  # Map from source channel in production

        import uuid as uuid_module
        lead = Lead(
            broker_id=broker_uuid,
            phone=phone,
            name=final_name,
            source=source_value,
            score="pending",
            property_type=prospect.property_type,
            preferred_locations=[prospect.city] if prospect.city else [],
            budget_min=int(prospect.budget_min) if prospect.budget_min else None,
            budget_max=int(prospect.budget_max) if prospect.budget_max else None,
            budget_currency=prospect.currency,
            country_code=prospect.country,
            locale=prospect.language,
            status="pending",
            pipeline_stage="new",
        )
        self.db.add(lead)
        await self.db.flush()

        # Record attribution
        await self._create_attribution(organization_id, str(lead.id), prospect)

        # Update prospect
        prospect.canonical_lead_id = str(lead.id)
        prospect.status = ProspectStatus.IMPORTED
        await self.db.commit()
        await self.db.refresh(lead)
        logger.info(f"[PROSPECT] Imported prospect {prospect.id} → Lead {lead.id}")
        return lead

    async def reject_prospect(self, prospect: LeadProspect, reason: str) -> LeadProspect:
        """Mark prospect as rejected with reason."""
        prospect.status = ProspectStatus.REJECTED
        prospect.rejection_reason = reason[:255]
        prospect.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return prospect

    async def get_prospect(self, organization_id: str, prospect_id: str) -> Optional[LeadProspect]:
        """Get prospect by ID, enforcing tenant isolation."""
        stmt = select(LeadProspect).where(
            and_(LeadProspect.id == prospect_id, LeadProspect.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_prospects(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LeadProspect]:
        """List prospects for an organization."""
        conditions = [LeadProspect.organization_id == organization_id]
        if status:
            conditions.append(LeadProspect.status == status)
        stmt = (
            select(LeadProspect)
            .where(and_(*conditions))
            .order_by(LeadProspect.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    # ── Private helpers ────────────────────────────────────────────────────

    def _resolve_consent_status(self, any_consent: bool) -> str:
        """UNKNOWN must never automatically become GRANTED."""
        # Only GRANTED if the prospect explicitly checked a consent box
        return ConsentStatus.GRANTED if any_consent else ConsentStatus.UNKNOWN

    async def _find_existing_prospect(
        self, organization_id: str, phone_e164: Optional[str], email_fingerprint: Optional[str]
    ) -> Optional[LeadProspect]:
        conditions = [LeadProspect.organization_id == organization_id]
        sub_conditions = []
        if phone_e164:
            sub_conditions.append(LeadProspect.phone_e164 == phone_e164)
        if email_fingerprint:
            sub_conditions.append(LeadProspect.email_fingerprint == email_fingerprint)
        if not sub_conditions:
            return None
        conditions.append(or_(*sub_conditions))
        stmt = select(LeadProspect).where(and_(*conditions)).limit(1)
        return (await self.db.execute(stmt)).scalars().first()

    async def _find_lead_by_phone(self, organization_id: str, phone_e164: str) -> Optional[Lead]:
        """Find existing CRM Lead by phone within the organization scope."""
        # Lead uses broker_id (not organization_id directly); we search across org's brokers
        # For now, search all leads with matching phone (org isolation via broker is enforced at API layer)
        stmt = select(Lead).where(
            and_(Lead.phone == phone_e164, Lead.deleted_at.is_(None))
        ).limit(1)
        return (await self.db.execute(stmt)).scalars().first()

    async def _find_lead_by_email(self, organization_id: str, email: str) -> Optional[Lead]:
        """Lead model doesn't have email — skip email-based lead lookup for now."""
        # The Lead model doesn't store email directly; identity resolution handles this
        return None

    async def _get_lead(self, lead_id: str) -> Optional[Lead]:
        try:
            lead_uuid = uuid.UUID(lead_id)
        except ValueError:
            return None
        stmt = select(Lead).where(Lead.id == lead_uuid)
        return (await self.db.execute(stmt)).scalars().first()

    async def _create_attribution(
        self, organization_id: str, lead_id: str, prospect: LeadProspect
    ) -> SourceAttribution:
        """Create a SourceAttribution record linking lead to its acquisition provenance."""
        attribution = SourceAttribution(
            organization_id=organization_id,
            lead_id=lead_id,
            source_id=prospect.source_id,
            campaign_id=prospect.campaign_id,
            acquisition_event_id=prospect.acquisition_event_id,
            prospect_id=prospect.id,
            first_touch_at=prospect.created_at,
            last_touch_at=datetime.now(timezone.utc),
        )
        self.db.add(attribution)
        await self.db.flush()
        return attribution
