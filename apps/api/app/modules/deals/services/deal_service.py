"""
Part 18 - Deal Lifecycle Service
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from app.models.deal_models import (
    Deal, DealStage, DealStageHistory, DealOffer, DealReservation,
    DealBooking, DealCommission, DealClosing, DealPostSale,
    DealDocument, DealApprovalRequest, DealCommercialAuditLog,
)
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.outbox_models import OutboxEvent
from app.common.redis.distributed_lock import RedisDistributedLock

_STAGE_ORDER_MAP: Dict[str, int] = {s: i for i, s in enumerate(DealStage.ORDERED)}

def _stage_idx(stage: str) -> int:
    return _STAGE_ORDER_MAP.get(stage, -1)

class DealServiceError(Exception):
    pass

class DealService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_deal_reference(self, org_id: str) -> str:
        count_stmt = select(func.count()).select_from(Deal).where(
            Deal.organization_id == uuid.UUID(str(org_id))
        )
        res = await self.db.execute(count_stmt)
        count = (res.scalar() or 0) + 1
        prefix = str(org_id)[:6].upper().replace("-", "")
        return f"WL-{prefix}-{count:06d}"

    def _write_audit(self, deal, event_type, actor_id, actor_type, resource_type, resource_id, previous_state=None, new_state=None, change_summary=None, idempotency_key=None):
        entry = DealCommercialAuditLog(
            deal_id=deal.id,
            organization_id=deal.organization_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            previous_state=previous_state,
            new_state=new_state,
            change_summary=change_summary,
            idempotency_key=idempotency_key,
        )
        self.db.add(entry)
        return entry

    def _write_outbox(self, deal, event_type, payload, idempotency_key=None):
        ev = OutboxEvent(
            tenant_id=str(deal.organization_id),
            event_type=event_type,
            aggregate_type="Deal",
            aggregate_id=str(deal.id),
            payload=payload,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )
        self.db.add(ev)
        return ev

    async def create_deal(self, lead_id, deal_title, broker_id, organization_id, property_id=None, current_stage=DealStage.OPPORTUNITY, agreed_price=None, currency="AED", commission_percentage=None, tags=None, notes=None, idempotency_key=None):
        org_uuid = uuid.UUID(organization_id)
        broker_uuid = uuid.UUID(broker_id)
        lead_uuid = uuid.UUID(lead_id)
        if idempotency_key:
            ex = await self.db.execute(select(Deal).where(Deal.organization_id == org_uuid, Deal.idempotency_key == idempotency_key, Deal.deleted_at.is_(None)))
            ed = ex.scalars().first()
            if ed:
                return ed
        lead_res = await self.db.execute(select(Lead).where(Lead.id == lead_uuid, Lead.deleted_at.is_(None)))
        if not lead_res.scalars().first():
            raise DealServiceError(f"Lead {lead_id} not found")
        deal_ref = await self._generate_deal_reference(organization_id)
        deal = Deal(
            id=uuid.uuid4(), organization_id=org_uuid, broker_id=broker_uuid, lead_id=lead_uuid,
            property_id=uuid.UUID(property_id) if property_id else None,
            deal_reference=deal_ref, deal_title=deal_title, current_stage=current_stage,
            agreed_price=agreed_price, currency=currency, commission_percentage=commission_percentage,
            tags=tags or [], notes=notes, idempotency_key=idempotency_key, status="ACTIVE",
        )
        self.db.add(deal)
        self.db.add(DealStageHistory(deal_id=deal.id, organization_id=org_uuid, from_stage=None, to_stage=current_stage, transitioned_by_id=broker_id, transitioned_by_type="HUMAN", reason="Deal created"))
        await self.db.flush()
        self._write_audit(deal, "deal.created", broker_id, "HUMAN", "Deal", str(deal.id), new_state={"stage": current_stage, "title": deal_title}, change_summary=f"Deal created at stage {current_stage}", idempotency_key=idempotency_key)
        self._write_outbox(deal, "deal.created", {"deal_id": str(deal.id), "deal_reference": deal_ref, "organization_id": organization_id, "broker_id": broker_id, "lead_id": lead_id, "stage": current_stage, "timestamp": datetime.now(timezone.utc).isoformat()}, idempotency_key=idempotency_key)
        await self.db.commit()
        await self.db.refresh(deal)
        return deal

    async def list_deals(self, broker_id, organization_id, stage=None, status=None, lead_id=None, limit=50, offset=0):
        org_uuid = uuid.UUID(organization_id)
        stmt = select(Deal).where(Deal.organization_id == org_uuid, Deal.deleted_at.is_(None))
        if lead_id:
            try:
                stmt = stmt.where(Deal.lead_id == uuid.UUID(lead_id))
            except Exception:
                pass
        if stage:
            stmt = stmt.where(Deal.current_stage == stage.lower())
        if status:
            stmt = stmt.where(Deal.status == status.upper())
        count_res = await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        total = count_res.scalar() or 0
        stmt = stmt.order_by(desc(Deal.created_at)).offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all()), total

    async def get_deal(self, deal_id, organization_id):
        return await self._get_deal_or_raise(deal_id, organization_id)

    async def _get_deal_or_raise(self, deal_id, org_id):
        res = await self.db.execute(select(Deal).where(Deal.id == uuid.UUID(deal_id), Deal.organization_id == uuid.UUID(org_id), Deal.deleted_at.is_(None)))
        deal = res.scalars().first()
        if not deal:
            raise DealServiceError(f"Deal {deal_id} not found")
        return deal

    async def advance_stage(self, deal_id, target_stage, organization_id, actor_id, actor_type="HUMAN", reason=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        if deal.is_closed:
            raise DealServiceError("Cannot advance a closed deal")
        curr_idx = _stage_idx(deal.current_stage)
        tgt_idx = _stage_idx(target_stage)
        if curr_idx == -1 or tgt_idx == -1:
            raise DealServiceError(f"Unknown stage: {deal.current_stage} or {target_stage}")
        if deal.current_stage in DealStage.IRREVERSIBLE and tgt_idx < curr_idx:
            raise DealServiceError(f"Stage {deal.current_stage} is irreversible")
        if target_stage in DealStage.IRREVERSIBLE and tgt_idx > curr_idx:
            has_approval = await self._check_approval(deal, f"ADVANCE_TO_{target_stage.upper()}")
            if target_stage == DealStage.BOOKING and not has_approval:
                has_approval = await self._check_approval(deal, "BOOKING_CONFIRM")
            if not has_approval:
                raise DealServiceError(f"Advancing to '{target_stage}' requires an approved DealApprovalRequest")
        old_stage = deal.current_stage
        now = datetime.now(timezone.utc)
        entered = deal.stage_entered_at
        if entered.tzinfo is None:
            entered = entered.replace(tzinfo=timezone.utc)
        hours_in_stage = max(0, int((now - entered).total_seconds() / 3600))
        deal.previous_stage = old_stage
        deal.current_stage = target_stage
        deal.stage_entered_at = now
        deal.stage_duration_hours = hours_in_stage
        deal.updated_at = now
        self.db.add(DealStageHistory(deal_id=deal.id, organization_id=deal.organization_id, from_stage=old_stage, to_stage=target_stage, transitioned_at=now, transitioned_by_id=actor_id, transitioned_by_type=actor_type, reason=reason, duration_hours_in_previous_stage=hours_in_stage))
        self._write_audit(deal, "deal.stage_advanced", actor_id, actor_type, "Deal", str(deal.id), previous_state={"stage": old_stage}, new_state={"stage": target_stage}, change_summary=f"Stage: {old_stage} -> {target_stage}")
        self._write_outbox(deal, "deal.stage_advanced", {"deal_id": str(deal.id), "from_stage": old_stage, "to_stage": target_stage, "actor_id": actor_id, "reason": reason, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(deal)
        return deal

    async def submit_offer(self, deal_id, organization_id, actor_id, offer_price, currency="AED", listing_price=None, payment_plan=None, token_amount=None, valid_until=None, possession_date_requested=None, special_conditions=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(select(DealOffer).where(DealOffer.deal_id == deal.id))
        existing = ex.scalars().first()
        now = datetime.now(timezone.utc)
        if existing:
            history_entry = {"version": existing.version, "offer_price": float(existing.offer_price), "status": existing.status, "archived_at": now.isoformat()}
            existing.offer_history = [*(existing.offer_history or []), history_entry]
            existing.version += 1
            existing.offer_price = offer_price
            existing.currency = currency
            existing.listing_price = listing_price
            existing.payment_plan = payment_plan
            existing.token_amount = token_amount
            existing.valid_until = valid_until
            existing.special_conditions = special_conditions
            existing.status = "SUBMITTED"
            existing.submitted_at = now
            existing.submitted_by_id = actor_id
            offer = existing
        else:
            offer = DealOffer(deal_id=deal.id, organization_id=deal.organization_id, offer_price=offer_price, currency=currency, listing_price=listing_price, payment_plan=payment_plan, token_amount=token_amount, valid_until=valid_until, possession_date_requested=possession_date_requested, special_conditions=special_conditions, status="SUBMITTED", version=1, offer_history=[], submitted_at=now, submitted_by_id=actor_id)
            self.db.add(offer)
        deal.offer_price = offer_price
        deal.updated_at = now
        self._write_audit(deal, "offer.submitted", actor_id, "HUMAN", "DealOffer", str(deal.id), new_state={"offer_price": float(offer_price), "status": "SUBMITTED"}, change_summary=f"Offer submitted at {currency} {offer_price}")
        self._write_outbox(deal, "deal.offer.submitted", {"deal_id": str(deal.id), "offer_price": str(offer_price), "currency": currency, "actor_id": actor_id, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(offer)
        return offer

    async def respond_to_offer(self, deal_id, organization_id, actor_id, action, counter_offer_price=None, rejection_reason=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        of_res = await self.db.execute(select(DealOffer).where(DealOffer.deal_id == deal.id))
        offer = of_res.scalars().first()
        if not offer:
            raise DealServiceError("No active offer on this deal")
        now = datetime.now(timezone.utc)
        action = action.upper()
        if action == "ACCEPT":
            offer.status = "ACCEPTED"; offer.accepted_at = now; offer.accepted_by_id = actor_id; deal.agreed_price = offer.offer_price
        elif action == "REJECT":
            offer.status = "REJECTED"; offer.rejected_at = now; offer.rejection_reason = rejection_reason
        elif action == "COUNTER":
            offer.status = "COUNTERED"; offer.counter_offer_price = counter_offer_price
        else:
            raise DealServiceError(f"Unknown action: {action}")
        deal.updated_at = now
        self._write_audit(deal, f"offer.{action.lower()}", actor_id, "HUMAN", "DealOffer", str(deal.id), new_state={"status": offer.status})
        self._write_outbox(deal, f"deal.offer.{action.lower()}", {"deal_id": str(deal.id), "action": action, "actor_id": actor_id, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(offer)
        return offer

    async def create_reservation(self, deal_id, organization_id, actor_id, reservation_amount=None, currency="AED", reserved_price=None, expires_at=None, reservation_form_url=None, customer_name=None, customer_phone=None, customer_email=None, reservation_notes=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(select(DealReservation).where(DealReservation.deal_id == deal.id))
        if ex.scalars().first():
            raise DealServiceError("Reservation already exists for this deal")
        now = datetime.now(timezone.utc)
        lock_token = None
        lock_name = None
        if deal.property_id:
            lock_name = f"property:{deal.property_id}:reservation"
            acquired, lock_token = RedisDistributedLock.acquire(lock_name, ttl_seconds=30)
            if not acquired:
                raise DealServiceError(f"Property unit {deal.property_id} is already reserved by another party.")
        try:
            if deal.property_id:
                prop_res = await self.db.execute(
                    select(DealReservation).where(
                        DealReservation.property_id == deal.property_id,
                        DealReservation.status == "ACTIVE",
                        DealReservation.expires_at > now
                    )
                )
                if prop_res.scalars().first():
                    raise DealServiceError(f"Property unit {deal.property_id} is already reserved by another party.")
            reservation = DealReservation(deal_id=deal.id, organization_id=deal.organization_id, property_id=deal.property_id, reservation_amount=reservation_amount, currency=currency, reserved_price=reserved_price, reserved_at=now, expires_at=expires_at or (now + timedelta(days=3)), status="ACTIVE", reservation_form_url=reservation_form_url, reserved_by_agent_id=actor_id, customer_name=customer_name, customer_phone=customer_phone, customer_email=customer_email, reservation_notes=reservation_notes)
            self.db.add(reservation)
            deal.updated_at = now
            self._write_audit(deal, "reservation.created", actor_id, "HUMAN", "DealReservation", str(deal.id), new_state={"status": "ACTIVE"}, change_summary="Property reservation created")
            self._write_outbox(deal, "deal.reservation.created", {"deal_id": str(deal.id), "actor_id": actor_id, "timestamp": now.isoformat()})
            await self.db.commit()
            await self.db.refresh(reservation)
            return reservation
        finally:
            if lock_name and lock_token:
                RedisDistributedLock.release(lock_name, lock_token)

    async def request_booking_approval(self, deal_id, organization_id, actor_id, booked_price, currency, token_amount, payment_plan_type, idempotency_key):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(select(DealApprovalRequest).where(DealApprovalRequest.idempotency_key == idempotency_key))
        if ex.scalars().first():
            raise DealServiceError("Booking approval request already exists (idempotent)")
        now = datetime.now(timezone.utc)
        approval = DealApprovalRequest(deal_id=deal.id, organization_id=deal.organization_id, requested_by_id=actor_id, requested_by_type="HUMAN", action_type="BOOKING_CONFIRM", action_payload={"booked_price": str(booked_price), "currency": currency, "token_amount": str(token_amount) if token_amount else None, "payment_plan_type": payment_plan_type}, reason=f"Booking confirmation for {deal.deal_reference}", idempotency_key=idempotency_key, status="PENDING", expires_at=now + timedelta(hours=48))
        self.db.add(approval)
        self._write_audit(deal, "approval.requested", actor_id, "HUMAN", "DealApprovalRequest", idempotency_key, new_state={"action_type": "BOOKING_CONFIRM", "status": "PENDING"}, change_summary="Booking approval requested", idempotency_key=idempotency_key)
        await self.db.commit()
        await self.db.refresh(approval)
        return approval

    async def approve_and_confirm_booking(self, deal_id, organization_id, reviewer_id, approval_id, review_notes=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        apr_res = await self.db.execute(select(DealApprovalRequest).where(DealApprovalRequest.id == uuid.UUID(approval_id), DealApprovalRequest.deal_id == deal.id, DealApprovalRequest.action_type == "BOOKING_CONFIRM", DealApprovalRequest.status == "PENDING"))
        approval = apr_res.scalars().first()
        if not approval:
            raise DealServiceError("Pending booking approval request not found")
        now = datetime.now(timezone.utc)
        approval.status = "APPROVED"
        approval.reviewed_by_id = reviewer_id
        approval.reviewed_at = now
        approval.review_notes = review_notes
        payload = approval.action_payload or {}
        booked_price = Decimal(str(payload.get("booked_price", 0)))
        currency = payload.get("currency", deal.currency)
        token_amount = Decimal(str(payload["token_amount"])) if payload.get("token_amount") else None
        payment_plan_type = payload.get("payment_plan_type")
        org_prefix = str(deal.organization_id)[:6].upper().replace("-", "")
        booking_ref = f"BK-{org_prefix}-{str(deal.id)[:8].upper()}"
        booking = DealBooking(deal_id=deal.id, organization_id=deal.organization_id, booking_reference=booking_ref, token_amount=token_amount, token_paid_at=now if token_amount else None, booked_price=booked_price, currency=currency, payment_plan_type=payment_plan_type, status="CONFIRMED" if token_amount else "PENDING_PAYMENT", booked_at=now)
        self.db.add(booking)
        deal.agreed_price = booked_price
        deal.updated_at = now
        self._write_audit(deal, "booking.confirmed", reviewer_id, "HUMAN", "DealBooking", str(deal.id), new_state={"booking_reference": booking_ref, "booked_price": str(booked_price)}, change_summary=f"Booking confirmed: {booking_ref}")
        self._write_outbox(deal, "deal.booking.confirmed", {"deal_id": str(deal.id), "booking_reference": booking_ref, "booked_price": str(booked_price), "reviewer_id": reviewer_id, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def record_commission(
        self,
        deal_id,
        organization_id,
        broker_id,
        actor_id,
        transaction_price,
        currency,
        commission_percentage,
        tax_deducted=None,
        tax_rate_percentage=None,
        split_basis="GROSS",
        other_deductions=None,
        broker_split_percentage=None,
        agency_split_percentage=None,
        commission_splits=None,
        invoice_reference=None,
        idempotency_key="",
    ):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        if deal.currency and currency.upper() != deal.currency.upper():
            raise DealServiceError(f"Currency mismatch: deal is denominated in {deal.currency}, but commission specified {currency}")

        ex = await self.db.execute(select(DealCommission).where(DealCommission.deal_id == deal.id))
        existing_comm = ex.scalars().first()
        if existing_comm:
            if idempotency_key or (invoice_reference and existing_comm.invoice_reference == invoice_reference):
                return existing_comm
            raise DealServiceError("Commission already recorded for this deal")

        # Exact Decimal commission arithmetic
        t_price = Decimal(str(transaction_price))
        c_pct = Decimal(str(commission_percentage))
        gross = (t_price * c_pct / Decimal("100")).quantize(Decimal("0.0001"))

        # Deductions & Tax calculation
        if tax_deducted is not None:
            tax = Decimal(str(tax_deducted)).quantize(Decimal("0.0001"))
        elif tax_rate_percentage is not None:
            tax = (gross * Decimal(str(tax_rate_percentage)) / Decimal("100")).quantize(Decimal("0.0001"))
        else:
            tax = Decimal("0")

        other = Decimal(str(other_deductions or "0")).quantize(Decimal("0.0001"))
        net = (gross - tax - other).quantize(Decimal("0.0001"))
        if net < Decimal("0"):
            raise DealServiceError(f"Total deductions ({tax + other}) cannot exceed gross commission ({gross})")

        # Commission Splits
        if not commission_splits:
            broker_pct = Decimal(str(broker_split_percentage)) if broker_split_percentage is not None else Decimal("70.0")
            agency_pct = Decimal(str(agency_split_percentage)) if agency_split_percentage is not None else (Decimal("100.0") - broker_pct)
            b_gross = (gross * broker_pct / Decimal("100")).quantize(Decimal("0.0001"))
            a_gross = (gross - b_gross).quantize(Decimal("0.0001"))
            b_net = (net * broker_pct / Decimal("100")).quantize(Decimal("0.0001"))
            a_net = (net - b_net).quantize(Decimal("0.0001"))
            commission_splits = [
                {
                    "recipient_role": "PRIMARY_BROKER",
                    "recipient_id": str(broker_id),
                    "split_percentage": float(broker_pct),
                    "gross_amount": float(b_gross),
                    "net_amount": float(b_net),
                    "amount": float(b_gross)
                },
                {
                    "recipient_role": "AGENCY_POOL",
                    "recipient_id": "AGENCY",
                    "split_percentage": float(agency_pct),
                    "gross_amount": float(a_gross),
                    "net_amount": float(a_net),
                    "amount": float(a_gross)
                }
            ]


        now = datetime.now(timezone.utc)
        commission = DealCommission(
            deal_id=deal.id,
            organization_id=deal.organization_id,
            broker_id=uuid.UUID(broker_id),
            transaction_price=t_price,
            currency=currency.upper(),
            commission_percentage=c_pct,
            gross_commission=gross,
            tax_deducted=tax,
            net_commission=net,
            commission_splits=commission_splits,
            status="PENDING",
            invoice_reference=invoice_reference
        )
        self.db.add(commission)
        deal.commission_percentage = c_pct
        deal.commission_amount = gross
        deal.final_transaction_price = t_price
        deal.updated_at = now
        self._write_audit(
            deal, "commission.recorded", actor_id, "HUMAN", "DealCommission", str(deal.id),
            new_state={
                "gross_commission": str(gross),
                "net_commission": str(net),
                "tax_deducted": str(tax),
                "split_basis": split_basis,
                "status": "PENDING"
            },
            change_summary=f"Commission recorded: {currency} {gross} gross, {tax} tax withheld, {net} net",
            idempotency_key=idempotency_key
        )
        self._write_outbox(
            deal, "deal.commission.recorded",
            {
                "deal_id": str(deal.id),
                "gross_commission": str(gross),
                "net_commission": str(net),
                "tax_deducted": str(tax),
                "actor_id": actor_id,
                "timestamp": now.isoformat()
            },
            idempotency_key=idempotency_key
        )
        await self.db.commit()
        await self.db.refresh(commission)
        return commission

    async def _get_actor_role(self, organization_id, actor_id) -> Optional[str]:
        if not actor_id or not organization_id:
            return None
        from app.models.organization import OrganizationMember
        try:
            b_uuid = uuid.UUID(str(actor_id))
            o_uuid = uuid.UUID(str(organization_id))
        except (ValueError, TypeError):
            return None
        stmt = select(OrganizationMember.role).where(
            OrganizationMember.organization_id == o_uuid,
            OrganizationMember.broker_id == b_uuid
        )
        res = await self.db.execute(stmt)
        role = res.scalars().first()
        if role:
            return str(role).lower()
        from app.models.broker import Broker
        b_res = await self.db.execute(select(Broker.role).where(Broker.id == b_uuid))
        b_role = b_res.scalars().first()
        return str(b_role).lower() if b_role else None

    async def settle_commission(
        self,
        deal_id,
        organization_id,
        actor_id,
        amount_received=None,
        settled_amount=None,
        payment_reference=None,
        payment_mode="MANUAL_BANK_TRANSFER",
        provenance="MANUAL_UNVERIFIED",
        currency=None,
        settled_at=None,
        notes=None,
        settlement_evidence_url=None,
        idempotency_key=""
    ):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(
            select(DealCommission).where(
                DealCommission.deal_id == deal.id,
                DealCommission.organization_id == deal.organization_id
            )
        )
        comm = ex.scalars().first()
        if not comm:
            raise DealServiceError("No commission record found for this deal. Commission must be recorded before settlement.")

        if currency and currency.upper() != comm.currency.upper():
            raise DealServiceError(f"Currency mismatch: commission is denominated in {comm.currency}, but settlement specified {currency}")

        target_amount = settled_amount if settled_amount is not None else amount_received
        if target_amount is None:
            raise DealServiceError("Settlement amount is required")

        # Idempotency / Double-Settlement guard
        received = Decimal(str(target_amount)).quantize(Decimal("0.0001"))
        if comm.status in ("PAID", "RECORDED_UNVERIFIED"):
            if comm.payment_reference == payment_reference and (comm.net_commission == received or comm.gross_commission == received):
                return comm
            raise DealServiceError(f"Commission for deal {deal_id} is already settled (Ref: {comm.payment_reference})")

        # Anti-replay guard: Ensure the payment reference is not already used across the organization
        if payment_reference:
            existing_ref_stmt = select(DealCommission).where(
                DealCommission.organization_id == deal.organization_id,
                DealCommission.payment_reference == payment_reference,
                DealCommission.id != comm.id,
                DealCommission.status.in_(["PAID", "RECORDED_UNVERIFIED"])
            )
            ex_ref = (await self.db.execute(existing_ref_stmt)).scalars().first()
            if ex_ref:
                raise DealServiceError(
                    f"Payment reference '{payment_reference}' has already been used in another settlement. Duplicate settlement is prohibited."
                )

        if comm.status in ("CANCELLED", "DISPUTED"):
            raise DealServiceError(f"Commission cannot be settled while in status {comm.status}")

        if received <= Decimal("0"):
            raise DealServiceError("Settlement amount must be positive")

        expected = (comm.net_commission if comm.net_commission is not None else comm.gross_commission).quantize(Decimal("0.0001"))
        if received > expected:
            raise DealServiceError(f"Settlement amount ({received}) cannot exceed expected net commission ({expected})")
        if received != expected:
            raise DealServiceError(
                f"Partial settlement is not supported. Record the full outstanding amount ({expected}) in {comm.currency}."
            )

        # Provenance truthfulness and authorized reviewer workflow enforcement
        raw_mode = payment_mode.upper() if payment_mode else "MANUAL_BANK_TRANSFER"
        requested_prov = (provenance or "MANUAL_UNVERIFIED").upper()
        is_automated_provider = (
            raw_mode.startswith("GATEWAY_") or
            raw_mode.startswith("WEBHOOK_") or
            raw_mode in ("RAZORPAY", "STRIPE")
        )
        has_audit_evidence = bool(
            (notes and any(k in notes.upper() for k in ("VERIF", "REVIEW", "AUDIT", "STATEMENT"))) or
            settlement_evidence_url
        )

        actor_role = await self._get_actor_role(deal.organization_id, actor_id)
        authorized_financial_roles = {"owner", "admin", "finance", "manager", "accountant", "financial_controller", "super_admin"}

        if requested_prov == "PROVIDER_CONFIRMED":
            if not is_automated_provider:
                raise DealServiceError(
                    "Cannot self-assert PROVIDER_CONFIRMED: Automated gateway or webhook confirmation payload is required for provider confirmation."
                )
            prov = "PROVIDER_CONFIRMED"
        elif requested_prov == "MANUAL_REVIEWED":
            # Actor must possess financial reviewer authorization
            if actor_role and actor_role not in authorized_financial_roles:
                raise DealServiceError(
                    f"Unauthorized reviewer: Role '{actor_role}' lacks financial reviewer authorization to certify manual settlement receipts."
                )
            # Supporting evidence must be provided
            if not has_audit_evidence:
                raise DealServiceError(
                    "Missing settlement evidence: MANUAL_REVIEWED requires supporting document URL or verified bank statement notes."
                )
            prov = "MANUAL_REVIEWED"
        else:
            # If authorized reviewer workflow provides verified audit evidence, classify as MANUAL_REVIEWED;
            # otherwise manual receipts remain strictly MANUAL_UNVERIFIED / RECORDED_UNVERIFIED.
            if actor_role in authorized_financial_roles and has_audit_evidence:
                prov = "MANUAL_REVIEWED"
            else:
                prov = "MANUAL_UNVERIFIED"

        mode = raw_mode

        # Enforce truthful distinction between verified receipt (PAID) and unverified manual entry (RECORDED_UNVERIFIED)
        comm_status = "PAID" if prov in ("MANUAL_REVIEWED", "PROVIDER_CONFIRMED") else "RECORDED_UNVERIFIED"

        now = settled_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        reviewed_by_id = actor_id if prov == "MANUAL_REVIEWED" else None
        reviewed_at = now if prov == "MANUAL_REVIEWED" else None

        comm.status = comm_status
        comm.paid_at = now
        comm.payment_reference = payment_reference
        comm.payment_mode = mode
        comm.updated_at = now
        deal.updated_at = now
        comm._provenance = prov

        # Persist provenance, evidence URL, and reviewer identity into commission splits for audit lineage
        if comm.commission_splits and isinstance(comm.commission_splits, list):
            updated_splits = []
            for s in comm.commission_splits:
                if isinstance(s, dict):
                    sc = dict(s)
                    sc["settlement_provenance"] = prov
                    sc["settlement_evidence_url"] = settlement_evidence_url
                    sc["reviewed_by_id"] = reviewed_by_id
                    sc["reviewed_at"] = reviewed_at.isoformat() if reviewed_at else None
                    updated_splits.append(sc)
                else:
                    updated_splits.append(s)
            comm.commission_splits = updated_splits

        action_name = "commission.settled" if comm_status == "PAID" else "commission.recorded_unverified"
        self._write_audit(
            deal, action_name, actor_id, "HUMAN", "DealCommission", str(comm.id),
            new_state={
                "status": comm_status,
                "paid_at": now.isoformat(),
                "payment_reference": payment_reference,
                "payment_mode": mode,
                "provenance": prov,
                "amount_received": str(received),
                "settlement_evidence_url": settlement_evidence_url,
                "reviewed_by_id": reviewed_by_id,
                "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
                "notes": notes
            },
            change_summary=f"Commission {comm_status.lower()}: {comm.currency} {received} via {mode} (Ref: {payment_reference}, Provenance: {prov})",
            idempotency_key=idempotency_key
        )
        self._write_outbox(
            deal, f"deal.{action_name}",
            {
                "deal_id": str(deal.id),
                "commission_id": str(comm.id),
                "status": comm_status,
                "amount_received": str(received),
                "currency": comm.currency,
                "payment_reference": payment_reference,
                "payment_mode": mode,
                "provenance": prov,
                "settlement_evidence_url": settlement_evidence_url,
                "reviewed_by_id": reviewed_by_id,
                "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
                "actor_id": actor_id,
                "timestamp": now.isoformat()
            },
            idempotency_key=idempotency_key
        )

        from app.models.sales_pipeline_models import RevenueEvent, RevenueEventType
        is_confirmed = (comm_status == "PAID")
        rev_event = RevenueEvent(
            organization_id=deal.organization_id,
            event_type=RevenueEventType.PAYMENT_RECEIVED,
            lead_id=deal.lead_id,
            opportunity_id=deal.id,
            amount=received,
            currency=comm.currency,
            source=mode,
            actor_id=actor_id,
            actor_type="HUMAN",
            payload={
                "commission_id": str(comm.id),
                "deal_id": str(deal.id),
                "payment_reference": payment_reference,
                "payment_mode": mode,
                "provenance": prov,
                "is_confirmed": is_confirmed,
                "requires_audit_review": not is_confirmed,
                "settlement_evidence_url": settlement_evidence_url,
                "reviewed_by_id": reviewed_by_id,
                "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
                "notes": notes
            },
            occurred_at=now
        )
        self.db.add(rev_event)

        await self.db.commit()
        await self.db.refresh(comm)
        return comm

    async def dispute_commission(self, deal_id, organization_id, actor_id, reason, idempotency_key=""):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(
            select(DealCommission).where(
                DealCommission.deal_id == deal.id,
                DealCommission.organization_id == deal.organization_id
            )
        )
        comm = ex.scalars().first()
        if not comm:
            raise DealServiceError("No commission record found for this deal")

        now = datetime.now(timezone.utc)
        comm.status = "DISPUTED"
        comm.disputed_at = now
        comm.dispute_reason = reason
        comm.updated_at = now
        deal.updated_at = now

        self._write_audit(
            deal, "commission.disputed", actor_id, "HUMAN", "DealCommission", str(comm.id),
            new_state={"status": "DISPUTED", "dispute_reason": reason, "disputed_at": now.isoformat()},
            change_summary=f"Commission disputed: {reason}",
            idempotency_key=idempotency_key
        )
        self._write_outbox(
            deal, "deal.commission.disputed",
            {"deal_id": str(deal.id), "commission_id": str(comm.id), "reason": reason, "timestamp": now.isoformat()},
            idempotency_key=idempotency_key
        )
        await self.db.commit()
        await self.db.refresh(comm)
        return comm

    async def reverse_settlement(self, deal_id, organization_id, actor_id, reason, idempotency_key=""):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(
            select(DealCommission).where(
                DealCommission.deal_id == deal.id,
                DealCommission.organization_id == deal.organization_id
            )
        )
        comm = ex.scalars().first()
        if not comm:
            raise DealServiceError("No commission record found for this deal")

        if comm.status not in ("PAID", "RECORDED_UNVERIFIED"):
            raise DealServiceError(f"Cannot reverse commission with status {comm.status}. Only settled or unverified recorded commissions can be reversed.")

        now = datetime.now(timezone.utc)
        prior_ref = comm.payment_reference
        comm.status = "PENDING"
        comm.paid_at = None
        comm.payment_reference = None
        comm.updated_at = now
        deal.updated_at = now

        self._write_audit(
            deal, "commission.settlement_reversed", actor_id, "HUMAN", "DealCommission", str(comm.id),
            new_state={"status": "PENDING", "reversal_reason": reason, "prior_reference": prior_ref},
            change_summary=f"Commission settlement reversed: {reason}",
            idempotency_key=idempotency_key
        )
        self._write_outbox(
            deal, "deal.commission.settlement_reversed",
            {"deal_id": str(deal.id), "commission_id": str(comm.id), "reason": reason, "timestamp": now.isoformat()},
            idempotency_key=idempotency_key
        )
        from app.models.sales_pipeline_models import RevenueEvent, RevenueEventType
        rev_event = RevenueEvent(
            organization_id=deal.organization_id,
            event_type=RevenueEventType.REFUND_ISSUED,
            lead_id=deal.lead_id,
            opportunity_id=deal.id,
            amount=comm.net_commission or comm.gross_commission,
            currency=comm.currency,
            source="SETTLEMENT_REVERSAL",
            actor_id=actor_id,
            actor_type="HUMAN",
            payload={"commission_id": str(comm.id), "reason": reason, "prior_reference": prior_ref},
            occurred_at=now
        )
        self.db.add(rev_event)

        await self.db.commit()
        await self.db.refresh(comm)
        return comm


    async def create_closing(self, deal_id, organization_id, actor_id, registration_authority=None, registration_number=None, registration_date=None, title_deed_number=None, handover_date=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(select(DealClosing).where(DealClosing.deal_id == deal.id))
        existing_closing = ex.scalars().first()
        if existing_closing:
            return existing_closing
        now = datetime.now(timezone.utc)
        default_checklist = [{"item": "Registration Authority Fee Paid", "completed": False}, {"item": "Title Deed Issued", "completed": bool(title_deed_number)}, {"item": "Land Registration Complete", "completed": bool(registration_number)}, {"item": "Keys Handed to Buyer", "completed": False}, {"item": "Commission Invoice Raised", "completed": False}]
        closing = DealClosing(deal_id=deal.id, organization_id=deal.organization_id, closing_checklist=default_checklist, registration_authority=registration_authority, registration_number=registration_number, registration_date=registration_date, title_deed_number=title_deed_number, handover_date=handover_date, status="IN_PROGRESS")
        self.db.add(closing)
        deal.updated_at = now
        self._write_audit(deal, "closing.initiated", actor_id, "HUMAN", "DealClosing", str(deal.id), new_state={"status": "IN_PROGRESS"}, change_summary="Closing process initiated")
        self._write_outbox(deal, "deal.closing.initiated", {"deal_id": str(deal.id), "actor_id": actor_id, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(closing)
        return closing

    async def complete_closing(self, deal_id, organization_id, actor_id):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        closing_res = await self.db.execute(select(DealClosing).where(DealClosing.deal_id == deal.id))
        closing = closing_res.scalars().first()
        now = datetime.now(timezone.utc)
        if closing:
            closing.status = "COMPLETE"
            closing.completed_at = now
        deal.status = "CLOSED_WON"
        deal.closed_at = now
        deal.close_reason = "Closing completed"
        deal.updated_at = now
        self._write_audit(deal, "deal.closed_won", actor_id, "HUMAN", "Deal", str(deal.id), new_state={"status": "CLOSED_WON"}, change_summary="Deal closed won")
        self._write_outbox(deal, "deal.closed_won", {"deal_id": str(deal.id), "final_price": str(deal.final_transaction_price or deal.agreed_price), "actor_id": actor_id, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(deal)
        return deal

    async def record_post_sale(self, deal_id, organization_id, actor_id, customer_satisfaction_score=None, nps_score=None, feedback_text=None, referral_given=False, success_factors=None, obstacle_factors=None, ai_recommendation_followed=None):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        ex = await self.db.execute(select(DealPostSale).where(DealPostSale.deal_id == deal.id))
        existing_ps = ex.scalars().first()
        if existing_ps:
            return existing_ps
        now = datetime.now(timezone.utc)
        created = deal.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        days_to_close = (now - created).days
        post_sale = DealPostSale(deal_id=deal.id, organization_id=deal.organization_id, customer_satisfaction_score=customer_satisfaction_score, nps_score=nps_score, feedback_text=feedback_text, feedback_collected_at=now, referral_given=referral_given, success_factors=success_factors or [], obstacle_factors=obstacle_factors or [], days_to_close=days_to_close, ai_recommendation_followed=ai_recommendation_followed)
        self.db.add(post_sale)
        deal.updated_at = now
        self._write_audit(deal, "post_sale.recorded", actor_id, "HUMAN", "DealPostSale", str(deal.id), new_state={"satisfaction": customer_satisfaction_score, "nps": nps_score, "days_to_close": days_to_close})
        self._write_outbox(deal, "deal.post_sale.recorded", {"deal_id": str(deal.id), "satisfaction_score": customer_satisfaction_score, "nps_score": nps_score, "days_to_close": days_to_close, "timestamp": now.isoformat()})
        await self.db.commit()
        await self.db.refresh(post_sale)
        return post_sale

    async def add_document(self, deal_id, organization_id, actor_id, document_type, document_name, required_at_stage, file_url=None, is_required=True):
        deal = await self._get_deal_or_raise(deal_id, organization_id)
        now = datetime.now(timezone.utc)
        doc = DealDocument(deal_id=deal.id, organization_id=deal.organization_id, document_type=document_type, document_name=document_name, required_at_stage=required_at_stage, is_required=is_required, status="UPLOADED" if file_url else "REQUIRED", file_url=file_url, uploaded_at=now if file_url else None, uploaded_by_id=actor_id if file_url else None)
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def get_pipeline_summary(self, broker_id, organization_id):
        org_uuid = uuid.UUID(organization_id)
        stage_count_res = await self.db.execute(select(Deal.current_stage, func.count().label("cnt")).where(Deal.organization_id == org_uuid, Deal.status == "ACTIVE", Deal.deleted_at.is_(None)).group_by(Deal.current_stage))
        stage_dist = {row[0]: row[1] for row in stage_count_res.all()}
        val_res = await self.db.execute(select(func.sum(Deal.agreed_price)).where(Deal.organization_id == org_uuid, Deal.status == "ACTIVE", Deal.deleted_at.is_(None)))
        pipeline_value = float(val_res.scalar() or 0)
        apr_res = await self.db.execute(select(func.count()).select_from(DealApprovalRequest).join(Deal, DealApprovalRequest.deal_id == Deal.id).where(Deal.organization_id == org_uuid, DealApprovalRequest.status == "PENDING"))
        pending_approvals = apr_res.scalar() or 0

        # Authoritative commission queries strictly scoped to organization
        comm_res = await self.db.execute(
            select(func.sum(func.coalesce(DealCommission.net_commission, DealCommission.gross_commission)))
            .where(DealCommission.organization_id == org_uuid, DealCommission.status == "PENDING")
        )
        commission_pending = float(comm_res.scalar() or 0)

        comm_paid_res = await self.db.execute(
            select(func.sum(func.coalesce(DealCommission.net_commission, DealCommission.gross_commission)))
            .where(DealCommission.organization_id == org_uuid, DealCommission.status.in_(["PAID", "SETTLED"]))
        )
        commission_earned = float(comm_paid_res.scalar() or 0)

        comm_unver_res = await self.db.execute(
            select(func.sum(func.coalesce(DealCommission.net_commission, DealCommission.gross_commission)))
            .where(DealCommission.organization_id == org_uuid, DealCommission.status == "RECORDED_UNVERIFIED")
        )
        commission_unverified = float(comm_unver_res.scalar() or 0)

        comm_disp_res = await self.db.execute(
            select(func.sum(func.coalesce(DealCommission.net_commission, DealCommission.gross_commission)))
            .where(DealCommission.organization_id == org_uuid, DealCommission.status == "DISPUTED")
        )
        commission_disputed = float(comm_disp_res.scalar() or 0)

        # Distinct Booked Value & Token Collected
        booked_res = await self.db.execute(
            select(func.sum(DealBooking.booked_price))
            .where(DealBooking.organization_id == org_uuid, DealBooking.status == "CONFIRMED")
        )
        booked_value = float(booked_res.scalar() or 0)

        token_res = await self.db.execute(
            select(func.sum(DealBooking.token_amount))
            .where(DealBooking.organization_id == org_uuid, DealBooking.status == "CONFIRMED")
        )
        token_collected = float(token_res.scalar() or 0)

        org_res = await self.db.execute(select(Organization.currency_code).where(Organization.id == org_uuid))
        org_curr = org_res.scalar()
        if org_curr:
            currency = org_curr.upper()
        else:
            curr_res = await self.db.execute(select(Deal.currency).where(Deal.organization_id == org_uuid, Deal.status == "ACTIVE").limit(1))
            currency = curr_res.scalar() or "INR"

        return {
            "total_active_deals": sum(stage_dist.values()),
            "total_pipeline_value": pipeline_value,
            "booked_value": booked_value,
            "token_collected": token_collected,
            "currency": currency,
            "deals_by_stage": stage_dist,
            "pending_approvals": pending_approvals,
            "stalled_deals": 0,
            "commission_pending": commission_pending,
            "commission_earned": commission_earned,
            "commission_unverified": commission_unverified,
            "commission_disputed": commission_disputed
        }

    async def _check_approval(self, deal, action_type):
        res = await self.db.execute(select(DealApprovalRequest).where(DealApprovalRequest.deal_id == deal.id, DealApprovalRequest.action_type == action_type, DealApprovalRequest.status == "APPROVED"))
        return res.scalars().first() is not None
