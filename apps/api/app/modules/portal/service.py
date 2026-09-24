"""
Part 21 — Customer Portal, Digital Deal Room & Transaction Collaboration Service
=================================================================================
Business logic for secure customer-facing workflows with strict authorization,
data boundary sanitization, and audit trail enforcement.
"""
from __future__ import annotations

import hashlib
import os
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
import jwt
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.deal_models import (
    Deal, DealStage, DealOffer, DealReservation, DealBooking,
    DealCommission, DealClosing, DealPostSale, DealDocument
)
from app.models.calendar_models import SchedulingMeeting
from app.models.communication_models import UnifiedConversation, UnifiedMessage
from app.models.crm_models import Task, Activity
from app.models.property_models import PropertyListing
from app.models.portal_models import (
    CustomerPortalInvite, CustomerSupportRequest,
    CustomerPaymentProof, CustomerTransactionAcknowledgement
)
from app.modules.portal.dto.portal_schemas import (
    CustomerPortalOverview, CustomerAssignedAdvisor, CustomerActiveDealSummary,
    CustomerNextAction, CustomerPortalDeal, DealPropertySummary, DealStageStep,
    CustomerDealOfferSummary, CustomerDealReservationSummary, CustomerDealBookingSummary,
    CustomerDealClosingSummary, CustomerPortalDocument, CustomerDocumentUploadRequest,
    CustomerPortalPaymentSchedule, CustomerPortalPaymentMilestone,
    CustomerPaymentProofSubmitRequest, CustomerPortalAppointment,
    CustomerPortalMessage, CustomerSendMessageRequest, CustomerSupportRequestCreate,
    CustomerSupportRequestResponse, CustomerPostSaleFeedbackRequest,
    CustomerPostSaleFeedbackResponse, CustomerAcknowledgementRequest,
    CustomerAIQueryResponse, PortalInviteResponse, PortalAuthTokenResponse
)


def _hash_token(raw_token: str) -> str:
    """Computes SHA-256 hash of a raw token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class CustomerPortalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── 1. Authentication & Token Management ─────────────────────────────────

    async def generate_portal_invite(
        self,
        broker: Broker,
        lead_id: str,
        deal_id: Optional[str] = None,
        expires_in_days: int = 7
    ) -> PortalInviteResponse:
        """Broker generates a secure time-bound invitation for a customer."""
        lead_uuid = uuid.UUID(str(lead_id))
        stmt = select(Lead).where(Lead.id == lead_uuid, Lead.deleted_at.is_(None))
        lead = (await self.db.execute(stmt)).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")

        # Ensure broker has access to this lead
        org_id = broker.organization_id
        if str(lead.broker_id) != str(broker.id) and str(broker.id) != org_id:
            raise HTTPException(status_code=403, detail="Unauthorized to invite this lead.")

        # Generate secure random token
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=expires_in_days)

        invite = CustomerPortalInvite(
            organization_id=org_id,
            lead_id=lead.id,
            deal_id=uuid.UUID(str(deal_id)) if deal_id else None,
            invited_by_id=broker.id,
            token_hash=token_hash,
            status="active",
            expires_at=expires_at,
            customer_email=lead.email
        )
        self.db.add(invite)
        await self.db.commit()
        await self.db.refresh(invite)

        portal_url = f"/portal?token={raw_token}"
        return PortalInviteResponse(
            invite_id=str(invite.id),
            lead_id=str(lead.id),
            customer_email=lead.email,
            raw_token=raw_token,
            portal_access_url=portal_url,
            expires_at=expires_at
        )

    async def exchange_invite_token(self, raw_token: str) -> PortalAuthTokenResponse:
        """Exchanges raw invite token for a signed customer session JWT."""
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)

        stmt = select(CustomerPortalInvite).where(
            CustomerPortalInvite.token_hash == token_hash,
            CustomerPortalInvite.status == "active"
        )
        invite = (await self.db.execute(stmt)).scalars().first()
        if not invite:
            raise HTTPException(status_code=401, detail="Invalid or already used invite token.")

        if invite.expires_at < now:
            invite.status = "expired"
            await self.db.commit()
            raise HTTPException(status_code=401, detail="Invite token has expired.")

        # Load Lead
        lead_stmt = select(Lead).where(Lead.id == invite.lead_id, Lead.deleted_at.is_(None))
        lead = (await self.db.execute(lead_stmt)).scalars().first()
        if not lead:
            raise HTTPException(status_code=401, detail="Associated customer profile not found.")

        # Update invite usage
        invite.access_count += 1
        invite.last_accessed_at = now
        await self.db.commit()

        # Generate customer JWT
        jwt_payload = {
            "sub": str(lead.id),
            "lead_id": str(lead.id),
            "organization_id": invite.organization_id,
            "role": "portal_customer",
            "email": lead.email,
            "name": lead.name or "Client",
            "iat": now,
            "exp": now + timedelta(hours=24)
        }
        access_token = jwt.encode(jwt_payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

        return PortalAuthTokenResponse(
            access_token=access_token,
            customer_id=str(lead.id),
            customer_name=lead.name or "Client",
            customer_email=lead.email,
            customer_phone=lead.phone,
            organization_id=invite.organization_id
        )

    async def request_magic_link(self, email_or_phone: str) -> Dict[str, Any]:
        """Requests a magic link for an existing customer by email or phone."""
        clean_input = email_or_phone.strip().lower()
        stmt = select(Lead).where(
            or_(
                func.lower(Lead.email) == clean_input,
                Lead.phone == clean_input
            ),
            Lead.deleted_at.is_(None)
        )
        lead = (await self.db.execute(stmt)).scalars().first()
        
        # Always return generic message to prevent account enumeration
        if not lead:
            return {"status": "SENT", "message": "If an account matches this contact, a magic link has been generated."}

        broker_res = await self.db.execute(select(Broker).where(Broker.id == lead.broker_id))
        broker = broker_res.scalars().first()
        org_id = broker.organization_id if broker else str(lead.broker_id)

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=2)  # Magic links valid for 2 hours

        invite = CustomerPortalInvite(
            organization_id=org_id,
            lead_id=lead.id,
            invited_by_id=broker.id if broker else None,
            token_hash=token_hash,
            status="active",
            expires_at=expires_at,
            customer_email=lead.email
        )
        self.db.add(invite)
        await self.db.commit()

        # In dev/test return the token directly so automated tests can verify flow
        return {
            "status": "SENT",
            "message": "Magic link sent to your registered contact.",
            "dev_magic_token": raw_token if settings.ENV in ("development", "test", "testing") else None
        }

    # ─── 2. Customer Portal Overview ──────────────────────────────────────────

    async def get_portal_overview(self, lead_id: str, organization_id: str) -> CustomerPortalOverview:
        """Assembles customer portal home overview strictly sanitized for customer visibility."""
        lead_uuid = uuid.UUID(lead_id)
        lead = (await self.db.execute(select(Lead).where(Lead.id == lead_uuid))).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Customer not found.")

        # Load assigned broker
        broker = (await self.db.execute(select(Broker).where(Broker.id == lead.broker_id))).scalars().first()
        advisor = None
        if broker:
            advisor = CustomerAssignedAdvisor(
                name=broker.name,
                agency_name=broker.agency_name or "WefyLabs Realty",
                email=broker.email,
                phone=broker.phone or broker.whatsapp_number
            )

        # Load active deal
        deal_stmt = select(Deal).where(
            Deal.lead_id == lead_uuid,
            Deal.status == "ACTIVE",
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal = (await self.db.execute(deal_stmt)).scalars().first()

        active_deal_summary = None
        pending_docs_count = 0
        due_payments_count = 0
        next_action_type = "NONE"
        next_action_title = "All Caught Up"
        next_action_desc = "Your advisor is reviewing your file. We will notify you when action is required."
        target_id = None

        if deal:
            stage_map = {
                "opportunity": "Property Selected",
                "negotiation": "In Negotiation",
                "offer": "Offer Under Review",
                "reservation": "Unit Reserved",
                "booking": "Booking Confirmed",
                "transaction": "Transaction Processing",
                "commission": "Documentation Complete",
                "closing": "Legal Closing & Registration",
                "post_sale": "Keys Handed Over"
            }
            active_deal_summary = CustomerActiveDealSummary(
                deal_id=str(deal.id),
                deal_reference=deal.deal_reference,
                deal_title=deal.deal_title,
                current_stage=deal.current_stage,
                stage_display_name=stage_map.get(deal.current_stage, deal.current_stage.title()),
                agreed_price=deal.agreed_price,
                currency=deal.currency,
                status=deal.status,
                booked_at=deal.booking.booked_at if deal.booking else None
            )

            # Check documents
            doc_stmt = select(DealDocument).where(
                DealDocument.deal_id == deal.id,
                DealDocument.status.in_(["REQUIRED", "REJECTED"])
            )
            pending_docs = (await self.db.execute(doc_stmt)).scalars().all()
            pending_docs_count = len(pending_docs)
            if pending_docs:
                first_doc = pending_docs[0]
                next_action_type = "UPLOAD_DOCUMENT"
                next_action_title = f"Upload Required Document: {first_doc.document_name}"
                next_action_desc = "Please submit the requested verification document to advance your transaction."
                target_id = str(first_doc.id)

            # Check payments
            if deal.booking and deal.booking.payment_schedule:
                for item in deal.booking.payment_schedule:
                    if isinstance(item, dict) and item.get("status") in ("DUE", "OVERDUE"):
                        due_payments_count += 1
                        if next_action_type == "NONE":
                            next_action_type = "PAY_MILESTONE"
                            next_action_title = f"Payment Milestone Due: {item.get('name', 'Installment')}"
                            next_action_desc = f"Amount due: {deal.currency} {item.get('amount', 0)}"

            # If closed / post-sale
            if deal.current_stage == "post_sale" and not (deal.post_sale_record and deal.post_sale_record.nps_score):
                if next_action_type == "NONE":
                    next_action_type = "COMPLETE_NPS"
                    next_action_title = "Share Your Experience"
                    next_action_desc = "Rate your transaction experience and help us serve you better."

        # Check upcoming appointments
        now = datetime.now(timezone.utc)
        mtg_stmt = select(func.count(SchedulingMeeting.id)).where(
            SchedulingMeeting.lead_id == lead_uuid,
            SchedulingMeeting.start_utc >= now,
            SchedulingMeeting.status.in_(["CONFIRMED", "REQUESTED"])
        )
        mtg_count = (await self.db.execute(mtg_stmt)).scalar() or 0

        # Check unread messages
        conv_stmt = select(UnifiedConversation).where(UnifiedConversation.lead_id == lead_uuid)
        conv = (await self.db.execute(conv_stmt)).scalars().first()
        unread_count = conv.unread_count if conv else 0

        return CustomerPortalOverview(
            customer_name=lead.name or "Client",
            customer_email=lead.email,
            customer_phone=lead.phone,
            assigned_advisor=advisor,
            active_deal=active_deal_summary,
            next_action=CustomerNextAction(
                action_type=next_action_type,
                title=next_action_title,
                description=next_action_desc,
                target_id=target_id,
                is_urgent=pending_docs_count > 0 or due_payments_count > 0
            ),
            upcoming_appointment_count=mtg_count,
            pending_documents_count=pending_docs_count,
            due_payments_count=due_payments_count,
            unread_messages_count=unread_count
        )

    # ─── 3. Digital Deal Room ─────────────────────────────────────────────────

    async def get_deal_room(
        self,
        lead_id: str,
        organization_id: str,
        deal_id: Optional[str] = None
    ) -> CustomerPortalDeal:
        """Fetches complete customer-safe Digital Deal Room for the active transaction."""
        lead_uuid = uuid.UUID(lead_id)

        if deal_id:
            deal_uuid = uuid.UUID(deal_id)
            stmt = select(Deal).where(
                Deal.id == deal_uuid,
                Deal.lead_id == lead_uuid,
                Deal.deleted_at.is_(None)
            )
        else:
            stmt = select(Deal).where(
                Deal.lead_id == lead_uuid,
                Deal.status == "ACTIVE",
                Deal.deleted_at.is_(None)
            ).order_by(desc(Deal.created_at))

        deal = (await self.db.execute(stmt)).scalars().first()
        if not deal:
            raise HTTPException(status_code=404, detail="No active deal room found for this customer.")

        # Property Projection
        prop_summary = None
        if deal.property_listing:
            pl = deal.property_listing
            prop_summary = DealPropertySummary(
                property_id=str(pl.id),
                project_name=pl.title,
                unit_number=None,
                bhk=f"{pl.bedrooms} BHK" if pl.bedrooms else pl.property_type,
                area_sqft=float(pl.area_sqft) if pl.area_sqft else None,
                price=deal.agreed_price or pl.price,
                currency=deal.currency,
                address=pl.address,
                city=pl.city,
                features=pl.features or [],
                image_urls=[m.media_url for m in pl.media] if pl.media else []
            )

        # Stage Stepper (9 canonical stages)
        stage_names = [
            ("opportunity", "Property Selection"),
            ("negotiation", "Terms Negotiation"),
            ("offer", "Offer & Acceptance"),
            ("reservation", "Unit Reservation"),
            ("booking", "Booking Confirmation"),
            ("transaction", "Transaction Processing"),
            ("commission", "Documentation Finalized"),
            ("closing", "Title Deed & Registration"),
            ("post_sale", "Handover & Move-In")
        ]
        current_idx = DealStage.ORDERED.index(deal.current_stage) if deal.current_stage in DealStage.ORDERED else 0
        stages_timeline = []
        for idx, (s_key, s_name) in enumerate(stage_names):
            stages_timeline.append(
                DealStageStep(
                    stage_key=s_key,
                    stage_name=s_name,
                    order_index=idx,
                    is_current=(idx == current_idx),
                    is_completed=(idx < current_idx),
                    completed_at=deal.stage_entered_at if idx <= current_idx else None
                )
            )

        # Offer Projection
        offer_summary = None
        if deal.offer:
            offer_summary = CustomerDealOfferSummary(
                offer_price=deal.offer.offer_price,
                currency=deal.offer.currency,
                listing_price=deal.offer.listing_price,
                status=deal.offer.status,
                valid_until=deal.offer.valid_until,
                accepted_at=deal.offer.accepted_at
            )

        # Reservation Projection
        res_summary = None
        if deal.reservation:
            res_summary = CustomerDealReservationSummary(
                reservation_amount=deal.reservation.reservation_amount,
                currency=deal.reservation.currency,
                reserved_price=deal.reservation.reserved_price,
                reserved_at=deal.reservation.reserved_at,
                expires_at=deal.reservation.expires_at,
                status=deal.reservation.status
            )

        # Booking Projection
        booking_summary = None
        if deal.booking:
            booking_summary = CustomerDealBookingSummary(
                booking_reference=deal.booking.booking_reference,
                token_amount=deal.booking.token_amount,
                token_paid_at=deal.booking.token_paid_at,
                booked_price=deal.booking.booked_price,
                currency=deal.booking.currency,
                payment_plan_type=deal.booking.payment_plan_type,
                status=deal.booking.status,
                booked_at=deal.booking.booked_at
            )

        # Closing Projection
        closing_summary = None
        if deal.closing_record:
            closing_summary = CustomerDealClosingSummary(
                registration_authority=deal.closing_record.registration_authority,
                registration_number=deal.closing_record.registration_number,
                title_deed_number=deal.closing_record.title_deed_number,
                title_deed_issued_at=deal.closing_record.title_deed_issued_at,
                handover_date=deal.closing_record.handover_date,
                keys_handed_at=deal.closing_record.keys_handed_at,
                status=deal.closing_record.status
            )

        # Check acknowledgement
        ack_res = await self.db.execute(
            select(CustomerTransactionAcknowledgement).where(
                CustomerTransactionAcknowledgement.deal_id == deal.id,
                CustomerTransactionAcknowledgement.lead_id == lead_uuid
            )
        )
        is_ack = ack_res.scalars().first() is not None

        return CustomerPortalDeal(
            deal_id=str(deal.id),
            deal_reference=deal.deal_reference,
            deal_title=deal.deal_title,
            current_stage=deal.current_stage,
            stage_display_name=dict(stage_names).get(deal.current_stage, deal.current_stage),
            currency=deal.currency,
            agreed_price=deal.agreed_price,
            status=deal.status,
            property=prop_summary,
            stages_timeline=stages_timeline,
            offer=offer_summary,
            reservation=res_summary,
            booking=booking_summary,
            closing=closing_summary,
            is_acknowledged=is_ack
        )

    # ─── 4. Document Request & Upload Engine ──────────────────────────────────

    async def get_documents(self, lead_id: str, organization_id: str) -> List[CustomerPortalDocument]:
        """Fetches document requests for the customer with customer-safe status mapping."""
        lead_uuid = uuid.UUID(lead_id)
        deal_stmt = select(Deal.id).where(
            Deal.lead_id == lead_uuid,
            Deal.status == "ACTIVE",
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal_id = (await self.db.execute(deal_stmt)).scalar()
        if not deal_id:
            return []

        doc_stmt = select(DealDocument).where(DealDocument.deal_id == deal_id).order_by(DealDocument.created_at)
        docs = (await self.db.execute(doc_stmt)).scalars().all()

        results = []
        for d in docs:
            # Map internal status -> customer-safe status
            if d.status == "VERIFIED":
                c_status = "APPROVED"
            elif d.status == "UPLOADED":
                c_status = "IN_REVIEW"
            else:
                c_status = "ACTION_REQUIRED"

            results.append(
                CustomerPortalDocument(
                    document_id=str(d.id),
                    document_type=d.document_type,
                    document_name=d.document_name,
                    required_at_stage=d.required_at_stage,
                    is_required=d.is_required,
                    customer_status=c_status,
                    file_url=d.file_url,
                    uploaded_at=d.uploaded_at,
                    verified_at=d.verified_at,
                    rejection_reason=d.rejection_reason if d.status == "REJECTED" else None
                )
            )
        return results

    async def upload_document(
        self,
        lead_id: str,
        organization_id: str,
        document_id: str,
        upload_data: CustomerDocumentUploadRequest
    ) -> CustomerPortalDocument:
        """Customer uploads a requested document."""
        lead_uuid = uuid.UUID(lead_id)
        doc_uuid = uuid.UUID(document_id)

        # Validate document belongs to customer's deal
        stmt = select(DealDocument).join(Deal, DealDocument.deal_id == Deal.id).where(
            DealDocument.id == doc_uuid,
            Deal.lead_id == lead_uuid,
            Deal.deleted_at.is_(None)
        )
        doc = (await self.db.execute(stmt)).scalars().first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document request not found or unauthorized.")

        now = datetime.now(timezone.utc)
        doc.file_url = upload_data.file_url
        if upload_data.document_name:
            doc.document_name = upload_data.document_name
        doc.status = "UPLOADED"
        doc.uploaded_at = now
        doc.uploaded_by_id = lead_id
        doc.rejection_reason = None  # clear prior rejection on replacement

        await self.db.commit()
        await self.db.refresh(doc)

        return CustomerPortalDocument(
            document_id=str(doc.id),
            document_type=doc.document_type,
            document_name=doc.document_name,
            required_at_stage=doc.required_at_stage,
            is_required=doc.is_required,
            customer_status="IN_REVIEW",
            file_url=doc.file_url,
            uploaded_at=doc.uploaded_at,
            verified_at=None,
            rejection_reason=None
        )

    # ─── 5. Payment Schedule & Proof Upload ───────────────────────────────────

    async def get_payments(self, lead_id: str, organization_id: str) -> CustomerPortalPaymentSchedule:
        """Fetches payment schedule and proof statuses. Razorpay is strictly MOCK."""
        lead_uuid = uuid.UUID(lead_id)
        deal_stmt = select(Deal).where(
            Deal.lead_id == lead_uuid,
            Deal.status == "ACTIVE",
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal = (await self.db.execute(deal_stmt)).scalars().first()

        if not deal:
            return CustomerPortalPaymentSchedule(
                deal_id="",
                currency="AED",
                total_payable=Decimal("0.00"),
                total_verified=Decimal("0.00"),
                remaining_balance=Decimal("0.00"),
                milestones=[],
                payment_instructions="No active transaction payment schedule found.",
                is_live_gateway_enabled=False
            )

        # Load proofs
        proofs_stmt = select(CustomerPaymentProof).where(CustomerPaymentProof.deal_id == deal.id)
        proofs = (await self.db.execute(proofs_stmt)).scalars().all()
        proof_by_index = {p.milestone_index: p for p in proofs}

        schedule_items = []
        raw_schedule = deal.booking.payment_schedule if (deal.booking and deal.booking.payment_schedule) else []

        total_payable = Decimal("0.00")
        total_verified = Decimal("0.00")

        # If booking exists with price but no granular schedule, create canonical initial milestones
        if not raw_schedule and deal.agreed_price:
            raw_schedule = [
                {"name": "Booking Deposit (10%)", "amount": float(deal.agreed_price * Decimal("0.10")), "status": "VERIFIED"},
                {"name": "Construction Milestone 1 (20%)", "amount": float(deal.agreed_price * Decimal("0.20")), "status": "DUE"},
                {"name": "Handover Balance (70%)", "amount": float(deal.agreed_price * Decimal("0.70")), "status": "UPCOMING"}
            ]

        for idx, item in enumerate(raw_schedule):
            amt = Decimal(str(item.get("amount", 0)))
            total_payable += amt
            raw_status = item.get("status", "UPCOMING").upper()

            # Check if customer submitted proof
            proof = proof_by_index.get(idx)
            if proof:
                if proof.status == "VERIFIED":
                    raw_status = "VERIFIED"
                elif proof.status == "REPORTED" and raw_status != "VERIFIED":
                    raw_status = "REPORTED"

            if raw_status == "VERIFIED":
                total_verified += amt

            schedule_items.append(
                CustomerPortalPaymentMilestone(
                    index=idx,
                    name=item.get("name", f"Installment {idx + 1}"),
                    amount=amt,
                    status=raw_status,
                    payment_mode=proof.payment_mode if proof else None,
                    receipt_reference=proof.transaction_reference if proof else None,
                    verified_at=proof.reviewed_at if proof and proof.status == "VERIFIED" else None
                )
            )

        instructions = (
            "Payments must be executed via official wire transfer to the designated developer escrow account. "
            "Online card processing is in test sandbox mode only. Upload your wire confirmation receipt here for verification."
        )

        return CustomerPortalPaymentSchedule(
            deal_id=str(deal.id),
            currency=deal.currency,
            total_payable=total_payable,
            total_verified=total_verified,
            remaining_balance=max(Decimal("0.00"), total_payable - total_verified),
            milestones=schedule_items,
            payment_instructions=instructions,
            is_live_gateway_enabled=False
        )

    async def submit_payment_proof(
        self,
        lead_id: str,
        organization_id: str,
        req: CustomerPaymentProofSubmitRequest
    ) -> CustomerPaymentProof:
        """Customer submits payment proof. Never marks verified automatically."""
        lead_uuid = uuid.UUID(lead_id)
        deal_stmt = select(Deal).where(
            Deal.lead_id == lead_uuid,
            Deal.status == "ACTIVE",
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal = (await self.db.execute(deal_stmt)).scalars().first()
        if not deal:
            raise HTTPException(status_code=404, detail="No active deal found.")

        # Idempotency check
        if req.idempotency_key:
            existing = (await self.db.execute(
                select(CustomerPaymentProof).where(
                    CustomerPaymentProof.deal_id == deal.id,
                    CustomerPaymentProof.idempotency_key == req.idempotency_key
                )
            )).scalars().first()
            if existing:
                return existing

        proof = CustomerPaymentProof(
            organization_id=organization_id,
            deal_id=deal.id,
            lead_id=lead_uuid,
            milestone_index=req.milestone_index,
            milestone_name=f"Milestone {req.milestone_index + 1}",
            amount_reported=req.amount_reported,
            currency=req.currency,
            payment_mode=req.payment_mode,
            transaction_reference=req.transaction_reference,
            receipt_url=req.receipt_url,
            customer_notes=req.customer_notes,
            status="REPORTED",
            idempotency_key=req.idempotency_key
        )
        self.db.add(proof)
        await self.db.commit()
        await self.db.refresh(proof)
        return proof

    # ─── 6. Appointments & Site Visits ────────────────────────────────────────

    async def get_appointments(self, lead_id: str, organization_id: str) -> List[CustomerPortalAppointment]:
        """Fetches customer appointments and property viewings."""
        lead_uuid = uuid.UUID(lead_id)
        stmt = select(SchedulingMeeting).where(
            SchedulingMeeting.lead_id == lead_uuid,
            SchedulingMeeting.status != "CANCELLED"
        ).order_by(SchedulingMeeting.start_utc)
        meetings = (await self.db.execute(stmt)).scalars().all()

        results = []
        for m in meetings:
            results.append(
                CustomerPortalAppointment(
                    appointment_id=str(m.id),
                    title=m.title,
                    meeting_type=m.meeting_type,
                    start_utc=m.start_utc,
                    end_utc=m.end_utc,
                    duration_minutes=m.duration_minutes,
                    location=m.location_address,
                    meeting_url=m.meeting_url,
                    status=m.status
                )
            )
        return results

    async def confirm_appointment(self, lead_id: str, organization_id: str, appointment_id: str) -> Dict[str, Any]:
        """Customer confirms scheduled appointment."""
        lead_uuid = uuid.UUID(lead_id)
        stmt = select(SchedulingMeeting).where(
            SchedulingMeeting.id == appointment_id,
            SchedulingMeeting.lead_id == lead_uuid
        )
        meeting = (await self.db.execute(stmt)).scalars().first()
        if not meeting:
            raise HTTPException(status_code=404, detail="Appointment not found or unauthorized.")

        meeting.status = "CONFIRMED"
        await self.db.commit()
        return {"status": "CONFIRMED", "appointment_id": appointment_id}

    # ─── 7. Customer Messaging (Strict CRM Boundary) ──────────────────────────

    async def get_messages(self, lead_id: str, organization_id: str) -> List[CustomerPortalMessage]:
        """
        Fetches customer-visible messages.
        CRITICAL: channel != 'internal_note' strictly filtered to protect internal CRM comments.
        """
        lead_uuid = uuid.UUID(lead_id)
        stmt = select(UnifiedMessage).where(
            UnifiedMessage.lead_id == lead_uuid,
            UnifiedMessage.channel != "internal_note"  # Strict confidentiality boundary
        ).order_by(UnifiedMessage.created_at)
        messages = (await self.db.execute(stmt)).scalars().all()

        results = []
        for msg in messages:
            results.append(
                CustomerPortalMessage(
                    message_id=str(msg.id),
                    direction=msg.direction,
                    sender_name=msg.sender_name,
                    content=msg.content,
                    created_at=msg.created_at,
                    attachments=msg.attachments or []
                )
            )
        return results

    async def send_message(
        self,
        lead_id: str,
        organization_id: str,
        req: CustomerSendMessageRequest
    ) -> CustomerPortalMessage:
        """Customer sends message to advisor. Creates webchat inbound message."""
        lead_uuid = uuid.UUID(lead_id)
        lead = (await self.db.execute(select(Lead).where(Lead.id == lead_uuid))).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Customer not found.")

        # Find or create conversation
        conv = (await self.db.execute(
            select(UnifiedConversation).where(UnifiedConversation.lead_id == lead_uuid)
        )).scalars().first()

        now = datetime.now(timezone.utc)
        if not conv:
            conv = UnifiedConversation(
                lead_id=lead.id,
                broker_id=lead.broker_id,
                last_channel="webchat",
                last_message_content=req.content,
                last_message_at=now
            )
            self.db.add(conv)
            await self.db.flush()

        msg = UnifiedMessage(
            conversation_id=conv.id,
            lead_id=lead.id,
            broker_id=lead.broker_id,
            channel="webchat",
            direction="inbound",
            sender_name=lead.name or "Client",
            sender_identifier=lead.email or lead.phone or "portal",
            content=req.content,
            status="delivered",
            attachments=req.attachments or []
        )
        self.db.add(msg)
        conv.last_message_content = req.content
        conv.last_message_at = now
        conv.unread_count += 1

        await self.db.commit()
        await self.db.refresh(msg)

        return CustomerPortalMessage(
            message_id=str(msg.id),
            direction=msg.direction,
            sender_name=msg.sender_name,
            content=msg.content,
            created_at=msg.created_at,
            attachments=msg.attachments or []
        )

    # ─── 8. Customer Support Requests ─────────────────────────────────────────

    async def create_support_request(
        self,
        lead_id: str,
        organization_id: str,
        req: CustomerSupportRequestCreate
    ) -> CustomerSupportRequestResponse:
        """Customer creates a support ticket. Automatically spawns a CRM task for the broker."""
        lead_uuid = uuid.UUID(lead_id)
        lead = (await self.db.execute(select(Lead).where(Lead.id == lead_uuid))).scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Customer not found.")

        ticket = CustomerSupportRequest(
            organization_id=organization_id,
            lead_id=lead_uuid,
            category=req.category,
            subject=req.subject,
            description=req.description,
            priority=req.priority,
            assigned_broker_id=lead.broker_id,
            status="OPEN",
            attachment_urls=req.attachment_urls or []
        )
        self.db.add(ticket)
        await self.db.flush()

        # Create CRM Task for assigned broker
        task = Task(
            broker_id=lead.broker_id,
            lead_id=lead.id,
            organization_id=organization_id,
            title=f"[Portal Query: {req.category}] {req.subject}",
            description=req.description,
            priority=req.priority.lower(),
            status="pending",
            due_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(ticket)

        return CustomerSupportRequestResponse(
            id=str(ticket.id),
            category=ticket.category,
            subject=ticket.subject,
            description=ticket.description,
            status=ticket.status,
            priority=ticket.priority,
            created_at=ticket.created_at or datetime.now(timezone.utc),
            resolved_at=None,
            resolution_notes=None
        )

    # ─── 9. Post-Sale & CSAT / NPS ────────────────────────────────────────────

    async def submit_post_sale_feedback(
        self,
        lead_id: str,
        organization_id: str,
        req: CustomerPostSaleFeedbackRequest
    ) -> CustomerPostSaleFeedbackResponse:
        """Submits customer CSAT & NPS. Protects against duplicate submissions."""
        lead_uuid = uuid.UUID(lead_id)
        deal_stmt = select(Deal).where(
            Deal.lead_id == lead_uuid,
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal = (await self.db.execute(deal_stmt)).scalars().first()
        if not deal:
            raise HTTPException(status_code=404, detail="No deal found for feedback.")

        now = datetime.now(timezone.utc)
        post_sale = deal.post_sale_record
        if not post_sale:
            post_sale = DealPostSale(
                deal_id=deal.id,
                organization_id=deal.organization_id,
                customer_satisfaction_score=req.csat_score,
                nps_score=req.nps_score,
                feedback_text=req.feedback_text,
                feedback_collected_at=now,
                referral_given=req.referral_interested
            )
            self.db.add(post_sale)
        else:
            post_sale.customer_satisfaction_score = req.csat_score
            post_sale.nps_score = req.nps_score
            post_sale.feedback_text = req.feedback_text
            post_sale.feedback_collected_at = now
            post_sale.referral_given = req.referral_interested

        await self.db.commit()
        return CustomerPostSaleFeedbackResponse(
            status="RECORDED",
            recorded_at=now,
            message="Thank you for your valuable feedback."
        )

    # ─── 10. Acknowledgements ─────────────────────────────────────────────────

    async def record_acknowledgement(
        self,
        lead_id: str,
        organization_id: str,
        req: CustomerAcknowledgementRequest,
        ip: Optional[str] = None,
        ua: Optional[str] = None
    ) -> Dict[str, Any]:
        """Records timestamped customer acceptance of transaction milestone or terms."""
        lead_uuid = uuid.UUID(lead_id)
        deal_stmt = select(Deal.id).where(
            Deal.lead_id == lead_uuid,
            Deal.status == "ACTIVE",
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal_id = (await self.db.execute(deal_stmt)).scalar()
        if not deal_id:
            raise HTTPException(status_code=404, detail="No active deal found to acknowledge.")

        now = datetime.now(timezone.utc)
        ack = CustomerTransactionAcknowledgement(
            organization_id=organization_id,
            deal_id=deal_id,
            lead_id=lead_uuid,
            acknowledgement_type=req.acknowledgement_type,
            item_version=req.item_version,
            ip_address=ip,
            user_agent=ua,
            acknowledged_at=now
        )
        self.db.add(ack)
        await self.db.commit()
        return {"status": "ACKNOWLEDGED", "acknowledged_at": now.isoformat()}

    # ─── 11. Governed Customer AI Assistant ───────────────────────────────────

    async def query_customer_ai(
        self,
        lead_id: str,
        organization_id: str,
        user_query: str
    ) -> CustomerAIQueryResponse:
        """
        AI Assistant grounded strictly in the customer's authorized deal data.
        Blocks queries attempting to leak internal notes, commissions, margins, or other customers.
        """
        lead_uuid = uuid.UUID(lead_id)
        q_lower = user_query.lower()

        # Guard against probing internal CRM confidential data
        forbidden_keywords = ["commission", "margin", "profit", "internal note", "lead score", "other client", "other buyer", "agent split"]
        if any(kw in q_lower for kw in forbidden_keywords):
            return CustomerAIQueryResponse(
                answer="I can only assist with your personal property details, pending document requirements, upcoming appointments, and payment milestones.",
                suggested_actions=["Check pending documents", "View payment schedule", "View upcoming appointments"],
                source_references=["WefyLabs Customer Privacy Policy"]
            )

        # Load customer deal
        deal_stmt = select(Deal).where(
            Deal.lead_id == lead_uuid,
            Deal.deleted_at.is_(None)
        ).order_by(desc(Deal.created_at))
        deal = (await self.db.execute(deal_stmt)).scalars().first()

        if not deal:
            return CustomerAIQueryResponse(
                answer="You do not have an active real estate transaction at this time. Your consultant will assign a property to your deal room shortly.",
                suggested_actions=["Contact advisor", "Submit support request"],
                source_references=["Customer Profile"]
            )

        # Pending docs
        doc_stmt = select(DealDocument).where(DealDocument.deal_id == deal.id, DealDocument.status == "REQUIRED")
        docs = (await self.db.execute(doc_stmt)).scalars().all()
        doc_names = [d.document_name for d in docs]

        if "document" in q_lower or "upload" in q_lower or "kyc" in q_lower:
            if doc_names:
                ans = f"You currently have {len(doc_names)} pending document(s) required: {', '.join(doc_names)}. Please upload them in the Documents tab."
                actions = ["Upload documents"]
            else:
                ans = "All your required documents have been submitted and are under review or approved."
                actions = ["View documents"]
            return CustomerAIQueryResponse(answer=ans, suggested_actions=actions, source_references=["Deal Room Documents"])

        if "payment" in q_lower or "money" in q_lower or "due" in q_lower or "price" in q_lower:
            agreed = f"{deal.currency} {deal.agreed_price:,.2f}" if deal.agreed_price else "TBD"
            ans = f"Your transaction price is {agreed}. You can view your complete payment milestones and report wire transfer receipts under the Payments tab."
            return CustomerAIQueryResponse(answer=ans, suggested_actions=["View payment schedule", "Report payment proof"], source_references=["Deal Booking Ledger"])

        if "appointment" in q_lower or "visit" in q_lower or "meeting" in q_lower:
            now = datetime.now(timezone.utc)
            mtg_stmt = select(SchedulingMeeting).where(
                SchedulingMeeting.lead_id == lead_uuid,
                SchedulingMeeting.start_utc >= now
            ).order_by(SchedulingMeeting.start_utc)
            next_mtg = (await self.db.execute(mtg_stmt)).scalars().first()
            if next_mtg:
                ans = f"Your next scheduled appointment is '{next_mtg.title}' on {next_mtg.start_utc.strftime('%B %d, %Y at %H:%M UTC')}."
                actions = ["Confirm appointment"]
            else:
                ans = "You do not have any upcoming appointments. Your advisor can schedule a property viewing with you."
                actions = ["Message advisor"]
            return CustomerAIQueryResponse(answer=ans, suggested_actions=actions, source_references=["Calendar Engine"])

        # Default summary
        ans = (
            f"Your transaction '{deal.deal_title}' is currently at the '{deal.current_stage.title()}' stage. "
            f"{'You have ' + str(len(doc_names)) + ' pending documents.' if doc_names else 'All documents are in order.'} "
            "Let me know if you have questions about your documents, payments, or appointments."
        )
        return CustomerAIQueryResponse(
            answer=ans,
            suggested_actions=["Check pending documents", "View payment schedule", "Message advisor"],
            source_references=["Deal Room Overview"]
        )

    # ─── 12. Broker Admin Document & Proof Reviews ────────────────────────────

    async def review_document(
        self,
        broker: Broker,
        document_id: str,
        action: str,
        rejection_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Broker approves or rejects a customer-uploaded document."""
        doc_uuid = uuid.UUID(document_id)
        doc = (await self.db.execute(select(DealDocument).where(DealDocument.id == doc_uuid))).scalars().first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        now = datetime.now(timezone.utc)
        if action.upper() == "APPROVE":
            doc.status = "VERIFIED"
            doc.verified_at = now
            doc.verified_by_id = str(broker.id)
            doc.rejection_reason = None
        elif action.upper() == "REJECT":
            doc.status = "REJECTED"
            doc.rejection_reason = rejection_reason or "Document verification failed. Please upload a clear replacement."
        else:
            raise HTTPException(status_code=422, detail="Action must be APPROVE or REJECT.")

        await self.db.commit()
        return {"document_id": document_id, "status": doc.status}

    async def review_payment_proof(
        self,
        broker: Broker,
        proof_id: str,
        action: str,
        review_notes: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Broker verifies or rejects reported customer payment proof."""
        proof_uuid = uuid.UUID(proof_id)
        proof = (await self.db.execute(select(CustomerPaymentProof).where(CustomerPaymentProof.id == proof_uuid))).scalars().first()
        if not proof:
            raise HTTPException(status_code=404, detail="Payment proof not found.")

        now = datetime.now(timezone.utc)
        if action.upper() == "VERIFY":
            proof.status = "VERIFIED"
            proof.reviewed_by_id = str(broker.id)
            proof.reviewed_at = now
            proof.review_notes = review_notes

            # Also update booking payment schedule milestone
            deal = (await self.db.execute(select(Deal).where(Deal.id == proof.deal_id))).scalars().first()
            if deal and deal.booking and deal.booking.payment_schedule:
                sched = list(deal.booking.payment_schedule)
                if 0 <= proof.milestone_index < len(sched):
                    sched[proof.milestone_index]["status"] = "VERIFIED"
                    deal.booking.payment_schedule = sched

        elif action.upper() == "REJECT":
            proof.status = "REJECTED"
            proof.reviewed_by_id = str(broker.id)
            proof.reviewed_at = now
            proof.rejection_reason = rejection_reason or "Proof rejected upon audit."
        else:
            raise HTTPException(status_code=422, detail="Action must be VERIFY or REJECT.")

        await self.db.commit()
        return {"proof_id": proof_id, "status": proof.status}
