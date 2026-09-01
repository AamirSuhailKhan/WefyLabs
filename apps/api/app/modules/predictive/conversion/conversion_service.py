"""
Lead Conversion Prediction Service
==================================
Coordinates feature extraction, inference execution, database persistence of
PredictionInferenceRecord, and cache TTL management.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.predictive_models import PredictionInferenceRecord
from app.modules.predictive.features.predictive_feature_store import PredictiveFeatureStore
from app.modules.predictive.models.calibrated_conversion_model import CalibratedConversionModel

logger = logging.getLogger(__name__)

class ConversionPredictionService:
    """
    Predicts calibrated conversion probabilities for leads.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.feature_store = PredictiveFeatureStore(db)
        self.model = CalibratedConversionModel(version_tag="v1.0.0")

    async def predict_lead_conversion(
        self,
        lead_id: str,
        organization_id: str,
        force_refresh: bool = False
    ) -> PredictionInferenceRecord:
        """
        Generates or retrieves a valid cached conversion probability for a lead.
        """
        now = datetime.now(timezone.utc)

        # 1. Check for valid cached prediction if not force_refresh
        if not force_refresh:
            stmt = select(PredictionInferenceRecord).where(
                and_(
                    PredictionInferenceRecord.entity_id == lead_id,
                    PredictionInferenceRecord.prediction_type == "CONVERSION",
                    PredictionInferenceRecord.valid_until > now
                )
            ).order_by(PredictionInferenceRecord.generated_at.desc()).limit(1)
            res = await self.db.execute(stmt)
            cached = res.scalar_one_or_none()
            if cached:
                return cached

        # 2. Extract real-time point-in-time features
        feats = await self.feature_store.get_lead_features(lead_id, as_of_timestamp=now)

        # 3. Model Inference
        pred_result = self.model.predict(feats, lead_id)

        # 4. Persist Prediction Inference Record
        record = PredictionInferenceRecord(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            entity_id=lead_id,
            entity_type="LEAD",
            prediction_type="CONVERSION",
            raw_score=pred_result.raw_score,
            calibrated_probability=pred_result.calibrated_probability,
            confidence_score=pred_result.confidence_score,
            confidence_level=pred_result.confidence_level,
            model_version_tag=pred_result.model_version_tag,
            feature_schema_version=pred_result.feature_schema_version,
            features_snapshot=feats,
            positive_drivers=[
                {"feature": d.feature_name, "impact": d.impact_score, "description": d.description}
                for d in pred_result.explanation.positive_drivers
            ],
            negative_drivers=[
                {"feature": d.feature_name, "impact": d.impact_score, "description": d.description}
                for d in pred_result.explanation.negative_drivers
            ],
            explanation_text=pred_result.explanation.summary_markdown,
            generated_at=pred_result.generated_at,
            valid_until=pred_result.valid_until or (now + timedelta(days=7))
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        logger.info(f"[PREDICTIVE] Computed conversion probability {record.calibrated_probability:.2f} for Lead {lead_id}.")
        return record
