"""
Part 21.2 — Discovery Duplicate & Identity Resolution Service
==============================================================
Evaluates discovery candidates against existing CRM leads and prior candidates.

Match Priority:
  1. Provider external ID
  2. Verified canonical E.164 phone
  3. Verified canonical email
  4. Strong multi-attribute combination
  NEVER match on name alone.

Conflict Resolution:
  Never overwrite verified CRM data blindly. Record conflict observations.
"""
from __future__ import annotations
import uuid
import logging
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.lead import Lead
from app.models.discovery_models import DiscoveryCandidate
from app.models.acquisition_models import DuplicateMatchStatus

logger = logging.getLogger(__name__)


class DiscoveryDuplicateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_duplicate(
        self, organization_id: str, candidate: DiscoveryCandidate
    ) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Check if candidate matches an existing CRM Lead or candidate within organization.

        Returns:
            (match_status, matched_lead_id_or_None, conflict_details_or_None)
        """
        contact = candidate.contact_information or {}
        norm = candidate.normalized_data or {}

        phone = contact.get("phone_e164") or contact.get("phone") or norm.get("phone")
        email = contact.get("email") or norm.get("email")
        ext_id = candidate.external_id

        # 1. External ID Match on prior candidates
        if ext_id:
            stmt = select(DiscoveryCandidate).where(
                and_(
                    DiscoveryCandidate.organization_id == organization_id,
                    DiscoveryCandidate.external_id == ext_id,
                    DiscoveryCandidate.id != candidate.id,
                )
            ).limit(1)
            existing_cand = (await self.db.execute(stmt)).scalars().first()
            if existing_cand and existing_cand.canonical_lead_id:
                return DuplicateMatchStatus.EXACT_MATCH, existing_cand.canonical_lead_id, None

        # 2. Check by Verified E.164 Phone against CRM Leads
        if phone:
            stmt = select(Lead).where(
                and_(Lead.phone == str(phone), Lead.deleted_at.is_(None))
            ).limit(1)
            lead = (await self.db.execute(stmt)).scalars().first()
            if lead:
                conflicts = self._detect_conflicts(lead, candidate)
                return DuplicateMatchStatus.EXACT_MATCH, str(lead.id), conflicts

        # 3. Check by Email against prior candidate attribution
        if email and "@" in str(email):
            email_clean = str(email).strip().lower()
            # If email matches another imported candidate in same org
            # (Leads don't store email directly on the core table; identity resolution connects it)
            stmt = select(DiscoveryCandidate).where(
                and_(
                    DiscoveryCandidate.organization_id == organization_id,
                    DiscoveryCandidate.id != candidate.id,
                    DiscoveryCandidate.canonical_lead_id.isnot(None),
                )
            )
            candidates = (await self.db.execute(stmt)).scalars().all()
            for c in candidates:
                c_email = (c.contact_information or {}).get("email")
                if c_email and c_email.strip().lower() == email_clean:
                    return DuplicateMatchStatus.HIGH_CONFIDENCE_MATCH, c.canonical_lead_id, None

        return DuplicateMatchStatus.NO_MATCH, None, None

    def _detect_conflicts(self, lead: Lead, candidate: DiscoveryCandidate) -> Optional[Dict[str, Any]]:
        """Identify conflicts between existing verified CRM lead data and new discovery observation."""
        conflicts = {}
        norm = candidate.normalized_data or {}

        # Budget conflict
        cand_bmax = norm.get("budget_max")
        if lead.budget_max and cand_bmax and int(lead.budget_max) != int(cand_bmax):
            conflicts["budget_max"] = {
                "crm_verified": int(lead.budget_max),
                "discovered_value": int(cand_bmax),
            }

        # Property type conflict
        cand_ptype = norm.get("property_type")
        if lead.property_type and cand_ptype and lead.property_type.lower() != cand_ptype.lower():
            conflicts["property_type"] = {
                "crm_verified": lead.property_type,
                "discovered_value": cand_ptype,
            }

        return conflicts if conflicts else None
