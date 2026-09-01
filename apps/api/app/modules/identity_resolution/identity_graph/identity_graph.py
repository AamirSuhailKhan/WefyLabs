"""
Identity Graph — Creates, manages, and queries the permanent identity graph.
Every new lead gets assigned to an Identity node.
Maintains alias registry for historical contact data lookups.
"""
import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.identity_models import Identity, IdentityLink, IdentityAlias, IdentityHistory

logger = logging.getLogger(__name__)


class IdentityGraph:
    """
    Manages Identity nodes, links, and aliases.

    Key responsibilities:
    - Create new Identity from a lead
    - Link a lead to an existing Identity
    - Maintain alias registry (historical phones, emails, names)
    - Record identity lifecycle events
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_identity(
        self,
        lead_data: Dict[str, Any],
        organization_id: str,
    ) -> Identity:
        """
        Create a new permanent Identity node from lead data.
        Also creates the initial IdentityLink and populates the alias registry.
        """
        phone = self._normalize_phone(lead_data.get("phone") or "")
        email = self._normalize_email(lead_data.get("email") or "")
        name = (lead_data.get("name") or "").strip() or None

        identity = Identity(
            organization_id=organization_id,
            primary_email=email or None,
            primary_phone_e164=phone or None,
            primary_name=name,
            primary_whatsapp=self._normalize_phone(lead_data.get("whatsapp") or ""),
            primary_telegram=(lead_data.get("telegram") or "").strip() or None,
            location_profile=lead_data.get("location_profile") or {},
            financial_profile=lead_data.get("financial_profile") or {},
            intent_profile=lead_data.get("intent_profile") or {},
            first_source=lead_data.get("source") or "unknown",
            lead_count=1,
            health_score=self._compute_health_score(lead_data),
            completeness_score=self._compute_completeness(lead_data),
        )
        self.db.add(identity)
        await self.db.flush()  # Get identity.id

        # Create initial IdentityLink
        lead_id = str(lead_data.get("id") or "")
        if lead_id:
            link = IdentityLink(
                identity_id=identity.id,
                lead_id=lead_id,
                organization_id=organization_id,
                link_confidence=1.0,
                link_method="initial_assignment",
                matched_fields=[],
                source=lead_data.get("source"),
                is_primary=True,
                is_active=True,
            )
            self.db.add(link)

        # Populate alias registry
        await self._create_aliases(identity.id, organization_id, lead_data, phone, email, name)

        # Write identity history
        self.db.add(IdentityHistory(
            identity_id=identity.id,
            organization_id=organization_id,
            event_type="created",
            event_data={
                "source": lead_data.get("source"),
                "lead_id": lead_id,
                "phone": phone,
                "email": email,
            },
            actor_type="system",
        ))

        logger.info(f"[IDENTITY_GRAPH] Created new identity {identity.id} for lead {lead_id}")
        return identity

    async def link_lead_to_identity(
        self,
        identity_id: str,
        lead_data: Dict[str, Any],
        organization_id: str,
        confidence: float,
        matched_fields: list,
        link_method: str = "auto_merge",
    ) -> IdentityLink:
        """
        Link an additional lead to an existing identity.
        Updates identity aliases and health score.
        """
        lead_id = str(lead_data.get("id") or "")
        phone = self._normalize_phone(lead_data.get("phone") or "")
        email = self._normalize_email(lead_data.get("email") or "")
        name = (lead_data.get("name") or "").strip() or None

        link = IdentityLink(
            identity_id=identity_id,
            lead_id=lead_id,
            organization_id=organization_id,
            link_confidence=confidence,
            link_method=link_method,
            matched_fields=matched_fields,
            source=lead_data.get("source"),
            is_primary=False,
            is_active=True,
        )
        self.db.add(link)

        # Add new aliases from this lead
        await self._create_aliases(identity_id, organization_id, lead_data, phone, email, name)

        # Update identity lead_count and last_activity
        result = await self.db.execute(select(Identity).where(Identity.id == identity_id))
        identity = result.scalar_one_or_none()
        if identity:
            identity.lead_count = (identity.lead_count or 0) + 1
            identity.last_activity_at = datetime.now(timezone.utc)

        # Write history
        self.db.add(IdentityHistory(
            identity_id=identity_id,
            organization_id=organization_id,
            event_type="linked",
            event_data={
                "lead_id": lead_id,
                "source": lead_data.get("source"),
                "confidence": confidence,
                "matched_fields": matched_fields,
                "link_method": link_method,
            },
            related_lead_id=lead_id,
            actor_type="system",
        ))

        logger.info(f"[IDENTITY_GRAPH] Linked lead {lead_id} → identity {identity_id} (conf={confidence:.2%})")
        return link

    async def _create_aliases(
        self,
        identity_id: str,
        organization_id: str,
        lead_data: Dict[str, Any],
        phone: str,
        email: str,
        name: Optional[str],
    ):
        """Register all contact points as aliases for historical search."""
        aliases_to_add = []

        if phone:
            aliases_to_add.append(("phone", phone, phone))
        if email:
            aliases_to_add.append(("email", email, email))
        if name:
            aliases_to_add.append(("name", name, name.lower()))
        if lead_data.get("whatsapp"):
            wa = self._normalize_phone(lead_data["whatsapp"])
            if wa:
                aliases_to_add.append(("whatsapp", wa, wa))
        if lead_data.get("telegram"):
            tg = lead_data["telegram"].strip()
            aliases_to_add.append(("telegram", tg, tg.lower()))

        for alias_type, alias_value, alias_normalized in aliases_to_add:
            # Check if alias already exists to avoid duplicates
            existing = await self.db.execute(
                select(IdentityAlias).where(
                    IdentityAlias.identity_id == identity_id,
                    IdentityAlias.alias_type == alias_type,
                    IdentityAlias.alias_value_normalized == alias_normalized,
                )
            )
            if not existing.scalar_one_or_none():
                self.db.add(IdentityAlias(
                    identity_id=identity_id,
                    organization_id=organization_id,
                    alias_type=alias_type,
                    alias_value=alias_value,
                    alias_value_normalized=alias_normalized,
                    source=lead_data.get("source"),
                    is_current=True,
                ))

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        digits = re.sub(r"\D", "", phone)
        return f"+{digits}" if digits else ""

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower() if email else ""

    @staticmethod
    def _compute_health_score(lead_data: Dict[str, Any]) -> float:
        score = 0.0
        if lead_data.get("phone"):
            score += 30.0
        if lead_data.get("email"):
            score += 25.0
        if lead_data.get("name"):
            score += 15.0
        if lead_data.get("whatsapp") or lead_data.get("telegram"):
            score += 10.0
        if lead_data.get("location_profile") or lead_data.get("city"):
            score += 10.0
        if lead_data.get("financial_profile") or lead_data.get("budget_max"):
            score += 10.0
        return min(100.0, score)

    @staticmethod
    def _compute_completeness(lead_data: Dict[str, Any]) -> float:
        fields = ["phone", "email", "name", "whatsapp", "city", "country", "budget_max", "property_type"]
        present = sum(1 for f in fields if lead_data.get(f))
        return round(present / len(fields), 2)
