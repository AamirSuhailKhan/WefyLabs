"""
Part 3 — Matching Intelligence Facade
======================================
Unified, tool-ready facade encapsulating:
- Canonical Lead ↔ Property Matching (AIPropertyMatchingEngine)
- Match Explanation & Structured Criteria Breakdown
- Lead Shortlist Management (LeadPropertyInterest)
- Customer-Property Interaction & Rejection Feedback (MemoryPropertyFeedback)
- Lead Qualification Snapshots & Missing Info (LeadQualificationDomainService)

Enforces strict tenant isolation, deterministic business rules, and zero hallucinations.
Part 4 AI tools consume this service without executing raw SQL or calculating scores.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.property_recommendation.matching_service import AIPropertyMatchingEngine
from app.modules.property_recommendation.dto import (
    PropertyRecommendationResponseDTO,
    PropertyShortlistResponseDTO,
    PropertyInteractionRequestDTO,
    PropertyInteractionResponseDTO,
    MatchExplanationDTO,
    ShortlistRequestDTO,
)
from app.modules.lead_qualification.service import LeadQualificationDomainService
from app.modules.lead_qualification.dto import (
    QualificationSnapshotDTO,
    QualificationMissingInfoDTO,
)

logger = logging.getLogger(__name__)


class MatchingIntelligenceFacade:
    """
    Authoritative facade for property matching, shortlists, customer interactions,
    and lead qualification. Built for direct consumption by future AI Sales Agent tools.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.matching_engine = AIPropertyMatchingEngine(db)
        self.qualification_service = LeadQualificationDomainService(db)

    async def _resolve_broker(self, tenant_id: str | uuid.UUID) -> Broker:
        """Helper to resolve broker instance within tenant scope."""
        tenant_uuid = uuid.UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
        stmt = select(Broker).where(Broker.id == tenant_uuid)
        broker = (await self.db.execute(stmt)).scalars().first()
        if not broker:
            broker = Broker(id=tenant_uuid, name="Tenant Broker", email="tenant@brokerage.com")
        return broker

    async def find_matches(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
        requirement_profile: Optional[Any] = None,
        top_k: int = 5,
        limit: Optional[int] = None,
        allow_alternatives: bool = False,
        flexibility_pct: float = 0.0,
        sort: str = "score_desc",
        force_refresh: bool = False,
        minimum_score: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Finds authoritative ranked property matches for a customer.
        Strict deterministic evaluation — never calls an LLM to invent matches.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        effective_limit = limit or top_k
        res = await self.matching_engine.match_properties_for_lead(
            lead_id=lead_id,
            broker=broker,
            top_k=effective_limit,
            allow_alternatives=allow_alternatives,
            flexibility_pct=flexibility_pct,
            sort=sort,
            force_refresh=force_refresh,
            minimum_score=minimum_score,
            requirement_profile=requirement_profile,
        )
        return {
            "status": "success",
            "lead_id": str(lead_id),
            "organization_id": str(tid),
            "total_matches": len(res.items),
            "results": [
                {
                    "property_id": str(item.property_id),
                    "property_title": item.property_title,
                    "property_code": item.property_code,
                    "compatibility_score": item.compatibility_score,
                    "match_label": item.match_label,
                    "is_alternative": item.is_alternative,
                    "price": item.price,
                    "locality": item.locality,
                    "city": item.city,
                    "bedrooms": item.bedrooms,
                    "matched_criteria": item.requirement_coverage.matched,
                    "negative_conflicts": item.requirement_coverage.negative_conflicts,
                    "unknown_criteria": item.requirement_coverage.unknown,
                }
                for item in res.items
            ],
            "no_match_reasons": res.no_match_reasons,
            "dto": res
        }

    async def explain_match(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        property_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves granular explainable criteria (matched, partial, unmet, negative_conflicts, unknown).
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        dto = await self.matching_engine.explain_property_match(
            lead_id=lead_id,
            property_id=property_id,
            broker=broker,
        )
        return {
            "status": "success",
            "property_id": str(property_id),
            "lead_id": str(lead_id),
            "match_score": dto.match_score,
            "confidence": dto.confidence,
            "recommendation_type": dto.recommendation_type,
            "matched_criteria": dto.matched_criteria,
            "partial_criteria": dto.partial_criteria,
            "unmatched_criteria": dto.unmatched_criteria,
            "negative_conflicts": dto.negative_conflicts,
            "unknown_criteria": dto.unknown_criteria,
            "deterministic_summary": dto.deterministic_summary,
            "talking_points": dto.talking_points,
            "dto": dto
        }

    async def shortlist_property(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        property_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
        notes: Optional[str] = None,
        interest_level: str = "high",
    ) -> Dict[str, Any]:
        """
        Shortlists a property in the canonical LeadPropertyInterest junction.
        Idempotent operation with tenant verification and audit trail.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        dto = ShortlistRequestDTO(
            lead_id=str(lead_id),
            property_id=str(property_id),
            notes=notes,
            interest_level=interest_level,
        )
        result = await self.matching_engine.shortlist_property_for_lead(
            lead_id=lead_id,
            property_id=property_id,
            broker=broker,
            dto=dto,
        )

        # ── Sprint 1E: Learning layer wiring for property demand ──────────────
        try:
            from app.modules.intelligence.outcome_recorder import OutcomeRecorder
            from app.models.intelligence_models import OutcomeEventType, OutcomeEntityType, OutcomeSource
            from datetime import datetime, timezone
            await OutcomeRecorder.safe_record(
                db=self.db,
                org_id=str(tid),
                event_type=OutcomeEventType.PROPERTY_SHORTLISTED,
                entity_type=OutcomeEntityType.PROPERTY,
                entity_id=str(property_id),
                source_table="lead_property_interest",
                source_event_id=str(property_id),
                occurred_at=datetime.now(timezone.utc),
                lead_id=str(lead_id) if lead_id else None,
                property_id=str(property_id),
                agent_id=str(broker.id),
                actor_type="HUMAN",
                outcome_source=OutcomeSource.HUMAN,
                metadata={"interest_level": interest_level, "notes": notes},
            )
        except Exception as exc:
            logger.warning(f"[MatchingIntelligence] Learning record error on shortlist: {exc}")

        return result

    async def remove_from_shortlist(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        property_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Removes a property from a lead's shortlist with audit trail.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        return await self.matching_engine.remove_property_from_shortlist(
            lead_id=lead_id,
            property_id=property_id,
            broker=broker,
        )

    async def get_shortlist(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
        status_filter: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Retrieves paginated shortlisted/saved properties for a customer.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        res = await self.matching_engine.get_lead_shortlist(
            lead_id=lead_id,
            broker=broker,
            status_filter=status_filter,
            offset=offset,
            limit=limit,
        )
        return {
            "status": "success",
            "lead_id": str(lead_id),
            "organization_id": str(tid),
            "total_count": res.total_count,
            "items": [item.model_dump() for item in res.items],
            "dto": res
        }

    async def record_property_interaction(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        property_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
        interaction_type: str = "VIEWED",
        rejection_reason: Optional[str] = None,
        notes: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records customer interaction (VIEWED, LIKED, SHORTLISTED, REJECTED, VISITED).
        Persists structured rejection reasons to MemoryPropertyFeedback.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        dto = PropertyInteractionRequestDTO(
            lead_id=str(lead_id),
            property_id=str(property_id),
            interaction_type=interaction_type,
            rejection_reason=rejection_reason,
            notes=notes or feedback,
            feedback=feedback or notes,
        )
        res = await self.matching_engine.record_property_interaction(
            req=dto,
            broker=broker,
        )

        # ── Sprint 1E: Learning layer wiring for customer preferences ─────────
        try:
            from app.modules.intelligence.outcome_recorder import OutcomeRecorder
            from app.models.intelligence_models import OutcomeEventType, OutcomeEntityType, OutcomeSource
            from datetime import datetime, timezone
            itype = (interaction_type or "").upper()
            evt_type = (
                OutcomeEventType.PROPERTY_MATCH_ACCEPTED if itype in ("LIKED", "SHORTLISTED")
                else OutcomeEventType.PROPERTY_MATCH_REJECTED if itype == "REJECTED"
                else OutcomeEventType.PROPERTY_VISITED if itype == "VISITED"
                else OutcomeEventType.PROPERTY_DISCUSSED
            )
            await OutcomeRecorder.safe_record(
                db=self.db,
                org_id=str(tid),
                event_type=evt_type,
                entity_type=OutcomeEntityType.PROPERTY,
                entity_id=str(property_id),
                source_table="memory_property_feedback",
                source_event_id=str(property_id),
                occurred_at=datetime.now(timezone.utc),
                lead_id=str(lead_id) if lead_id else None,
                property_id=str(property_id),
                agent_id=str(broker.id),
                actor_type="HUMAN",
                outcome_source=OutcomeSource.HUMAN,
                metadata={
                    "interaction_type": interaction_type,
                    "rejection_reason": rejection_reason,
                    "notes": notes or feedback,
                },
            )
        except Exception as exc:
            logger.warning(f"[MatchingIntelligence] Learning record error on interaction: {exc}")

        return {
            "status": "success",
            "lead_id": str(lead_id),
            "property_id": str(property_id),
            "interaction_type": res.interaction_type,
            "interest_status": res.interest_status,
            "rejection_reason": res.rejection_reason,
            "dto": res
        }

    # Alias for tool calling
    record_interaction = record_property_interaction

    async def get_qualification(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
    ) -> QualificationSnapshotDTO:
        """
        Retrieves deterministically evaluated qualification snapshot for lead.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        return await self.qualification_service.get_lead_qualification_snapshot(
            organization_id=str(tid),
            lead_id=str(lead_id),
            broker=broker,
        )

    async def get_missing_qualification(
        self,
        tenant_id: Optional[str | uuid.UUID] = None,
        lead_id: Optional[str | uuid.UUID] = None,
        organization_id: Optional[str | uuid.UUID] = None,
    ) -> QualificationMissingInfoDTO:
        """
        Retrieves prioritized missing qualification information and recommended question prompts.
        """
        tid = tenant_id or organization_id
        if not tid:
            raise ValueError("tenant_id or organization_id must be provided")
        broker = await self._resolve_broker(tid)
        return await self.qualification_service.get_missing_qualification_info(
            organization_id=str(tid),
            lead_id=str(lead_id),
            broker=broker,
        )
