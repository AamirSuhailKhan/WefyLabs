"""
Ground Truth Outcome Tracking & Reconciliation Engine
======================================================
Records real-world conversion and deal outcomes linked to historical predictions
without overwriting original inference records, enabling continuous model evaluation.
"""

import math
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.predictive_models import PredictionInferenceRecord, PredictionOutcomeRecord

logger = logging.getLogger(__name__)

class OutcomeTrackerService:
    """
    Reconciles ground truth events with historical prediction records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_prediction_outcome(
        self,
        prediction_id: str,
        actual_outcome: str,  # CONVERTED | WON | LOST | NO_SHOW | ATTENDED
        outcome_revenue_aed: Optional[float] = None
    ) -> PredictionOutcomeRecord:
        """
        Records the actual ground truth outcome for a prediction and computes Brier loss.
        """
        # 1. Fetch original prediction
        stmt = select(PredictionInferenceRecord).where(PredictionInferenceRecord.id == prediction_id)
        res = await self.db.execute(stmt)
        pred = res.scalar_one_or_none()
        if not pred:
            raise ValueError(f"PredictionInferenceRecord '{prediction_id}' not found.")

        # 2. Binary Outcome Value (1.0 for positive success, 0.0 for negative)
        is_positive = actual_outcome.upper() in ("CONVERTED", "WON", "ATTENDED")
        outcome_val = 1.0 if is_positive else 0.0

        # 3. Calculate Errors
        p = min(max(pred.calibrated_probability, 0.001), 0.999)
        brier_err = (p - outcome_val) ** 2
        log_loss_err = -(outcome_val * math.log(p) + (1.0 - outcome_val) * math.log(1.0 - p))

        # 4. Check for existing outcome record
        stmt_exist = select(PredictionOutcomeRecord).where(PredictionOutcomeRecord.prediction_id == prediction_id)
        res_exist = await self.db.execute(stmt_exist)
        existing = res_exist.scalar_one_or_none()
        if existing:
            existing.actual_outcome = actual_outcome
            existing.outcome_value = outcome_val
            existing.outcome_revenue_aed = outcome_revenue_aed
            existing.brier_error = round(brier_err, 4)
            existing.log_loss_error = round(log_loss_err, 4)
            await self.db.commit()
            return existing

        record = PredictionOutcomeRecord(
            id=str(uuid.uuid4()),
            prediction_id=pred.id,
            organization_id=pred.organization_id,
            entity_id=pred.entity_id,
            actual_outcome=actual_outcome,
            outcome_value=outcome_val,
            outcome_revenue_aed=outcome_revenue_aed,
            outcome_timestamp=datetime.now(timezone.utc),
            brier_error=round(brier_err, 4),
            log_loss_error=round(log_loss_err, 4)
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        logger.info(f"[OUTCOME] Reconciled Prediction {prediction_id} with actual outcome '{actual_outcome}' (Brier Err: {brier_err:.4f}).")
        return record
