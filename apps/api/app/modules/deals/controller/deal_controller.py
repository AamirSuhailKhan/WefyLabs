"""
Part 18 — Real Estate Deal, Booking & Transaction OS Controller
================================================================
FastAPI router mounted under /api/v1/deals.
Provides complete endpoints for:
  - Canonical Deals management & filtering
  - Stage advance with deterministic validation
  - Structured Negotiation & Offer history
  - Unit Reservation with distributed locking & expiry
  - Booking confirmation gated by human approval
  - Commission ledger with splits & deductions
  - Legal Closing, Title Transfer & Key Handover
  - Post-Sale NPS, Referrals & AI Revenue Learning
  - Deal Documents & Verification
  - Commercial Audit Log
"""
from __future__ import annotations

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.deal_models import DealCommercialAuditLog
from app.modules.deals.services.deal_service import DealService, DealServiceError
from app.modules.deals.dto.deal_schemas import (
    DealCreateRequest, DealStageAdvanceRequest, DealSummaryResponse,
    DealDetailResponse, OfferSubmitRequest, OfferResponseRequest,
    ReservationCreateRequest, BookingConfirmRequest, BookingApproveRequest,
    CommissionRecordRequest, ClosingCreateRequest, PostSaleRecordRequest,
    DocumentUploadRequest, DealPipelineSummary, CommercialAuditLogEntry
)

router = APIRouter(prefix="/deals", tags=["Deal, Booking & Transaction OS"])


def _to_summary_dict(d, lead_map=None, prop_map=None) -> Dict[str, Any]:
    lead = lead_map.get(d.lead_id) if lead_map else None
    prop = prop_map.get(d.property_id) if prop_map and d.property_id else None

    return {
        "id": str(d.id),
        "organization_id": str(d.organization_id),
        "broker_id": str(d.broker_id),
        "lead_id": str(d.lead_id),
        "lead_name": lead.name if lead else None,
        "lead_phone": lead.phone if lead else None,
        "property_id": str(d.property_id) if d.property_id else None,
        "property_title": prop.title if prop else None,
        "deal_reference": d.deal_reference,
        "deal_title": d.deal_title,
        "current_stage": d.current_stage,
        "previous_stage": d.previous_stage,
        "status": d.status,
        "agreed_price": float(d.agreed_price) if d.agreed_price is not None else None,
        "offer_price": float(d.offer_price) if d.offer_price is not None else None,
        "final_transaction_price": float(d.final_transaction_price) if d.final_transaction_price is not None else None,
        "currency": d.currency,
        "commission_percentage": float(d.commission_percentage) if d.commission_percentage is not None else None,
        "commission_amount": float(d.commission_amount) if d.commission_amount is not None else None,
        "closing_probability_pct": float(d.closing_probability_pct),
        "risk_level": d.risk_level,
        "has_offer": bool(d.__dict__.get("offer") is not None),
        "has_reservation": bool(d.__dict__.get("reservation") is not None),
        "has_booking": bool(d.__dict__.get("booking") is not None),
        "has_commission": bool(d.__dict__.get("commission_record") is not None),
        "has_closing": bool(d.__dict__.get("closing_record") is not None),
        "tags": d.tags or [],
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pipeline Summary & Metrics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=DealPipelineSummary)
async def get_deals_summary(
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Retrieve multi-stage pipeline metrics strictly scoped to authenticated tenant."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    summary = await service.get_pipeline_summary(str(broker.id), org_id)
    return DealPipelineSummary(**summary)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Deals List & Create
# ─────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[DealSummaryResponse])
async def list_deals(
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """List deals across all stages with tenant isolation and optional stage/status filter."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    deals, _ = await service.list_deals(
        broker_id=str(broker.id),
        organization_id=org_id,
        stage=stage,
        status=status,
        limit=limit,
        offset=offset
    )

    # Pre-fetch leads and properties for display titles
    lead_ids = {d.lead_id for d in deals if d.lead_id}
    prop_ids = {d.property_id for d in deals if d.property_id}

    lead_map = {}
    if lead_ids:
        l_res = await db.execute(select(Lead).where(Lead.id.in_(lead_ids)))
        lead_map = {l.id: l for l in l_res.scalars().all()}

    prop_map = {}
    if prop_ids:
        p_res = await db.execute(select(PropertyListing).where(PropertyListing.id.in_(prop_ids)))
        prop_map = {p.id: p for p in p_res.scalars().all()}

    return [_to_summary_dict(d, lead_map, prop_map) for d in deals]


@router.post("", response_model=DealSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_deal(
    payload: DealCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Create a new canonical deal within the authenticated organization."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        deal = await service.create_deal(
            lead_id=payload.lead_id,
            deal_title=payload.deal_title,
            broker_id=str(broker.id),
            organization_id=org_id,
            property_id=payload.property_id,
            current_stage=payload.current_stage,
            agreed_price=payload.agreed_price,
            currency=payload.currency,
            commission_percentage=payload.commission_percentage,
            tags=payload.tags,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
        )
        return _to_summary_dict(deal)
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Deal Detail & Stage Advance
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{deal_id}", response_model=DealDetailResponse)
async def get_deal(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Fetch complete deal workspace including stage history, offers, reservation, booking, commission, closing, documents."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        deal = await service.get_deal(deal_id, org_id)
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    base_summary = _to_summary_dict(deal)

    # Stage history
    stage_hist = [
        {
            "id": str(h.id),
            "from_stage": h.from_stage,
            "to_stage": h.to_stage,
            "transitioned_at": h.transitioned_at.isoformat(),
            "transitioned_by_id": h.transitioned_by_id,
            "transitioned_by_type": h.transitioned_by_type,
            "reason": h.reason,
            "duration_hours": h.duration_hours_in_previous_stage,
        }
        for h in (deal.stage_history or [])
    ]

    # Sub-entities serialization
    offer_data = None
    if deal.offer:
        o = deal.offer
        offer_data = {
            "id": str(o.id),
            "offer_price": float(o.offer_price),
            "currency": o.currency,
            "listing_price": float(o.listing_price) if o.listing_price else None,
            "discount_amount": float(o.discount_amount) if o.discount_amount else None,
            "payment_plan": o.payment_plan,
            "token_amount": float(o.token_amount) if o.token_amount else None,
            "status": o.status,
            "version": o.version,
            "offer_history": o.offer_history or [],
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
            "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
            "counter_offer_price": float(o.counter_offer_price) if o.counter_offer_price else None,
        }

    res_data = None
    if deal.reservation:
        r = deal.reservation
        res_data = {
            "id": str(r.id),
            "reservation_amount": float(r.reservation_amount) if r.reservation_amount else None,
            "currency": r.currency,
            "reserved_price": float(r.reserved_price) if r.reserved_price else None,
            "reserved_at": r.reserved_at.isoformat(),
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "status": r.status,
            "customer_name": r.customer_name,
            "customer_phone": r.customer_phone,
        }

    bk_data = None
    if deal.booking:
        b = deal.booking
        bk_data = {
            "id": str(b.id),
            "booking_reference": b.booking_reference,
            "booked_price": float(b.booked_price),
            "currency": b.currency,
            "token_amount": float(b.token_amount) if b.token_amount else None,
            "token_paid_at": b.token_paid_at.isoformat() if b.token_paid_at else None,
            "status": b.status,
            "booked_at": b.booked_at.isoformat() if b.booked_at else None,
            "payment_schedule": b.payment_schedule or [],
        }

    comm_data = None
    if deal.commission_record:
        c = deal.commission_record
        comm_data = {
            "id": str(c.id),
            "transaction_price": float(c.transaction_price),
            "currency": c.currency,
            "commission_percentage": float(c.commission_percentage),
            "gross_commission": float(c.gross_commission),
            "net_commission": float(c.net_commission) if c.net_commission else None,
            "commission_splits": c.commission_splits or [],
            "status": c.status,
            "invoice_reference": c.invoice_reference,
        }

    closing_data = None
    if deal.closing_record:
        cl = deal.closing_record
        closing_data = {
            "id": str(cl.id),
            "status": cl.status,
            "registration_authority": cl.registration_authority,
            "registration_number": cl.registration_number,
            "title_deed_number": cl.title_deed_number,
            "handover_date": cl.handover_date.isoformat() if cl.handover_date else None,
            "closing_checklist": cl.closing_checklist or [],
        }

    post_sale_data = None
    if deal.post_sale_record:
        ps = deal.post_sale_record
        post_sale_data = {
            "id": str(ps.id),
            "customer_satisfaction_score": ps.customer_satisfaction_score,
            "nps_score": ps.nps_score,
            "feedback_text": ps.feedback_text,
            "referral_given": ps.referral_given,
            "days_to_close": ps.days_to_close,
        }

    docs_data = [
        {
            "id": str(doc.id),
            "document_type": doc.document_type,
            "document_name": doc.document_name,
            "required_at_stage": doc.required_at_stage,
            "status": doc.status,
            "is_required": doc.is_required,
            "file_url": doc.file_url,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        }
        for doc in (deal.documents or [])
    ]

    approvals_data = [
        {
            "id": str(apr.id),
            "action_type": apr.action_type,
            "status": apr.status,
            "reason": apr.reason,
            "created_at": apr.created_at.isoformat(),
        }
        for apr in (deal.approval_requests or [])
    ]

    return DealDetailResponse(
        **base_summary,
        notes=deal.notes,
        risk_factors=deal.risk_factors or [],
        stage_history=stage_hist,
        offer=offer_data,
        reservation=res_data,
        booking=bk_data,
        commission=comm_data,
        closing=closing_data,
        post_sale=post_sale_data,
        documents=docs_data,
        pending_approvals=approvals_data,
        commercial_audit=[],
        ai_recommendations=["Verify KYC documents before advance", "Ensure deposit cheque received prior to title transfer"]
    )


@router.post("/{deal_id}/stage", response_model=DealSummaryResponse)
async def advance_stage(
    deal_id: str,
    payload: DealStageAdvanceRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Advance deal stage under strict state machine rules and outbox event logging."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        deal = await service.advance_stage(
            deal_id=deal_id,
            target_stage=payload.target_stage,
            organization_id=org_id,
            actor_id=str(broker.id),
            actor_type="HUMAN",
            reason=payload.reason
        )
        return _to_summary_dict(deal)
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Offers & Negotiation
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/offers", status_code=status.HTTP_201_CREATED)
async def submit_offer(
    deal_id: str,
    payload: OfferSubmitRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Submit a formal commercial offer, archiving prior versions to preserve negotiation history."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        offer = await service.submit_offer(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            offer_price=payload.offer_price,
            currency=payload.currency,
            listing_price=payload.listing_price,
            payment_plan=payload.payment_plan,
            token_amount=payload.token_amount,
            valid_until=payload.valid_until,
            possession_date_requested=payload.possession_date_requested,
            special_conditions=payload.special_conditions
        )
        return {"status": "success", "offer_id": str(offer.id), "version": offer.version, "offer_status": offer.status}
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{deal_id}/offers/respond")
async def respond_to_offer(
    deal_id: str,
    payload: OfferResponseRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Accept, reject, or counter an existing commercial offer."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        offer = await service.respond_to_offer(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            action=payload.action,
            counter_offer_price=payload.counter_offer_price,
            rejection_reason=payload.rejection_reason
        )
        return {"status": "success", "offer_id": str(offer.id), "offer_status": offer.status}
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 5. Unit Reservations
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/reservations", status_code=status.HTTP_201_CREATED)
async def create_reservation(
    deal_id: str,
    payload: ReservationCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Reserve property unit with TTL hold and race-condition prevention."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        reservation = await service.create_reservation(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            reservation_amount=payload.reservation_amount,
            currency=payload.currency,
            reserved_price=payload.reserved_price,
            expires_at=payload.expires_at,
            reservation_form_url=payload.reservation_form_url,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            customer_email=payload.customer_email,
            reservation_notes=payload.reservation_notes
        )
        return {
            "status": "success",
            "reservation_id": str(reservation.id),
            "expires_at": reservation.expires_at.isoformat() if reservation.expires_at else None
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bookings (Human-in-the-loop Gate)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/bookings/request", status_code=status.HTTP_201_CREATED)
async def request_booking_approval(
    deal_id: str,
    payload: BookingConfirmRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Step 1: Create an approval request for booking confirmation to enforce human gating."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        approval = await service.request_booking_approval(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            booked_price=payload.booked_price,
            currency=payload.currency,
            token_amount=payload.token_amount,
            payment_plan_type=payload.payment_plan_type,
            idempotency_key=payload.idempotency_key
        )
        return {
            "status": "PENDING_APPROVAL",
            "approval_id": str(approval.id),
            "message": "Booking requires authorized human sign-off before confirmation."
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{deal_id}/bookings/confirm", status_code=status.HTTP_201_CREATED)
async def approve_and_confirm_booking(
    deal_id: str,
    payload: BookingApproveRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Step 2: Sign off and confirm booking, generating booking reference & outbox event."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        booking = await service.approve_and_confirm_booking(
            deal_id=deal_id,
            organization_id=org_id,
            reviewer_id=str(broker.id),
            approval_id=payload.approval_id,
            review_notes=payload.review_notes
        )
        return {
            "status": "success",
            "booking_reference": booking.booking_reference,
            "booked_price": float(booking.booked_price),
            "booking_status": booking.status
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 7. Commission Ledger
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/commissions", status_code=status.HTTP_201_CREATED)
async def record_commission(
    deal_id: str,
    payload: CommissionRecordRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Record commission economics, splits, and payable ledger with high decimal precision."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        comm = await service.record_commission(
            deal_id=deal_id,
            organization_id=org_id,
            broker_id=str(broker.id),
            actor_id=str(broker.id),
            transaction_price=payload.transaction_price,
            currency=payload.currency,
            commission_percentage=payload.commission_percentage,
            tax_deducted=payload.tax_deducted,
            commission_splits=payload.commission_splits,
            invoice_reference=payload.invoice_reference,
            idempotency_key=payload.idempotency_key
        )
        return {
            "status": "success",
            "commission_id": str(comm.id),
            "gross_commission": float(comm.gross_commission),
            "net_commission": float(comm.net_commission) if comm.net_commission else None
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 8. Closing & Handover
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/closings", status_code=status.HTTP_201_CREATED)
async def create_closing(
    deal_id: str,
    payload: ClosingCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Initiate closing workflow with default statutory checklist and registration tracking."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        closing = await service.create_closing(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            registration_authority=payload.registration_authority,
            registration_number=payload.registration_number,
            registration_date=payload.registration_date,
            title_deed_number=payload.title_deed_number,
            handover_date=payload.handover_date
        )
        return {
            "status": "success",
            "closing_id": str(closing.id),
            "closing_status": closing.status
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{deal_id}/closings/complete")
async def complete_closing(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Mark closing complete and set deal to CLOSED_WON."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        deal = await service.complete_closing(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id)
        )
        return {
            "status": "success",
            "deal_id": str(deal.id),
            "deal_status": deal.status,
            "closed_at": deal.closed_at.isoformat() if deal.closed_at else None
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 9. Post-Sale & Revenue Learning
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/post-sale", status_code=status.HTTP_201_CREATED)
async def record_post_sale(
    deal_id: str,
    payload: PostSaleRecordRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Record post-sale satisfaction, NPS, referral leads, and AI revenue learning signals."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        ps = await service.record_post_sale(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            customer_satisfaction_score=payload.customer_satisfaction_score,
            nps_score=payload.nps_score,
            feedback_text=payload.feedback_text,
            referral_given=payload.referral_given,
            success_factors=payload.success_factors,
            obstacle_factors=payload.obstacle_factors,
            ai_recommendation_followed=payload.ai_recommendation_followed
        )
        return {
            "status": "success",
            "post_sale_id": str(ps.id),
            "days_to_close": ps.days_to_close
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Documents & Audit Log
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{deal_id}/documents", status_code=status.HTTP_201_CREATED)
async def add_deal_document(
    deal_id: str,
    payload: DocumentUploadRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Attach required statutory deal document with stage gating."""
    org_id = str(broker.organization_id or broker.id)
    service = DealService(db)
    try:
        doc = await service.add_document(
            deal_id=deal_id,
            organization_id=org_id,
            actor_id=str(broker.id),
            document_type=payload.document_type,
            document_name=payload.document_name,
            required_at_stage=payload.required_at_stage,
            file_url=payload.file_url,
            is_required=payload.is_required
        )
        return {
            "status": "success",
            "document_id": str(doc.id),
            "document_status": doc.status
        }
    except DealServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{deal_id}/audit", response_model=List[CommercialAuditLogEntry])
async def get_commercial_audit_log(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Immutable audit trail of all commercial operations on this deal."""
    org_id = str(broker.organization_id or broker.id)
    stmt = select(DealCommercialAuditLog).where(
        DealCommercialAuditLog.deal_id == uuid.UUID(deal_id),
        DealCommercialAuditLog.organization_id == uuid.UUID(org_id)
    ).order_by(desc(DealCommercialAuditLog.created_at))
    res = await db.execute(stmt)
    entries = res.scalars().all()
    return [
        CommercialAuditLogEntry(
            id=str(e.id),
            event_type=e.event_type,
            actor_id=e.actor_id,
            actor_type=e.actor_type,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            change_summary=e.change_summary,
            created_at=e.created_at
        )
        for e in entries
    ]
