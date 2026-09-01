"""
Lead Intelligence Service — Main Pipeline Orchestrator
======================================================
Pipeline:
    lead_dto → Feature Extractor → Rules Engine → ML Model → Intent Engine →
    Urgency Engine → Priority Engine → Conversion Predictor → Confidence Engine →
    Recommendation Engine → Revenue Engine → DB Persistence → Event Publishing
"""
import time
import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.lead import Lead
from app.models.lead_intelligence_models import (
    LeadIntelligenceProfile, LeadPrediction, LeadRecommendation,
    PredictionHistory, ScoringRule, FeatureVector, PredictionExplanation
)
from app.modules.lead_intelligence.feature_engine.feature_extractor import FeatureExtractor
from app.modules.lead_intelligence.intent_engine.intent_calculator import IntentCalculator
from app.modules.lead_intelligence.urgency_engine.urgency_calculator import UrgencyCalculator
from app.modules.lead_intelligence.priority_engine.priority_calculator import PriorityCalculator
from app.modules.lead_intelligence.conversion_engine.conversion_predictor import ConversionPredictor
from app.modules.lead_intelligence.rules_engine.rule_evaluator import RuleEvaluator
from app.modules.lead_intelligence.ml_engine.model_registry import MLModelRegistry
from app.modules.lead_intelligence.confidence_engine.confidence_calculator import ConfidenceCalculator
from app.modules.lead_intelligence.recommendation_engine.action_recommender import ActionRecommender
from app.modules.lead_intelligence.revenue_engine.revenue_calculator import RevenueCalculator
from app.modules.lead_intelligence.monitoring.intelligence_metrics import IntelligenceMetricsCollector
from app.modules.lead_intelligence.events.event_publisher import IntelligenceEventPublisher
from app.modules.lead_intelligence.events.intelligence_events import (
    LeadScored, LeadPriorityChanged, IntentUpdated, PredictionUpdated, RecommendationGenerated
)

logger = logging.getLogger(__name__)


class LeadIntelligenceService:
    """
    Enterprise AI Lead Intelligence & Revenue Engine Pipeline Orchestrator.
    """

    def __init__(self, db: AsyncSession, redis_client: Optional[Any] = None):
        self.db = db
        self.feature_extractor = FeatureExtractor()
        self.intent_calculator = IntentCalculator()
        self.urgency_calculator = UrgencyCalculator()
        self.priority_calculator = PriorityCalculator()
        self.conversion_predictor = ConversionPredictor()
        self.rule_evaluator = RuleEvaluator()
        self.ml_registry = MLModelRegistry()
        self.confidence_calculator = ConfidenceCalculator()
        self.action_recommender = ActionRecommender()
        self.revenue_calculator = RevenueCalculator()
        self.metrics_collector = IntelligenceMetricsCollector()
        self.event_publisher = IntelligenceEventPublisher(redis_client)

    async def score_lead(
        self,
        lead_dto: Dict[str, Any],
        organization_id: str,
        trigger_event: str = "LeadCreated",
        enrichment_profile: Optional[Dict[str, Any]] = None,
        identity_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main pipeline entry point. Performs 12-step end-to-end lead intelligence & revenue calculation.
        """
        start_time = time.time()
        lead_id = str(lead_dto.get("id") or "")
        logger.info(f"[LEAD_INTELLIGENCE] Starting pipeline for Lead ID: {lead_id} (Trigger: {trigger_event})")

        # ── Step 1: Feature Extraction ────────────────────────────────────────
        features = self.feature_extractor.extract_features(
            lead_dto, enrichment_profile, identity_profile
        )

        # ── Step 2: Load DB rules & evaluate ──────────────────────────────────
        db_rules = await self._load_active_rules(organization_id)
        rule_adjustment, rules_fired = self.rule_evaluator.evaluate_rules(features, db_rules)

        # ── Step 3: ML Model Inference ────────────────────────────────────────
        ml_model = self.ml_registry.get_active_model()
        ml_result = ml_model.predict(features, rule_adjustment)
        lead_score = ml_result["raw_score"]

        # ── Step 4: Intent & Urgency Engines ──────────────────────────────────
        intent_score, intent_phase = self.intent_calculator.calculate(features)
        urgency_score = self.urgency_calculator.calculate(features)

        # ── Step 5: Score Yesterday & Momentum ────────────────────────────────
        existing_profile = await self._get_existing_profile(lead_id)
        score_yesterday = existing_profile.lead_score if existing_profile else lead_score

        # ── Step 6: Priority & Temperature Engine ─────────────────────────────
        temperature, momentum, follow_up_priority, agent_priority = self.priority_calculator.calculate(
            lead_score, score_yesterday, intent_phase, features
        )

        # ── Step 7: Conversion Probabilities & Risk ───────────────────────────
        predictions = self.conversion_predictor.predict(lead_score, features)
        conversion_prob = predictions["conversion_probability"]

        # ── Step 8: Confidence & Explainable AI ──────────────────────────────
        confidence, pos_drivers, neg_drivers, rationale = self.confidence_calculator.compute_explanation(
            features, lead_score, rules_fired, ml_result.get("feature_contributions", {})
        )

        # ── Step 9: Next Best Action Recommendations ──────────────────────────
        recommendations = self.action_recommender.generate_recommendations(
            features, lead_score, temperature
        )

        # ── Step 10: Revenue Intelligence ─────────────────────────────────────
        rev_metrics = self.revenue_calculator.calculate_revenue(features, conversion_prob)

        # ── Step 11: DB Persistence ───────────────────────────────────────────
        await self._persist_intelligence(
            lead_id=lead_id,
            organization_id=organization_id,
            lead_score=lead_score,
            intent_score=intent_score,
            urgency_score=urgency_score,
            score_yesterday=score_yesterday,
            momentum=momentum,
            temperature=temperature,
            intent_phase=intent_phase,
            follow_up_priority=follow_up_priority,
            agent_priority=agent_priority,
            conversion_prob=conversion_prob,
            predictions=predictions,
            rev_metrics=rev_metrics,
            confidence=confidence,
            model_version=ml_model.version,
            features=features,
            recommendations=recommendations,
            pos_drivers=pos_drivers,
            neg_drivers=neg_drivers,
            rationale=rationale,
            trigger_event=trigger_event,
            rules_fired_count=len(rules_fired),
            execution_time_ms=round((time.time() - start_time) * 1000, 1),
        )

        # Update core Lead table score field for backwards compatibility
        await self._update_core_lead(lead_id, temperature, conversion_prob)

        # ── Step 12: Event Publishing ─────────────────────────────────────────
        await self.event_publisher.publish(LeadScored(
            lead_id=lead_id,
            organization_id=organization_id,
            lead_score=lead_score,
            intent_score=intent_score,
            urgency_score=urgency_score,
            temperature=temperature,
            intent_phase=intent_phase,
            momentum=momentum,
            conversion_probability=conversion_prob,
        ))

        if recommendations:
            top_rec = recommendations[0]
            await self.event_publisher.publish(RecommendationGenerated(
                lead_id=lead_id,
                organization_id=organization_id,
                top_action_type=top_rec["action_type"],
                top_action_title=top_rec["action_title"],
                estimated_conversion_lift=top_rec["estimated_conversion_lift"],
            ))

        exec_ms = round((time.time() - start_time) * 1000, 1)
        self.metrics_collector.record_scoring(exec_ms)
        await self.db.commit()

        logger.info(
            f"[LEAD_INTELLIGENCE] Completed Lead {lead_id}: score={lead_score} "
            f"temp={temperature} phase={intent_phase} momentum={momentum:+} ({exec_ms}ms)"
        )

        return {
            "lead_id": lead_id,
            "lead_score": lead_score,
            "intent_score": intent_score,
            "urgency_score": urgency_score,
            "temperature": temperature,
            "intent_phase": intent_phase,
            "momentum": momentum,
            "conversion_probability": conversion_prob,
            "follow_up_priority": follow_up_priority,
            "agent_priority": agent_priority,
            "estimated_revenue_aed": rev_metrics["estimated_revenue_aed"],
            "probability_weighted_revenue_aed": rev_metrics["probability_weighted_revenue_aed"],
            "confidence": confidence,
            "recommendations": recommendations,
            "positive_drivers": pos_drivers,
            "negative_drivers": neg_drivers,
            "rationale": rationale,
            "execution_time_ms": exec_ms,
        }

    async def get_lead_profile(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full intelligence profile for a lead."""
        result = await self.db.execute(
            select(LeadIntelligenceProfile).where(LeadIntelligenceProfile.lead_id == lead_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        # Fetch predictions
        pred_res = await self.db.execute(
            select(LeadPrediction).where(LeadPrediction.lead_id == lead_id).order_by(LeadPrediction.created_at.desc())
        )
        pred = pred_res.scalars().first()

        # Fetch recommendations
        rec_res = await self.db.execute(
            select(LeadRecommendation).where(LeadRecommendation.lead_id == lead_id, LeadRecommendation.status == "active").order_by(LeadRecommendation.rank.asc())
        )
        recs = rec_res.scalars().all()

        # Fetch explanation
        exp_res = await self.db.execute(
            select(PredictionExplanation).where(PredictionExplanation.lead_id == lead_id)
        )
        exp = exp_res.scalars().first()

        return {
            "lead_id": profile.lead_id,
            "organization_id": profile.organization_id,
            "lead_score": profile.lead_score,
            "intent_score": profile.intent_score,
            "urgency_score": profile.urgency_score,
            "temperature": profile.temperature,
            "intent_phase": profile.intent_phase,
            "momentum": profile.momentum,
            "follow_up_priority": profile.follow_up_priority,
            "agent_priority": profile.agent_priority,
            "conversion_probability": profile.conversion_probability,
            "estimated_revenue_aed": profile.estimated_revenue_aed,
            "probability_weighted_revenue_aed": profile.probability_weighted_revenue_aed,
            "overall_confidence": profile.overall_confidence,
            "predictions": {
                "response_probability": pred.response_probability if pred else 0.0,
                "meeting_probability": pred.meeting_probability if pred else 0.0,
                "viewing_probability": pred.viewing_probability if pred else 0.0,
                "closing_probability": pred.closing_probability if pred else 0.0,
                "churn_probability": pred.churn_probability if pred else 0.0,
                "risk_score": pred.risk_score if pred else 0.0,
            } if pred else {},
            "recommendations": [
                {
                    "rank": r.rank,
                    "action_type": r.action_type,
                    "action_title": r.action_title,
                    "estimated_conversion_lift": r.estimated_conversion_lift,
                    "reasoning": r.reasoning,
                }
                for r in recs
            ],
            "explanation": {
                "positive_drivers": exp.positive_drivers if exp else [],
                "negative_drivers": exp.negative_drivers if exp else [],
                "business_rationale": exp.business_rationale if exp else "",
            } if exp else {},
        }

    async def _load_active_rules(self, organization_id: str) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(ScoringRule).where(
                ScoringRule.organization_id == organization_id,
                ScoringRule.is_active == True,
            ).order_by(ScoringRule.priority.asc())
        )
        rules = result.scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "condition_json": r.condition_json,
                "action_value": r.action_value,
            }
            for r in rules
        ]

    async def _get_existing_profile(self, lead_id: str) -> Optional[LeadIntelligenceProfile]:
        result = await self.db.execute(
            select(LeadIntelligenceProfile).where(LeadIntelligenceProfile.lead_id == lead_id)
        )
        return result.scalar_one_or_none()

    async def _update_core_lead(self, lead_id: str, temperature: str, confidence: float):
        try:
            lead_uuid = uuid.UUID(lead_id)
            score_map = {"very_hot": "hot", "purchase_ready": "hot", "hot": "hot", "warm": "warm", "cold": "cold"}
            mapped_score = score_map.get(temperature, "cold")
            await self.db.execute(
                update(Lead)
                .where(Lead.id == lead_uuid)
                .values(score=mapped_score, score_confidence=confidence)
            )
        except Exception as e:
            logger.debug(f"[LEAD_INTELLIGENCE] Core lead update skipped/failed: {e}")

    async def _persist_intelligence(
        self,
        lead_id: str,
        organization_id: str,
        lead_score: float,
        intent_score: float,
        urgency_score: float,
        score_yesterday: float,
        momentum: float,
        temperature: str,
        intent_phase: str,
        follow_up_priority: int,
        agent_priority: int,
        conversion_prob: float,
        predictions: Dict[str, Any],
        rev_metrics: Dict[str, Any],
        confidence: float,
        model_version: str,
        features: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
        pos_drivers: List[Dict[str, Any]],
        neg_drivers: List[Dict[str, Any]],
        rationale: str,
        trigger_event: str,
        rules_fired_count: int,
        execution_time_ms: float,
    ):
        # 1. LeadIntelligenceProfile
        profile = await self._get_existing_profile(lead_id)
        if not profile:
            profile = LeadIntelligenceProfile(lead_id=lead_id, organization_id=organization_id)
            self.db.add(profile)

        profile.lead_score = lead_score
        profile.intent_score = intent_score
        profile.urgency_score = urgency_score
        profile.score_yesterday = score_yesterday
        profile.momentum = momentum
        profile.temperature = temperature
        profile.intent_phase = intent_phase
        profile.follow_up_priority = follow_up_priority
        profile.agent_priority = agent_priority
        profile.conversion_probability = conversion_prob
        profile.closing_probability = predictions["closing_probability"]
        profile.estimated_revenue_aed = rev_metrics["estimated_revenue_aed"]
        profile.probability_weighted_revenue_aed = rev_metrics["probability_weighted_revenue_aed"]
        profile.estimated_commission_aed = rev_metrics["estimated_commission_aed"]
        profile.ltv_estimate_aed = rev_metrics["ltv_estimate_aed"]
        profile.overall_confidence = confidence
        profile.active_model_version = model_version
        profile.updated_at = datetime.now(timezone.utc)

        # 2. LeadPrediction
        pred = LeadPrediction(
            lead_id=lead_id,
            organization_id=organization_id,
            response_probability=predictions["response_probability"],
            meeting_probability=predictions["meeting_probability"],
            viewing_probability=predictions["viewing_probability"],
            closing_probability=predictions["closing_probability"],
            churn_probability=predictions["churn_probability"],
            referral_probability=predictions["referral_probability"],
            buying_timeline_predicted=predictions["buying_timeline_predicted"],
            investment_potential_tier=predictions["investment_potential_tier"],
            risk_score=predictions["risk_score"],
            confidence=confidence,
            model_version=model_version,
        )
        self.db.add(pred)

        # 3. LeadRecommendations
        for rec_data in recommendations:
            rec = LeadRecommendation(
                lead_id=lead_id,
                organization_id=organization_id,
                rank=rec_data["rank"],
                action_type=rec_data["action_type"],
                action_title=rec_data["action_title"],
                estimated_conversion_lift=rec_data["estimated_conversion_lift"],
                reasoning=rec_data["reasoning"],
                status="active",
            )
            self.db.add(rec)

        # 4. FeatureVector
        fv = FeatureVector(
            lead_id=lead_id,
            organization_id=organization_id,
            feature_data=features,
            feature_count=len(features),
        )
        self.db.add(fv)

        # 5. PredictionExplanation
        exp_res = await self.db.execute(select(PredictionExplanation).where(PredictionExplanation.lead_id == lead_id))
        exp = exp_res.scalars().first()
        if not exp:
            exp = PredictionExplanation(lead_id=lead_id, organization_id=organization_id)
            self.db.add(exp)

        exp.positive_drivers = pos_drivers
        exp.negative_drivers = neg_drivers
        exp.business_rationale = rationale

        # 6. PredictionHistory
        ph = PredictionHistory(
            lead_id=lead_id,
            organization_id=organization_id,
            trigger_event=trigger_event,
            lead_score=lead_score,
            conversion_probability=conversion_prob,
            temperature=temperature,
            intent_phase=intent_phase,
            model_version=model_version,
            rules_fired_count=rules_fired_count,
            execution_time_ms=execution_time_ms,
            features_snapshot=features,
        )
        self.db.add(ph)
