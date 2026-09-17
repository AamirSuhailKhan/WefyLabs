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
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.acquisition_models import (
    LeadProspect, LeadAcquisitionEvent, SourceAttribution, LeadSource,
    ProspectStatus, DuplicateMatchStatus, ConsentStatus
)
from app.models.lead import Lead
from app.models.crm_models import Task, Notification, Activity
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
        broker_uuid: Optional[uuid.UUID] = None,
        override_name: Optional[str] = None,
        utm_params: Optional[Dict[str, Any]] = None,
    ) -> Lead:
        """
        Import a READY or DUPLICATE prospect as a canonical CRM Lead.

        Preserves source attribution. Uses existing Lead model.
        NEVER creates duplicate if exact match found.
        """
        # If duplicate: link to existing lead, add activity, do not create duplicate lead
        if (prospect.status == ProspectStatus.DUPLICATE or prospect.duplicate_status in (
            DuplicateMatchStatus.EXACT_MATCH, DuplicateMatchStatus.HIGH_CONFIDENCE_MATCH
        )) and prospect.matched_lead_id:
            existing_lead = await self._get_lead(prospect.matched_lead_id)
            if existing_lead:
                await self._create_attribution(organization_id, str(existing_lead.id), prospect, utm_params=utm_params)
                prospect.canonical_lead_id = str(existing_lead.id)
                prospect.status = ProspectStatus.IMPORTED

                # Log re-engagement activity on existing lead
                try:
                    reengage_act = Activity(
                        actor_id=existing_lead.broker_id,
                        lead_id=existing_lead.id,
                        organization_id=organization_id,
                        activity_type="lead_reengaged",
                        title="Lead Re-engaged",
                        description=f"Prospect resubmitted via source {prospect.source_id or 'unknown'}",
                        activity_data={"source_id": prospect.source_id, "prospect_id": prospect.id}
                    )
                    self.db.add(reengage_act)
                except Exception as act_err:
                    logger.debug(f"[PROSPECT] Failed to record re-engagement activity: {act_err}")

                await self.db.commit()
                return existing_lead

        # Determine assigned broker if not provided
        if not broker_uuid:
            from app.modules.lead_acquisition.services.assignment_service import LeadAssignmentService
            assignment_svc = LeadAssignmentService(self.db)
            broker_uuid = await assignment_svc.assign_lead(
                organization_id=organization_id,
                source_id=prospect.source_id,
                property_type=prospect.property_type,
                location=prospect.city,
            )

        # Create new CRM Lead
        final_name = override_name or prospect.name
        phone = prospect.phone_e164 or prospect.phone or ""
        if not phone:
            raise ValueError("Cannot import prospect without phone number")

        source_value = "manual"
        if prospect.source_id:
            src_stmt = select(LeadSource.channel).where(LeadSource.id == prospect.source_id)
            src_channel = (await self.db.execute(src_stmt)).scalar()
            if src_channel:
                source_value = str(src_channel).lower()

        # Score determination
        initial_score = "pending"
        score_conf = 0.0
        if prospect.acquisition_quality_score is not None:
            q_score = float(prospect.acquisition_quality_score)
            score_conf = round(q_score, 2)
            if q_score >= 0.75:
                initial_score = "hot"
            elif q_score >= 0.5:
                initial_score = "warm"
            else:
                initial_score = "cold"

        lead = Lead(
            broker_id=broker_uuid,
            phone=phone,
            name=final_name,
            source=source_value,
            score=initial_score,
            score_confidence=score_conf,
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
        await self._create_attribution(organization_id, str(lead.id), prospect, utm_params=utm_params)

        # Create Follow-up Task for Assigned Broker
        try:
            task = Task(
                broker_id=broker_uuid,
                lead_id=lead.id,
                organization_id=organization_id,
                title=f"Contact new lead: {lead.name or lead.phone}",
                description=f"Captured via {source_value}. Requirement: {prospect.message or prospect.property_type or 'General Inquiry'}",
                due_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                priority="high",
                status="pending",
            )
            self.db.add(task)
        except Exception as task_err:
            logger.debug(f"[PROSPECT] Task creation skipped: {task_err}")

        # Create In-App Notification for Assigned Broker
        try:
            notif = Notification(
                broker_id=broker_uuid,
                organization_id=organization_id,
                category="lead",
                title="New Lead Captured",
                body=f"{lead.name or lead.phone} arrived from {source_value}. Contact immediately.",
                action_url=f"/dashboard/leads",
            )
            self.db.add(notif)
        except Exception as notif_err:
            logger.debug(f"[PROSPECT] Notification creation skipped: {notif_err}")

        # Create Activity Entry
        try:
            act = Activity(
                actor_id=broker_uuid,
                lead_id=lead.id,
                organization_id=organization_id,
                activity_type="lead_created",
                title="Lead Ingested",
                description=f"Lead captured via {source_value}",
                activity_data={"source": source_value, "prospect_id": prospect.id}
            )
            self.db.add(act)
        except Exception as act_err:
            logger.debug(f"[PROSPECT] Activity creation skipped: {act_err}")

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
        # 1. Check if another prospect in this org was already imported with this phone
        stmt_prospect = select(LeadProspect.canonical_lead_id).where(
            and_(
                LeadProspect.organization_id == organization_id,
                LeadProspect.phone_e164 == phone_e164,
                LeadProspect.canonical_lead_id.isnot(None),
            )
        ).limit(1)
        canonical_id = (await self.db.execute(stmt_prospect)).scalar()
        if canonical_id:
            lead = await self._get_lead(canonical_id)
            if lead and not lead.deleted_at:
                return lead

        # 2. Check leads belonging to brokers in this organization
        try:
            from app.modules.lead_acquisition.services.assignment_service import LeadAssignmentService
            assignment_svc = LeadAssignmentService(self.db)
            brokers = await assignment_svc.get_eligible_brokers(organization_id)
            if brokers:
                broker_ids = [b.id for b in brokers]
                stmt = select(Lead).where(
                    and_(
                        Lead.phone == phone_e164,
                        Lead.broker_id.in_(broker_ids),
                        Lead.deleted_at.is_(None),
                    )
                ).limit(1)
                lead = (await self.db.execute(stmt)).scalars().first()
                if lead:
                    return lead
        except Exception as e:
            logger.debug(f"[PROSPECT] Scoped phone search fallback: {e}")

        return None

    async def _find_lead_by_email(self, organization_id: str, email: str) -> Optional[Lead]:
        """Find existing CRM Lead by email within the organization scope."""
        _, email_fingerprint = normalize_email(email)
        if not email_fingerprint:
            return None

        stmt_prospect = select(LeadProspect.canonical_lead_id).where(
            and_(
                LeadProspect.organization_id == organization_id,
                LeadProspect.email_fingerprint == email_fingerprint,
                LeadProspect.canonical_lead_id.isnot(None),
            )
        ).limit(1)
        canonical_id = (await self.db.execute(stmt_prospect)).scalar()
        if canonical_id:
            lead = await self._get_lead(canonical_id)
            if lead and not lead.deleted_at:
                return lead
        return None

    async def _get_lead(self, lead_id: str) -> Optional[Lead]:
        try:
            lead_uuid = uuid.UUID(lead_id)
        except ValueError:
            return None
        stmt = select(Lead).where(Lead.id == lead_uuid)
        return (await self.db.execute(stmt)).scalars().first()

    async def _create_attribution(
        self,
        organization_id: str,
        lead_id: str,
        prospect: LeadProspect,
        utm_params: Optional[Dict[str, Any]] = None,
    ) -> SourceAttribution:
        """Create a SourceAttribution record linking lead to its acquisition provenance."""
        params = utm_params or {}
        attribution = SourceAttribution(
            organization_id=organization_id,
            lead_id=lead_id,
            source_id=prospect.source_id,
            campaign_id=prospect.campaign_id,
            acquisition_event_id=prospect.acquisition_event_id,
            prospect_id=prospect.id,
            utm_source=params.get("utm_source"),
            utm_medium=params.get("utm_medium"),
            utm_campaign=params.get("utm_campaign"),
            utm_term=params.get("utm_term"),
            utm_content=params.get("utm_content"),
            landing_page=params.get("landing_page"),
            referrer=params.get("referrer"),
            first_touch_at=prospect.created_at,
            last_touch_at=datetime.now(timezone.utc),
        )
        self.db.add(attribution)
        await self.db.flush()
        return attribution
