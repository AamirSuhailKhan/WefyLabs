"""
Canonical Customer Intelligence Domain Service
==============================================
Orchestrates:
1. Canonical Customer Identity & Tenant Context
2. Identity Resolution (EXACT_MATCH, POSSIBLE_MATCH, NO_MATCH)
3. Structured Requirement Profile with Provenance Precedence
4. Canonical Conversation & Message Domain
5. 4-Tier Bounded Conversation Memory Foundation
"""
import uuid
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func

from app.models.lead import Lead
from app.models.identity_models import Identity, IdentityLink, IdentityAlias, DuplicateCandidate
from app.models.communication_models import (
    OmnichannelConversation, ChannelMessage, ConversationControl, ConversationChannelLink
)
from app.models.memory_models import (
    MemoryRecord, MemoryVersion, MemoryObjection, MemoryPropertyFeedback
)
from app.modules.memory.provenance.provenance_tracker import ProvenanceTracker
from app.infrastructure.events.event_bus import DomainEventBus, DomainEvent, StandardDomainEvents, ActorContext
from app.modules.customer_intelligence.schemas import (
    CustomerCreateDTO, CustomerUpdateDTO, CustomerResponse,
    IdentityResolutionRequest, IdentityResolutionResponse,
    RequirementProfileDTO, RequirementUpdateDTO,
    ConversationCreateDTO, ConversationResponse,
    MessageCreateDTO, MessageResponse,
    BoundedMemoryContextResponse
)

logger = logging.getLogger(__name__)


def _to_uuid(val: Any) -> uuid.UUID:
    """Safely converts string or UUID to uuid.UUID for PostgreSQL UUID(as_uuid=True) columns."""
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


def _normalize_phone(phone: Optional[str]) -> str:
    """Normalizes phone numbers by stripping whitespace and non-digits (preserving leading +)."""
    if not phone:
        return ""
    clean = re.sub(r"[^\d+]", "", phone.strip())
    return clean


def _normalize_email(email: Optional[str]) -> str:
    """Normalizes email to lowercased and stripped format."""
    if not email:
        return ""
    return email.strip().lower()


def _sanitize_content(content: str) -> str:
    """Strips secrets, access tokens, or credentials from stored messages."""
    sanitized = re.sub(r"(?i)(password|secret|bearer|api[_-]?key)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-\.]{8,}['\"]?", "[REDACTED_CREDENTIAL]", content)
    return sanitized


class CustomerIntelligenceService:
    """
    Canonical Service powering WefyLabs Customer Intelligence,
    Conversation Management, and Bounded Memory.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_bus = DomainEventBus()

    # ─── 1. Identity Resolution ───────────────────────────────────────────────

    async def resolve_identity(
        self,
        organization_id: str,
        request: IdentityResolutionRequest
    ) -> IdentityResolutionResponse:
        """
        Deterministic, safe identity resolution.
        Never performs aggressive fuzzy merges across tenant or low-confidence thresholds.
        Supports: EXACT_MATCH | POSSIBLE_MATCH | NO_MATCH
        """
        org_uuid = _to_uuid(organization_id)
        norm_phone = _normalize_phone(request.phone)
        norm_email = _normalize_email(request.email)
        req_lead_id = request.lead_id.strip() if request.lead_id else None

        # 1. Exact match by lead_id
        if req_lead_id:
            try:
                lead_uuid = _to_uuid(req_lead_id)
                stmt = select(Lead).where(
                    and_(
                        Lead.id == lead_uuid,
                        Lead.broker_id == org_uuid,
                        Lead.deleted_at.is_(None)
                    )
                )
                res = await self.db.execute(stmt)
                lead = res.scalar_one_or_none()
                if lead:
                    return IdentityResolutionResponse(
                        match_status="EXACT_MATCH",
                        confidence=1.0,
                        customer_id=str(lead.id),
                        matched_by="lead_id",
                        explanation=f"Exact match on customer ID '{lead.id}'."
                    )
            except Exception as e:
                logger.warning(f"[IDENTITY] Invalid lead_id provided for resolution: {req_lead_id} ({e})")

        # 2. Exact match by phone
        if norm_phone:
            stmt = select(Lead).where(
                and_(
                    Lead.broker_id == org_uuid,
                    Lead.phone == norm_phone,
                    Lead.deleted_at.is_(None)
                )
            ).order_by(desc(Lead.created_at))
            res = await self.db.execute(stmt)
            lead = res.scalar_one_or_none()
            if lead:
                return IdentityResolutionResponse(
                    match_status="EXACT_MATCH",
                    confidence=1.0,
                    customer_id=str(lead.id),
                    matched_by="phone",
                    explanation=f"Exact match on normalized phone number '{norm_phone}'."
                )

        # 3. Exact match by email
        if norm_email:
            stmt = select(Lead).where(
                and_(
                    Lead.broker_id == org_uuid,
                    Lead.email == norm_email,
                    Lead.deleted_at.is_(None)
                )
            ).order_by(desc(Lead.created_at))
            res = await self.db.execute(stmt)
            lead = res.scalar_one_or_none()
            if lead:
                return IdentityResolutionResponse(
                    match_status="EXACT_MATCH",
                    confidence=1.0,
                    customer_id=str(lead.id),
                    matched_by="email",
                    explanation=f"Exact match on normalized email '{norm_email}'."
                )

        # 4. Alias or Partial Candidate Check (POSSIBLE_MATCH)
        # Check if an alias matches in IdentityAlias within the same organization
        if norm_phone or norm_email:
            alias_clauses = []
            if norm_phone:
                alias_clauses.append(IdentityAlias.alias_value_normalized == norm_phone)
            if norm_email:
                alias_clauses.append(IdentityAlias.alias_value_normalized == norm_email)

            stmt_alias = (
                select(IdentityAlias)
                .where(
                    and_(
                        IdentityAlias.organization_id == str(organization_id),
                        or_(*alias_clauses)
                    )
                )
                .limit(5)
            )
            res_alias = await self.db.execute(stmt_alias)
            alias = res_alias.scalar_one_or_none()
            if alias:
                # Find linked lead
                stmt_link = select(IdentityLink).where(
                    and_(
                        IdentityLink.identity_id == alias.identity_id,
                        IdentityLink.organization_id == str(organization_id),
                        IdentityLink.is_active == True
                    )
                ).limit(1)
                link = (await self.db.execute(stmt_link)).scalar_one_or_none()
                candidate_lead_id = link.lead_id if link else None

                return IdentityResolutionResponse(
                    match_status="POSSIBLE_MATCH",
                    confidence=0.88,
                    customer_id=candidate_lead_id,
                    identity_id=alias.identity_id,
                    matched_by="alias",
                    candidate_details={"alias_type": alias.alias_type, "alias_value": alias.alias_value},
                    explanation="Historical contact alias matched an existing identity. Flagged for manual confirmation."
                )

        # 5. No match found
        return IdentityResolutionResponse(
            match_status="NO_MATCH",
            confidence=0.0,
            customer_id=None,
            matched_by=None,
            explanation="No matching customer found within tenant scope. New customer creation required."
        )

    # ─── 2. Canonical Customer Management ─────────────────────────────────────

    async def create_customer(
        self,
        organization_id: str,
        dto: CustomerCreateDTO,
        actor_id: str = "system"
    ) -> CustomerResponse:
        """
        Creates a canonical customer Lead, establishes identity node linkage,
        and initializes explicit requirement facts.
        """
        org_uuid = _to_uuid(organization_id)
        norm_phone = _normalize_phone(dto.phone)
        norm_email = _normalize_email(dto.email) if dto.email else None

        # Check existing exact match
        existing_res = await self.resolve_identity(
            organization_id,
            IdentityResolutionRequest(phone=norm_phone, email=norm_email)
        )
        if existing_res.match_status == "EXACT_MATCH" and existing_res.customer_id:
            logger.info(f"[CUSTOMER] Reusing existing customer {existing_res.customer_id} on exact match.")
            return await self.get_customer(organization_id, existing_res.customer_id)

        # Create new Lead
        new_lead = Lead(
            id=uuid.uuid4(),
            broker_id=org_uuid,
            phone=norm_phone,
            name=dto.name,
            email=norm_email,
            source=dto.source,
            status="pending",
            pipeline_stage="new",
            score="pending",
            score_confidence=0.0,
            transaction_type=dto.transaction_type,
            budget_min=dto.budget_min,
            budget_max=dto.budget_max,
            budget_currency=dto.budget_currency or "INR",
            property_type=dto.property_type,
            preferred_locations=dto.preferred_locations or [],
            timeline=dto.timeline,
            loan_status=dto.loan_status,
            notes=[{"text": dto.notes, "added_at": datetime.now(timezone.utc).isoformat()}] if dto.notes else []
        )
        self.db.add(new_lead)
        await self.db.flush()

        # Create or link permanent Identity node
        identity_id = str(uuid.uuid4())
        identity_node = Identity(
            id=identity_id,
            organization_id=str(organization_id),
            primary_phone_e164=norm_phone,
            primary_email=norm_email,
            primary_name=dto.name,
            first_source=dto.source,
            lead_count=1
        )
        self.db.add(identity_node)

        link = IdentityLink(
            id=str(uuid.uuid4()),
            identity_id=identity_id,
            lead_id=str(new_lead.id),
            organization_id=str(organization_id),
            link_confidence=1.0,
            link_method="initial_assignment",
            matched_fields=["phone", "email"] if norm_email else ["phone"],
            source=dto.source,
            is_primary=True,
            is_active=True
        )
        self.db.add(link)

        # Add initial explicit requirements to MemoryRecord
        initial_facts: List[Tuple[str, str, Dict[str, Any], Optional[str]]] = []
        if dto.budget_max:
            initial_facts.append(("BUDGET", "budget_max", {"budget_max": dto.budget_max, "currency": dto.budget_currency or "INR"}, str(dto.budget_max)))
        if dto.budget_min:
            initial_facts.append(("BUDGET", "budget_min", {"budget_min": dto.budget_min, "currency": dto.budget_currency or "INR"}, str(dto.budget_min)))
        if dto.preferred_locations:
            initial_facts.append(("LOCATION", "preferred_locations", {"locations": dto.preferred_locations}, ", ".join(dto.preferred_locations)))
        if dto.property_type:
            initial_facts.append(("PREFERENCE", "property_type", {"property_type": dto.property_type}, dto.property_type))
        if dto.transaction_type:
            initial_facts.append(("INTENT", "transaction_type", {"transaction_type": dto.transaction_type}, dto.transaction_type))

        for mem_type, key, val_json, val_text in initial_facts:
            mem_rec = MemoryRecord(
                id=str(uuid.uuid4()),
                organization_id=str(organization_id),
                lead_id=str(new_lead.id),
                memory_type=mem_type,
                key=key,
                value_json=val_json,
                value_text=val_text,
                source_type="EXPLICIT",
                confidence=1.0,
                importance=0.90,
                status="ACTIVE",
                version_number=1,
                is_customer_safe=True
            )
            self.db.add(mem_rec)

        await self.db.commit()
        await self.db.refresh(new_lead)

        # Publish domain event
        await self.event_bus.publish(DomainEvent(
            event_type=StandardDomainEvents.LEAD_CREATED,
            organization_id=str(organization_id),
            actor=ActorContext(user_id=actor_id, actor_type="user" if actor_id != "system" else "system"),
            payload={"customer_id": str(new_lead.id), "phone": norm_phone, "email": norm_email}
        ))

        return CustomerResponse.model_validate(new_lead.to_canonical_dict())

    async def get_customer(self, organization_id: str, customer_id: str) -> CustomerResponse:
        """Retrieves canonical customer context, strictly scoped to tenant."""
        org_uuid = _to_uuid(organization_id)
        cust_uuid = _to_uuid(customer_id)

        stmt = select(Lead).where(
            and_(
                Lead.id == cust_uuid,
                Lead.broker_id == org_uuid,
                Lead.deleted_at.is_(None)
            )
        )
        res = await self.db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise KeyError(f"Customer '{customer_id}' not found in organization.")

        return CustomerResponse.model_validate(lead.to_canonical_dict())

    # ─── 3. Structured Requirement Profile & Deterministic Updates ─────────────

    async def get_requirement_profile(
        self,
        organization_id: str,
        customer_id: str
    ) -> RequirementProfileDTO:
        """
        Compiles the normalized requirement profile from Lead attributes and
        active MemoryRecord entries, preserving provenance and negative preferences.
        """
        org_uuid = _to_uuid(organization_id)
        cust_uuid = _to_uuid(customer_id)

        stmt_lead = select(Lead).where(
            and_(Lead.id == cust_uuid, Lead.broker_id == org_uuid, Lead.deleted_at.is_(None))
        )
        lead = (await self.db.execute(stmt_lead)).scalar_one_or_none()
        if not lead:
            raise KeyError(f"Customer '{customer_id}' not found.")

        # Query all active MemoryRecords for this customer
        stmt_mem = select(MemoryRecord).where(
            and_(
                MemoryRecord.organization_id == str(organization_id),
                MemoryRecord.lead_id == str(customer_id),
                MemoryRecord.status == "ACTIVE"
            )
        )
        mem_records = (await self.db.execute(stmt_mem)).scalars().all()

        provenance_map: Dict[str, str] = {}
        pos_prefs: List[Dict[str, Any]] = []
        neg_prefs: List[Dict[str, Any]] = []

        # Baseline values from Lead
        profile = {
            "customer_id": str(lead.id),
            "transaction_type": lead.transaction_type,
            "budget_min": lead.budget_min,
            "budget_max": lead.budget_max,
            "currency": lead.budget_currency or "INR",
            "locations": list(lead.preferred_locations) if lead.preferred_locations else [],
            "property_types": [lead.property_type] if lead.property_type else [],
            "bhk": [],
            "area_min": None,
            "area_max": None,
            "amenities": [],
            "furnishing": None,
            "possession_preference": None,
            "timeline": lead.timeline,
            "purpose": None,
            "financing_required": lead.loan_status,
            "urgency": None,
            "positive_preferences": [],
            "negative_preferences": [],
            "provenance_map": {},
            "last_updated_at": lead.updated_at.isoformat() if lead.updated_at else None
        }

        for rec in mem_records:
            source = rec.source_type
            provenance_map[rec.key] = source

            if rec.memory_type == "NEGATIVE_PREFERENCE":
                neg_prefs.append({
                    "key": rec.key,
                    "description": rec.value_text or str(rec.value_json),
                    "provenance": source,
                    "confidence": rec.confidence
                })
            elif rec.memory_type == "PREFERENCE":
                pos_prefs.append({
                    "key": rec.key,
                    "value": rec.value_json,
                    "provenance": source,
                    "confidence": rec.confidence
                })

            # Field mappings from MemoryRecord
            if rec.key == "budget_max" and "budget_max" in rec.value_json:
                profile["budget_max"] = rec.value_json["budget_max"]
            elif rec.key == "budget_min" and "budget_min" in rec.value_json:
                profile["budget_min"] = rec.value_json["budget_min"]
            elif rec.key == "preferred_locations" and "locations" in rec.value_json:
                profile["locations"] = rec.value_json["locations"]
            elif rec.key == "bhk":
                profile["bhk"] = rec.value_json.get("bhk", [])
            elif rec.key == "amenities":
                profile["amenities"] = rec.value_json.get("amenities", [])
            elif rec.key == "furnishing":
                profile["furnishing"] = rec.value_text or rec.value_json.get("furnishing")
            elif rec.key == "possession_preference":
                profile["possession_preference"] = rec.value_text or rec.value_json.get("possession")
            elif rec.key == "timeline":
                profile["timeline"] = rec.value_text or rec.value_json.get("timeline")
            elif rec.key == "purpose":
                profile["purpose"] = rec.value_text or rec.value_json.get("purpose")
            elif rec.key == "urgency":
                profile["urgency"] = rec.value_text or rec.value_json.get("urgency")
            elif rec.key == "area_min":
                profile["area_min"] = float(rec.value_text or rec.value_json.get("area_min", 0))
            elif rec.key == "area_max":
                profile["area_max"] = float(rec.value_text or rec.value_json.get("area_max", 0))

        profile["positive_preferences"] = pos_prefs
        profile["negative_preferences"] = neg_prefs
        profile["provenance_map"] = provenance_map

        return RequirementProfileDTO.model_validate(profile)

    async def update_requirements(
        self,
        organization_id: str,
        customer_id: str,
        dto: RequirementUpdateDTO,
        actor: str = "system"
    ) -> RequirementProfileDTO:
        """
        Applies deterministic update semantics enforcing the Provenance Priority Rule:
        - Inferred information CANNOT overwrite explicit or verified CRM information.
        - Higher or equal rank updates supersede prior facts and archive older versions into MemoryVersion.
        - Negative preferences are additive and durable.
        """
        org_uuid = _to_uuid(organization_id)
        cust_uuid = _to_uuid(customer_id)

        stmt_lead = select(Lead).where(
            and_(Lead.id == cust_uuid, Lead.broker_id == org_uuid, Lead.deleted_at.is_(None))
        )
        lead = (await self.db.execute(stmt_lead)).scalar_one_or_none()
        if not lead:
            raise KeyError(f"Customer '{customer_id}' not found.")

        incoming_source = dto.source.upper()
        incoming_rank = ProvenanceTracker.get_source_rank(incoming_source)
        calc_confidence = dto.confidence if dto.confidence is not None else ProvenanceTracker.get_default_confidence(incoming_source)
        now = datetime.now(timezone.utc)

        # Helper to update or reject a key based on provenance
        async def _apply_field(key: str, mem_type: str, val_json: Dict[str, Any], val_text: Optional[str] = None):
            stmt_exist = select(MemoryRecord).where(
                and_(
                    MemoryRecord.organization_id == str(organization_id),
                    MemoryRecord.lead_id == str(customer_id),
                    MemoryRecord.key == key,
                    MemoryRecord.status == "ACTIVE"
                )
            )
            existing = (await self.db.execute(stmt_exist)).scalar_one_or_none()

            if existing:
                existing_rank = ProvenanceTracker.get_source_rank(existing.source_type)
                if incoming_rank < existing_rank:
                    logger.info(f"[PROVENANCE_REJECTED] Source '{incoming_source}' (Rank {incoming_rank}) cannot override '{existing.source_type}' (Rank {existing_rank}) for key '{key}'.")
                    return  # Reject lower rank override

                # Supersede and archive old version
                archived = MemoryVersion(
                    id=str(uuid.uuid4()),
                    memory_record_id=existing.id,
                    version_number=existing.version_number,
                    value_json=existing.value_json,
                    value_text=existing.value_text,
                    source_type=existing.source_type,
                    confidence=existing.confidence,
                    status="CONTRADICTED",
                    reason_for_change=f"Superseded by {incoming_source} update",
                    superseded_at=now
                )
                self.db.add(archived)

                existing.value_json = val_json
                existing.value_text = val_text
                existing.source_type = incoming_source
                existing.confidence = calc_confidence
                existing.version_number += 1
                existing.updated_at = now
            else:
                new_rec = MemoryRecord(
                    id=str(uuid.uuid4()),
                    organization_id=str(organization_id),
                    lead_id=str(customer_id),
                    memory_type=mem_type,
                    key=key,
                    value_json=val_json,
                    value_text=val_text,
                    source_type=incoming_source,
                    confidence=calc_confidence,
                    importance=0.90,
                    status="ACTIVE",
                    version_number=1,
                    is_customer_safe=True
                )
                self.db.add(new_rec)

        # 1. Budget Max
        if dto.budget_max is not None:
            await _apply_field("budget_max", "BUDGET", {"budget_max": dto.budget_max, "currency": dto.currency or lead.budget_currency or "INR"}, str(dto.budget_max))
            # Sync to Lead only if incoming rank >= current lead baseline
            if incoming_rank >= 80:
                lead.budget_max = dto.budget_max

        # 2. Budget Min
        if dto.budget_min is not None:
            await _apply_field("budget_min", "BUDGET", {"budget_min": dto.budget_min, "currency": dto.currency or lead.budget_currency or "INR"}, str(dto.budget_min))
            if incoming_rank >= 80:
                lead.budget_min = dto.budget_min

        # 3. Currency
        if dto.currency:
            if incoming_rank >= 80:
                lead.budget_currency = dto.currency

        # 4. Locations
        if dto.locations is not None:
            await _apply_field("preferred_locations", "LOCATION", {"locations": dto.locations}, ", ".join(dto.locations))
            if incoming_rank >= 80:
                lead.preferred_locations = dto.locations

        # 5. Property Types
        if dto.property_types is not None:
            await _apply_field("property_types", "PREFERENCE", {"property_types": dto.property_types}, ", ".join(dto.property_types))
            if incoming_rank >= 80 and dto.property_types:
                lead.property_type = dto.property_types[0]

        # 6. BHK (Single or Multi-select configuration preference)
        if dto.bhk is not None:
            bhk_text = ", ".join(str(b) for b in dto.bhk)
            await _apply_field("bhk", "PREFERENCE", {"bhk": dto.bhk}, bhk_text)

        # 7. Timeline
        if dto.timeline is not None:
            await _apply_field("timeline", "TIMELINE", {"timeline": dto.timeline}, dto.timeline)
            if incoming_rank >= 80:
                lead.timeline = dto.timeline

        # 8. Amenities
        if dto.amenities is not None:
            await _apply_field("amenities", "PREFERENCE", {"amenities": dto.amenities}, ", ".join(dto.amenities))

        # 9. Furnishing
        if dto.furnishing is not None:
            await _apply_field("furnishing", "PREFERENCE", {"furnishing": dto.furnishing}, dto.furnishing)

        # 10. Possession Preference
        if dto.possession_preference is not None:
            await _apply_field("possession_preference", "PREFERENCE", {"possession": dto.possession_preference}, dto.possession_preference)

        # 11. Purpose
        if dto.purpose is not None:
            await _apply_field("purpose", "INTENT", {"purpose": dto.purpose}, dto.purpose)

        # 12. Financing
        if dto.financing_required is not None:
            await _apply_field("financing_required", "INTENT", {"financing": dto.financing_required}, dto.financing_required)
            if incoming_rank >= 80:
                lead.loan_status = dto.financing_required

        # 13. Urgency
        if dto.urgency is not None:
            await _apply_field("urgency", "INTENT", {"urgency": dto.urgency}, dto.urgency)

        # 14. Negative Preferences (Durable and Additive Constraints)
        if dto.negative_preferences:
            for neg_pref_text in dto.negative_preferences:
                neg_key = f"neg_{re.sub(r'[^a-zA-Z0-9_]', '_', neg_pref_text.strip().lower())[:40]}"
                await _apply_field(
                    key=neg_key,
                    mem_type="NEGATIVE_PREFERENCE",
                    val_json={"constraint": neg_pref_text},
                    val_text=neg_pref_text
                )

        lead.updated_at = now
        await self.db.commit()

        # Emit domain events
        try:
            await self.event_bus.publish(DomainEvent(
                event_type=StandardDomainEvents.CUSTOMER_REQUIREMENT_UPDATED,
                organization_id=str(organization_id),
                actor=ActorContext(user_id=actor, actor_type="user" if actor != "system" else "system"),
                payload={"customer_id": str(customer_id), "source": incoming_source}
            ))
        except Exception as e:
            logger.warning(f"Failed to publish CUSTOMER_REQUIREMENT_UPDATED event: {e}")

        # Invalidate matching query cache for this tenant
        try:
            from app.infrastructure.cache.query_cache import AsyncQueryCacheService
            AsyncQueryCacheService.invalidate_tag(f"tenant:{org_uuid}:matches")
        except Exception as e:
            logger.warning(f"Failed to invalidate matching cache for tenant {org_uuid}: {e}")

        return await self.get_requirement_profile(organization_id, customer_id)

    # ─── 4. Conversation Domain ───────────────────────────────────────────────

    async def create_conversation(
        self,
        organization_id: str,
        customer_id: str,
        dto: ConversationCreateDTO
    ) -> ConversationResponse:
        """
        Creates a unified conversation envelope for the customer.
        Statuses: ACTIVE | WAITING | HANDED_OFF | CLOSED | ARCHIVED
        """
        org_uuid = _to_uuid(organization_id)
        cust_uuid = _to_uuid(customer_id)

        # Verify customer exists
        stmt_lead = select(Lead).where(
            and_(Lead.id == cust_uuid, Lead.broker_id == org_uuid, Lead.deleted_at.is_(None))
        )
        lead = (await self.db.execute(stmt_lead)).scalar_one_or_none()
        if not lead:
            raise KeyError(f"Customer '{customer_id}' not found.")

        conv_id = str(uuid.uuid4())
        norm_status = dto.status.lower()

        conv = OmnichannelConversation(
            id=conv_id,
            organization_id=str(organization_id),
            lead_id=str(customer_id),
            control_mode=dto.control_mode,
            preferred_channel=dto.channel,
            status=norm_status,
            metadata_=dto.metadata or {}
        )
        self.db.add(conv)

        # Conversation control record
        control = ConversationControl(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            organization_id=str(organization_id),
            control_mode=dto.control_mode
        )
        self.db.add(control)

        # Channel Link
        link = ConversationChannelLink(
            id=str(uuid.uuid4()),
            conversation_id=conv_id,
            organization_id=str(organization_id),
            channel=dto.channel,
            channel_identifier=lead.phone or "unknown",
            provider_name="system"
        )
        self.db.add(link)

        await self.db.commit()
        await self.db.refresh(conv)

        # Emit event
        await self.event_bus.publish(DomainEvent(
            event_type=StandardDomainEvents.CONVERSATION_CREATED,
            organization_id=str(organization_id),
            payload={"conversation_id": conv.id, "customer_id": str(customer_id), "channel": dto.channel}
        ))

        return ConversationResponse(
            id=conv.id,
            organization_id=conv.organization_id,
            customer_id=conv.lead_id,
            status=conv.status.upper(),
            channel=conv.preferred_channel,
            control_mode=conv.control_mode,
            total_messages=conv.total_messages,
            unread_count=conv.unread_count,
            last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
            last_message_preview=conv.last_message_preview,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat()
        )

    async def get_conversations(
        self,
        organization_id: str,
        customer_id: str
    ) -> List[ConversationResponse]:
        """Lists conversations for a customer within tenant scope."""
        stmt = (
            select(OmnichannelConversation)
            .where(
                and_(
                    OmnichannelConversation.organization_id == str(organization_id),
                    OmnichannelConversation.lead_id == str(customer_id)
                )
            )
            .order_by(desc(OmnichannelConversation.created_at))
        )
        res = await self.db.execute(stmt)
        items = res.scalars().all()

        return [
            ConversationResponse(
                id=c.id,
                organization_id=c.organization_id,
                customer_id=c.lead_id,
                status=c.status.upper(),
                channel=c.preferred_channel,
                control_mode=c.control_mode,
                total_messages=c.total_messages,
                unread_count=c.unread_count,
                last_message_at=c.last_message_at.isoformat() if c.last_message_at else None,
                last_message_preview=c.last_message_preview,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat()
            )
            for c in items
        ]

    # ─── 5. Message Domain ───────────────────────────────────────────────────

    async def create_message(
        self,
        organization_id: str,
        customer_id: str,
        conversation_id: str,
        dto: MessageCreateDTO
    ) -> MessageResponse:
        """
        Creates a canonical message with sender_type validation and credential stripping.
        Sender Types: CUSTOMER | AI_AGENT | HUMAN_AGENT | SYSTEM
        """
        sender_type_norm = dto.sender_type.upper().strip()
        allowed_types = {"CUSTOMER", "AI_AGENT", "HUMAN_AGENT", "SYSTEM"}
        if sender_type_norm not in allowed_types:
            raise ValueError(f"Invalid sender_type '{dto.sender_type}'. Must be one of: {allowed_types}")

        # Verify conversation belongs to customer and organization
        stmt_conv = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.id == conversation_id,
                OmnichannelConversation.organization_id == str(organization_id),
                OmnichannelConversation.lead_id == str(customer_id)
            )
        )
        conv = (await self.db.execute(stmt_conv)).scalar_one_or_none()
        if not conv:
            raise KeyError(f"Conversation '{conversation_id}' not found for customer.")

        # Direction logic
        direction = "inbound" if sender_type_norm == "CUSTOMER" else "outbound"
        sent_by_ai = sender_type_norm == "AI_AGENT"
        sanitized_content = _sanitize_content(dto.content)
        now = datetime.now(timezone.utc)

        msg_id = str(uuid.uuid4())
        msg = ChannelMessage(
            id=msg_id,
            conversation_id=conversation_id,
            organization_id=str(organization_id),
            lead_id=str(customer_id),
            channel=dto.channel or conv.preferred_channel,
            direction=direction,
            sender_type=sender_type_norm,
            sent_by_ai=sent_by_ai,
            message_type=dto.message_type,
            content=sanitized_content,
            sender_identifier=sender_type_norm.lower(),
            sender_name=sender_type_norm.replace("_", " ").title(),
            delivery_status="delivered",
            sent_at=now,
            delivered_at=now,
            content_structured=dto.metadata
        )
        self.db.add(msg)

        # Update conversation stats
        conv.total_messages += 1
        conv.last_message_at = now
        conv.last_message_preview = sanitized_content[:200]
        if direction == "inbound":
            conv.unread_count += 1

        # Also update customer lead last_message_at
        stmt_lead = select(Lead).where(Lead.id == _to_uuid(customer_id))
        lead = (await self.db.execute(stmt_lead)).scalar_one_or_none()
        if lead:
            lead.last_message_at = now

        await self.db.commit()
        await self.db.refresh(msg)

        # Emit events
        event_name = StandardDomainEvents.MESSAGE_RECEIVED if direction == "inbound" else StandardDomainEvents.MESSAGE_CREATED
        await self.event_bus.publish(DomainEvent(
            event_type=event_name,
            organization_id=str(organization_id),
            payload={
                "message_id": msg.id,
                "conversation_id": conversation_id,
                "customer_id": str(customer_id),
                "sender_type": sender_type_norm,
                "direction": direction
            }
        ))

        return MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            customer_id=msg.lead_id,
            organization_id=msg.organization_id,
            sender_type=msg.resolved_sender_type,
            direction=msg.direction,
            content=msg.content,
            message_type=msg.message_type,
            delivery_status=msg.delivery_status,
            timestamp=msg.created_at.isoformat(),
            metadata=msg.content_structured
        )

    async def get_messages(
        self,
        organization_id: str,
        customer_id: str,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[MessageResponse]:
        """Retrieves paginated messages for a conversation in chronological order."""
        # Verify conversation ownership
        stmt_conv = select(OmnichannelConversation).where(
            and_(
                OmnichannelConversation.id == conversation_id,
                OmnichannelConversation.organization_id == str(organization_id),
                OmnichannelConversation.lead_id == str(customer_id)
            )
        )
        conv = (await self.db.execute(stmt_conv)).scalar_one_or_none()
        if not conv:
            raise KeyError(f"Conversation '{conversation_id}' not found.")

        stmt = (
            select(ChannelMessage)
            .where(
                and_(
                    ChannelMessage.conversation_id == conversation_id,
                    ChannelMessage.organization_id == str(organization_id)
                )
            )
            .order_by(ChannelMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.db.execute(stmt)
        messages = res.scalars().all()

        return [
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                customer_id=m.lead_id,
                organization_id=m.organization_id,
                sender_type=m.resolved_sender_type,
                direction=m.direction,
                content=m.content,
                message_type=m.message_type,
                delivery_status=m.delivery_status,
                timestamp=m.created_at.isoformat(),
                metadata=m.content_structured
            )
            for m in messages
        ]

    # ─── 6. Bounded 4-Tier Conversation Memory ───────────────────────────────

    async def get_bounded_memory(
        self,
        organization_id: str,
        customer_id: str,
        conversation_id: Optional[str] = None
    ) -> BoundedMemoryContextResponse:
        """
        Builds the canonical 4-tier bounded memory context:
        Level 1: CURRENT_TURN — latest in-flight message exchange
        Level 2: CURRENT_SESSION — recent window (up to 6 messages)
        Level 3: CUSTOMER_MEMORY — verified requirements, positive/negative preferences, objections
        Level 4: CRM_MEMORY — pipeline stage, score, assigned broker/agent, CRM tasks
        """
        # Fetch customer Lead
        org_uuid = _to_uuid(organization_id)
        cust_uuid = _to_uuid(customer_id)
        stmt_lead = select(Lead).where(
            and_(Lead.id == cust_uuid, Lead.broker_id == org_uuid, Lead.deleted_at.is_(None))
        )
        lead = (await self.db.execute(stmt_lead)).scalar_one_or_none()
        if not lead:
            raise KeyError(f"Customer '{customer_id}' not found.")

        # 1. CURRENT_TURN & 2. CURRENT_SESSION
        current_turn: Optional[Dict[str, Any]] = None
        current_session: Dict[str, Any] = {"channel": "unknown", "recent_messages": []}

        if conversation_id:
            stmt_msgs = (
                select(ChannelMessage)
                .where(
                    and_(
                        ChannelMessage.conversation_id == conversation_id,
                        ChannelMessage.organization_id == str(organization_id)
                    )
                )
                .order_by(desc(ChannelMessage.created_at))
                .limit(6)
            )
            recent_msgs = (await self.db.execute(stmt_msgs)).scalars().all()
            recent_msgs.reverse()

            if recent_msgs:
                latest = recent_msgs[-1]
                current_turn = {
                    "sender_type": latest.resolved_sender_type,
                    "direction": latest.direction,
                    "content": latest.content,
                    "timestamp": latest.created_at.isoformat()
                }
                current_session = {
                    "conversation_id": conversation_id,
                    "recent_turn_count": len(recent_msgs),
                    "recent_messages": [
                        f"[{m.resolved_sender_type}]: {m.content}" for m in recent_msgs
                    ]
                }

        # 3. CUSTOMER_MEMORY
        req_profile = await self.get_requirement_profile(organization_id, customer_id)

        # Active objections
        stmt_obj = select(MemoryObjection).where(
            and_(
                MemoryObjection.organization_id == str(organization_id),
                MemoryObjection.lead_id == str(customer_id),
                MemoryObjection.status == "OPEN"
            )
        )
        objections = (await self.db.execute(stmt_obj)).scalars().all()

        # Property feedback (rejected or liked)
        stmt_fb = select(MemoryPropertyFeedback).where(
            and_(
                MemoryPropertyFeedback.organization_id == str(organization_id),
                MemoryPropertyFeedback.lead_id == str(customer_id)
            )
        ).limit(5)
        feedbacks = (await self.db.execute(stmt_fb)).scalars().all()

        customer_memory = {
            "requirements": {
                "budget_min": req_profile.budget_min,
                "budget_max": req_profile.budget_max,
                "currency": req_profile.currency,
                "locations": req_profile.locations,
                "property_types": req_profile.property_types,
                "bhk": req_profile.bhk,
                "timeline": req_profile.timeline,
                "purpose": req_profile.purpose,
            },
            "negative_preferences": [np["description"] for np in req_profile.negative_preferences],
            "positive_preferences": [pp["key"] for pp in req_profile.positive_preferences],
            "active_objections": [f"[{o.category}] {o.description}" for o in objections],
            "property_feedback": [
                f"Property {f.property_id}: {f.feedback_type}" + (f" ({f.rejection_reason_code})" if f.rejection_reason_code else "")
                for f in feedbacks
            ]
        }

        # 4. CRM_MEMORY
        crm_memory = {
            "customer_id": str(lead.id),
            "pipeline_stage": lead.pipeline_stage,
            "status": lead.status,
            "score": lead.score,
            "score_confidence": lead.score_confidence,
            "financing_status": lead.loan_status,
            "source": lead.source,
            "created_at": lead.created_at.isoformat()
        }

        # Format compact prompt context string
        context_lines = [
            "=== CUSTOMER CONVERSATION MEMORY CONTEXT ===",
            f"Customer ID: {lead.id} | Stage: {lead.pipeline_stage.upper()} | Score: {lead.score.upper()}",
            "--- Customer Requirements (Verified) ---",
            f"Budget: {req_profile.currency} {req_profile.budget_min or 0} - {req_profile.budget_max or 'Open'}",
            f"Locations: {', '.join(req_profile.locations) if req_profile.locations else 'Any'}",
            f"Property Types: {', '.join(req_profile.property_types) if req_profile.property_types else 'Any'}",
            f"BHK: {', '.join(str(b) for b in req_profile.bhk) if req_profile.bhk else 'Any'}",
            f"Timeline: {req_profile.timeline or 'Flexible'}",
            "--- Negative Constraints (Strict Disqualifiers) ---",
            "\n".join(f"- {n}" for n in customer_memory["negative_preferences"]) if customer_memory["negative_preferences"] else "- None recorded",
            "--- Open Objections ---",
            "\n".join(f"- {o}" for o in customer_memory["active_objections"]) if customer_memory["active_objections"] else "- None",
            "--- Recent Session Dialogue (Last 6 messages) ---",
            "\n".join(current_session.get("recent_messages", [])) if current_session.get("recent_messages") else "(No prior dialogue in session)"
        ]
        formatted_prompt_context = "\n".join(context_lines)

        return BoundedMemoryContextResponse(
            customer_id=str(customer_id),
            conversation_id=conversation_id,
            current_turn=current_turn,
            current_session=current_session,
            customer_memory=customer_memory,
            crm_memory=crm_memory,
            formatted_prompt_context=formatted_prompt_context
        )
