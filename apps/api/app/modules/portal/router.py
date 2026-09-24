"""
Part 21 — Customer Portal & Digital Transaction Room FastAPI Router
===================================================================
Endpoints for:
- Customer Portal Overview & Deal Room
- Document Request & Customer Upload Engine
- Payment Schedule & Proof Verification Workflow
- Customer Appointments & Viewing Confirmations
- Customer Messaging with Strict CRM Boundary
- Support Queries & Issue Escalation
- Post-Sale CSAT / NPS & Acknowledgements
- Governed Customer AI Assistant
- Broker-facing Invite Generation & Document/Payment Review

Security:
- Every customer route enforces get_current_portal_customer.
- Customer identity & tenant context are derived strictly from JWT.
- Client-supplied tenant/customer parameters are rejected.
"""
from __future__ import annotations

import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.portal.dependencies import get_current_portal_customer
from app.modules.portal.service import CustomerPortalService
from app.modules.portal.dto.portal_schemas import (
    PortalTokenExchangeRequest, PortalMagicLinkRequest, PortalAuthTokenResponse,
    PortalCustomerContext, CustomerPortalOverview, CustomerPortalDeal,
    CustomerPortalDocument, CustomerDocumentUploadRequest,
    CustomerPortalPaymentSchedule, CustomerPaymentProofSubmitRequest,
    CustomerPortalAppointment, CustomerAppointmentConfirmRequest,
    CustomerPortalMessage, CustomerSendMessageRequest,
    CustomerSupportRequestCreate, CustomerSupportRequestResponse,
    CustomerPostSaleFeedbackRequest, CustomerPostSaleFeedbackResponse,
    CustomerAcknowledgementRequest, CustomerAIQueryRequest, CustomerAIQueryResponse,
    PortalInviteGenerateRequest, PortalInviteResponse,
    DocumentReviewDecision, PaymentProofReviewDecision
)

router = APIRouter(prefix="/portal", tags=["Part 21 — Customer Portal & Deal Room OS"])
portal_router = router


# ═══════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION & ACCESS TOKENS (Public)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/auth/exchange", response_model=PortalAuthTokenResponse, summary="Exchange invite token for customer session JWT")
async def exchange_token(
    req: PortalTokenExchangeRequest,
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.exchange_invite_token(req.token)


@router.post("/auth/magic-link", summary="Request customer magic link by email/phone")
async def request_magic_link(
    req: PortalMagicLinkRequest,
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.request_magic_link(req.email_or_phone)


@router.get("/auth/me", response_model=PortalCustomerContext, summary="Get current authenticated customer profile")
async def get_current_customer(
    customer: PortalCustomerContext = Depends(get_current_portal_customer)
):
    return customer


# ═══════════════════════════════════════════════════════════════════════════
# 2. CUSTOMER OVERVIEW & DIGITAL DEAL ROOM (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/overview", response_model=CustomerPortalOverview, summary="Customer portal home overview")
async def get_overview(
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_portal_overview(customer.lead_id, customer.organization_id)


@router.get("/deal", response_model=CustomerPortalDeal, summary="Get current active deal room")
async def get_active_deal_room(
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_deal_room(customer.lead_id, customer.organization_id)


@router.get("/deals/{deal_id}", response_model=CustomerPortalDeal, summary="Get specific deal room by deal ID")
async def get_deal_room_by_id(
    deal_id: str,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_deal_room(customer.lead_id, customer.organization_id, deal_id=deal_id)


# ═══════════════════════════════════════════════════════════════════════════
# 3. DOCUMENTS (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/documents", response_model=List[CustomerPortalDocument], summary="Get requested transaction documents")
async def list_documents(
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_documents(customer.lead_id, customer.organization_id)


@router.post("/documents/{document_id}/upload", response_model=CustomerPortalDocument, summary="Upload document for review")
async def upload_document(
    document_id: str,
    req: CustomerDocumentUploadRequest,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.upload_document(customer.lead_id, customer.organization_id, document_id, req)


# ═══════════════════════════════════════════════════════════════════════════
# 4. PAYMENTS & PROOF SUBMISSION (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/payments", response_model=CustomerPortalPaymentSchedule, summary="Get payment schedule & milestones")
async def get_payments(
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_payments(customer.lead_id, customer.organization_id)


@router.post("/payments/proof", status_code=status.HTTP_201_CREATED, summary="Submit payment confirmation proof")
async def submit_payment_proof(
    req: CustomerPaymentProofSubmitRequest,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    proof = await svc.submit_payment_proof(customer.lead_id, customer.organization_id, req)
    return {
        "status": proof.status,
        "proof_id": str(proof.id),
        "milestone_index": proof.milestone_index,
        "amount_reported": float(proof.amount_reported),
        "message": "Payment proof submitted. Our finance team will review and verify it."
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. APPOINTMENTS & VIEWINGS (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/appointments", response_model=List[CustomerPortalAppointment], summary="Get customer appointments & site visits")
async def list_appointments(
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_appointments(customer.lead_id, customer.organization_id)


@router.post("/appointments/{appointment_id}/confirm", summary="Customer confirms attendance for appointment")
async def confirm_appointment(
    appointment_id: str,
    req: Optional[CustomerAppointmentConfirmRequest] = None,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.confirm_appointment(customer.lead_id, customer.organization_id, appointment_id)


# ═══════════════════════════════════════════════════════════════════════════
# 6. MESSAGING (Strict CRM Confidentiality Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/messages", response_model=List[CustomerPortalMessage], summary="Get customer-visible messages")
async def list_messages(
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.get_messages(customer.lead_id, customer.organization_id)


@router.post("/messages", response_model=CustomerPortalMessage, status_code=status.HTTP_201_CREATED, summary="Send message to advisor")
async def send_message(
    req: CustomerSendMessageRequest,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.send_message(customer.lead_id, customer.organization_id, req)


# ═══════════════════════════════════════════════════════════════════════════
# 7. SUPPORT REQUESTS (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/support", response_model=CustomerSupportRequestResponse, status_code=status.HTTP_201_CREATED, summary="Create support query")
async def create_support_ticket(
    req: CustomerSupportRequestCreate,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.create_support_request(customer.lead_id, customer.organization_id, req)


# ═══════════════════════════════════════════════════════════════════════════
# 8. POST-SALE & ACKNOWLEDGEMENTS (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/post-sale/feedback", response_model=CustomerPostSaleFeedbackResponse, summary="Submit CSAT & NPS feedback")
async def submit_feedback(
    req: CustomerPostSaleFeedbackRequest,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.submit_post_sale_feedback(customer.lead_id, customer.organization_id, req)


@router.post("/acknowledgements", summary="Record customer milestone acknowledgement")
async def acknowledge_terms(
    req: CustomerAcknowledgementRequest,
    request: Request,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await svc.record_acknowledgement(customer.lead_id, customer.organization_id, req, ip=client_ip, ua=user_agent)


# ═══════════════════════════════════════════════════════════════════════════
# 9. GOVERNED CUSTOMER AI ASSISTANT (Customer Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/ai/query", response_model=CustomerAIQueryResponse, summary="Grounded customer assistant query")
async def customer_ai_query(
    req: CustomerAIQueryRequest,
    customer: PortalCustomerContext = Depends(get_current_portal_customer),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.query_customer_ai(customer.lead_id, customer.organization_id, req.query)


# ═══════════════════════════════════════════════════════════════════════════
# 10. BROKER-FACING ADMIN ENDPOINTS (Broker Guarded)
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/admin/invites", response_model=PortalInviteResponse, status_code=status.HTTP_201_CREATED, summary="Broker generates portal invite")
async def broker_generate_invite(
    req: PortalInviteGenerateRequest,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.generate_portal_invite(broker, req.lead_id, deal_id=req.deal_id, expires_in_days=req.expires_in_days)


@router.post("/admin/documents/{document_id}/review", summary="Broker reviews customer document")
async def broker_review_document(
    document_id: str,
    decision: DocumentReviewDecision,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.review_document(broker, document_id, decision.action, rejection_reason=decision.rejection_reason)


@router.post("/admin/payments/proofs/{proof_id}/review", summary="Broker reviews customer payment proof")
async def broker_review_payment_proof(
    proof_id: str,
    decision: PaymentProofReviewDecision,
    broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    svc = CustomerPortalService(db)
    return await svc.review_payment_proof(broker, proof_id, decision.action, review_notes=decision.review_notes, rejection_reason=decision.rejection_reason)
