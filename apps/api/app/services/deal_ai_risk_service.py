from typing import Dict, Any, List
from app.core.domain.transactions.entities import TransactionStage, DealRiskLevel
from app.services.deal_workflow_engine import DealWorkflowEngine

class DealAIRiskService:
    """
    AI Deal Risk Engine predicting closing probability, missing document flags, stall alerts, and escalations.
    """

    @classmethod
    def analyze_deal_risk(
        cls,
        current_stage: TransactionStage,
        submitted_documents: List[str],
        days_in_current_stage: int = 5
    ) -> Dict[str, Any]:
        required_docs = DealWorkflowEngine.REQUIRED_DOCUMENTS_BY_STAGE.get(current_stage, [])
        missing_docs = [doc for doc in required_docs if doc not in submitted_documents]

        # Calculate closing probability
        base_probability_map: Dict[TransactionStage, float] = {
            TransactionStage.LEAD: 15.0,
            TransactionStage.QUALIFIED: 30.0,
            TransactionStage.PROPERTY_VISIT: 45.0,
            TransactionStage.OFFER: 60.0,
            TransactionStage.NEGOTIATION: 70.0,
            TransactionStage.BOOKING: 80.0,
            TransactionStage.DOCUMENTS: 85.0,
            TransactionStage.LOAN: 90.0,
            TransactionStage.LEGAL: 95.0,
            TransactionStage.REGISTRATION: 98.0,
            TransactionStage.CLOSING: 100.0,
            TransactionStage.COMMISSION: 100.0,
            TransactionStage.AFTER_SALES: 100.0,
        }

        prob = base_probability_map.get(current_stage, 50.0)

        # Deduct for missing documents or stalled days
        if missing_docs:
            prob -= len(missing_docs) * 7.5
        if days_in_current_stage > 10:
            prob -= (days_in_current_stage - 10) * 2.0

        prob = max(min(prob, 99.0), 10.0)

        # Assess Risk Level
        if missing_docs and days_in_current_stage > 12:
            risk_level = DealRiskLevel.CRITICAL_STALLED.value
        elif missing_docs or days_in_current_stage > 7:
            risk_level = DealRiskLevel.HIGH_RISK.value
        elif days_in_current_stage > 4:
            risk_level = DealRiskLevel.MEDIUM.value
        else:
            risk_level = DealRiskLevel.LOW.value

        next_action = f"Request missing {missing_docs[0]}" if missing_docs else f"Advance deal from {current_stage.value} to next stage."

        return {
            "risk_level": risk_level,
            "closing_probability_pct": round(prob, 1),
            "missing_documents": missing_docs,
            "days_in_current_stage": days_in_current_stage,
            "recommended_next_action": next_action
        }
