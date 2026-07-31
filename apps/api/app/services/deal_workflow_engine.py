from typing import Dict, Any, List, Optional
from app.core.domain.transactions.entities import TransactionStage

class DealWorkflowEngine:
    """
    Deterministic State Machine enforcing 13 Transaction Stages and Milestone Approvals.
    """

    STAGE_ORDER: List[TransactionStage] = [
        TransactionStage.LEAD,
        TransactionStage.QUALIFIED,
        TransactionStage.PROPERTY_VISIT,
        TransactionStage.OFFER,
        TransactionStage.NEGOTIATION,
        TransactionStage.BOOKING,
        TransactionStage.DOCUMENTS,
        TransactionStage.LOAN,
        TransactionStage.LEGAL,
        TransactionStage.REGISTRATION,
        TransactionStage.CLOSING,
        TransactionStage.COMMISSION,
        TransactionStage.AFTER_SALES
    ]

    REQUIRED_DOCUMENTS_BY_STAGE: Dict[TransactionStage, List[str]] = {
        TransactionStage.BOOKING: ["Passport Copy / National ID", "Reservation Form Signed", "Token Booking Receipt"],
        TransactionStage.DOCUMENTS: ["KYC Verification", "Proof of Funds", "Source of Income Declaration"],
        TransactionStage.LOAN: ["Bank Pre-Approval Letter", "Salary Certificate / Tax Return", "Property Valuation Report"],
        TransactionStage.LEGAL: ["Title Deed Verification", "NOC (No Objection Certificate) from Developer", "Draft Sale Agreement (MOU)"],
        TransactionStage.REGISTRATION: ["Manager's Cheque", "Land Department Transfer Booking", "Power of Attorney (if applicable)"]
    }

    @classmethod
    def get_next_stage(cls, current_stage: TransactionStage) -> Optional[TransactionStage]:
        try:
            curr_idx = cls.STAGE_ORDER.index(current_stage)
            if curr_idx + 1 < len(cls.STAGE_ORDER):
                return cls.STAGE_ORDER[curr_idx + 1]
        except ValueError:
            pass
        return None

    @classmethod
    def validate_stage_transition(cls, current_stage: TransactionStage, target_stage: TransactionStage) -> Dict[str, Any]:
        """Validates if advancing to target stage is permitted by business rules."""
        curr_idx = cls.STAGE_ORDER.index(current_stage)
        target_idx = cls.STAGE_ORDER.index(target_stage)

        if target_idx < curr_idx:
            return {"allowed": True, "reason": "Rollback permitted"}

        if target_idx > curr_idx + 1:
            return {
                "allowed": False,
                "reason": f"Cannot skip intermediate stages. Must transition from '{current_stage.value}' to '{cls.STAGE_ORDER[curr_idx + 1].value}' first."
            }

        return {"allowed": True, "reason": "Stage progression approved"}
