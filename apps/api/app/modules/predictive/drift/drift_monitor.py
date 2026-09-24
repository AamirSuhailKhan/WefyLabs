"""
Population Stability Index (PSI) & Model Drift Monitor
======================================================
Monitors feature distribution shifts and prediction drift to detect
model decay before real-world revenue performance degrades.
"""

import math
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.predictive_models import PredictionDriftRecord

logger = logging.getLogger(__name__)

class DriftMonitorService:
    """
    Computes Population Stability Index (PSI) and monitors statistical drift.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def calculate_psi(baseline_distribution: List[float], target_distribution: List[float]) -> float:
        """
        Calculates Population Stability Index (PSI):
        PSI < 0.10: No significant shift (Stable)
        0.10 <= PSI < 0.25: Moderate shift (Monitor)
        PSI >= 0.25: Significant shift (Retraining required)
        """
        if not baseline_distribution or len(baseline_distribution) != len(target_distribution):
            return 0.0

        psi = 0.0
        for b, t in zip(baseline_distribution, target_distribution):
            b_clean = max(b, 0.0001)
            t_clean = max(t, 0.0001)
            psi += (t_clean - b_clean) * math.log(t_clean / b_clean)

        return round(psi, 4)

    async def evaluate_prediction_drift(
        self,
        model_version_tag: str = "v1.0.0",
        baseline_bins: Optional[List[float]] = None,
        recent_bins: Optional[List[float]] = None
    ) -> PredictionDriftRecord:
        """
        Evaluates PSI between baseline training distribution and recent production inferences.
        """
        b_dist = baseline_bins or [0.15, 0.25, 0.30, 0.20, 0.10]
        r_dist = recent_bins or [0.12, 0.22, 0.34, 0.21, 0.11]

        psi_score = self.calculate_psi(b_dist, r_dist)
        drift_detected = psi_score >= 0.10
        alert_triggered = psi_score >= 0.25

        record = PredictionDriftRecord(
            id=str(uuid.uuid4()),
            model_version_tag=model_version_tag,
            metric_name="CONVERSION_PROBABILITY_DISTRIBUTION",
            drift_type="PREDICTION_DRIFT",
            psi_score=psi_score,
            drift_detected=drift_detected,
            alert_triggered=alert_triggered,
            evaluated_at=datetime.now(timezone.utc)
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        if alert_triggered:
            logger.warning(f"[DRIFT] Significant prediction drift detected for {model_version_tag} (PSI = {psi_score:.4f}).")
        else:
            logger.info(f"[DRIFT] Model {model_version_tag} distribution stable (PSI = {psi_score:.4f}).")

        return record
