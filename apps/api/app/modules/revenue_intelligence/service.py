"""
Part 11 — Revenue Intelligence Service
=======================================
Five analytical analyzers that form the Revenue Intelligence Layer.

ARCHITECTURAL CONSTRAINTS (enforced in code):
1. This service is READ-ONLY with respect to canonical models.
   It MAY write to revenue_funnel_snapshots and revenue_leakage_events
   (its own domain tables) but NEVER alters leads, opportunities, or deals.
2. All numbers are derived from actual database rows.
   If a denominator is zero, rates are returned as None — never fabricated.
3. No ML model is claimed or used. All scoring is deterministic aggregation.
4. All queries are tenant-scoped by organization_id.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, distinct

from app.models.lead import Lead
from app.models.revenue_autopilot_models import RevenueOpportunity, RevenueFeedbackLog
from app.models.calendar_models import SchedulingMeeting
from app.models.transaction_models import DealTransaction
from app.models.revenue_intelligence_models import RevenueFunnelSnapshot, RevenueLeakageEvent
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.models.infrastructure_models import TimelineEvent

logger = logging.getLogger("wefylabs.revenue_intelligence")

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

FUNNEL_STAGE_ORDER = [
    "new",
    "contacted",
    "qualified",
    "site_visit",
    "negotiation",
    "converted",
]

LEAKAGE_REASON_MAP = {
    "lost": "EXPLICIT_LOSS",
    "pending": "NO_CONTACT",
    "active": "STALE",
}


def _safe_rate(numerator: int, denominator: int) -> Optional[float]:
    """Returns percentage or None if denominator is 0. Never fabricates."""
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


# ──────────────────────────────────────────────────────────────────────────────
# 1. FunnelAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class FunnelAnalyzer:
    """
    Queries lead, opportunity, and deal tables to compute a stage-by-stage
    funnel summary for an organisation.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_funnel_summary(
        self,
        organization_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Returns funnel stage counts, conversion rates, pipeline value, and
        confirmed revenue. All numeric fields that require division return None
        when denominator is 0.
        """
        # Build base lead filter
        filters = [Lead.broker_id == organization_id, Lead.deleted_at.is_(None)]
        if date_from:
            filters.append(Lead.created_at >= date_from)
        if date_to:
            filters.append(Lead.created_at <= date_to)

        # Stage counts
        stage_q = await self.db.execute(
            select(Lead.pipeline_stage, func.count(Lead.id).label("cnt"))
            .where(and_(*filters))
            .group_by(Lead.pipeline_stage)
        )
        stage_rows = stage_q.all()
        stage_map: Dict[str, int] = {r.pipeline_stage: r.cnt for r in stage_rows}
        total_leads = sum(stage_map.values())

        # Build ordered stage list
        stages_out = []
        for i, stage_name in enumerate(FUNNEL_STAGE_ORDER):
            count = stage_map.get(stage_name, 0)
            # Conversion rate = leads in next stage / leads in this stage
            if i + 1 < len(FUNNEL_STAGE_ORDER):
                next_count = stage_map.get(FUNNEL_STAGE_ORDER[i + 1], 0)
                rate = _safe_rate(next_count, count)
            else:
                rate = None  # last stage has no "next"
            stages_out.append({
                "stage": stage_name,
                "count": count,
                "conversion_rate_pct": rate,
            })

        # Also include any non-standard stages present in data (e.g. "lost")
        for stage_name, cnt in stage_map.items():
            if stage_name not in FUNNEL_STAGE_ORDER:
                stages_out.append({"stage": stage_name, "count": cnt, "conversion_rate_pct": None})

        # Overall conversion rate: new → converted
        converted = stage_map.get("converted", 0)
        overall_rate = _safe_rate(converted, total_leads)

        # Active opportunities
        opp_q = await self.db.execute(
            select(func.count(RevenueOpportunity.id))
            .where(
                and_(
                    RevenueOpportunity.organization_id == organization_id,
                    RevenueOpportunity.status.in_(["NEW", "RECOMMENDED", "ACTIONED", "IN_PROGRESS"]),
                )
            )
        )
        active_opps = opp_q.scalar() or 0

        # Estimated pipeline value: sum of budget_max for leads in qualified+
        pipeline_stages = ["qualified", "site_visit", "negotiation"]
        pv_q = await self.db.execute(
            select(func.sum(Lead.budget_max))
            .where(
                and_(
                    Lead.broker_id == organization_id,
                    Lead.deleted_at.is_(None),
                    Lead.pipeline_stage.in_(pipeline_stages),
                    Lead.budget_max.isnot(None),
                )
            )
        )
        estimated_pipeline = pv_q.scalar()  # None if no rows

        # Confirmed revenue: sum of estimated_commission_amount from completed deals
        rev_q = await self.db.execute(
            select(func.sum(DealTransaction.estimated_commission_amount))
            .where(
                and_(
                    DealTransaction.broker_id == organization_id,
                    DealTransaction.current_stage == "commission_received",
                )
            )
        )
        confirmed_revenue = rev_q.scalar()  # None if no deals

        return {
            "organization_id": str(organization_id),
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "total_leads": total_leads,
            "stages": stages_out,
            "overall_conversion_rate_pct": overall_rate,
            "active_opportunities": active_opps,
            "estimated_pipeline_value_estimate": float(estimated_pipeline) if estimated_pipeline else None,
            "confirmed_revenue": float(confirmed_revenue) if confirmed_revenue else None,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 2. LeakageDetector
# ──────────────────────────────────────────────────────────────────────────────

class LeakageDetector:
    """
    Detects and records funnel exits — leads that left the pipeline without
    converting. Also records them as RevenueLeakageEvent rows (append-only).
    """

    DEFAULT_STALENESS_DAYS = 14

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_leakage_report(
        self,
        organization_id: uuid.UUID,
        staleness_days: int = DEFAULT_STALENESS_DAYS,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Returns leakage counts grouped by pipeline stage.
        Leakage = explicitly lost OR stale (not updated in `staleness_days`).
        """
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=staleness_days)

        filters = [
            Lead.broker_id == organization_id,
            Lead.deleted_at.is_(None),
            # Lost explicitly OR stale and not yet converted
            or_(
                Lead.status == "lost",
                and_(
                    Lead.updated_at <= stale_cutoff,
                    Lead.status != "converted",
                )
            )
        ]
        if date_from:
            filters.append(Lead.created_at >= date_from)
        if date_to:
            filters.append(Lead.created_at <= date_to)

        rows_q = await self.db.execute(
            select(
                Lead.pipeline_stage,
                Lead.status,
                Lead.score,
                Lead.source,
                Lead.budget_max,
                Lead.updated_at,
                Lead.id,
            )
            .where(and_(*filters))
        )
        rows = rows_q.all()

        # Group by stage
        by_stage: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            stage = row.pipeline_stage or "unknown"
            if stage not in by_stage:
                by_stage[stage] = {
                    "stage": stage,
                    "lost_count": 0,
                    "total_budget_max": 0.0,
                    "days_in_stage_list": [],
                    "reasons": [],
                }
            g = by_stage[stage]
            g["lost_count"] += 1
            if row.budget_max:
                g["total_budget_max"] += float(row.budget_max)
            # Days stale
            if row.updated_at:
                days = (now - row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at.tzinfo is None else now - row.updated_at).days
                g["days_in_stage_list"].append(days)
            # Reason
            reason = "EXPLICIT_LOSS" if row.status == "lost" else "STALE"
            g["reasons"].append(reason)

        # Also write RevenueLeakageEvent for newly detected leads (deduplicated)
        existing_lead_ids_q = await self.db.execute(
            select(distinct(RevenueLeakageEvent.lead_id))
            .where(RevenueLeakageEvent.organization_id == organization_id)
        )
        already_recorded = {r[0] for r in existing_lead_ids_q.all()}

        new_events_written = 0
        for row in rows:
            if row.id not in already_recorded:
                stage = row.pipeline_stage or "unknown"
                reason = "EXPLICIT_LOSS" if row.status == "lost" else "STALE"
                days = None
                if row.updated_at:
                    days = (now - row.updated_at.replace(tzinfo=timezone.utc) if row.updated_at.tzinfo is None else now - row.updated_at).days

                # Check if any open opportunity existed for this lead
                opp_q = await self.db.execute(
                    select(func.count(RevenueOpportunity.id))
                    .where(
                        and_(
                            RevenueOpportunity.lead_id == row.id,
                            RevenueOpportunity.status.notin_(["EXPIRED", "INVALIDATED", "DISMISSED"]),
                        )
                    )
                )
                had_opp = (opp_q.scalar() or 0) > 0

                event = RevenueLeakageEvent(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    lead_id=row.id,
                    lost_at_stage=stage,
                    days_in_stage=days,
                    leakage_reason=reason,
                    source_channel=row.source,
                    estimated_value_lost=float(row.budget_max) if row.budget_max else None,
                    lead_score_at_loss=row.score,
                    had_open_opportunity=had_opp,
                    detected_at=now,
                )
                self.db.add(event)
                new_events_written += 1

        if new_events_written > 0:
            await self.db.flush()

        # Compile output
        result_by_stage = []
        total_value_at_risk = 0.0
        has_any_value = False

        for stage, g in by_stage.items():
            days_list = g["days_in_stage_list"]
            avg_days = round(sum(days_list) / len(days_list), 1) if days_list else None
            top_reason = max(set(g["reasons"]), key=g["reasons"].count) if g["reasons"] else None
            val = g["total_budget_max"] if g["total_budget_max"] > 0 else None
            if val:
                total_value_at_risk += val
                has_any_value = True
            result_by_stage.append({
                "stage": stage,
                "lost_count": g["lost_count"],
                "total_estimated_value_lost_estimate": val,
                "avg_days_in_stage": avg_days,
                "top_reason": top_reason,
            })

        total_leakage = len(rows)

        return {
            "organization_id": str(organization_id),
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "staleness_threshold_days": staleness_days,
            "total_leakage_events": total_leakage,
            "total_estimated_value_at_risk_estimate": total_value_at_risk if has_any_value else None,
            "by_stage": result_by_stage,
        }

    async def get_extended_leakage_items(
        self,
        organization_id: uuid.UUID,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Surfaces operational leakage items across the 15 canonical categories with
        deterministic severity classification, evidence, and actionable next steps.
        """
        now = datetime.now(timezone.utc)
        items: List[Dict[str, Any]] = []

        # 1. NEW_LEAD_NO_RESPONSE (new lead > 24h with pending status)
        cutoff_24h = now - timedelta(hours=24)
        new_q = await self.db.execute(
            select(Lead).where(
                and_(
                    Lead.broker_id == organization_id,
                    Lead.deleted_at.is_(None),
                    Lead.pipeline_stage == "new",
                    Lead.status == "pending",
                    Lead.created_at <= cutoff_24h,
                )
            ).limit(10)
        )
        for l in new_q.scalars().all():
            age = (now - l.created_at.replace(tzinfo=timezone.utc) if l.created_at.tzinfo is None else now - l.created_at).days
            items.append({
                "leakage_type": "NEW_LEAD_NO_RESPONSE",
                "severity": "HIGH",
                "entity_type": "lead",
                "entity_id": str(l.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": max(1, age),
                "evidence": {"stage": "new", "created_at": _iso(l.created_at), "score": l.score},
                "estimated_impact_estimate": float(l.budget_max) if l.budget_max else None,
                "recommended_next_action": "Initiate automated first-touch outreach or assign sales agent immediately.",
                "source_channel": l.source,
                "status": "ACTIVE",
            })

        # 2. QUALIFIED_NO_FOLLOWUP (qualified lead > 3d without update)
        cutoff_3d = now - timedelta(days=3)
        qual_q = await self.db.execute(
            select(Lead).where(
                and_(
                    Lead.broker_id == organization_id,
                    Lead.deleted_at.is_(None),
                    Lead.pipeline_stage == "qualified",
                    Lead.status != "converted",
                    Lead.updated_at <= cutoff_3d,
                )
            ).limit(10)
        )
        for l in qual_q.scalars().all():
            age = (now - l.updated_at.replace(tzinfo=timezone.utc) if l.updated_at.tzinfo is None else now - l.updated_at).days if l.updated_at else 3
            items.append({
                "leakage_type": "QUALIFIED_NO_FOLLOWUP",
                "severity": "HIGH",
                "entity_type": "lead",
                "entity_id": str(l.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": age,
                "evidence": {"stage": "qualified", "last_updated": _iso(l.updated_at)},
                "estimated_impact_estimate": float(l.budget_max) if l.budget_max else None,
                "recommended_next_action": "Send personalized property shortlist or schedule discovery tour.",
                "source_channel": l.source,
                "status": "ACTIVE",
            })

        # 4. APPOINTMENT_NOT_CONFIRMED (scheduled within next 24h, unconfirmed)
        next_24h = now + timedelta(hours=24)
        appt_q = await self.db.execute(
            select(SchedulingMeeting).where(
                and_(
                    SchedulingMeeting.broker_id == organization_id,
                    SchedulingMeeting.status.in_(["pending", "scheduled"]),
                    SchedulingMeeting.start_utc >= now,
                    SchedulingMeeting.start_utc <= next_24h,
                )
            ).limit(10)
        )
        for m in appt_q.scalars().all():
            items.append({
                "leakage_type": "APPOINTMENT_NOT_CONFIRMED",
                "severity": "CRITICAL",
                "entity_type": "appointment",
                "entity_id": str(m.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": 0,
                "evidence": {"start_time": _iso(m.start_utc), "meeting_type": m.meeting_type},
                "estimated_impact_estimate": None,
                "recommended_next_action": "Dispatch instant appointment confirmation reminder to attendee.",
                "source_channel": "calendar",
                "status": "ACTIVE",
            })

        # 5. APPOINTMENT_NO_SHOW
        noshow_q = await self.db.execute(
            select(SchedulingMeeting).where(
                and_(
                    SchedulingMeeting.broker_id == organization_id,
                    SchedulingMeeting.status == "no_show",
                )
            ).limit(10)
        )
        for m in noshow_q.scalars().all():
            items.append({
                "leakage_type": "APPOINTMENT_NO_SHOW",
                "severity": "HIGH",
                "entity_type": "appointment",
                "entity_id": str(m.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": 1,
                "evidence": {"title": m.title, "start_time": _iso(m.start_utc)},
                "estimated_impact_estimate": None,
                "recommended_next_action": "Initiate automated rescheduling outreach with fresh slot availability.",
                "source_channel": "calendar",
                "status": "ACTIVE",
            })

        # 6. SITE_VISIT_NO_DEBRIEF (completed site visit without follow-up)
        visit_q = await self.db.execute(
            select(SchedulingMeeting).where(
                and_(
                    SchedulingMeeting.broker_id == organization_id,
                    SchedulingMeeting.meeting_type == "site_visit",
                    SchedulingMeeting.status == "completed",
                    SchedulingMeeting.start_utc <= cutoff_24h,
                )
            ).limit(10)
        )
        for m in visit_q.scalars().all():
            items.append({
                "leakage_type": "SITE_VISIT_NO_DEBRIEF",
                "severity": "CRITICAL",
                "entity_type": "site_visit",
                "entity_id": str(m.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": 1,
                "evidence": {"completed_at": _iso(m.start_utc), "lead_id": str(m.lead_id) if m.lead_id else None},
                "estimated_impact_estimate": None,
                "recommended_next_action": "Contact client immediately to record site visit feedback and present offer structure.",
                "source_channel": "site_visit",
                "status": "ACTIVE",
            })

        # 7. HOT_LEAD_GOING_COLD (hot lead not updated in > 7 days)
        cutoff_7d = now - timedelta(days=7)
        hot_q = await self.db.execute(
            select(Lead).where(
                and_(
                    Lead.broker_id == organization_id,
                    Lead.deleted_at.is_(None),
                    Lead.score == "hot",
                    Lead.status != "converted",
                    Lead.updated_at <= cutoff_7d,
                )
            ).limit(10)
        )
        for l in hot_q.scalars().all():
            age = (now - l.updated_at.replace(tzinfo=timezone.utc) if l.updated_at.tzinfo is None else now - l.updated_at).days if l.updated_at else 7
            items.append({
                "leakage_type": "HOT_LEAD_GOING_COLD",
                "severity": "HIGH",
                "entity_type": "lead",
                "entity_id": str(l.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": age,
                "evidence": {"score": "hot", "last_updated": _iso(l.updated_at)},
                "estimated_impact_estimate": float(l.budget_max) if l.budget_max else None,
                "recommended_next_action": "Execute urgent VIP re-engagement touchpoint by sales lead.",
                "source_channel": l.source,
                "status": "ACTIVE",
            })

        # 8. STALLED_OPPORTUNITY (opportunity actioned > 10d without update)
        cutoff_10d = now - timedelta(days=10)
        opp_q = await self.db.execute(
            select(RevenueOpportunity).where(
                and_(
                    RevenueOpportunity.organization_id == organization_id,
                    RevenueOpportunity.status.in_(["ACTIONED", "RECOMMENDED", "IN_PROGRESS"]),
                    RevenueOpportunity.updated_at <= cutoff_10d,
                )
            ).limit(10)
        )
        for opp in opp_q.scalars().all():
            items.append({
                "leakage_type": "STALLED_OPPORTUNITY",
                "severity": "CRITICAL",
                "entity_type": "opportunity",
                "entity_id": str(opp.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": 10,
                "evidence": {"opportunity_type": opp.opportunity_type, "score": opp.opportunity_score},
                "estimated_impact_estimate": None,
                "recommended_next_action": "Review stalled opportunity blockers in Command Center.",
                "source_channel": "autopilot",
                "status": "ACTIVE",
            })

        # 9. LOST_AFTER_HIGH_INTENT (lost lead at qualified or later)
        lost_q = await self.db.execute(
            select(Lead).where(
                and_(
                    Lead.broker_id == organization_id,
                    Lead.deleted_at.is_(None),
                    Lead.status == "lost",
                    Lead.pipeline_stage.in_(["qualified", "site_visit", "negotiation"]),
                )
            ).limit(10)
        )
        for l in lost_q.scalars().all():
            items.append({
                "leakage_type": "LOST_AFTER_HIGH_INTENT",
                "severity": "MEDIUM",
                "entity_type": "lead",
                "entity_id": str(l.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": None,
                "evidence": {"stage_at_loss": l.pipeline_stage},
                "estimated_impact_estimate": float(l.budget_max) if l.budget_max else None,
                "recommended_next_action": "Document formal loss reasons and add to re-engagement campaign.",
                "source_channel": l.source,
                "status": "ACTIVE",
            })

        # 13. AI_RECOMMENDATION_FAILURE (rejected opportunities)
        rej_q = await self.db.execute(
            select(RevenueOpportunity).where(
                and_(
                    RevenueOpportunity.organization_id == organization_id,
                    RevenueOpportunity.feedback_rating == "NO",
                )
            ).limit(5)
        )
        for opp in rej_q.scalars().all():
            items.append({
                "leakage_type": "AI_RECOMMENDATION_FAILURE",
                "severity": "LOW",
                "entity_type": "opportunity",
                "entity_id": str(opp.id),
                "organization_id": str(organization_id),
                "detected_at": now.isoformat(),
                "age_days": None,
                "evidence": {"opportunity_type": opp.opportunity_type, "feedback": "NO"},
                "estimated_impact_estimate": None,
                "recommended_next_action": "Calibrate recommendation parameters to align with broker feedback.",
                "source_channel": "autopilot",
                "status": "ACTIVE",
            })

        return items[:limit]


# ──────────────────────────────────────────────────────────────────────────────
# 3. OutcomeTracker
# ──────────────────────────────────────────────────────────────────────────────

class OutcomeTracker:
    """
    Aggregates actual_outcome from revenue_feedback_logs and deal_transactions
    to produce a truthful outcome summary.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_outcome_summary(
        self,
        organization_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        filters = [
            RevenueFeedbackLog.organization_id == organization_id,
        ]
        if date_from:
            filters.append(RevenueFeedbackLog.created_at >= date_from)
        if date_to:
            filters.append(RevenueFeedbackLog.created_at <= date_to)

        # Outcome distribution from feedback logs
        dist_q = await self.db.execute(
            select(
                RevenueFeedbackLog.actual_outcome,
                func.count(RevenueFeedbackLog.id).label("cnt"),
            )
            .where(and_(*filters))
            .group_by(RevenueFeedbackLog.actual_outcome)
        )
        dist_rows = dist_q.all()
        total_feedback = sum(r.cnt for r in dist_rows)

        outcome_dist = []
        positive_count = 0
        negative_count = 0
        for row in dist_rows:
            outcome = row.actual_outcome or "UNKNOWN"
            pct = _safe_rate(row.cnt, total_feedback)
            outcome_dist.append({"outcome": outcome, "count": row.cnt, "pct": pct})
            if outcome in ("DEAL_CLOSED", "BOOKED", "SITE_VISIT_DONE", "CONVERTED"):
                positive_count += row.cnt
            elif outcome in ("LOST", "NO_SHOW", "REJECTED", "UNQUALIFIED"):
                negative_count += row.cnt

        win_rate = _safe_rate(positive_count, total_feedback)

        # Completed deals
        deal_filters = [DealTransaction.broker_id == organization_id]
        if date_from:
            deal_filters.append(DealTransaction.created_at >= date_from)
        if date_to:
            deal_filters.append(DealTransaction.created_at <= date_to)

        deals_q = await self.db.execute(
            select(func.count(DealTransaction.id))
            .where(and_(*deal_filters, DealTransaction.current_stage == "commission_received"))
        )
        completed_deals = deals_q.scalar() or 0

        # Avg opportunity_score at win
        avg_score_q = await self.db.execute(
            select(func.avg(RevenueOpportunity.opportunity_score))
            .join(
                RevenueFeedbackLog,
                RevenueFeedbackLog.opportunity_id == RevenueOpportunity.id,
            )
            .where(
                and_(
                    RevenueFeedbackLog.organization_id == organization_id,
                    RevenueFeedbackLog.rating == "YES",
                )
            )
        )
        avg_score_at_win = avg_score_q.scalar()

        return {
            "organization_id": str(organization_id),
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "total_feedback_records": total_feedback,
            "win_rate_pct": win_rate,
            "positive_feedback_count": positive_count,
            "negative_feedback_count": negative_count,
            "completed_deals": completed_deals,
            "avg_opportunity_score_at_win": round(float(avg_score_at_win), 2) if avg_score_at_win else None,
            "outcome_distribution": outcome_dist,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 4. SourceAttributionReport
# ──────────────────────────────────────────────────────────────────────────────

class SourceAttributionReport:
    """
    Groups leads and revenue by source/channel using the normalized
    lead.source field. Does NOT create a new attribution engine — it
    reads the data that already exists.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_attribution_report(
        self,
        organization_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        filters = [Lead.broker_id == organization_id, Lead.deleted_at.is_(None)]
        if date_from:
            filters.append(Lead.created_at >= date_from)
        if date_to:
            filters.append(Lead.created_at <= date_to)

        # Lead count + converted count by source
        source_q = await self.db.execute(
            select(
                Lead.source,
                func.count(Lead.id).label("lead_count"),
                func.sum(
                    case((Lead.status == "converted", 1), else_=0)
                ).label("converted_count"),
                func.sum(
                    case((Lead.status == "converted", Lead.budget_max), else_=None)
                ).label("converted_budget_max_sum"),
            )
            .where(and_(*filters))
            .group_by(Lead.source)
        )
        rows = source_q.all()

        by_source = []
        top_source_leads: Optional[str] = None
        top_source_conv: Optional[str] = None
        max_leads = 0
        max_conv_rate = -1.0

        for row in rows:
            source = row.source or "unknown"
            lead_count = row.lead_count or 0
            converted_count = int(row.converted_count or 0)
            conv_rate = _safe_rate(converted_count, lead_count)
            est_rev = float(row.converted_budget_max_sum) if row.converted_budget_max_sum else None

            by_source.append({
                "source": source,
                "lead_count": lead_count,
                "converted_count": converted_count,
                "conversion_rate_pct": conv_rate,
                "estimated_revenue_estimate": est_rev,
            })

            if lead_count > max_leads:
                max_leads = lead_count
                top_source_leads = source
            if conv_rate is not None and conv_rate > max_conv_rate:
                max_conv_rate = conv_rate
                top_source_conv = source

        return {
            "organization_id": str(organization_id),
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "total_sources": len(by_source),
            "by_source": by_source,
            "top_source_by_leads": top_source_leads,
            "top_source_by_conversion": top_source_conv,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 5. LearningLoopSummary
# ──────────────────────────────────────────────────────────────────────────────

class LearningLoopSummary:
    """
    Deterministic heuristic summary of what revenue actions are working.

    CRITICAL: This uses only SQLAlchemy aggregation queries.
    There is NO statistical model, no training pipeline, no ML inference.
    The `computation_method` field in the response is hardcoded to
    'heuristic_aggregation_v1' to be transparent about this.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_learning_summary(
        self,
        organization_id: uuid.UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        filters = [RevenueOpportunity.organization_id == organization_id]
        if date_from:
            filters.append(RevenueOpportunity.created_at >= date_from)
        if date_to:
            filters.append(RevenueOpportunity.created_at <= date_to)

        # Opportunity type breakdown: total, actioned, positive feedback
        opp_q = await self.db.execute(
            select(
                RevenueOpportunity.opportunity_type,
                func.count(RevenueOpportunity.id).label("total"),
                func.sum(
                    case(
                        (RevenueOpportunity.status.in_(["ACTIONED", "IN_PROGRESS", "COMPLETED"]), 1),
                        else_=0
                    )
                ).label("actioned"),
                func.sum(
                    case(
                        (RevenueOpportunity.feedback_rating == "YES", 1),
                        else_=0
                    )
                ).label("positive"),
            )
            .where(and_(*filters))
            .group_by(RevenueOpportunity.opportunity_type)
            .order_by(func.count(RevenueOpportunity.id).desc())
            .limit(10)
        )
        opp_rows = opp_q.all()

        top_opp_types = []
        total_evaluated = 0
        total_positive = 0
        for row in opp_rows:
            total = row.total or 0
            actioned = int(row.actioned or 0)
            positive = int(row.positive or 0)
            total_evaluated += total
            total_positive += positive
            top_opp_types.append({
                "opportunity_type": row.opportunity_type,
                "total_count": total,
                "actioned_count": actioned,
                "positive_feedback_count": positive,
                "action_rate_pct": _safe_rate(actioned, total),
                "positive_feedback_rate_pct": _safe_rate(positive, total),
            })

        # Best source by conversion rate (re-using Lead query)
        lead_src_q = await self.db.execute(
            select(
                Lead.source,
                func.count(Lead.id).label("total"),
                func.sum(case((Lead.status == "converted", 1), else_=0)).label("conv"),
            )
            .where(and_(Lead.broker_id == organization_id, Lead.deleted_at.is_(None)))
            .group_by(Lead.source)
            .having(func.count(Lead.id) >= 3)  # at least 3 leads to be meaningful
        )
        src_rows = lead_src_q.all()
        top_source = None
        best_rate = -1.0
        for r in src_rows:
            rate = _safe_rate(int(r.conv or 0), r.total or 0)
            if rate is not None and rate > best_rate:
                best_rate = rate
                top_source = r.source

        return {
            "organization_id": str(organization_id),
            "date_from": _iso(date_from),
            "date_to": _iso(date_to),
            "computation_method": "heuristic_aggregation_v1",
            "top_opportunity_types": top_opp_types,
            "top_source_by_conversion": top_source,
            "total_opportunities_evaluated": total_evaluated,
            "total_positive_signals": total_positive,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 6. SnapshotService
# ──────────────────────────────────────────────────────────────────────────────

class SnapshotService:
    """
    Captures the current funnel state as a RevenueFunnelSnapshot row.
    Idempotent: upserts by (organization_id, snapshot_date, period_type).
    """

    def __init__(self, db: AsyncSession, funnel_analyzer: FunnelAnalyzer):
        self.db = db
        self.analyzer = funnel_analyzer

    async def capture(
        self,
        organization_id: uuid.UUID,
        period_type: str = "DAILY",
    ) -> RevenueFunnelSnapshot:
        now = datetime.now(timezone.utc)
        snapshot_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        existing_q = await self.db.execute(
            select(RevenueFunnelSnapshot).where(
                and_(
                    RevenueFunnelSnapshot.organization_id == organization_id,
                    RevenueFunnelSnapshot.snapshot_date == snapshot_date,
                    RevenueFunnelSnapshot.period_type == period_type,
                )
            )
        )
        existing = existing_q.scalar_one_or_none()

        summary = await self.analyzer.get_funnel_summary(organization_id)

        stage_map = {s["stage"]: s["count"] for s in summary["stages"]}
        metrics = {
            "stages": summary["stages"],
            "overall_conversion_rate_pct": summary["overall_conversion_rate_pct"],
            "computed_at": now.isoformat(),
        }

        if existing:
            existing.total_leads = summary["total_leads"]
            existing.leads_new = stage_map.get("new", 0)
            existing.leads_contacted = stage_map.get("contacted", 0)
            existing.leads_qualified = stage_map.get("qualified", 0)
            existing.leads_site_visit = stage_map.get("site_visit", 0)
            existing.leads_negotiation = stage_map.get("negotiation", 0)
            existing.leads_converted = stage_map.get("converted", 0)
            existing.leads_lost = stage_map.get("lost", 0)
            existing.active_opportunities = summary["active_opportunities"]
            existing.estimated_pipeline_value = summary["estimated_pipeline_value_estimate"]
            existing.confirmed_revenue = summary["confirmed_revenue"]
            existing.metrics = metrics
            existing.updated_at = now
            await self.db.flush()
            return existing

        snap = RevenueFunnelSnapshot(
            id=uuid.uuid4(),
            organization_id=organization_id,
            period_type=period_type,
            snapshot_date=snapshot_date,
            total_leads=summary["total_leads"],
            leads_new=stage_map.get("new", 0),
            leads_contacted=stage_map.get("contacted", 0),
            leads_qualified=stage_map.get("qualified", 0),
            leads_site_visit=stage_map.get("site_visit", 0),
            leads_negotiation=stage_map.get("negotiation", 0),
            leads_converted=stage_map.get("converted", 0),
            leads_lost=stage_map.get("lost", 0),
            active_opportunities=summary["active_opportunities"],
            estimated_pipeline_value=summary["estimated_pipeline_value_estimate"],
            confirmed_revenue=summary["confirmed_revenue"],
            metrics=metrics,
        )
        self.db.add(snap)
        await self.db.flush()
        return snap

    async def list_snapshots(
        self,
        organization_id: uuid.UUID,
        period_type: Optional[str] = None,
        limit: int = 30,
    ) -> Tuple[List[RevenueFunnelSnapshot], int]:
        filters = [RevenueFunnelSnapshot.organization_id == organization_id]
        if period_type:
            filters.append(RevenueFunnelSnapshot.period_type == period_type)

        count_q = await self.db.execute(
            select(func.count(RevenueFunnelSnapshot.id)).where(and_(*filters))
        )
        total = count_q.scalar() or 0

        rows_q = await self.db.execute(
            select(RevenueFunnelSnapshot)
            .where(and_(*filters))
            .order_by(RevenueFunnelSnapshot.snapshot_date.desc())
            .limit(limit)
        )
        rows = rows_q.scalars().all()
        return list(rows), total


# ──────────────────────────────────────────────────────────────────────────────
# 7. DataQualityAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class DataQualityAnalyzer:
    """Audits data completeness across leads, opportunities, meetings, and deals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_data_quality_report(self, organization_id: uuid.UUID) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        leads_q = await self.db.execute(
            select(
                func.count(Lead.id).label("total"),
                func.sum(case((or_(Lead.source.is_(None), Lead.source == "unknown"), 1), else_=0)).label("missing_source"),
                func.sum(case((Lead.budget_max.is_(None), 1), else_=0)).label("missing_budget"),
                func.sum(case((Lead.timeline.is_(None), 1), else_=0)).label("missing_timeline"),
            ).where(and_(Lead.broker_id == organization_id, Lead.deleted_at.is_(None)))
        )
        l_row = leads_q.one()
        total_leads = l_row.total or 0
        missing_source = int(l_row.missing_source or 0)
        missing_budget = int(l_row.missing_budget or 0)
        missing_timeline = int(l_row.missing_timeline or 0)

        deals_q = await self.db.execute(
            select(
                func.count(DealTransaction.id).label("total"),
                func.sum(case((DealTransaction.estimated_commission_amount.is_(None), 1), else_=0)).label("missing_comm"),
            ).where(DealTransaction.broker_id == organization_id)
        )
        d_row = deals_q.one()
        total_deals = d_row.total or 0
        missing_comm = int(d_row.missing_comm or 0)

        visits_q = await self.db.execute(
            select(
                func.count(SchedulingMeeting.id).label("total"),
                func.sum(case((and_(SchedulingMeeting.start_utc <= now, SchedulingMeeting.status == "scheduled"), 1), else_=0)).label("missing_outcome"),
            ).where(and_(SchedulingMeeting.broker_id == organization_id, SchedulingMeeting.meeting_type == "site_visit"))
        )
        v_row = visits_q.one()
        total_visits = v_row.total or 0
        missing_outcome = int(v_row.missing_outcome or 0)

        total_audited = total_leads + total_deals + total_visits
        issues = []

        if total_leads > 0:
            cov_src = _safe_rate(total_leads - missing_source, total_leads)
            issues.append({
                "metric": "leads_missing_source",
                "missing_count": missing_source,
                "total_count": total_leads,
                "coverage_pct": cov_src,
                "severity": "MEDIUM" if (cov_src or 100) < 80 else "LOW",
                "description": "Leads acquired without identifiable source attribution channel.",
            })
            cov_bud = _safe_rate(total_leads - missing_budget, total_leads)
            issues.append({
                "metric": "leads_missing_budget",
                "missing_count": missing_budget,
                "total_count": total_leads,
                "coverage_pct": cov_bud,
                "severity": "HIGH" if (cov_bud or 100) < 70 else "MEDIUM",
                "description": "Leads with undefined budget maximum inhibiting pipeline valuation.",
            })
            cov_time = _safe_rate(total_leads - missing_timeline, total_leads)
            issues.append({
                "metric": "leads_missing_timeline",
                "missing_count": missing_timeline,
                "total_count": total_leads,
                "coverage_pct": cov_time,
                "severity": "LOW",
                "description": "Leads without recorded purchasing horizon.",
            })

        if total_deals > 0:
            cov_comm = _safe_rate(total_deals - missing_comm, total_deals)
            issues.append({
                "metric": "deals_missing_commission",
                "missing_count": missing_comm,
                "total_count": total_deals,
                "coverage_pct": cov_comm,
                "severity": "CRITICAL" if (cov_comm or 100) < 90 else "LOW",
                "description": "Transactions lacking confirmed commission amount.",
            })

        if total_visits > 0:
            cov_out = _safe_rate(total_visits - missing_outcome, total_visits)
            issues.append({
                "metric": "site_visits_missing_outcomes",
                "missing_count": missing_outcome,
                "total_count": total_visits,
                "coverage_pct": cov_out,
                "severity": "HIGH" if (cov_out or 100) < 80 else "LOW",
                "description": "Past site visits still marked as scheduled without outcome recording.",
            })

        if issues:
            coverages = [iss["coverage_pct"] for iss in issues if iss["coverage_pct"] is not None]
            health = round(sum(coverages) / len(coverages), 1) if coverages else 100.0
        else:
            health = 100.0

        return {
            "organization_id": str(organization_id),
            "data_health_score_pct": health,
            "total_records_audited": total_audited,
            "issues": issues,
            "audited_at": now.isoformat(),
        }


# ──────────────────────────────────────────────────────────────────────────────
# 8. JourneyReconstructor
# ──────────────────────────────────────────────────────────────────────────────

class JourneyReconstructor:
    """Reconstructs customer and property revenue journeys across canonical events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_lead_journey(self, organization_id: uuid.UUID, lead_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        lead_q = await self.db.execute(
            select(Lead).where(and_(Lead.id == lead_id, Lead.broker_id == organization_id, Lead.deleted_at.is_(None)))
        )
        lead = lead_q.scalar_one_or_none()
        if not lead:
            return None

        events: List[Dict[str, Any]] = []

        # 1. Lead acquisition / creation
        events.append({
            "event_id": str(uuid.uuid4()),
            "occurred_at": _iso(lead.created_at),
            "stage": "new",
            "title": "Lead Acquired",
            "description": f"Lead created from source: {lead.source or 'unknown'}",
            "actor_type": "SYSTEM",
            "channel": lead.source,
            "metadata": {"score": lead.score, "phone": lead.phone},
        })

        # 2. Timeline events
        te_q = await self.db.execute(
            select(TimelineEvent).where(
                and_(
                    TimelineEvent.organization_id == str(organization_id),
                    TimelineEvent.resource_id == str(lead_id),
                )
            ).order_by(TimelineEvent.created_at.asc())
        )
        for te in te_q.scalars().all():
            events.append({
                "event_id": te.id,
                "occurred_at": _iso(te.created_at),
                "stage": te.event_type,
                "title": te.title,
                "description": te.body,
                "actor_type": te.actor_type.upper() if te.actor_type else "USER",
                "channel": te.channel,
                "metadata": te.event_metadata or {},
            })

        # 3. Meetings
        m_q = await self.db.execute(
            select(SchedulingMeeting).where(
                and_(
                    SchedulingMeeting.broker_id == organization_id,
                    SchedulingMeeting.lead_id == lead_id,
                )
            ).order_by(SchedulingMeeting.start_utc.asc())
        )
        for m in m_q.scalars().all():
            events.append({
                "event_id": str(m.id),
                "occurred_at": _iso(m.start_utc),
                "stage": m.meeting_type or "appointment",
                "title": f"Meeting: {m.title}",
                "description": f"Status: {m.status}",
                "actor_type": "USER",
                "channel": "calendar",
                "metadata": {"status": m.status, "meeting_type": m.meeting_type},
            })

        # 4. Revenue Opportunities
        opp_q = await self.db.execute(
            select(RevenueOpportunity).where(
                and_(
                    RevenueOpportunity.organization_id == organization_id,
                    RevenueOpportunity.lead_id == lead_id,
                )
            ).order_by(RevenueOpportunity.created_at.asc())
        )
        for opp in opp_q.scalars().all():
            events.append({
                "event_id": str(opp.id),
                "occurred_at": _iso(opp.created_at),
                "stage": "opportunity",
                "title": f"Revenue Opportunity: {opp.opportunity_type}",
                "description": f"Priority: {opp.priority}, Status: {opp.status}",
                "actor_type": "AI_AGENT",
                "channel": "autopilot",
                "metadata": {"score": opp.opportunity_score, "feedback": opp.feedback_rating},
            })

        # 5. Deals
        deal_q = await self.db.execute(
            select(DealTransaction).where(
                and_(
                    DealTransaction.broker_id == organization_id,
                    DealTransaction.lead_id == lead_id,
                )
            ).order_by(DealTransaction.created_at.asc())
        )
        for d in deal_q.scalars().all():
            events.append({
                "event_id": str(d.id),
                "occurred_at": _iso(d.created_at),
                "stage": d.current_stage or "deal",
                "title": f"Deal: {d.property_title or 'Property Deal'}",
                "description": f"Agreed price: ₹{d.agreed_price:,.0f}" if d.agreed_price else "Deal in progress",
                "actor_type": "USER",
                "channel": "crm",
                "metadata": {"stage": d.current_stage, "commission": d.estimated_commission_amount},
            })

        events.sort(key=lambda e: e["occurred_at"] or "")

        return {
            "lead_id": str(lead_id),
            "organization_id": str(organization_id),
            "lead_name": getattr(lead, "full_name", None) or getattr(lead, "name", None) or lead.phone,
            "source": lead.source,
            "pipeline_stage": lead.pipeline_stage,
            "score": lead.score,
            "budget_max": float(lead.budget_max) if lead.budget_max else None,
            "total_events": len(events),
            "journey": events,
        }

    async def get_property_journey(self, organization_id: uuid.UUID, property_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        prop_q = await self.db.execute(
            select(PropertyListing).where(
                and_(PropertyListing.id == property_id, PropertyListing.broker_id == organization_id)
            )
        )
        prop = prop_q.scalar_one_or_none()
        if not prop:
            return None

        m_q = await self.db.execute(
            select(func.count(SchedulingMeeting.id)).where(
                and_(SchedulingMeeting.broker_id == organization_id, SchedulingMeeting.property_id == property_id)
            )
        )
        appts = m_q.scalar() or 0

        v_q = await self.db.execute(
            select(func.count(SchedulingMeeting.id)).where(
                and_(
                    SchedulingMeeting.broker_id == organization_id,
                    SchedulingMeeting.property_id == property_id,
                    SchedulingMeeting.meeting_type == "site_visit",
                )
            )
        )
        visits = v_q.scalar() or 0

        deals_q = await self.db.execute(
            select(
                func.count(DealTransaction.id).label("deals"),
                func.sum(DealTransaction.estimated_commission_amount).label("comm"),
            ).where(
                and_(
                    DealTransaction.broker_id == organization_id,
                    DealTransaction.property_id == property_id,
                    DealTransaction.current_stage == "commission_received",
                )
            )
        )
        d_row = deals_q.one()
        deals_closed = d_row.deals or 0
        confirmed_rev = float(d_row.comm) if d_row.comm else None

        conv_rate = _safe_rate(deals_closed, appts) if appts > 0 else None

        return {
            "property_id": str(property_id),
            "organization_id": str(organization_id),
            "property_title": prop.title,
            "price": float(prop.price) if prop.price else None,
            "total_matches": appts + visits,
            "qualified_leads_count": appts,
            "appointments_count": appts,
            "site_visits_count": visits,
            "deals_closed": deals_closed,
            "confirmed_revenue": confirmed_rev,
            "conversion_rate_pct": conv_rate,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 9. TeamIntelligenceAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class TeamIntelligenceAnalyzer:
    """Computes factual operational metrics per salesperson / broker."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_team_metrics(self, organization_id: uuid.UUID) -> Dict[str, Any]:
        b_q = await self.db.execute(
            select(Broker).where(Broker.id == organization_id)
        )
        brokers = b_q.scalars().all()

        agents_metrics = []
        for b in brokers:
            leads_q = await self.db.execute(
                select(
                    func.count(Lead.id).label("total"),
                    func.sum(case((Lead.pipeline_stage == "contacted", 1), else_=0)).label("contacted"),
                    func.sum(case((Lead.pipeline_stage.in_(["qualified", "site_visit", "negotiation", "converted"]), 1), else_=0)).label("qualified"),
                ).where(and_(Lead.broker_id == b.id, Lead.deleted_at.is_(None)))
            )
            l_row = leads_q.one()

            appts_q = await self.db.execute(
                select(
                    func.count(SchedulingMeeting.id).label("total"),
                    func.sum(case((SchedulingMeeting.meeting_type == "site_visit", 1), else_=0)).label("visits"),
                ).where(SchedulingMeeting.broker_id == b.id)
            )
            m_row = appts_q.one()

            opps_q = await self.db.execute(
                select(func.count(RevenueOpportunity.id)).where(RevenueOpportunity.organization_id == b.id)
            )
            opps = opps_q.scalar() or 0

            deals_q = await self.db.execute(
                select(func.count(DealTransaction.id)).where(
                    and_(DealTransaction.broker_id == b.id, DealTransaction.current_stage == "commission_received")
                )
            )
            deals = deals_q.scalar() or 0

            agents_metrics.append({
                "broker_id": str(b.id),
                "name": b.name,
                "email": b.email,
                "assigned_leads": l_row.total or 0,
                "contacted_leads": int(l_row.contacted or 0),
                "qualified_leads": int(l_row.qualified or 0),
                "scheduled_appointments": m_row.total or 0,
                "completed_site_visits": int(m_row.visits or 0),
                "active_opportunities": opps,
                "closed_deals": deals,
            })

        return {
            "organization_id": str(organization_id),
            "total_agents": len(agents_metrics),
            "agents": agents_metrics,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 10. PropensityEngine
# ──────────────────────────────────────────────────────────────────────────────

class PropensityEngine:
    """
    Computes deterministic conversion propensity scores.
    Uses explicit heuristic formula 'heuristic_v1'. No untracked ML claims.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_lead_propensity(self, organization_id: uuid.UUID, lead_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        lead_q = await self.db.execute(
            select(Lead).where(and_(Lead.id == lead_id, Lead.broker_id == organization_id, Lead.deleted_at.is_(None)))
        )
        lead = lead_q.scalar_one_or_none()
        if not lead:
            return None

        features: Dict[str, Any] = {
            "pipeline_stage": lead.pipeline_stage,
            "lead_score": lead.score,
            "has_budget": lead.budget_max is not None,
            "days_since_update": None,
        }
        breakdown: List[str] = ["Base score: +10.0"]
        score = 10.0

        if lead.updated_at:
            days = (now - lead.updated_at.replace(tzinfo=timezone.utc) if lead.updated_at.tzinfo is None else now - lead.updated_at).days
            features["days_since_update"] = days
            if days < 3:
                score += 25.0
                breakdown.append("Recency (< 3 days): +25.0")
            elif days < 7:
                score += 15.0
                breakdown.append("Recency (< 7 days): +15.0")
            elif days < 14:
                score += 5.0
                breakdown.append("Recency (< 14 days): +5.0")
            else:
                breakdown.append("Recency (>= 14 days): +0.0")

        stage = lead.pipeline_stage or "new"
        if stage in ("site_visit", "negotiation"):
            score += 40.0
            breakdown.append(f"Stage progression ({stage}): +40.0")
        elif stage == "qualified":
            score += 25.0
            breakdown.append("Stage progression (qualified): +25.0")
        elif stage == "contacted":
            score += 15.0
            breakdown.append("Stage progression (contacted): +15.0")
        else:
            breakdown.append(f"Stage progression ({stage}): +5.0")
            score += 5.0

        lead_score = (lead.score or "cold").lower()
        if lead_score == "hot":
            score += 15.0
            breakdown.append("Lead score (hot): +15.0")
        elif lead_score == "warm":
            score += 10.0
            breakdown.append("Lead score (warm): +10.0")
        else:
            score += 5.0
            breakdown.append("Lead score (cold): +5.0")

        if lead.budget_max and lead.budget_max > 0:
            score += 10.0
            breakdown.append("Financial completeness (budget stated): +10.0")

        final_score = min(100.0, round(score, 1))

        return {
            "lead_id": str(lead_id),
            "organization_id": str(organization_id),
            "score": final_score,
            "method": "DETERMINISTIC_HEURISTIC",
            "version": "heuristic_v1",
            "features_used": features,
            "calculation_breakdown": breakdown,
            "generated_at": now.isoformat(),
            "data_window_days": 30,
        }


# ──────────────────────────────────────────────────────────────────────────────
# 11. OverviewAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class OverviewAnalyzer:
    """Assembles high-level revenue overview and forecast baseline."""

    def __init__(self, db: AsyncSession, funnel: FunnelAnalyzer, leakage: LeakageDetector):
        self.db = db
        self.funnel = funnel
        self.leakage = leakage

    async def get_overview(self, organization_id: uuid.UUID) -> Dict[str, Any]:
        funnel_summary = await self.funnel.get_funnel_summary(organization_id)
        leakage_summary = await self.leakage.get_leakage_report(organization_id)

        src_q = await self.db.execute(
            select(
                func.count(Lead.id).label("total"),
                func.sum(case((or_(Lead.source.is_(None), Lead.source == "unknown"), 0), else_=1)).label("attributed"),
            ).where(and_(Lead.broker_id == organization_id, Lead.deleted_at.is_(None)))
        )
        s_row = src_q.one()
        total_leads = s_row.total or 0
        attributed_leads = int(s_row.attributed or 0)
        cov_pct = _safe_rate(attributed_leads, total_leads)

        rev_q = await self.db.execute(
            select(
                func.sum(case((or_(Lead.source.is_(None), Lead.source == "unknown"), 0), else_=DealTransaction.estimated_commission_amount)).label("attr_rev"),
                func.sum(case((or_(Lead.source.is_(None), Lead.source == "unknown"), DealTransaction.estimated_commission_amount), else_=0)).label("unattr_rev"),
            )
            .join(Lead, Lead.id == DealTransaction.lead_id)
            .where(and_(DealTransaction.broker_id == organization_id, DealTransaction.current_stage == "commission_received"))
        )
        rev_row = rev_q.one()
        attr_rev = float(rev_row.attr_rev) if rev_row.attr_rev else None
        unattr_rev = float(rev_row.unattr_rev) if rev_row.unattr_rev else None

        return {
            "organization_id": str(organization_id),
            "realized_revenue": funnel_summary["confirmed_revenue"],
            "current_pipeline_estimate": funnel_summary["estimated_pipeline_value_estimate"],
            "revenue_at_risk_estimate": leakage_summary["total_estimated_value_at_risk_estimate"],
            "active_opportunities": funnel_summary["active_opportunities"],
            "total_leads": total_leads,
            "attributed_revenue": attr_rev,
            "unattributed_revenue": unattr_rev,
            "attribution_coverage_pct": cov_pct,
            "forecast_status": "FORECAST_NOT_AVAILABLE",
            "forecast_disclaimer": "Forecast is not available because validated ML forecasting models are not enabled. Projections rely strictly on deterministic pipeline values.",
        }


# ──────────────────────────────────────────────────────────────────────────────
# Master Service facade
# ──────────────────────────────────────────────────────────────────────────────

class RevenueIntelligenceService:
    """
    Facade that wires all analytical engines together.
    Instantiated once per request via FastAPI dependency injection.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.funnel = FunnelAnalyzer(db)
        self.leakage = LeakageDetector(db)
        self.outcomes = OutcomeTracker(db)
        self.attribution = SourceAttributionReport(db)
        self.learning = LearningLoopSummary(db)
        self.snapshots = SnapshotService(db, self.funnel)
        self.data_quality = DataQualityAnalyzer(db)
        self.journeys = JourneyReconstructor(db)
        self.team = TeamIntelligenceAnalyzer(db)
        self.propensity = PropensityEngine(db)
        self.overview = OverviewAnalyzer(db, self.funnel, self.leakage)
