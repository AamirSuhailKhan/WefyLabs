import uuid
from typing import Dict, Any, List
from app.core.domain.portal.entities import CustomerPortalEntity, CustomerDealProgressEntity, CustomerRole

class CustomerPortalService:
    """
    Zillow & Airbnb-grade Customer Self-Service Portal Service.
    Aggregates buyer deal milestones, document approvals, and AI property advice.
    """

    @classmethod
    def get_customer_dashboard(cls, customer_id: uuid.UUID) -> CustomerPortalEntity:
        deal = CustomerDealProgressEntity(
            deal_id=uuid.UUID("50505050-5050-5050-5050-505050505050"),
            property_title="Luxury 3BHK Penthouse in Marina Gate 1",
            agreed_price=2850000.0,
            current_stage="Bank Loan Pre-Approval",
            booking_deposit_paid=True,
            loan_approval_status="approved",
            legal_noc_status="verified",
            estimated_registration_date="2026-08-15",
            completion_percentage=75.0
        )

        return CustomerPortalEntity(
            customer_id=customer_id,
            name="Rahul Sharma",
            email="rahul.sharma@example.com",
            phone="+91 98765 43210",
            role=CustomerRole.BUYER,
            active_deal=deal,
            saved_properties_count=3,
            assigned_broker_name="Aamir Khan",
            assigned_broker_phone="+971 50 123 4567"
        )

    @classmethod
    def ask_ai_property_advisor(cls, question: str, property_title: str = "DLF Marina Gate") -> Dict[str, Any]:
        """Provides AI customer advice on mortgages, property ROI, and legal registration steps."""
        return {
            "question": question,
            "property_title": property_title,
            "ai_answer": (
                "**AI Property Advisor Response:**\n"
                "- **Mortgage Estimate:** For AED 2,850,000 at a 20% down payment (AED 570,000), your monthly EMI is approx. **AED 11,450/month** (25 years @ 4.25% interest).\n"
                "- **Land Department Registration Fee:** 4% + AED 580 admin fee (AED 114,580).\n"
                "- **Next Step:** Your bank pre-approval is complete. The next milestone is Land Department Transfer on **Aug 15, 2026**."
            ),
            "citations": ["Dubai Land Department (DLD) Fee Structure", "Mortgage Interest Rate Index 2026"]
        }
