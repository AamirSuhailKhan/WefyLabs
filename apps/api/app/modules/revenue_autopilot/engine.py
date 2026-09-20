"""
Part 35 — AI Real Estate Revenue Autopilot Engine
==================================================
Deterministic scoring, explainability, urgency classification,
deduplication, opportunity lifecycle, and demand gap intelligence.
Strict Principles:
1. Grounded in real CRM data — zero invented prices or hallucinated properties.
2. Property Match Score is separated from Revenue Opportunity Score.
3. Scoring is transparent, explainable, and versioned ("v1").
4. Strict multi-tenant isolation on all database queries.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, update

from app.models.lead import Lead
from app.models.property_models import PropertyListing, PropertyPriceHistory, LeadPropertyInterest
from app.models.crm_models import Task, Meeting, Activity
from app.models.broker import Broker
from app.models.revenue_autopilot_models import RevenueOpportunity, RevenueFeedbackLog
from app.modules.property_recommendation.matching_service import AIPropertyMatchingEngine
from app.modules.property_recommendation.requirement_normalizer import (
    RequirementNormalizer, extract_bedrooms_from_text
)
from app.modules.revenue_autopilot.dto import (
    ActionQueueItemDTO,
    RevenueOpportunityDTO,
    DemandGapItemDTO,
    DemandIntelligenceResponseDTO,
)

logger = logging.getLogger("beetlelabs.revenue_autopilot.engine")

SCORING_VERSION = "v1"

# Scoring factor weights (Transparent & Deterministic)
SCORING_WEIGHTS = {
    "match_fit": 0.35,
    "lead_recency": 0.20,
    "lead_engagement": 0.15,
    "urgency_signal": 0.15,
    "inventory_freshness": 0.15,
}

VALID_STATUS_TRANSITIONS = {
    "NEW": {"RECOMMENDED", "ACTIONED", "DISMISSED", "EXPIRED", "INVALIDATED"},
    "RECOMMENDED": {"ACTIONED", "IN_PROGRESS", "DISMISSED", "EXPIRED", "INVALIDATED"},
    "ACTIONED": {"IN_PROGRESS", "COMPLETED", "DISMISSED", "INVALIDATED"},
    "IN_PROGRESS": {"COMPLETED", "DISMISSED", "INVALIDATED"},
    "COMPLETED": set(),
    "DISMISSED": set(),
    "EXPIRED": set(),
    "INVALIDATED": set(),
}


class RevenueAutopilotEngine:
    """
    Central operational engine for AI Revenue Autopilot.
    Evaluates revenue opportunities, scores actionability, classifies urgency,
    and manages opportunity lifecycle and demand intelligence.
    """

    def __init__(self, db: AsyncSession, matching_engine: Optional[AIPropertyMatchingEngine] = None):
        self.db = db
        self.matching_engine = matching_engine or AIPropertyMatchingEngine(db)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Deterministic Scoring & Explainability
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def calculate_revenue_opportunity_score(
        cls,
        match_score: float,
        lead: Lead,
        prop: Optional[PropertyListing] = None,
        category: str = "NEW_HIGH_VALUE_MATCH",
        now: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[float, List[str], List[str], Dict[str, Any]]:
        """
        Calculates Revenue Opportunity Score (0-100) separating suitability from commercial urgency.
        Returns: (opportunity_score, positive_signals, negative_signals, data_freshness)
        """
        now = now or datetime.now(timezone.utc)
        positive_signals: List[str] = []
        negative_signals: List[str] = []
        freshness: Dict[str, Any] = {}

        # 1. Match Fit Score (0-100)
        s_match = min(100.0, max(0.0, match_score))
        if s_match >= 90.0:
            positive_signals.append(f"Strong property fit ({s_match:.0f}% match)")
        elif s_match >= 75.0:
            positive_signals.append(f"Good property fit ({s_match:.0f}% match)")
        elif s_match > 0:
            negative_signals.append(f"Moderate match ({s_match:.0f}%)")

        # 2. Lead Recency Score (0-100)
        last_activity = lead.last_message_at or lead.updated_at or lead.created_at
        if last_activity:
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            delta = now - last_activity
            hours_ago = delta.total_seconds() / 3600.0
            freshness["lead_activity_hours_ago"] = round(hours_ago, 1)

            if hours_ago <= 12:
                s_recency = 100.0
                positive_signals.append("Lead active in last 12 hours")
            elif hours_ago <= 24:
                s_recency = 90.0
                positive_signals.append("Lead active today")
            elif hours_ago <= 72:
                s_recency = 75.0
                positive_signals.append(f"Last contact {int(hours_ago // 24)} days ago")
            elif hours_ago <= 168:  # 7 days
                s_recency = 50.0
                negative_signals.append("No interaction for 4-7 days")
            elif hours_ago <= 720:  # 30 days
                s_recency = 25.0
                negative_signals.append(f"Inactive for {int(hours_ago // 24)} days")
                if category in ("STALE_HOT_LEAD", "REACTIVATION_OPPORTUNITY"):
                    s_recency = 75.0
            else:  # > 30 days
                s_recency = 5.0
                negative_signals.append(f"Inactive for {int(hours_ago // 24)} days")
                if category in ("STALE_HOT_LEAD", "REACTIVATION_OPPORTUNITY"):
                    s_recency = 65.0
        else:
            s_recency = 50.0
            hours_ago = 0.0
            freshness["lead_activity_hours_ago"] = None

        # 3. Lead Engagement Tier Score (0-100)
        lead_score_tier = (lead.score or "warm").lower().strip()
        if lead_score_tier == "hot":
            s_engagement = 100.0
            positive_signals.append("High-intent 'HOT' buyer tier")
        elif lead_score_tier == "warm":
            s_engagement = 75.0
            positive_signals.append("Qualified warm buyer interest")
        elif lead_score_tier in ("cold", "pending"):
            s_engagement = 35.0
        else:
            s_engagement = 20.0
            negative_signals.append(f"Buyer lead status: {lead_score_tier}")

        # 4. Urgency & SLA Factor (0-100)
        s_urgency = 50.0
        if hours_ago and hours_ago > 336 and category not in ("STALE_HOT_LEAD", "REACTIVATION_OPPORTUNITY"):
            # Dormant leads (> 14 days) should not have artificially high urgency
            s_urgency = 20.0
            negative_signals.append("Low immediate urgency due to lead dormancy")
        elif category in ("HOT_LEAD_NEEDS_CONTACT", "NEW_HIGH_VALUE_MATCH"):
            s_urgency = 90.0
            positive_signals.append("Immediate contact required to prevent drop-off")
        elif category in ("POST_SITE_VISIT_FOLLOW_UP", "SITE_VISIT_FOLLOW_UP"):
            s_urgency = 95.0
            positive_signals.append("Site visit follow-up window closing")
        elif category == "PRICE_CHANGE_MATCH":
            s_urgency = 85.0
            positive_signals.append("New price drop created budget compatibility")
        elif category == "DEAL_STALLED":
            s_urgency = 80.0
            negative_signals.append("Deal stalled in pipeline — requires intervention")
        elif category == "STALE_HOT_LEAD":
            s_urgency = 70.0
            positive_signals.append("High lifetime value at risk of churn")

        # 5. Inventory Freshness & Event Factor (0-100)
        s_inventory = 60.0
        if prop:
            prop_created = prop.created_at
            if prop_created:
                if prop_created.tzinfo is None:
                    prop_created = prop_created.replace(tzinfo=timezone.utc)
                prop_hours = (now - prop_created).total_seconds() / 3600.0
                freshness["property_listed_hours_ago"] = round(prop_hours, 1)
                if prop_hours <= 48:
                    s_inventory = 100.0
                    positive_signals.append("Fresh listing added in last 48 hours")
                elif prop_hours <= 168:
                    s_inventory = 85.0
                    positive_signals.append("New inventory listed this week")
            if prop.construction_status and "ready" in prop.construction_status.lower():
                positive_signals.append("Ready-to-move inventory available")
            if prop.locality:
                positive_signals.append(f"Located in prime {prop.locality}")

        # Composite Calculation
        w = SCORING_WEIGHTS
        composite = (
            s_match * w["match_fit"]
            + s_recency * w["lead_recency"]
            + s_engagement * w["lead_engagement"]
            + s_urgency * w["urgency_signal"]
            + s_inventory * w["inventory_freshness"]
        )
        opp_score = round(min(100.0, max(0.0, composite)), 1)
        return opp_score, positive_signals, negative_signals, freshness

    @classmethod
    def classify_urgency(
        cls,
        category: str,
        opportunity_score: float,
        lead: Lead,
        hours_since_activity: Optional[float] = None,
    ) -> str:
        """
        Classifies urgency: CRITICAL | HIGH | MEDIUM | LOW.
        Deterministic rules based on category and timeliness.
        """
        if category in ("POST_SITE_VISIT_FOLLOW_UP", "HOT_LEAD_NEEDS_CONTACT"):
            if hours_since_activity and hours_since_activity >= 24:
                return "CRITICAL"
            return "HIGH"

        if category == "DEAL_STALLED":
            return "HIGH"

        if category in ("NEW_HIGH_VALUE_MATCH", "PRICE_CHANGE_MATCH"):
            if opportunity_score >= 85.0:
                return "HIGH"
            return "MEDIUM"

        if category in ("STALE_HOT_LEAD", "REACTIVATION_OPPORTUNITY"):
            return "MEDIUM"

        if opportunity_score >= 90.0:
            return "CRITICAL"
        elif opportunity_score >= 75.0:
            return "HIGH"
        elif opportunity_score >= 50.0:
            return "MEDIUM"
        return "LOW"

    @classmethod
    def classify_priority(cls, opportunity_score: float, urgency: str) -> str:
        """Determines display priority from score and urgency."""
        if urgency == "CRITICAL" or opportunity_score >= 88.0:
            return "CRITICAL"
        if urgency == "HIGH" or opportunity_score >= 72.0:
            return "HIGH"
        if opportunity_score >= 50.0:
            return "MEDIUM"
        return "LOW"

    @classmethod
    def evaluate_confidence(cls, lead: Lead, prop: Optional[PropertyListing] = None) -> float:
        """Evaluates confidence (0.0 to 1.0) based on verified CRM data completeness."""
        known = 0
        total = 3.0
        if lead.budget_max or lead.budget_min:
            known += 1
        if lead.preferred_locations and len(lead.preferred_locations) > 0:
            known += 1
        bhk = extract_bedrooms_from_text(lead.property_type) if lead.property_type else None
        if bhk or lead.property_type:
            known += 1

        if prop:
            total += 1.0
            if prop.price and (prop.locality or prop.city):
                known += 1

        ratio = known / total
        return round(min(1.0, max(0.25, ratio)), 2)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. State Machine & Deduplication Key
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def generate_dedup_key(
        cls,
        organization_id: uuid.UUID | str,
        lead_id: uuid.UUID | str,
        property_id: Optional[uuid.UUID | str],
        opportunity_type: str,
    ) -> str:
        """
        Generates stable deduplication key for active lifecycle tracking:
        f"{org_id}:{lead_id}:{prop_id or 'none'}:{opportunity_type}"
        """
        p_str = str(property_id) if property_id else "none"
        return f"{str(organization_id)}:{str(lead_id)}:{p_str}:{opportunity_type}"

    @classmethod
    def validate_transition(cls, current_status: str, new_status: str) -> bool:
        """Validates state machine transitions."""
        current_status = current_status.upper()
        new_status = new_status.upper()
        if current_status == new_status:
            return True
        allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
        return new_status in allowed

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Opportunity Invalidation
    # ─────────────────────────────────────────────────────────────────────────

    async def invalidate_stale_opportunities(self, broker_uuid: uuid.UUID) -> int:
        """
        Automatically invalidates opportunities when underlying conditions no longer hold:
        - Property is sold / inactive / unavailable
        - Lead is converted, lost, or soft-deleted
        - Expiration timestamp passed
        """
        now = datetime.now(timezone.utc)
        active_statuses = ["NEW", "RECOMMENDED", "ACTIONED", "IN_PROGRESS"]

        # 1. Fetch active opportunities for tenant
        stmt = select(RevenueOpportunity).where(
            and_(
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.status.in_(active_statuses),
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        opps = list((await self.db.execute(stmt)).scalars().all())
        invalidated_count = 0

        for opp in opps:
            should_invalidate = False
            reason = None

            # Check expiration
            exp = opp.expires_at
            if exp:
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < now:
                    opp.status = "EXPIRED"
                    invalidated_count += 1
                    continue

            # Check Lead status
            lead_stmt = select(Lead).where(
                and_(Lead.id == opp.lead_id, Lead.broker_id == broker_uuid)
            )
            lead = (await self.db.execute(lead_stmt)).scalars().first()
            if not lead or lead.deleted_at is not None:
                should_invalidate = True
                reason = "Lead deleted or removed from CRM"
            elif lead.status in ("converted", "lost"):
                should_invalidate = True
                reason = f"Lead lifecycle stage transitioned to '{lead.status}'"

            # Check Property status if property-tied
            if not should_invalidate and opp.property_id:
                prop_stmt = select(PropertyListing).where(
                    and_(PropertyListing.id == opp.property_id, PropertyListing.broker_id == broker_uuid)
                )
                prop = (await self.db.execute(prop_stmt)).scalars().first()
                if not prop or prop.deleted_at is not None:
                    should_invalidate = True
                    reason = "Property removed from inventory"
                elif (prop.status or "").lower() not in ("available", "active", "ready"):
                    should_invalidate = True
                    reason = f"Property status changed to '{prop.status}'"

            if should_invalidate:
                opp.status = "INVALIDATED"
                opp.dismissal_reason = reason
                invalidated_count += 1

        if invalidated_count > 0:
            await self.db.commit()
            logger.info(f"Invalidated {invalidated_count} stale revenue opportunities for broker {broker_uuid}")

        return invalidated_count

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Multi-Category Tenant Opportunity Generation & Evaluation
    # ─────────────────────────────────────────────────────────────────────────

    async def evaluate_tenant_opportunities(
        self,
        broker: Broker,
        limit_candidates: int = 50,
    ) -> List[RevenueOpportunity]:
        """
        Evaluates active leads, inventory, and activities for an organization,
        generating deduplicated revenue opportunities across all categories.
        """
        broker_uuid = uuid.UUID(str(broker.id))
        org_uuid = uuid.UUID(str(getattr(broker, "organization_id", None) or broker.id))
        now = datetime.now(timezone.utc)

        # Invalidate stale ones first
        await self.invalidate_stale_opportunities(broker_uuid)

        # 1. Fetch active leads (not lost, not converted, not soft-deleted)
        leads_stmt = select(Lead).where(
            and_(
                Lead.broker_id == broker_uuid,
                Lead.deleted_at.is_(None),
                Lead.status.in_(["pending", "active", "qualified"])
            )
        ).order_by(Lead.updated_at.desc()).limit(limit_candidates)
        leads = list((await self.db.execute(leads_stmt)).scalars().all())

        # 2. Fetch available properties
        props_stmt = select(PropertyListing).where(
            and_(
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None),
                PropertyListing.status == "available"
            )
        ).order_by(PropertyListing.created_at.desc()).limit(100)
        properties = list((await self.db.execute(props_stmt)).scalars().all())

        # 3. Fetch recent price drops in last 7 days
        seven_days_ago = now - timedelta(days=7)
        price_drop_stmt = select(PropertyPriceHistory, PropertyListing).join(
            PropertyListing, PropertyPriceHistory.property_id == PropertyListing.id
        ).where(
            and_(
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None),
                PropertyPriceHistory.changed_at >= seven_days_ago,
                PropertyPriceHistory.new_price < PropertyPriceHistory.old_price
            )
        )
        price_drops = list((await self.db.execute(price_drop_stmt)).all())

        # 4. Fetch completed site visits in last 48 hours without follow-up task
        forty_eight_hours_ago = now - timedelta(hours=48)
        visits_stmt = select(Meeting).where(
            and_(
                Meeting.broker_id == broker_uuid,
                Meeting.status.in_(["completed", "COMPLETED"]),
                Meeting.scheduled_at >= forty_eight_hours_ago,
                Meeting.lead_id.isnot(None)
            )
        )
        completed_visits = list((await self.db.execute(visits_stmt)).scalars().all())

        # Include canonical SchedulingMeeting records
        from app.models.calendar_models import Meeting as SchedulingMeeting
        sched_stmt = select(SchedulingMeeting).where(
            and_(
                SchedulingMeeting.broker_id == broker_uuid,
                SchedulingMeeting.status.in_(["completed", "COMPLETED"]),
                SchedulingMeeting.start_utc >= forty_eight_hours_ago,
                SchedulingMeeting.lead_id.isnot(None)
            )
        )
        sched_visits = list((await self.db.execute(sched_stmt)).scalars().all())
        all_completed_visits = completed_visits + sched_visits

        # 5. Fetch existing active opportunities for deduplication
        existing_stmt = select(RevenueOpportunity).where(
            and_(
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.status.in_(["NEW", "RECOMMENDED", "ACTIONED", "IN_PROGRESS"]),
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        existing_opps = list((await self.db.execute(existing_stmt)).scalars().all())
        existing_by_key: Dict[str, RevenueOpportunity] = {o.dedup_key: o for o in existing_opps}

        generated_opportunities: List[RevenueOpportunity] = []

        # ── Evaluation Category A: High-Value Match & New Property Match ───────
        for lead in leads:
            req = RequirementNormalizer.normalize(lead=lead)
            top_matches: List[Tuple[PropertyListing, float, List[str], List[str]]] = []

            for prop in properties:
                is_valid, _ = self.matching_engine.evaluate_hard_constraints(
                    prop=prop,
                    lead=lead,
                    req=req,
                    allow_alternatives=False
                )
                if not is_valid:
                    continue

                m_score, breakdown, reasons, mismatches = self.matching_engine.calculate_compatibility_score(
                    prop=prop,
                    lead=lead,
                    req=req
                )
                if m_score >= 70.0:
                    top_matches.append((prop, m_score, reasons, mismatches))

            top_matches.sort(key=lambda x: x[1], reverse=True)

            if top_matches:
                primary_prop, primary_match_score, m_reasons, m_mismatches = top_matches[0]
                alternatives = [
                    {
                        "property_id": str(alt_prop.id),
                        "title": alt_prop.title,
                        "price": alt_prop.price,
                        "currency": alt_prop.currency_code or "INR",
                        "match_score": alt_score,
                        "bedrooms": alt_prop.bedrooms,
                        "locality": alt_prop.locality or alt_prop.city,
                    }
                    for alt_prop, alt_score, _, _ in top_matches[1:4]
                ]

                # Determine if NEW_HIGH_VALUE_MATCH or NEW_PROPERTY_MATCH
                is_new_listing = (now - primary_prop.created_at.replace(tzinfo=timezone.utc)).total_seconds() < 172800 if primary_prop.created_at else False
                opp_type = "NEW_PROPERTY_MATCH" if is_new_listing else "NEW_HIGH_VALUE_MATCH"

                opp_score, pos_signals, neg_signals, freshness = self.calculate_revenue_opportunity_score(
                    match_score=primary_match_score,
                    lead=lead,
                    prop=primary_prop,
                    category=opp_type,
                    now=now
                )
                urgency = self.classify_urgency(opp_type, opp_score, lead)
                priority = self.classify_priority(opp_score, urgency)
                conf = self.evaluate_confidence(lead, primary_prop)

                why_now_desc = (
                    f"Lead is actively looking for {lead.property_type or 'homes'} in "
                    f"{', '.join(lead.preferred_locations or ['the city'])}. "
                    f"{'New inventory listed in the last 48 hours.' if is_new_listing else 'High compatibility with live inventory.'}"
                )
                why_prop_desc = (
                    f"Matches stated budget (₹{primary_prop.price:,.0f}), "
                    f"{primary_prop.bedrooms} BHK requirement, and locality ({primary_prop.locality or primary_prop.city})."
                )

                dedup_key = self.generate_dedup_key(org_uuid, lead.id, primary_prop.id, opp_type)
                existing = existing_by_key.get(dedup_key)

                prop_snapshot = {
                    "property_id": str(primary_prop.id),
                    "title": primary_prop.title,
                    "price": primary_prop.price,
                    "currency": primary_prop.currency_code or "INR",
                    "locality": primary_prop.locality or primary_prop.city,
                    "bedrooms": primary_prop.bedrooms,
                    "bathrooms": primary_prop.bathrooms,
                    "area_value": primary_prop.area_value,
                    "area_unit": primary_prop.area_unit,
                    "status": primary_prop.status,
                }

                default_call_brief = {
                    "lead_name": lead.name or "Buyer",
                    "objective": f"Recommend {primary_prop.title}",
                    "key_requirements": f"{primary_prop.bedrooms}BHK, budget ₹{lead.budget_max or 0:,.0f}",
                    "relevant_context": f"Matched {primary_match_score:.0f}% with live inventory",
                    "suggested_opening": f"Hi {lead.name or 'there'}, I noticed you are exploring properties in {primary_prop.locality or 'this area'}. We have a verified {primary_prop.bedrooms}BHK matching your criteria."
                }
                default_email_draft = {
                    "subject": f"Curated Property Match: {primary_prop.title}",
                    "body": f"Dear {lead.name or 'Client'},\n\nBased on your preferred criteria, we have identified a {primary_prop.bedrooms}BHK in {primary_prop.locality or primary_prop.city} listed at ₹{primary_prop.price:,.0f}.\n\nWould you be available for a brief viewing this week?\n\nBest regards,\nYour Real Estate Advisory Team",
                    "cta": "Schedule Viewing"
                }

                if existing:
                    existing.opportunity_score = opp_score
                    existing.match_score = primary_match_score
                    existing.priority = priority
                    existing.urgency = urgency
                    existing.confidence = conf
                    existing.positive_signals = pos_signals
                    existing.negative_signals = neg_signals
                    existing.data_freshness = freshness
                    existing.alternative_properties = alternatives
                    existing.recommended_property_snapshot = prop_snapshot
                    generated_opportunities.append(existing)
                else:
                    opp = RevenueOpportunity(
                        organization_id=org_uuid,
                        broker_id=broker_uuid,
                        lead_id=lead.id,
                        property_id=primary_prop.id,
                        assigned_agent_id=lead.broker_id,
                        opportunity_type=opp_type,
                        priority=priority,
                        urgency=urgency,
                        opportunity_score=opp_score,
                        match_score=primary_match_score,
                        confidence=conf,
                        status="RECOMMENDED",
                        reason=f"High-confidence {primary_match_score:.0f}% property match for active buyer.",
                        why_now=why_now_desc,
                        why_property=why_prop_desc,
                        risk_of_inactivity="Buyer may explore competitor listings if not contacted within 24 hours.",
                        recommended_action="CALL_LEAD",
                        recommended_channel="CALL",
                        recommended_property_snapshot=prop_snapshot,
                        alternative_properties=alternatives,
                        positive_signals=pos_signals,
                        negative_signals=neg_signals,
                        data_freshness=freshness,
                        call_brief=default_call_brief,
                        email_draft=default_email_draft,
                        dedup_key=dedup_key,
                        provenance=["lead_preferences", "property_inventory", "compatibility_engine_v1"],
                        scoring_version=SCORING_VERSION,
                        expires_at=now + timedelta(days=7),
                    )
                    self.db.add(opp)
                    generated_opportunities.append(opp)
                    existing_by_key[dedup_key] = opp

        # ── Evaluation Category B: Stale Hot Leads & Reactivation ─────────────
        for lead in leads:
            if (lead.score or "").lower() == "hot":
                last_msg = lead.last_message_at or lead.updated_at or lead.created_at
                if last_msg:
                    if last_msg.tzinfo is None:
                        last_msg = last_msg.replace(tzinfo=timezone.utc)
                    days_inactive = (now - last_msg).total_seconds() / 86400.0
                    if days_inactive >= 4.0:
                        opp_type = "STALE_HOT_LEAD"
                        dedup_key = self.generate_dedup_key(org_uuid, lead.id, None, opp_type)
                        if dedup_key not in existing_by_key:
                            opp_score, pos_signals, neg_signals, freshness = self.calculate_revenue_opportunity_score(
                                match_score=50.0,
                                lead=lead,
                                category=opp_type,
                                now=now
                            )
                            opp = RevenueOpportunity(
                                organization_id=org_uuid,
                                broker_id=broker_uuid,
                                lead_id=lead.id,
                                property_id=None,
                                assigned_agent_id=lead.broker_id,
                                opportunity_type=opp_type,
                                priority="HIGH",
                                urgency="HIGH",
                                opportunity_score=opp_score,
                                match_score=0.0,
                                confidence=0.85,
                                status="RECOMMENDED",
                                reason=f"High-intent buyer has had no recorded contact for {int(days_inactive)} days.",
                                why_now=f"Lead was classified as HOT but has been inactive for {int(days_inactive)} days. Fast re-engagement protects pipeline conversion.",
                                why_property="No specific property selected. Recommended to share latest matching portfolio.",
                                risk_of_inactivity="Lead will cool down and consider competitors.",
                                recommended_action="REACTIVATE_LEAD",
                                recommended_channel="CALL",
                                recommended_property_snapshot={},
                                alternative_properties=[],
                                positive_signals=pos_signals,
                                negative_signals=neg_signals,
                                data_freshness=freshness,
                                call_brief={
                                    "lead_name": lead.name or "Buyer",
                                    "objective": "Re-activate dormant conversation and verify current timeline",
                                    "key_requirements": f"Budget: ₹{lead.budget_max or 0:,.0f}",
                                    "suggested_opening": f"Hi {lead.name or 'there'}, checking in to see if you are still seeking properties in {', '.join(lead.preferred_locations or ['town'])}."
                                },
                                email_draft={
                                    "subject": "Quick update on your property search",
                                    "body": f"Hi {lead.name or 'there'},\n\nWe have several new properties that just became available in your preferred areas. Are you still actively looking?\n\nBest,",
                                    "cta": "Reply to Discuss"
                                },
                                dedup_key=dedup_key,
                                provenance=["lead_score", "last_message_at", "inactivity_detector"],
                                scoring_version=SCORING_VERSION,
                                expires_at=now + timedelta(days=5),
                            )
                            self.db.add(opp)
                            generated_opportunities.append(opp)
                            existing_by_key[dedup_key] = opp

        # ── Evaluation Category C: Post Site Visit Follow-Ups ─────────────────
        for visit in all_completed_visits:
            lead_stmt = select(Lead).where(and_(Lead.id == visit.lead_id, Lead.broker_id == broker_uuid))
            visit_lead = (await self.db.execute(lead_stmt)).scalars().first()
            if not visit_lead:
                continue

            # Determine property_id and location from visit (supporting both SchedulingMeeting and legacy Meeting)
            prop_id = None
            if hasattr(visit, "property_id") and getattr(visit, "property_id"):
                prop_id = getattr(visit, "property_id")
            else:
                from app.models.calendar_models import Viewing
                stmt_view = select(Viewing).where(Viewing.meeting_id == str(visit.id))
                res_view = await self.db.execute(stmt_view)
                v_record = res_view.scalars().first()
                if v_record and v_record.property_id:
                    prop_id = v_record.property_id

            visit_location = getattr(visit, "location_address", None) or getattr(visit, "location", None) or "property"
            visit_time = getattr(visit, "start_utc", None) or getattr(visit, "scheduled_at", None)

            prop_uuid = None
            if prop_id:
                try:
                    prop_uuid = uuid.UUID(str(prop_id))
                except Exception:
                    prop_uuid = None

            opp_type = "POST_SITE_VISIT_FOLLOW_UP"
            dedup_key = self.generate_dedup_key(org_uuid, visit_lead.id, prop_id, opp_type)
            if dedup_key not in existing_by_key:
                opp = RevenueOpportunity(
                    organization_id=org_uuid,
                    broker_id=broker_uuid,
                    lead_id=visit_lead.id,
                    property_id=prop_uuid,
                    assigned_agent_id=visit_lead.broker_id,
                    opportunity_type=opp_type,
                    priority="CRITICAL",
                    urgency="CRITICAL",
                    opportunity_score=94.0,
                    match_score=85.0,
                    confidence=0.95,
                    status="RECOMMENDED",
                    reason=f"Site visit completed at {visit_location}. Follow-up call required.",
                    why_now="Site visit completed recently. Immediate post-visit feedback is the single highest predictor of deal closure.",
                    why_property=f"Viewing was conducted at {visit_location}.",
                    risk_of_inactivity="Unaddressed client objections lead to ghosting after viewings.",
                    recommended_action="FOLLOW_UP_AFTER_SITE_VISIT",
                    recommended_channel="CALL",
                    recommended_property_snapshot={},
                    alternative_properties=[],
                    positive_signals=["Site visit completed", "In-person interaction established"],
                    negative_signals=["No follow-up logged yet"],
                    data_freshness={"visit_completed_at": visit_time.isoformat() if visit_time else None},
                    call_brief={
                        "lead_name": visit_lead.name or "Client",
                        "objective": "Collect feedback on site visit, address objections, and propose offer or next viewing",
                        "key_requirements": f"Location: {visit_location}",
                        "suggested_opening": f"Hi {visit_lead.name or 'there'}, thank you for attending the site visit at {visit_location}. How did you feel about the layout and location?"
                    },
                    email_draft={
                        "subject": f"Thank you for visiting {visit_location}",
                        "body": f"Dear {visit_lead.name or 'Client'},\n\nIt was a pleasure showing you the property. Please let us know if you'd like to review the floor plans, pricing structure, or schedule another visit.\n\nWarm regards,",
                        "cta": "Submit Feedback"
                    },
                    dedup_key=dedup_key,
                    provenance=["meetings_audit", "visit_completed_trigger"],
                    scoring_version=SCORING_VERSION,
                    expires_at=now + timedelta(days=3),
                )
                self.db.add(opp)
                generated_opportunities.append(opp)
                existing_by_key[dedup_key] = opp

        # ── Evaluation Category D: Price Drops Matching Active Leads ──────────
        for price_hist, prop in price_drops:
            for lead in leads:
                if lead.budget_max and price_hist.new_price <= (lead.budget_max * 1.05):
                    opp_type = "PRICE_CHANGE_MATCH"
                    dedup_key = self.generate_dedup_key(org_uuid, lead.id, prop.id, opp_type)
                    if dedup_key not in existing_by_key:
                        opp_score, pos_signals, neg_signals, freshness = self.calculate_revenue_opportunity_score(
                            match_score=85.0,
                            lead=lead,
                            prop=prop,
                            category=opp_type,
                            now=now
                        )
                        pos_signals.append(f"Price reduced from ₹{price_hist.old_price:,.0f} to ₹{price_hist.new_price:,.0f}")
                        opp = RevenueOpportunity(
                            organization_id=org_uuid,
                            broker_id=broker_uuid,
                            lead_id=lead.id,
                            property_id=prop.id,
                            assigned_agent_id=lead.broker_id,
                            opportunity_type=opp_type,
                            priority="HIGH",
                            urgency="HIGH",
                            opportunity_score=opp_score,
                            match_score=85.0,
                            confidence=0.9,
                            status="RECOMMENDED",
                            reason=f"Price drop from ₹{price_hist.old_price:,.0f} to ₹{price_hist.new_price:,.0f} brings {prop.title} into buyer budget.",
                            why_now="Recent price revision moved property directly into buyer's target budget.",
                            why_property=f"Matches buyer budget of ₹{lead.budget_max:,.0f} following ₹{(price_hist.old_price - price_hist.new_price):,.0f} reduction.",
                            risk_of_inactivity="Other buyers monitoring this property will act on the price reduction.",
                            recommended_action="SEND_PROPERTY_RECOMMENDATION",
                            recommended_channel="CALL",
                            recommended_property_snapshot={
                                "property_id": str(prop.id),
                                "title": prop.title,
                                "price": price_hist.new_price,
                                "old_price": price_hist.old_price,
                                "currency": prop.currency_code or "INR",
                                "locality": prop.locality or prop.city,
                                "bedrooms": prop.bedrooms,
                            },
                            alternative_properties=[],
                            positive_signals=pos_signals,
                            negative_signals=neg_signals,
                            data_freshness=freshness,
                            call_brief={
                                "lead_name": lead.name or "Buyer",
                                "objective": f"Notify buyer of price drop on {prop.title}",
                                "key_requirements": f"New price: ₹{price_hist.new_price:,.0f}",
                                "suggested_opening": f"Hi {lead.name or 'there'}, a property in {prop.locality or 'your target area'} just had a price drop to ₹{price_hist.new_price:,.0f}, perfectly fitting your budget."
                            },
                            email_draft={
                                "subject": f"Price Drop Alert: {prop.title}",
                                "body": f"Dear {lead.name or 'Client'},\n\nWe wanted you to be the first to know: {prop.title} has just been reduced from ₹{price_hist.old_price:,.0f} to ₹{price_hist.new_price:,.0f}.\n\nWould you like to schedule a viewing before it sells?",
                                "cta": "View Price Details"
                            },
                            dedup_key=dedup_key,
                            provenance=["price_history_event", "budget_match"],
                            scoring_version=SCORING_VERSION,
                            expires_at=now + timedelta(days=7),
                        )
                        self.db.add(opp)
                        generated_opportunities.append(opp)
                        existing_by_key[dedup_key] = opp

        await self.db.commit()
        return generated_opportunities

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Demand Gap Intelligence
    # ─────────────────────────────────────────────────────────────────────────

    async def get_demand_gap_intelligence(self, broker: Broker) -> DemandIntelligenceResponseDTO:
        """
        Aggregates active buyer preferences across the tenant,
        identifying localities and BHK types with supply deficits.
        """
        broker_uuid = uuid.UUID(str(broker.id))

        # 1. Fetch active leads with location and BHK
        leads_stmt = select(Lead).where(
            and_(
                Lead.broker_id == broker_uuid,
                Lead.deleted_at.is_(None),
                Lead.status.in_(["pending", "active", "qualified"])
            )
        )
        leads = list((await self.db.execute(leads_stmt)).scalars().all())

        # 2. Fetch available properties
        props_stmt = select(PropertyListing).where(
            and_(
                PropertyListing.broker_id == broker_uuid,
                PropertyListing.deleted_at.is_(None),
                PropertyListing.status == "available"
            )
        )
        properties = list((await self.db.execute(props_stmt)).scalars().all())

        # Group demand by (locality, bhk)
        demand_map: Dict[Tuple[str, int], int] = {}
        locality_counter: Dict[str, int] = {}

        for lead in leads:
            bhk = extract_bedrooms_from_text(lead.property_type) or 2
            locations = lead.preferred_locations or ["General"]
            for loc in locations:
                norm_loc = loc.strip().title()
                key = (norm_loc, bhk)
                demand_map[key] = demand_map.get(key, 0) + 1
                locality_counter[norm_loc] = locality_counter.get(norm_loc, 0) + 1

        # Group supply by (locality, bhk)
        supply_map: Dict[Tuple[str, int], int] = {}
        for prop in properties:
            norm_loc = (prop.locality or prop.city or "General").strip().title()
            bhk = prop.bedrooms or 2
            key = (norm_loc, bhk)
            supply_map[key] = supply_map.get(key, 0) + 1

        # Calculate gaps
        gaps: List[DemandGapItemDTO] = []
        for (loc, bhk), demand_count in demand_map.items():
            supply_count = supply_map.get((loc, bhk), 0)
            deficit = demand_count - supply_count
            if deficit > 0:
                urgency = "CRITICAL" if deficit >= 5 else ("HIGH" if deficit >= 3 else "MEDIUM")
                gap_item = DemandGapItemDTO(
                    segment_id=f"{loc.lower()}-{bhk}bhk",
                    locality=loc,
                    bedrooms=bhk,
                    property_type="Apartment",
                    budget_band="Segment Target",
                    active_buyer_demand_count=demand_count,
                    matching_inventory_count=supply_count,
                    deficit_count=deficit,
                    urgency=urgency,
                    recommended_action=f"Acquire {deficit} more {bhk}BHK properties in {loc} to satisfy active buyer demand."
                )
                gaps.append(gap_item)

        gaps.sort(key=lambda g: g.deficit_count, reverse=True)

        sorted_localities = sorted(locality_counter.keys(), key=lambda l: locality_counter[l], reverse=True)

        return DemandIntelligenceResponseDTO(
            total_active_buyers=len(leads),
            total_available_listings=len(properties),
            top_demand_gaps=gaps[:5],
            high_demand_localities=sorted_localities[:5]
        )

    async def get_action_queue(self, broker: Broker, limit: int = 10) -> List[RevenueOpportunity]:
        """
        Returns top actionable opportunities for the tenant, ordered by urgency and score.
        """
        broker_uuid = uuid.UUID(str(broker.id))
        stmt = (
            select(RevenueOpportunity)
            .where(
                and_(
                    RevenueOpportunity.broker_id == broker_uuid,
                    RevenueOpportunity.status.in_(["NEW", "RECOMMENDED", "ACTIONED"]),
                    RevenueOpportunity.deleted_at.is_(None)
                )
            )
            .order_by(
                desc(RevenueOpportunity.urgency == "CRITICAL"),
                desc(RevenueOpportunity.opportunity_score),
                desc(RevenueOpportunity.created_at)
            )
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

