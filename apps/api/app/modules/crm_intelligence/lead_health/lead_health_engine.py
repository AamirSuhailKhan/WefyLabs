"""
Lead Health & Decay Evaluation Engine
=====================================
Calculates dynamic 9-dimensional lead health, detects decay/cooling velocity,
flags neglected high-value buyers, and creates explainable health snapshots.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.crm_intelligence_models import LeadHealthSnapshot, LeadRisk
from app.modules.crm_intelligence.feature_store.feature_aggregator import FeatureAggregator

logger = logging.getLogger(__name__)

class LeadHealthEngine:
    """
    Evaluates multi-dimensional health and decay for leads.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.aggregator = FeatureAggregator(db)

    async def evaluate_lead_health(self, lead_id: str, organization_id: str) -> LeadHealthSnapshot:
        """
        Evaluates 9 health dimensions, detects decay/neglect, and persists a LeadHealthSnapshot.
        """
        feats = await self.aggregator.extract_lead_features(lead_id, organization_id)

        # 1. Dimension Calculations (0.0 to 100.0)
        # Engagement Health
        act_score = min(100.0, feats["activity_count"] * 15.0 + feats["message_count"] * 5.0)
        engagement_health = max(10.0, min(100.0, act_score - (feats["hours_since_last_activity"] * 0.5)))

        # Intent Health
        intent_health = feats["lead_score"]

        # Response Health
        resp_pen = (feats["first_response_time_seconds"] / 60.0) * 2.0  # -2 pts per min delay
        response_health = max(10.0, min(100.0, 95.0 - resp_pen))

        # Follow-Up Health
        fu_pen = feats["overdue_tasks_count"] * 25.0
        follow_up_health = max(10.0, min(100.0, 90.0 - fu_pen))

        # Meeting Health
        mtg_score = 70.0
        if feats["cancelled_meetings_count"] > 0 or feats["no_show_meetings_count"] > 0:
            mtg_score -= (feats["cancelled_meetings_count"] * 30.0 + feats["no_show_meetings_count"] * 40.0)
        elif feats["meeting_count"] > 0:
            mtg_score += 25.0
        meeting_health = max(10.0, min(100.0, mtg_score))

        # Qualification Health
        qualification_health = 85.0 if feats["has_preferred_locations"] and feats["budget_max"] > 0 else 45.0

        # Property Match Health
        property_match_health = 80.0 if feats["budget_max"] > 0 else 50.0

        # Agent Attention Health
        agent_attention_health = max(10.0, min(100.0, 100.0 - (feats["hours_since_last_activity"] * 1.2)))

        # Conversion Health
        conversion_health = (intent_health * 0.4 + engagement_health * 0.3 + follow_up_health * 0.3)

        # Overall Composite Health Score
        overall_health = (
            engagement_health * 0.15 +
            intent_health * 0.15 +
            response_health * 0.10 +
            follow_up_health * 0.15 +
            meeting_health * 0.15 +
            qualification_health * 0.10 +
            agent_attention_health * 0.10 +
            conversion_health * 0.10
        )

        # 2. State & Decay Detection
        decay_detected = False
        neglect_detected = False
        risks_to_create: List[Dict[str, Any]] = []

        # Neglect detection: High intent / budget but no broker action for > 24 hours
        if feats["lead_score"] >= 70.0 and feats["hours_since_last_activity"] >= 24.0:
            neglect_detected = True
            health_state = "NEGLECTED"
            explanation = f"Lead has high intent ({feats['lead_score']:.0f}/100) but has received no broker activity for {feats['hours_since_last_activity']:.0f} hours."
            risks_to_create.append({
                "risk_type": "NEGLECT",
                "severity": "HIGH",
                "evidence": f"No broker contact in {feats['hours_since_last_activity']:.0f}h for high-scoring lead.",
                "action": "Assign immediate follow-up task or dispatch re-engagement WhatsApp."
            })
        elif feats["cancelled_meetings_count"] > 0 and feats["hours_since_last_activity"] >= 48.0:
            decay_detected = True
            health_state = "AT_RISK"
            explanation = "Lead health declined because a scheduled viewing was cancelled and no recovery follow-up occurred in 48 hours."
            risks_to_create.append({
                "risk_type": "VIEWING_CANCELLED",
                "severity": "HIGH",
                "evidence": "Viewing cancelled without rescheduled slot in 48h.",
                "action": "Offer alternative viewing itinerary with 3 candidate slots."
            })
        elif feats["hours_since_customer_message"] > 120.0 and feats["message_count"] > 0:
            decay_detected = True
            health_state = "COOLING"
            explanation = f"Lead intent is cooling down. No customer response for {feats['hours_since_customer_message'] / 24.0:.1f} days."
            risks_to_create.append({
                "risk_type": "COOLING_INTENT",
                "severity": "MEDIUM",
                "evidence": f"Customer inactive for {feats['hours_since_customer_message']:.0f} hours.",
                "action": "Trigger automated value-add property drop to rekindle interest."
            })
        elif feats["stage_name"] in ("converted", "closed_won"):
            health_state = "CONVERTED"
            explanation = "Lead successfully converted / closed won."
        elif feats["stage_name"] in ("lost", "closed_lost"):
            health_state = "LOST"
            explanation = "Lead marked closed lost."
        elif overall_health >= 80.0:
            health_state = "HOT"
            explanation = "Lead exhibits strong engagement, verified budget, and rapid response velocity."
        elif overall_health >= 60.0:
            health_state = "HEALTHY"
            explanation = "Lead is progressing normally through the pipeline with active engagement."
        else:
            health_state = "STALE"
            explanation = "Lead is stagnant with low engagement momentum."

        # 3. Persist Snapshot
        snapshot = LeadHealthSnapshot(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=str(feats["lead_id"]),
            broker_id=feats["broker_id"],
            health_state=health_state,
            health_score=round(overall_health, 1),
            engagement_health=round(engagement_health, 1),
            intent_health=round(intent_health, 1),
            response_health=round(response_health, 1),
            follow_up_health=round(follow_up_health, 1),
            meeting_health=round(meeting_health, 1),
            qualification_health=round(qualification_health, 1),
            property_match_health=round(property_match_health, 1),
            agent_attention_health=round(agent_attention_health, 1),
            conversion_health=round(conversion_health, 1),
            explanation=explanation,
            decay_detected=decay_detected,
            neglect_detected=neglect_detected,
            evaluated_at=datetime.now(timezone.utc)
        )
        self.db.add(snapshot)

        # 4. Persist Lead Risks
        for r in risks_to_create:
            risk = LeadRisk(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                lead_id=str(feats["lead_id"]),
                snapshot_id=snapshot.id,
                risk_type=r["risk_type"],
                severity=r["severity"],
                confidence=0.92,
                evidence=r["evidence"],
                recommended_recovery_action=r["action"],
                status="ACTIVE"
            )
            self.db.add(risk)

        await self.db.commit()
        await self.db.refresh(snapshot)
        logger.info(f"[LEAD_HEALTH] Evaluated Lead {lead_id}: State '{health_state}' ({overall_health:.1f}/100).")
        return snapshot
