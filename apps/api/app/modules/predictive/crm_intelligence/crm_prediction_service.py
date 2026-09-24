"""
Part 16 — CRM Prediction Intelligence Service
===============================================
The single entry point for the CRM to access all Part 16 predictive intelligence
for a lead or opportunity. This is the bridge between the predictive engine and
the Native WefyLabs CRM (Part 14).

Responsibilities:
  - Hydrate full feature vector from the existing PredictiveFeatureStore
  - Execute all propensity scores via PropensityEngine
  - Rank next best actions via NextBestActionRanker
  - Execute existing conversion prediction (CalibratedConversionModel)
  - Persist PredictionInferenceRecord for audit/drift tracking
  - Fail gracefully — never raises exceptions into the CRM flow

Tenant isolation: organization_id is threaded through all calls.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.predictive_models import PredictionInferenceRecord
from app.modules.predictive.features.predictive_feature_store import PredictiveFeatureStore
from app.modules.predictive.models.calibrated_conversion_model import CalibratedConversionModel
from app.modules.predictive.propensity.propensity_engine import PropensityEngine, PropensityScore
from app.modules.predictive.nba.next_best_action import NextBestActionRanker, NextBestActionResult

logger = logging.getLogger(__name__)

# ─── Prediction Surface Contract ──────────────────────────────────────────────

class LeadPredictionSurface:
    """
    Complete predictive intelligence surface for a single lead in the CRM.
    This is returned to the CRM and surfaced in the Lead 360 / Kanban card.
    """

    def __init__(
        self,
        lead_id: str,
        organization_id: str,
        conversion_probability: float,
        confidence_level: str,
        explanation_text: str,
        positive_drivers: List[Dict[str, Any]],
        negative_drivers: List[Dict[str, Any]],
        propensity_scores: Dict[str, Dict[str, Any]],
        next_best_actions: Dict[str, Any],
        prediction_id: str,
        model_version_tag: str,
        generated_at: datetime,
        valid_until: datetime,
    ):
        self.lead_id = lead_id
        self.organization_id = organization_id
        self.conversion_probability = conversion_probability
        self.confidence_level = confidence_level
        self.explanation_text = explanation_text
        self.positive_drivers = positive_drivers
        self.negative_drivers = negative_drivers
        self.propensity_scores = propensity_scores
        self.next_best_actions = next_best_actions
        self.prediction_id = prediction_id
        self.model_version_tag = model_version_tag
        self.generated_at = generated_at
        self.valid_until = valid_until

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lead_id": self.lead_id,
            "organization_id": self.organization_id,
            "conversion_probability": self.conversion_probability,
            "conversion_probability_pct": round(self.conversion_probability * 100, 1),
            "confidence_level": self.confidence_level,
            "explanation_text": self.explanation_text,
            "positive_drivers": self.positive_drivers,
            "negative_drivers": self.negative_drivers,
            "propensity_scores": self.propensity_scores,
            "next_best_actions": self.next_best_actions,
            "prediction_id": self.prediction_id,
            "model_version_tag": self.model_version_tag,
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
        }


# ─── CRM Prediction Intelligence Service ─────────────────────────────────────

class CRMPredictionIntelligenceService:
    """
    Aggregates all predictive intelligence for the Native CRM surface.
    The CRM calls this service to get the complete prediction panel for a lead.
    Designed to fail gracefully — always returns a result, even if degraded.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.feature_store = PredictiveFeatureStore(db)
        self.conversion_model = CalibratedConversionModel(version_tag="v1.0.0")

    async def get_lead_intelligence(
        self,
        lead_id: str,
        organization_id: str,
        force_refresh: bool = False,
    ) -> LeadPredictionSurface:
        """
        Returns the complete predictive intelligence surface for a lead.
        Checks cache first (valid until expiry), computes fresh if needed.
        """
        now = datetime.now(timezone.utc)

        # ── 1. Cache Check ─────────────────────────────────────────────────
        if not force_refresh:
            cached = await self._get_cached_surface(lead_id, organization_id, now)
            if cached:
                return cached

        # ── 2. Feature Extraction ──────────────────────────────────────────
        try:
            features = await self.feature_store.get_lead_features(lead_id, as_of_timestamp=now)
        except ValueError as ve:
            logger.warning(f"[CRM_PREDICT] Feature extraction failed for {lead_id}: {ve}")
            return self._degraded_surface(lead_id, organization_id, reason=str(ve))
        except Exception as e:
            logger.error(f"[CRM_PREDICT] Feature store error for {lead_id}: {e}")
            return self._degraded_surface(lead_id, organization_id, reason="Feature extraction failed")

        # ── 3. Conversion Prediction ───────────────────────────────────────
        try:
            conv_result = self.conversion_model.predict(features, lead_id)
            calibrated_prob = conv_result.calibrated_probability
            confidence_level = conv_result.confidence_level
            explanation_text = conv_result.explanation.summary_markdown
            positive_drivers = [
                {"feature": d.feature_name, "impact": d.impact_score, "description": d.description}
                for d in conv_result.explanation.positive_drivers
            ]
            negative_drivers = [
                {"feature": d.feature_name, "impact": d.impact_score, "description": d.description}
                for d in conv_result.explanation.negative_drivers
            ]
        except Exception as e:
            logger.error(f"[CRM_PREDICT] Conversion model failed for {lead_id}: {e}")
            calibrated_prob = 0.30
            confidence_level = "LOW"
            explanation_text = "Prediction degraded — using baseline estimate."
            positive_drivers = []
            negative_drivers = []

        # ── 4. Propensity Scores ───────────────────────────────────────────
        try:
            all_propensity = PropensityEngine.score_all(features, organization_id)
            propensity_dict = {k: v.to_dict() for k, v in all_propensity.items()}
        except Exception as e:
            logger.error(f"[CRM_PREDICT] Propensity engine failed for {lead_id}: {e}")
            all_propensity = {}
            propensity_dict = {}

        # ── 5. Next Best Actions ───────────────────────────────────────────
        try:
            nba_result = NextBestActionRanker.rank(
                features=features,
                org_id=organization_id,
                propensity_scores={k: v.to_dict() for k, v in all_propensity.items()},
            )
            nba_dict = nba_result.to_dict()
        except Exception as e:
            logger.error(f"[CRM_PREDICT] NBA engine failed for {lead_id}: {e}")
            nba_dict = {"ranked_actions": [], "reasoning_summary": "NBA unavailable.", "action_count": 0}

        # ── 6. Persist Inference Record ────────────────────────────────────
        pred_id = str(uuid.uuid4())
        try:
            record = PredictionInferenceRecord(
                id=pred_id,
                organization_id=organization_id,
                entity_id=lead_id,
                entity_type="LEAD",
                prediction_type="CONVERSION",
                raw_score=round(calibrated_prob, 4),
                calibrated_probability=round(calibrated_prob, 4),
                confidence_score=0.85 if confidence_level == "HIGH" else 0.65 if confidence_level == "MEDIUM" else 0.45,
                confidence_level=confidence_level,
                model_version_tag="v1.0.0",
                feature_schema_version="v1.0.0",
                features_snapshot=features,
                positive_drivers=positive_drivers,
                negative_drivers=negative_drivers,
                explanation_text=explanation_text,
                generated_at=now,
                valid_until=now + timedelta(hours=12),
            )
            self.db.add(record)
            await self.db.commit()
            await self.db.refresh(record)
        except Exception as e:
            logger.error(f"[CRM_PREDICT] Failed to persist inference record for {lead_id}: {e}")
            await self.db.rollback()
            # Non-fatal — surface still returned

        return LeadPredictionSurface(
            lead_id=lead_id,
            organization_id=organization_id,
            conversion_probability=calibrated_prob,
            confidence_level=confidence_level,
            explanation_text=explanation_text,
            positive_drivers=positive_drivers,
            negative_drivers=negative_drivers,
            propensity_scores=propensity_dict,
            next_best_actions=nba_dict,
            prediction_id=pred_id,
            model_version_tag="v1.0.0",
            generated_at=now,
            valid_until=now + timedelta(hours=12),
        )

    async def _get_cached_surface(
        self,
        lead_id: str,
        organization_id: str,
        now: datetime,
    ) -> Optional[LeadPredictionSurface]:
        """Returns a cached surface from the most recent valid inference record."""
        try:
            stmt = select(PredictionInferenceRecord).where(
                and_(
                    PredictionInferenceRecord.entity_id == lead_id,
                    PredictionInferenceRecord.organization_id == organization_id,
                    PredictionInferenceRecord.prediction_type == "CONVERSION",
                    PredictionInferenceRecord.valid_until > now,
                )
            ).order_by(PredictionInferenceRecord.generated_at.desc()).limit(1)
            res = await self.db.execute(stmt)
            cached_record = res.scalar_one_or_none()

            if not cached_record:
                return None

            # Reconstruct surface from cached record (propensity/NBA are cheap to recompute)
            features = dict(cached_record.features_snapshot) if cached_record.features_snapshot else {}
            if features:
                try:
                    all_propensity = PropensityEngine.score_all(features, organization_id)
                    propensity_dict = {k: v.to_dict() for k, v in all_propensity.items()}
                    nba_result = NextBestActionRanker.rank(
                        features=features,
                        org_id=organization_id,
                        propensity_scores={k: v.to_dict() for k, v in all_propensity.items()},
                    )
                    nba_dict = nba_result.to_dict()
                except Exception:
                    propensity_dict = {}
                    nba_dict = {}
            else:
                propensity_dict = {}
                nba_dict = {}

            return LeadPredictionSurface(
                lead_id=lead_id,
                organization_id=organization_id,
                conversion_probability=cached_record.calibrated_probability,
                confidence_level=cached_record.confidence_level,
                explanation_text=cached_record.explanation_text,
                positive_drivers=list(cached_record.positive_drivers or []),
                negative_drivers=list(cached_record.negative_drivers or []),
                propensity_scores=propensity_dict,
                next_best_actions=nba_dict,
                prediction_id=cached_record.id,
                model_version_tag=cached_record.model_version_tag,
                generated_at=cached_record.generated_at,
                valid_until=cached_record.valid_until,
            )
        except Exception as e:
            logger.warning(f"[CRM_PREDICT] Cache check failed: {e}")
            return None

    @staticmethod
    def _degraded_surface(
        lead_id: str,
        organization_id: str,
        reason: str = "Prediction unavailable",
    ) -> LeadPredictionSurface:
        """Returns a minimal, gracefully degraded surface when the engine fails."""
        now = datetime.now(timezone.utc)
        return LeadPredictionSurface(
            lead_id=lead_id,
            organization_id=organization_id,
            conversion_probability=0.25,
            confidence_level="LOW",
            explanation_text=f"⚠️ Prediction degraded: {reason}. Using statistical baseline.",
            positive_drivers=[],
            negative_drivers=[{"feature": "Prediction Error", "impact": 0.0, "description": reason}],
            propensity_scores={},
            next_best_actions={"ranked_actions": [], "reasoning_summary": reason, "action_count": 0},
            prediction_id=str(uuid.uuid4()),
            model_version_tag="DEGRADED",
            generated_at=now,
            valid_until=now + timedelta(hours=1),
        )
