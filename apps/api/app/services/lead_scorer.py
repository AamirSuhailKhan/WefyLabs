import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Literal, Tuple, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.models.broker import Broker
from app.models.score import Score
from app.services.whatsapp_service import send_message

logger = logging.getLogger(__name__)

class ExtractedData(BaseModel):
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    preferred_locations: Optional[List[str]] = None
    property_type: Optional[Literal["1bhk", "2bhk", "3bhk", "villa", "plot"]] = None
    transaction_type: Optional[Literal["buy", "rent", "lease"]] = None
    timeline: Optional[Literal["immediate", "1_month", "3_months", "6_months"]] = None
    loan_status: Optional[Literal["pre_approved", "in_process", "not_started"]] = None

def calculate_score(data: ExtractedData) -> Tuple[str, float, str]:
    """
    Calculates lead score based on exact PRD Section 8 rules.
    Returns: (score: 'hot'|'warm'|'cold', confidence: float 0.0-1.0, reasoning: str)
    """
    hot_points = 0
    warm_points = 0
    reasons = []

    # 1. Budget logic
    if data.budget_min and data.budget_max:
        hot_points += 1
        reasons.append("Clear budget stated")
    elif data.budget_min or data.budget_max:
        warm_points += 1
        reasons.append("Partial budget information")
    else:
        reasons.append("No budget information")

    # 2. Timeline logic
    if data.timeline in ("immediate", "1_month"):
        hot_points += 2
        reasons.append("Immediate timeline")
    elif data.timeline in ("3_months", "6_months"):
        warm_points += 1
        reasons.append(f"Timeline: {data.timeline}")
    else:
        reasons.append("Vague or distant timeline")

    # 3. Location logic
    if data.preferred_locations and len(data.preferred_locations) > 0:
        hot_points += 1
        reasons.append("Specific locations mentioned")
    else:
        reasons.append("No specific location")

    # 4. Intent/Property type logic
    if data.property_type and data.transaction_type:
        hot_points += 1
        reasons.append("Clear property requirements")
    elif data.property_type or data.transaction_type:
        warm_points += 1
        reasons.append("Partial property requirements")
    else:
        reasons.append("Unclear property requirements")

    # 5. Loan status (bonus for buyers)
    if data.transaction_type == "buy" and data.loan_status == "pre_approved":
        hot_points += 1
        reasons.append("Pre-approved loan")

    # Scoring algorithm
    if hot_points >= 3:
        score = "hot"
        confidence = round(min(0.70 + (hot_points * 0.05), 0.95), 2)
    elif hot_points >= 1 or warm_points >= 2:
        score = "warm"
        confidence = round(min(0.50 + (warm_points * 0.10), 0.75), 2)
    else:
        score = "cold"
        confidence = round(max(0.30 - (warm_points * 0.05), 0.10), 2)

    reasoning = " | ".join(reasons)
    return score, confidence, reasoning

def calculate_lead_score(data_dict: Dict[str, Any]) -> Tuple[str, float, str]:
    """Helper wrapper taking a dict, validating via ExtractedData, and running calculate_score."""
    try:
        extracted = ExtractedData(**data_dict)
    except Exception:
        extracted = ExtractedData()
    return calculate_score(extracted)

async def qualify_and_score_lead(
    db: AsyncSession,
    lead_id: uuid.UUID,
    force: bool = False
) -> Dict[str, Any]:
    """
    Idempotent qualification and scoring pipeline.
    Fetches lead, evaluates score, updates DB, creates audit trail, and sends broker notification.
    """
    stmt = (
        select(Lead)
        .where(Lead.id == lead_id, Lead.deleted_at.is_(None))
        .options(
            selectinload(Lead.conversations),
            selectinload(Lead.scores)
        )
    )
    result = await db.execute(stmt)
    lead = result.scalars().first()

    if not lead:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found."
        )

    # Idempotency check: if lead is already qualified and has scores and force=False
    if not force and lead.status == "qualified" and lead.scores:
        latest = lead.scores[0]
        return {
            "lead_id": str(lead.id),
            "score": latest.score,
            "confidence": latest.confidence,
            "reasoning": latest.reasoning,
            "extracted_data": latest.extracted_data or {}
        }

    # Construct ExtractedData from lead record attributes
    data_dict = {
        "budget_min": lead.budget_min,
        "budget_max": lead.budget_max,
        "preferred_locations": lead.preferred_locations,
        "property_type": lead.property_type,
        "transaction_type": lead.transaction_type,
        "timeline": lead.timeline,
        "loan_status": lead.loan_status
    }
    extracted = ExtractedData(**data_dict)
    score_category, confidence_val, reasoning_str = calculate_score(extracted)

    # Update lead
    lead.score = score_category
    lead.score_confidence = confidence_val
    lead.status = "qualified"
    lead.qualified_at = datetime.now(timezone.utc)
    lead.updated_at = datetime.now(timezone.utc)

    # Create Score audit entry
    score_entry = Score(
        lead_id=lead.id,
        score=score_category,
        confidence=confidence_val,
        reasoning=reasoning_str,
        extracted_data=extracted.model_dump(exclude_none=True)
    )
    db.add(score_entry)
    await db.commit()

    # Send Broker WhatsApp Alert
    broker_stmt = select(Broker).where(Broker.id == lead.broker_id)
    broker = (await db.execute(broker_stmt)).scalars().first()

    if broker and broker.whatsapp_number:
        loc_str = ", ".join(lead.preferred_locations or ["Bengaluru"])
        b_min = f"₹{lead.budget_min/100000:.0f}L" if lead.budget_min else "N/A"
        b_max = f"₹{lead.budget_max/100000:.0f}L" if lead.budget_max else "N/A"
        conf_pct = int(confidence_val * 100)

        if score_category == "hot":
            alert_msg = (
                f"🔥 HOT LEAD ({lead.phone}) — Budget: {b_min}-{b_max} | "
                f"Location: {loc_str} | Timeline: {lead.timeline or 'Immediate'}. "
                f"Confidence: {conf_pct}%. Call now!"
            )
        elif score_category == "warm":
            alert_msg = (
                f"🌡️ WARM LEAD ({lead.phone}) — Budget: {b_min}-{b_max} | "
                f"Location: {loc_str}. Follow up within 24h."
            )
        else:
            alert_msg = f"❄️ COLD LEAD ({lead.phone}) — {reasoning_str}. Saved to dashboard."

        await send_message(broker.whatsapp_number, alert_msg)

    return {
        "lead_id": str(lead.id),
        "score": score_category,
        "confidence": confidence_val,
        "reasoning": reasoning_str,
        "extracted_data": extracted.model_dump(exclude_none=True)
    }
