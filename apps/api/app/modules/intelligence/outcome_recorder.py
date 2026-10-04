"""
Sprint 1E — Outcome Recorder
==============================
Lightweight bridge that operational modules use to write canonical OutcomeEvent
records into the learning layer.

DESIGN RULES:
- This module is a WRITE-ONLY bridge. It only creates OutcomeEvent records.
- It NEVER modifies any operational record (leads, deals, bookings, revenue).
- Failures MUST NOT propagate to the calling operational code.
  The learning signal is valuable but never business-critical.
- Every event must have a traceable source_event_id and source_table.
- occurred_at must use the operational business timestamp — never datetime.now().

USAGE PATTERN:
    from app.modules.intelligence.outcome_recorder import OutcomeRecorder

    # Inside an operational service method, after a successful DB commit:
    await OutcomeRecorder.safe_record(
        db=session,
        org_id=deal.organization_id,
        event_type=OutcomeEventType.SITE_VISIT_COMPLETED,
        entity_type=OutcomeEntityType.SITE_VISIT,
        entity_id=str(visit.id),
        source_table="site_visits",
        source_event_id=str(visit.id),
        occurred_at=visit.completed_at,
        lead_id=str(visit.lead_id),
        opportunity_id=str(visit.deal_id) if visit.deal_id else None,
        metadata={...},
    )
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence_models import (
    OutcomeEvent,
    OutcomeEventType,
    OutcomeEntityType,
    OutcomeSource,
)

logger = logging.getLogger("wefylabs.intelligence.outcome_recorder")


class OutcomeRecorder:
    """
    Provides safe, non-blocking outcome event recording for operational modules.

    All methods are class methods. No instance state.
    Failures are caught and logged — they never propagate to callers.
    """

    @classmethod
    async def safe_record(
        cls,
        db: AsyncSession,
        org_id: str,
        event_type: OutcomeEventType,
        entity_type: OutcomeEntityType,
        entity_id: str,
        source_table: str,
        occurred_at: datetime,
        *,
        source_event_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        property_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        actor_type: str = "SYSTEM",
        channel: Optional[str] = None,
        outcome_source: OutcomeSource = OutcomeSource.SYSTEM,
        revenue_impact: Optional[Decimal] = None,
        currency: str = "AED",
        metadata: Optional[Dict[str, Any]] = None,
        is_human_override: bool = False,
    ) -> Optional[str]:
        """
        Records an OutcomeEvent. Returns the event ID if successful, None on failure.
        Failure is logged but NEVER raised.
        """
        try:
            event_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            event = OutcomeEvent(
                id=event_id,
                organization_id=org_id,
                event_type=event_type.value if isinstance(event_type, OutcomeEventType) else str(event_type),
                entity_type=entity_type.value if isinstance(entity_type, OutcomeEntityType) else str(entity_type),
                entity_id=str(entity_id),
                source_system=outcome_source.value if isinstance(outcome_source, OutcomeSource) else str(outcome_source),
                source_event_id=source_event_id or str(entity_id),
                source_table=source_table,
                actor_type=actor_type,
                actor_id=str(agent_id) if agent_id else None,
                is_human_override=is_human_override,
                lead_id=str(lead_id) if lead_id else None,
                opportunity_id=str(opportunity_id) if opportunity_id else None,
                property_id=str(property_id) if property_id else None,
                agent_id=str(agent_id) if agent_id else None,
                channel=channel,
                revenue_impact=revenue_impact,
                currency=currency,
                occurred_at=occurred_at,
                captured_at=now,
                metadata_json=metadata or {},
            )
            db.add(event)
            await db.flush()

            logger.info(
                "[OutcomeRecorder] Recorded %s for entity=%s lead=%s org=%s",
                event_type,
                entity_id,
                lead_id,
                org_id,
            )
            return event_id

        except Exception as exc:
            logger.warning(
                "[OutcomeRecorder] Failed to record outcome event %s for entity=%s org=%s: %s",
                event_type,
                entity_id,
                org_id,
                exc,
            )
            return None

    @classmethod
    async def record_site_visit_completed(
        cls,
        db: AsyncSession,
        org_id: str,
        visit_id: str,
        lead_id: str,
        deal_id: Optional[str],
        property_id: Optional[str],
        agent_id: Optional[str],
        completed_at: datetime,
        outcome_notes: Optional[str] = None,
    ) -> Optional[str]:
        """Convenience method for site visit completion."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.SITE_VISIT_COMPLETED,
            entity_type=OutcomeEntityType.SITE_VISIT,
            entity_id=visit_id,
            source_table="site_visits",
            source_event_id=visit_id,
            occurred_at=completed_at,
            lead_id=lead_id,
            opportunity_id=deal_id,
            property_id=property_id,
            agent_id=agent_id,
            actor_type="HUMAN",
            outcome_source=OutcomeSource.HUMAN,
            metadata={"outcome_notes": outcome_notes} if outcome_notes else {},
        )

    @classmethod
    async def record_site_visit_no_show(
        cls,
        db: AsyncSession,
        org_id: str,
        visit_id: str,
        lead_id: str,
        deal_id: Optional[str],
        agent_id: Optional[str],
        occurred_at: datetime,
    ) -> Optional[str]:
        """Convenience method for site visit no-show."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.SITE_VISIT_NO_SHOW,
            entity_type=OutcomeEntityType.SITE_VISIT,
            entity_id=visit_id,
            source_table="site_visits",
            source_event_id=visit_id,
            occurred_at=occurred_at,
            lead_id=lead_id,
            opportunity_id=deal_id,
            agent_id=agent_id,
            actor_type="SYSTEM",
            outcome_source=OutcomeSource.SYSTEM,
        )

    @classmethod
    async def record_offer_accepted(
        cls,
        db: AsyncSession,
        org_id: str,
        offer_id: str,
        lead_id: str,
        deal_id: str,
        property_id: Optional[str],
        agent_id: Optional[str],
        offer_amount: Optional[Decimal],
        currency: str,
        accepted_at: datetime,
    ) -> Optional[str]:
        """Convenience method for offer acceptance."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.OFFER_ACCEPTED,
            entity_type=OutcomeEntityType.OFFER,
            entity_id=offer_id,
            source_table="negotiation_rounds",
            source_event_id=offer_id,
            occurred_at=accepted_at,
            lead_id=lead_id,
            opportunity_id=deal_id,
            property_id=property_id,
            agent_id=agent_id,
            actor_type="HUMAN",
            outcome_source=OutcomeSource.HUMAN,
            revenue_impact=offer_amount,
            currency=currency,
            is_human_override=False,
        )

    @classmethod
    async def record_deal_won(
        cls,
        db: AsyncSession,
        org_id: str,
        deal_id: str,
        lead_id: str,
        property_id: Optional[str],
        agent_id: Optional[str],
        revenue_amount: Optional[Decimal],
        currency: str,
        won_at: datetime,
    ) -> Optional[str]:
        """Convenience method for deal won / revenue realized."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.REVENUE_REALIZED,
            entity_type=OutcomeEntityType.OPPORTUNITY,
            entity_id=deal_id,
            source_table="deals",
            source_event_id=deal_id,
            occurred_at=won_at,
            lead_id=lead_id,
            opportunity_id=deal_id,
            property_id=property_id,
            agent_id=agent_id,
            actor_type="HUMAN",
            outcome_source=OutcomeSource.HUMAN,
            revenue_impact=revenue_amount,
            currency=currency,
        )

    @classmethod
    async def record_deal_lost(
        cls,
        db: AsyncSession,
        org_id: str,
        deal_id: str,
        lead_id: str,
        agent_id: Optional[str],
        lost_reason: Optional[str],
        lost_at: datetime,
    ) -> Optional[str]:
        """Convenience method for deal lost."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.OPPORTUNITY_LOST,
            entity_type=OutcomeEntityType.OPPORTUNITY,
            entity_id=deal_id,
            source_table="deals",
            source_event_id=deal_id,
            occurred_at=lost_at,
            lead_id=lead_id,
            opportunity_id=deal_id,
            agent_id=agent_id,
            actor_type="HUMAN",
            outcome_source=OutcomeSource.HUMAN,
            metadata={"lost_reason": lost_reason} if lost_reason else {},
        )

    @classmethod
    async def record_lead_qualified(
        cls,
        db: AsyncSession,
        org_id: str,
        lead_id: str,
        qualified_by: str,  # "AI" | "HUMAN" | "DETERMINISTIC_POLICY"
        qualification_score: Optional[float],
        qualified_at: datetime,
    ) -> Optional[str]:
        """Convenience method for lead qualification."""
        actor_type = "AI_AGENT" if qualified_by == "AI" else "HUMAN" if qualified_by == "HUMAN" else "SYSTEM"
        outcome_source = OutcomeSource.AI_AGENT if qualified_by == "AI" else (
            OutcomeSource.HUMAN if qualified_by == "HUMAN" else OutcomeSource.AUTOMATION
        )
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.LEAD_QUALIFIED,
            entity_type=OutcomeEntityType.LEAD,
            entity_id=lead_id,
            source_table="leads",
            source_event_id=lead_id,
            occurred_at=qualified_at,
            lead_id=lead_id,
            actor_type=actor_type,
            outcome_source=outcome_source,
            metadata={
                "qualified_by": qualified_by,
                "qualification_score": qualification_score,
            },
        )

    @classmethod
    async def record_followup_completed(
        cls,
        db: AsyncSession,
        org_id: str,
        work_item_id: str,
        lead_id: str,
        channel: Optional[str],
        agent_id: Optional[str],
        completed_at: datetime,
        response_received: bool = False,
    ) -> Optional[str]:
        """Convenience method for follow-up execution completion."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.FOLLOWUP_COMPLETED,
            entity_type=OutcomeEntityType.FOLLOW_UP,
            entity_id=work_item_id,
            source_table="work_items",
            source_event_id=work_item_id,
            occurred_at=completed_at,
            lead_id=lead_id,
            agent_id=agent_id,
            channel=channel,
            actor_type="HUMAN" if agent_id else "SYSTEM",
            outcome_source=OutcomeSource.HUMAN if agent_id else OutcomeSource.AUTOMATION,
            metadata={
                "response_received": response_received,
            },
        )

    @classmethod
    async def record_property_match_shared(
        cls,
        db: AsyncSession,
        org_id: str,
        match_id: str,
        lead_id: str,
        property_id: str,
        agent_id: Optional[str],
        match_score: Optional[float],
        shared_at: datetime,
    ) -> Optional[str]:
        """Convenience method for property match sharing."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.PROPERTY_SHORTLISTED,
            entity_type=OutcomeEntityType.PROPERTY,
            entity_id=property_id,
            source_table="property_match_results",
            source_event_id=match_id,
            occurred_at=shared_at,
            lead_id=lead_id,
            property_id=property_id,
            agent_id=agent_id,
            actor_type="HUMAN" if agent_id else "AI_AGENT",
            outcome_source=OutcomeSource.AI_AGENT,
            metadata={
                "match_id": match_id,
                "match_score": match_score,
            },
        )

    @classmethod
    async def record_booking_intent_created(
        cls,
        db: AsyncSession,
        org_id: str,
        booking_intent_id: str,
        lead_id: str,
        deal_id: str,
        property_id: Optional[str],
        agent_id: Optional[str],
        intent_amount: Optional[Decimal],
        currency: str,
        created_at: datetime,
    ) -> Optional[str]:
        """Convenience method for booking intent creation."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.BOOKING_CREATED,
            entity_type=OutcomeEntityType.BOOKING,
            entity_id=booking_intent_id,
            source_table="booking_intents",
            source_event_id=booking_intent_id,
            occurred_at=created_at,
            lead_id=lead_id,
            opportunity_id=deal_id,
            property_id=property_id,
            agent_id=agent_id,
            actor_type="HUMAN",
            outcome_source=OutcomeSource.HUMAN,
            revenue_impact=intent_amount,
            currency=currency,
        )

    @classmethod
    async def record_nba_recommended(
        cls,
        db: AsyncSession,
        org_id: str,
        recommendation_id: str,
        lead_id: str,
        action_type: str,
        reason: str,
        generated_at: datetime,
        generated_by: str = "SYSTEM",
    ) -> Optional[str]:
        """Records that an NBA recommendation was generated (not yet acted upon)."""
        return await cls.safe_record(
            db=db,
            org_id=org_id,
            event_type=OutcomeEventType.AI_ACTION_ACCEPTED,  # Will be tracked via AIActionOutcome
            entity_type=OutcomeEntityType.AI_ACTION,
            entity_id=recommendation_id,
            source_table="command_center_priority_items",
            source_event_id=recommendation_id,
            occurred_at=generated_at,
            lead_id=lead_id,
            actor_type="AI_AGENT",
            outcome_source=OutcomeSource.AI_AGENT,
            metadata={
                "action_type": action_type,
                "reason": reason,
                "generated_by": generated_by,
            },
        )
