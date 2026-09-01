"""
Candidate Finder — Pre-filters existing identities to find potential duplicates.
Uses indexed fast lookups (phone, email, alias) before running the full similarity engine.
Max candidates capped at 50 per resolution run for performance.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models.identity_models import Identity, IdentityAlias

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 50


class CandidateFinder:
    """
    Finds candidate identity matches for an incoming lead using fast indexed lookups.

    Strategy:
    1. Exact phone match (E.164 normalized) — B-tree index
    2. Exact email match (lowercased) — B-tree index
    3. WhatsApp / Telegram match — B-tree index
    4. Alias table search (historical phones/emails/names)
    5. Deduplicate and return up to MAX_CANDIDATES
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_candidates(
        self,
        lead_data: Dict[str, Any],
        organization_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of candidate identity dicts to evaluate against.
        Each candidate includes all comparable fields for the similarity engine.
        """
        candidate_ids = set()
        candidates = []

        phone = self._normalize_phone(lead_data.get("phone") or "")
        email = self._normalize_email(lead_data.get("email") or "")
        whatsapp = self._normalize_phone(lead_data.get("whatsapp") or "")
        telegram = (lead_data.get("telegram") or "").strip().lower()
        name = (lead_data.get("name") or "").strip()

        # ── 1. Fast exact lookups on primary fields ────────────────────────────
        clauses = []
        if phone:
            clauses.append(Identity.primary_phone_e164 == phone)
        if email:
            clauses.append(Identity.primary_email == email)
        if whatsapp:
            clauses.append(Identity.primary_whatsapp == whatsapp)
        if telegram:
            clauses.append(Identity.primary_telegram == telegram)

        if clauses:
            stmt = (
                select(Identity)
                .where(
                    Identity.organization_id == organization_id,
                    Identity.is_merged == False,
                    or_(*clauses),
                )
                .limit(MAX_CANDIDATES)
            )
            result = await self.db.execute(stmt)
            identities = result.scalars().all()
            for ident in identities:
                if ident.id not in candidate_ids:
                    candidate_ids.add(ident.id)
                    candidates.append(self._identity_to_dict(ident))

        # ── 2. Alias table lookup (historical phones/emails) ──────────────────
        if len(candidates) < MAX_CANDIDATES:
            alias_values = [v for v in [phone, email, whatsapp, telegram] if v]
            if alias_values:
                alias_stmt = (
                    select(IdentityAlias)
                    .where(
                        IdentityAlias.organization_id == organization_id,
                        IdentityAlias.alias_value_normalized.in_(alias_values),
                    )
                    .limit(MAX_CANDIDATES - len(candidates))
                )
                alias_result = await self.db.execute(alias_stmt)
                aliases = alias_result.scalars().all()

                # Load the parent identities for each alias match
                alias_identity_ids = [
                    a.identity_id for a in aliases if a.identity_id not in candidate_ids
                ]
                if alias_identity_ids:
                    id_stmt = (
                        select(Identity)
                        .where(
                            Identity.id.in_(alias_identity_ids),
                            Identity.is_merged == False,
                        )
                    )
                    id_result = await self.db.execute(id_stmt)
                    for ident in id_result.scalars().all():
                        if ident.id not in candidate_ids:
                            candidate_ids.add(ident.id)
                            candidates.append(self._identity_to_dict(ident))

        logger.info(
            f"[CANDIDATE_FINDER] Found {len(candidates)} candidates for "
            f"phone={phone} email={email} org={organization_id}"
        )
        return candidates[:MAX_CANDIDATES]

    @staticmethod
    def _identity_to_dict(identity: Identity) -> Dict[str, Any]:
        return {
            "id": identity.id,
            "email": identity.primary_email,
            "phone": identity.primary_phone_e164,
            "name": identity.primary_name,
            "whatsapp": identity.primary_whatsapp,
            "telegram": identity.primary_telegram,
            "location_profile": identity.location_profile,
            "financial_profile": identity.financial_profile,
            "first_source": identity.first_source,
            "lead_count": identity.lead_count,
            "health_score": identity.health_score,
            "verification_status": identity.verification_status,
        }

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        import re
        digits = re.sub(r"\D", "", phone)
        return f"+{digits}" if digits else ""

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower() if email else ""
