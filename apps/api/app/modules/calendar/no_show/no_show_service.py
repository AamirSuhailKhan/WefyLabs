"""
No-Show Prediction & Mitigation Engine
======================================
Predicts the probability of a participant missing a scheduled appointment
and triggers preventative confirmation actions.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.calendar_models import Meeting, NoShowPrediction
from app.models.lead import Lead

logger = logging.getLogger(__name__)

class NoShowPredictionService:
    """
    Evaluates no-show risk factors based on lead engagement, distance, and booking lead-time.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def predict_no_show_risk(self, meeting_id: str) -> NoShowPrediction:
        """
        Calculates no-show risk score (0.0 to 1.0) and assigns preventative confirmation action.
        """
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        res = await self.db.execute(stmt)
        meeting = res.scalar_one_or_none()

        if not meeting:
            raise ValueError(f"Meeting '{meeting_id}' not found.")

        lead: Optional[Lead] = None
        if meeting.lead_id:
            stmt_l = select(Lead).where(Lead.id == meeting.lead_id)
            res_l = await self.db.execute(stmt_l)
            lead = res_l.scalar_one_or_none()

        factors: List[str] = []
        base_risk = 0.15 # Baseline real estate site visit no-show rate

        # Risk Factor 1: Long booking lead-time (> 5 days)
        days_ahead = (meeting.start_utc - datetime.now(timezone.utc)).total_seconds() / 86400.0
        if days_ahead > 5.0:
            base_risk += 0.20
            factors.append(f"Appointment booked {days_ahead:.0f} days in advance (High decay window)")

        # Risk Factor 2: Unqualified / cold lead
        if lead and (lead.score == "cold" or lead.score_confidence < 0.4):
            base_risk += 0.25
            factors.append("Lead score is cold with low engagement confidence")

        # Risk Factor 3: Virtual vs In-Person
        if meeting.meeting_type == "VIDEO_CALL":
            base_risk += 0.10
            factors.append("Virtual meetings have higher drop-off rates")

        no_show_prob = min(0.95, round(base_risk, 2))
        risk_level = "HIGH" if no_show_prob >= 0.5 else "MEDIUM" if no_show_prob >= 0.3 else "LOW"

        action = "Send standard 24h & 2h reminders"
        if risk_level == "HIGH":
            action = "Dispatch interactive WhatsApp confirmation prompt requesting reply confirmation"
        elif risk_level == "MEDIUM":
            action = "Share detailed location directions and parking pin"

        prediction = NoShowPrediction(
            id=str(uuid.uuid4()),
            meeting_id=meeting.id,
            no_show_probability=no_show_prob,
            risk_level=risk_level,
            confidence=0.88,
            influencing_factors=factors,
            preventative_action=action,
            calculated_at=datetime.now(timezone.utc)
        )
        self.db.add(prediction)
        await self.db.commit()
        await self.db.refresh(prediction)

        logger.info(f"[NO_SHOW] Meeting {meeting.id} assessed with {risk_level} no-show risk ({no_show_prob * 100:.0f}%).")
        return prediction
