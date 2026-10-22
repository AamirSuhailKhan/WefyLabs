"""
Phase 9.3 — Commission Settlement, Financial Integrity and Revenue Reconciliation Test Suite
=============================================================================================
Asserts authoritative financial lifecycle:
  1. Accepted offer without booking preserves separation (no false revenue/booking).
  2. Confirmed booking records token deposit without pre-realizing revenue.
  3. Exact Decimal commission calculation:
     - Offer: ₹18,000,000
     - 2.0% gross: ₹360,000.00
     - 10% TDS deduction: ₹36,000.00
     - Net commission: ₹324,000.00
     - 70/30 split: Broker (₹226,800 net / ₹252,000 gross), Agency (₹97,200 net / ₹108,000 gross)
  4. Commission settlement workflow:
     - Transitions PENDING -> PAID
     - Persists manual receipt tag, payment reference, and timestamp
     - Reconciles dashboard commission_pending -> commission_earned
     - Creates RevenueEvent(PAYMENT_RECEIVED) in revenue intelligence
  5. Idempotent replay: identical settlement payload returns success without duplicating revenue.
  6. Financial guardrails:
     - Over-settlement exceeding expected net commission is rejected.
     - Currency mismatch between deal and commission or settlement is rejected.
     - Excess deductions exceeding gross are rejected.
  7. Commission dispute & settlement reversal:
     - Dispute transitions to DISPUTED and blocks settlement.
     - Reversal reverts PAID -> PENDING and issues refund event.
  8. Tenant isolation & security:
     - Cross-org access (reads & mutations) is strictly prohibited.
"""
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.organization import Organization, OrganizationMember
from app.models.deal_models import Deal, DealCommission, DealCommercialAuditLog
from app.models.sales_pipeline_models import RevenueEvent, RevenueEventType
from app.modules.auth.service import create_access_token


@pytest.mark.asyncio
async def test_phase9_3_financial_lifecycle_and_reconciliation(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Setup Org 1 (Authoritative Alpha Brokerage - INR)
    org1 = Organization(id=uuid.uuid4(), name="Alpha Brokerage", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    mem1 = OrganizationMember(organization_id=org1.id, broker_id=test_broker.id, role="admin")
    db_session.add_all([org1, mem1])
    await db_session.commit()

    token1 = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers1 = {
        "Authorization": f"Bearer {token1}",
        "X-WefyLabs-Organization-Id": str(org1.id)
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # ─────────────────────────────────────────────────────────────────────
        # Step 1: Create canonical deal for ₹18,000,000 Penthouse
        # ─────────────────────────────────────────────────────────────────────
        deal_payload = {
            "lead_id": str(test_lead.id),
            "deal_title": "Deepak Choudhury - Penthouse Deal",
            "current_stage": "opportunity",
            "agreed_price": 18000000.0,
            "currency": "INR",
            "commission_percentage": 2.0,
            "tags": ["luxury", "penthouse"]
        }
        res_create = await ac.post("/api/v1/deals", json=deal_payload, headers=headers1)
        assert res_create.status_code == 201
        deal_id = res_create.json()["id"]

        # Initial summary check: 1 active deal, ₹18M pipeline value, 0 booked value, 0 earned
        res_sum0 = await ac.get("/api/v1/deals/summary", headers=headers1)
        assert res_sum0.status_code == 200
        sum0 = res_sum0.json()
        assert sum0["total_active_deals"] == 1
        assert sum0["total_pipeline_value"] == 18000000.0
        assert sum0["booked_value"] == 0.0
        assert sum0["commission_pending"] == 0.0
        assert sum0["commission_earned"] == 0.0

        # ─────────────────────────────────────────────────────────────────────
        # Step 2: Accepted Offer without a Booking
        # ─────────────────────────────────────────────────────────────────────
        offer_payload = {
            "offer_price": 18000000.0,
            "currency": "INR",
            "listing_price": 19000000.0,
            "token_amount": 360000.0,
            "payment_plan": "10% token deposit, balance on handover"
        }
        res_offer = await ac.post(f"/api/v1/deals/{deal_id}/offers", json=offer_payload, headers=headers1)
        assert res_offer.status_code == 201

        res_accept = await ac.post(
            f"/api/v1/deals/{deal_id}/offers/respond",
            json={"action": "ACCEPT"},
            headers=headers1
        )
        assert res_accept.status_code == 200
        assert res_accept.json()["offer_status"] == "ACCEPTED"

        # Offer accepted must NOT create a booking or realize revenue
        res_sum_offer = await ac.get("/api/v1/deals/summary", headers=headers1)
        sum_offer = res_sum_offer.json()
        assert sum_offer["booked_value"] == 0.0
        assert sum_offer["commission_earned"] == 0.0
        assert sum_offer["commission_pending"] == 0.0

        # ─────────────────────────────────────────────────────────────────────
        # Step 3: Confirmed Booking with Token Deposit
        # ─────────────────────────────────────────────────────────────────────
        res_bk_req = await ac.post(
            f"/api/v1/deals/{deal_id}/bookings/request",
            json={
                "booked_price": 18000000.0,
                "currency": "INR",
                "token_amount": 360000.0,
                "payment_plan_type": "CONSTRUCTION_LINKED",
                "idempotency_key": f"bk-req-{uuid.uuid4()}"
            },
            headers=headers1
        )
        assert res_bk_req.status_code == 201
        approval_id = res_bk_req.json()["approval_id"]

        res_bk_conf = await ac.post(
            f"/api/v1/deals/{deal_id}/bookings/confirm",
            json={"approval_id": approval_id, "review_notes": "Token deposit verified by finance"},
            headers=headers1
        )
        assert res_bk_conf.status_code == 201
        assert res_bk_conf.json()["booking_status"] == "CONFIRMED"

        # Advance deal to booking stage
        await ac.post(
            f"/api/v1/deals/{deal_id}/stage",
            json={"target_stage": "booking"},
            headers=headers1
        )

        # Dashboard truthfulness check: Booked value is now ₹18M, token collected is ₹360k, but earned revenue is 0
        res_sum_bk = await ac.get("/api/v1/deals/summary", headers=headers1)
        sum_bk = res_sum_bk.json()
        assert sum_bk["booked_value"] == 18000000.0
        assert sum_bk["token_collected"] == 360000.0
        assert sum_bk["commission_earned"] == 0.0
        assert sum_bk["commission_pending"] == 0.0

        # ─────────────────────────────────────────────────────────────────────
        # Step 4: Record Commission with exact Decimal math, 10% TDS, 70/30 split
        # ─────────────────────────────────────────────────────────────────────
        comm_payload = {
            "transaction_price": 18000000.0,
            "currency": "INR",
            "commission_percentage": 2.0,
            "tax_rate_percentage": 10.0,
            "broker_split_percentage": 70.0,
            "agency_split_percentage": 30.0,
            "invoice_reference": "INV-PENT-2026-001",
            "idempotency_key": f"comm-idemp-{uuid.uuid4()}"
        }
        res_comm = await ac.post(f"/api/v1/deals/{deal_id}/commissions", json=comm_payload, headers=headers1)
        assert res_comm.status_code == 201
        comm_res_data = res_comm.json()

        # Exact Decimal Math Assertions:
        # Gross = 18,000,000 * 2% = 360,000
        # Tax = 360,000 * 10% = 36,000
        # Net = 360,000 - 36,000 = 324,000
        assert comm_res_data["gross_commission"] == 360000.0
        assert comm_res_data["tax_deducted"] == 36000.0
        assert comm_res_data["net_commission"] == 324000.0

        # Verify Splits (70/30 split)
        splits = comm_res_data["commission_splits"]
        broker_split = next(s for s in splits if s["recipient_role"] == "PRIMARY_BROKER")
        agency_split = next(s for s in splits if s["recipient_role"] == "AGENCY_POOL")

        assert broker_split["split_percentage"] == 70.0
        assert broker_split["gross_amount"] == 252000.0
        assert broker_split["net_amount"] == 226800.0

        assert agency_split["split_percentage"] == 30.0
        assert agency_split["gross_amount"] == 108000.0
        assert agency_split["net_amount"] == 97200.0

        # Sum of splits must exactly match gross and net
        assert Decimal(str(broker_split["gross_amount"])) + Decimal(str(agency_split["gross_amount"])) == Decimal("360000.0")
        assert Decimal(str(broker_split["net_amount"])) + Decimal(str(agency_split["net_amount"])) == Decimal("324000.0")

        # Check pipeline summary: commission_pending is ₹324,000, commission_earned is STILL 0
        res_sum_comm = await ac.get("/api/v1/deals/summary", headers=headers1)
        sum_comm = res_sum_comm.json()
        assert sum_comm["commission_pending"] == 324000.0
        assert sum_comm["commission_earned"] == 0.0

        # ─────────────────────────────────────────────────────────────────────
        # Step 5: Settle Commission (Manual Receipt Recording)
        # ─────────────────────────────────────────────────────────────────────
        settle_payload = {
            "settled_amount": 324000.0,
            "payment_reference": "UTR-HDFC-99081234",
            "payment_mode": "MANUAL_BANK_TRANSFER",
            "currency": "INR",
            "notes": "Verified against HDFC corporate account statement",
            "idempotency_key": "settle-penthouse-001"
        }
        res_settle = await ac.post(f"/api/v1/deals/{deal_id}/commissions/settle", json=settle_payload, headers=headers1)
        assert res_settle.status_code == 200
        settle_data = res_settle.json()
        assert settle_data["commission_status"] == "PAID"
        assert settle_data["settled_amount"] == 324000.0
        assert settle_data["payment_reference"] == "UTR-HDFC-99081234"
        assert settle_data["payment_mode"] == "MANUAL_BANK_TRANSFER"
        assert settle_data["paid_at"] is not None

        # Recheck pipeline summary: commission_pending is now 0, commission_earned is ₹324,000!
        res_sum_settled = await ac.get("/api/v1/deals/summary", headers=headers1)
        sum_settled = res_sum_settled.json()
        assert sum_settled["commission_pending"] == 0.0
        assert sum_settled["commission_earned"] == 324000.0

        # Verify DB Persistence for DealCommission and RevenueEvent
        db_comm = (await db_session.execute(
            select(DealCommission).where(DealCommission.deal_id == uuid.UUID(deal_id))
        )).scalars().first()
        assert db_comm is not None
        assert db_comm.status == "PAID"
        assert db_comm.payment_reference == "UTR-HDFC-99081234"
        assert db_comm.paid_at is not None

        # Verify RevenueEvent in Revenue Intelligence Ledger
        rev_events = (await db_session.execute(
            select(RevenueEvent).where(
                RevenueEvent.organization_id == org1.id,
                RevenueEvent.opportunity_id == uuid.UUID(deal_id)
            )
        )).scalars().all()
        assert len(rev_events) >= 1
        pay_event = next(e for e in rev_events if e.event_type == RevenueEventType.PAYMENT_RECEIVED)
        assert pay_event.amount == Decimal("324000.0")
        assert pay_event.currency == "INR"

        # ─────────────────────────────────────────────────────────────────────
        # Step 6: Idempotent Replay of Commission Settlement
        # ─────────────────────────────────────────────────────────────────────
        res_replay = await ac.post(f"/api/v1/deals/{deal_id}/commissions/settle", json=settle_payload, headers=headers1)
        assert res_replay.status_code == 200
        assert res_replay.json()["commission_status"] == "PAID"
        assert res_replay.json()["payment_reference"] == "UTR-HDFC-99081234"

        # Re-check summary: commission_earned is NOT doubled
        res_sum_replay = await ac.get("/api/v1/deals/summary", headers=headers1)
        assert res_sum_replay.json()["commission_earned"] == 324000.0

        # ─────────────────────────────────────────────────────────────────────
        # Step 7: Settlement Reversal
        # ─────────────────────────────────────────────────────────────────────
        res_reverse = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/reverse",
            json={"reason": "Audit correction: Commission receipt allocated to incorrect branch", "idempotency_key": "rev-01"},
            headers=headers1
        )
        assert res_reverse.status_code == 200
        assert res_reverse.json()["commission_status"] == "PENDING"

        # Verify reversal in summary: commission_pending is back to ₹324,000, commission_earned back to 0
        res_sum_rev = await ac.get("/api/v1/deals/summary", headers=headers1)
        assert res_sum_rev.json()["commission_pending"] == 324000.0
        assert res_sum_rev.json()["commission_earned"] == 0.0

        # Verify Refund Event was created
        refund_events = (await db_session.execute(
            select(RevenueEvent).where(
                RevenueEvent.organization_id == org1.id,
                RevenueEvent.opportunity_id == uuid.UUID(deal_id),
                RevenueEvent.event_type == RevenueEventType.REFUND_ISSUED
            )
        )).scalars().all()
        assert len(refund_events) == 1
        assert refund_events[0].amount == Decimal("324000.0")

        # ─────────────────────────────────────────────────────────────────────
        # Step 8: Commission Dispute Workflow
        # ─────────────────────────────────────────────────────────────────────
        res_dispute = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/dispute",
            json={"reason": "Developer disputed agreement clause 4.2 regarding brokerage timeline"},
            headers=headers1
        )
        assert res_dispute.status_code == 200
        assert res_dispute.json()["commission_status"] == "DISPUTED"
        assert "Developer disputed" in res_dispute.json()["dispute_reason"]

        # Attempt to settle disputed commission must be REJECTED
        res_settle_disputed = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json=settle_payload,
            headers=headers1
        )
        assert res_settle_disputed.status_code == 400
        assert "cannot be settled while in status DISPUTED" in res_settle_disputed.json()["detail"]


@pytest.mark.asyncio
async def test_phase9_3_financial_guardrails_and_precision(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    org = Organization(id=uuid.uuid4(), name="Guardrail Agency", slug=f"guard-{uuid.uuid4().hex[:6]}")
    mem = OrganizationMember(organization_id=org.id, broker_id=test_broker.id, role="admin")
    db_session.add_all([org, mem])
    await db_session.commit()

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-WefyLabs-Organization-Id": str(org.id)
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        deal_payload = {
            "lead_id": str(test_lead.id),
            "deal_title": "Currency & Precision Guard Deal",
            "current_stage": "opportunity",
            "agreed_price": 5000000.0,
            "currency": "AED",
            "commission_percentage": 2.0
        }
        res_create = await ac.post("/api/v1/deals", json=deal_payload, headers=headers)
        deal_id = res_create.json()["id"]

        # 1. Currency Mismatch on Commission Recording (AED Deal, USD Commission)
        res_curr_mismatch = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions",
            json={
                "transaction_price": 5000000.0,
                "currency": "USD",
                "commission_percentage": 2.0,
                "idempotency_key": "curr-mismatch"
            },
            headers=headers
        )
        assert res_curr_mismatch.status_code == 400
        assert "Currency mismatch" in res_curr_mismatch.json()["detail"]

        # 2. Excess Deductions exceeding Gross Commission
        res_excess_deduct = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions",
            json={
                "transaction_price": 5000000.0,
                "currency": "AED",
                "commission_percentage": 2.0,
                "tax_deducted": 150000.0,  # Gross is 100,000; tax of 150,000 exceeds gross
                "idempotency_key": "excess-deduct"
            },
            headers=headers
        )
        assert res_excess_deduct.status_code == 400
        assert "cannot exceed gross commission" in res_excess_deduct.json()["detail"]

        # 3. Valid Commission Recording
        res_valid_comm = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions",
            json={
                "transaction_price": 5000000.0,
                "currency": "AED",
                "commission_percentage": 2.0,
                "tax_rate_percentage": 5.0,
                "idempotency_key": "valid-comm"
            },
            headers=headers
        )
        assert res_valid_comm.status_code == 201
        # Gross = 100,000, Tax = 5,000, Net = 95,000
        assert res_valid_comm.json()["net_commission"] == 95000.0

        # Partial receipt must not mark the entire commission PAID.
        res_partial_settle = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 50000.0,
                "payment_reference": "PARTIAL-REF",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "currency": "AED",
                "idempotency_key": "partial-settle"
            },
            headers=headers
        )
        assert res_partial_settle.status_code == 400
        assert "Partial settlement is not supported" in res_partial_settle.json()["detail"]

        # 4. Over-settlement attempt (Trying to settle 120,000 when net is 95,000)
        res_over_settle = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 120000.0,
                "payment_reference": "OVER-REF",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "currency": "AED",
                "idempotency_key": "over-settle"
            },
            headers=headers
        )
        assert res_over_settle.status_code == 400
        assert "cannot exceed expected net commission" in res_over_settle.json()["detail"]

        # 5. Currency Mismatch on Settlement
        res_settle_curr_mismatch = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 95000.0,
                "payment_reference": "REF-INR",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "currency": "INR",  # Deal and commission are AED
                "idempotency_key": "settle-curr-mismatch"
            },
            headers=headers
        )
        assert res_settle_curr_mismatch.status_code == 400
        assert "Currency mismatch" in res_settle_curr_mismatch.json()["detail"]

        # 6. Non-positive Settlement Amount
        res_zero_settle = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 0.0,
                "payment_reference": "ZERO-REF",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "currency": "AED",
                "idempotency_key": "zero-settle"
            },
            headers=headers
        )
        assert res_zero_settle.status_code in (400, 422)
        assert "greater than 0" in str(res_zero_settle.json()).lower() or "positive" in str(res_zero_settle.json()).lower()


@pytest.mark.asyncio
async def test_phase9_3_tenant_isolation_on_financial_mutations(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead
):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Org A (Owner)
    org_a = Organization(id=uuid.uuid4(), name="Org Alpha", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    mem_a = OrganizationMember(organization_id=org_a.id, broker_id=test_broker.id, role="admin")

    # Org B (Attacker / Unauthorized Tenant)
    org_b = Organization(id=uuid.uuid4(), name="Org Beta", slug=f"beta-{uuid.uuid4().hex[:6]}")
    broker_b = Broker(
        id=uuid.uuid4(),
        email=f"broker-b-{uuid.uuid4().hex[:6]}@example.com",
        name="Broker B",
        password_hash="fake"
    )
    mem_b = OrganizationMember(organization_id=org_b.id, broker_id=broker_b.id, role="admin")

    db_session.add_all([org_a, mem_a, org_b, broker_b, mem_b])
    await db_session.commit()

    token_a = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers_a = {"Authorization": f"Bearer {token_a}", "X-WefyLabs-Organization-Id": str(org_a.id)}

    token_b = create_access_token({"sub": broker_b.email, "email": broker_b.email})
    headers_b = {"Authorization": f"Bearer {token_b}", "X-WefyLabs-Organization-Id": str(org_b.id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Org A creates deal and records commission
        res_create = await ac.post(
            "/api/v1/deals",
            json={
                "lead_id": str(test_lead.id),
                "deal_title": "Isolated Commercial Deal",
                "current_stage": "opportunity",
                "agreed_price": 2000000.0,
                "currency": "AED",
                "commission_percentage": 2.0
            },
            headers=headers_a
        )
        deal_id = res_create.json()["id"]

        await ac.post(
            f"/api/v1/deals/{deal_id}/commissions",
            json={
                "transaction_price": 2000000.0,
                "currency": "AED",
                "commission_percentage": 2.0,
                "idempotency_key": "comm-iso"
            },
            headers=headers_a
        )

        # 1. Org B cannot read Org A's deal
        res_read_cross = await ac.get(f"/api/v1/deals/{deal_id}", headers=headers_b)
        assert res_read_cross.status_code == 404

        # 2. Org B cannot settle Org A's commission
        res_settle_cross = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 40000.0,
                "payment_reference": "MALICIOUS-SETTLE",
                "idempotency_key": "cross-settle"
            },
            headers=headers_b
        )
        assert res_settle_cross.status_code == 400
        assert "not found" in res_settle_cross.json()["detail"].lower()

        # 3. Org B cannot dispute Org A's commission
        res_dispute_cross = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/dispute",
            json={"reason": "Unauthorized dispute attempt"},
            headers=headers_b
        )
        assert res_dispute_cross.status_code == 400
        assert "not found" in res_dispute_cross.json()["detail"].lower()


@pytest.mark.asyncio
async def test_phase9_3_unverified_manual_settlement_and_provenance_separation(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead
):
    """
    Enforce truthful revenue recognition:
    - MANUAL_UNVERIFIED settlement transitions to RECORDED_UNVERIFIED, NOT PAID.
    - commission_unverified increments, while commission_earned remains 0.0.
    - RevenueEvent is flagged as requires_audit_review=True, is_confirmed=False.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    org = Organization(id=uuid.uuid4(), name="Provenance Integrity Org", slug=f"prov-{uuid.uuid4().hex[:6]}")
    member = OrganizationMember(organization_id=org.id, broker_id=test_broker.id, role="admin")
    db_session.add_all([org, member])
    await db_session.commit()

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}", "X-WefyLabs-Organization-Id": str(org.id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_deal = await ac.post(
            "/api/v1/deals",
            json={
                "lead_id": str(test_lead.id),
                "deal_title": "Unverified Receipt Deal",
                "current_stage": "opportunity",
                "agreed_price": 10000000.0,
                "currency": "INR",
                "commission_percentage": 2.0
            },
            headers=headers
        )
        deal_id = res_deal.json()["id"]

        # Record commission: Gross = 200,000, 2% Tax/TDS = 4,000, Net = 196,000
        res_comm = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions",
            json={
                "transaction_price": 10000000.0,
                "currency": "INR",
                "commission_percentage": 2.0,
                "tax_rate_percentage": 2.0,
                "idempotency_key": "comm-prov-001"
            },
            headers=headers
        )
        assert res_comm.status_code == 201
        assert res_comm.json()["gross_commission"] == 200000.0
        assert res_comm.json()["tax_deducted"] == 4000.0
        assert res_comm.json()["net_commission"] == 196000.0

        # Settle with unverified manual bank transfer without accountant audit notes
        settle_payload = {
            "settled_amount": 196000.0,
            "payment_reference": "UTR-UNVERIF-1001",
            "payment_mode": "MANUAL_BANK_TRANSFER",
            "provenance": "MANUAL_UNVERIFIED",
            "currency": "INR",
            "notes": "Agent uploaded deposit slip screenshot",
            "idempotency_key": "settle-unverif-001"
        }
        res_settle = await ac.post(f"/api/v1/deals/{deal_id}/commissions/settle", json=settle_payload, headers=headers)
        assert res_settle.status_code == 200
        settle_data = res_settle.json()
        assert settle_data["commission_status"] == "RECORDED_UNVERIFIED"
        assert settle_data["provenance"] == "MANUAL_UNVERIFIED"

        # Check Pipeline Summary: commission_unverified must be 196,000; commission_earned must be 0!
        res_summary = await ac.get("/api/v1/deals/summary", headers=headers)
        summary_data = res_summary.json()
        assert summary_data["commission_unverified"] == 196000.0
        assert summary_data["commission_earned"] == 0.0

        # Check RevenueEvent requires_audit_review
        rev_events = (await db_session.execute(
            select(RevenueEvent).where(
                RevenueEvent.organization_id == org.id,
                RevenueEvent.opportunity_id == uuid.UUID(deal_id)
            )
        )).scalars().all()
        assert len(rev_events) >= 1
        pay_event = next(e for e in rev_events if e.event_type == RevenueEventType.PAYMENT_RECEIVED)
        assert pay_event.payload.get("is_confirmed") is False
        assert pay_event.payload.get("requires_audit_review") is True

        # Reversal works on RECORDED_UNVERIFIED
        res_rev = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/reverse",
            json={"reason": "Incorrect deposit slip rejected during financial review", "idempotency_key": "rev-unverif-01"},
            headers=headers
        )
        assert res_rev.status_code == 200
        assert res_rev.json()["commission_status"] == "PENDING"

        # After reversal, commission_unverified drops back to 0
        res_sum2 = await ac.get("/api/v1/deals/summary", headers=headers)
        assert res_sum2.json()["commission_unverified"] == 0.0


@pytest.mark.asyncio
async def test_phase9_3_anti_replay_duplicate_payment_reference_blocked(
    db_session: AsyncSession, test_broker: Broker, test_lead: Lead
):
    """
    Ensure anti-replay guardrail:
    A payment reference (e.g. bank UTR) cannot be reused to settle a different deal commission.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    org = Organization(id=uuid.uuid4(), name="Anti-Replay Org", slug=f"replay-{uuid.uuid4().hex[:6]}")
    member = OrganizationMember(organization_id=org.id, broker_id=test_broker.id, role="admin")
    db_session.add_all([org, member])
    await db_session.commit()

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}", "X-WefyLabs-Organization-Id": str(org.id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create Deal 1 and record commission
        res_d1 = await ac.post(
            "/api/v1/deals",
            json={
                "lead_id": str(test_lead.id),
                "deal_title": "Deal 1 - Original Settlement",
                "current_stage": "opportunity",
                "agreed_price": 5000000.0,
                "currency": "INR",
                "commission_percentage": 2.0
            },
            headers=headers
        )
        deal1_id = res_d1.json()["id"]
        await ac.post(
            f"/api/v1/deals/{deal1_id}/commissions",
            json={
                "transaction_price": 5000000.0,
                "currency": "INR",
                "commission_percentage": 2.0,
                "tax_rate_percentage": 2.0,
                "idempotency_key": "comm-d1"
            },
            headers=headers
        )

        # Create Deal 2 and record commission
        res_d2 = await ac.post(
            "/api/v1/deals",
            json={
                "lead_id": str(test_lead.id),
                "deal_title": "Deal 2 - Duplicate Settlement Target",
                "current_stage": "opportunity",
                "agreed_price": 5000000.0,
                "currency": "INR",
                "commission_percentage": 2.0
            },
            headers=headers
        )
        deal2_id = res_d2.json()["id"]
        await ac.post(
            f"/api/v1/deals/{deal2_id}/commissions",
            json={
                "transaction_price": 5000000.0,
                "currency": "INR",
                "commission_percentage": 2.0,
                "tax_rate_percentage": 2.0,
                "idempotency_key": "comm-d2"
            },
            headers=headers
        )

        # Settle Deal 1 with reference UTR-DUPLICATE-CHECK-999
        res_settle1 = await ac.post(
            f"/api/v1/deals/{deal1_id}/commissions/settle",
            json={
                "settled_amount": 98000.0,
                "payment_reference": "UTR-DUPLICATE-CHECK-999",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "provenance": "MANUAL_REVIEWED",
                "currency": "INR",
                "notes": "Verified against bank statement",
                "idempotency_key": "settle-d1"
            },
            headers=headers
        )
        assert res_settle1.status_code == 200

        # Attempt to settle Deal 2 with the SAME reference UTR-DUPLICATE-CHECK-999 must fail closed
        res_settle2 = await ac.post(
            f"/api/v1/deals/{deal2_id}/commissions/settle",
            json={
                "settled_amount": 98000.0,
                "payment_reference": "UTR-DUPLICATE-CHECK-999",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "provenance": "MANUAL_REVIEWED",
                "currency": "INR",
                "notes": "Attempting reuse of UTR with verified statement",
                "idempotency_key": "settle-d2"
            },
            headers=headers
        )
        assert res_settle2.status_code == 400
        assert "has already been used in another settlement" in res_settle2.json()["detail"]


@pytest.mark.asyncio
async def test_phase9_3_settlement_reviewer_authorization_and_role_escalation_blocked(
    db_session: AsyncSession, test_lead: Lead
):
    """
    Ensure authorization integrity:
      1. Ordinary agent (role='agent') cannot certify manual receipts as MANUAL_REVIEWED (HTTP 403 Forbidden).
      2. Caller cannot self-assert PROVIDER_CONFIRMED without automated gateway/webhook evidence (HTTP 400).
      3. MANUAL_REVIEWED requires supporting document URL or verified bank statement notes (HTTP 400).
      4. Authorized reviewer (role='finance') certifies MANUAL_REVIEWED with evidence, persisting audit metadata.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    org = Organization(id=uuid.uuid4(), name="Auth Security Org", slug=f"authsec-{uuid.uuid4().hex[:6]}")
    # Agent broker
    agent_broker = Broker(
        id=uuid.uuid4(),
        email=f"agent-{uuid.uuid4().hex[:6]}@agency.com",
        name="Agent Smith",
        password_hash="pw"
    )
    agent_member = OrganizationMember(organization_id=org.id, broker_id=agent_broker.id, role="agent")

    # Finance reviewer broker
    finance_broker = Broker(
        id=uuid.uuid4(),
        email=f"finance-{uuid.uuid4().hex[:6]}@agency.com",
        name="Fiona Finance",
        password_hash="pw"
    )
    finance_member = OrganizationMember(organization_id=org.id, broker_id=finance_broker.id, role="finance")

    db_session.add_all([org, agent_broker, agent_member, finance_broker, finance_member])
    await db_session.commit()

    agent_token = create_access_token({"sub": agent_broker.email, "email": agent_broker.email})
    agent_headers = {"Authorization": f"Bearer {agent_token}", "X-WefyLabs-Organization-Id": str(org.id)}

    finance_token = create_access_token({"sub": finance_broker.email, "email": finance_broker.email})
    finance_headers = {"Authorization": f"Bearer {finance_token}", "X-WefyLabs-Organization-Id": str(org.id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create Deal and Commission
        res_d = await ac.post(
            "/api/v1/deals",
            json={
                "lead_id": str(test_lead.id),
                "deal_title": "Settlement Auth Escalation Test Deal",
                "current_stage": "opportunity",
                "agreed_price": 10000000.0,
                "currency": "INR",
                "commission_percentage": 2.0
            },
            headers=agent_headers
        )
        assert res_d.status_code == 201
        deal_id = res_d.json()["id"]

        await ac.post(
            f"/api/v1/deals/{deal_id}/commissions",
            json={
                "transaction_price": 10000000.0,
                "currency": "INR",
                "commission_percentage": 2.0,
                "tax_rate_percentage": 2.0,
                "idempotency_key": "comm-auth-01"
            },
            headers=agent_headers
        )

        # Attack 1: Ordinary agent attempts to self-certify receipt as MANUAL_REVIEWED -> Rejected with 403 Forbidden!
        res_agent_escalate = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 196000.0,
                "payment_reference": "UTR-AGENT-ESCALATE-001",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "provenance": "MANUAL_REVIEWED",
                "currency": "INR",
                "notes": "Verified against statement (agent self-asserting)",
                "settlement_evidence_url": "https://vault.agency.com/slip.pdf",
                "idempotency_key": "settle-agent-attack"
            },
            headers=agent_headers
        )
        assert res_agent_escalate.status_code == 403
        assert "Unauthorized reviewer" in res_agent_escalate.json()["detail"]

        # Attack 2: Caller attempts to self-assert PROVIDER_CONFIRMED for a manual transfer -> Rejected with 400 Bad Request!
        res_prov_confirmed_attack = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 196000.0,
                "payment_reference": "UTR-FAKE-GATEWAY-001",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "provenance": "PROVIDER_CONFIRMED",
                "currency": "INR",
                "notes": "Self claiming provider confirmation without gateway payload",
                "idempotency_key": "settle-prov-attack"
            },
            headers=finance_headers
        )
        assert res_prov_confirmed_attack.status_code == 400
        assert "Cannot self-assert PROVIDER_CONFIRMED" in res_prov_confirmed_attack.json()["detail"]

        # Attack 3: Finance reviewer attempts MANUAL_REVIEWED without evidence or audit notes -> Rejected with 400 Bad Request!
        res_no_evidence = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 196000.0,
                "payment_reference": "UTR-NO-EVIDENCE-001",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "provenance": "MANUAL_REVIEWED",
                "currency": "INR",
                "notes": "No proof attached whatsoever",
                "settlement_evidence_url": None,
                "idempotency_key": "settle-no-evidence"
            },
            headers=finance_headers
        )
        assert res_no_evidence.status_code == 400
        assert "Missing settlement evidence" in res_no_evidence.json()["detail"]

        # Success Case: Authorized Finance reviewer certifies receipt as MANUAL_REVIEWED with verified statement notes & evidence URL
        res_legit_settle = await ac.post(
            f"/api/v1/deals/{deal_id}/commissions/settle",
            json={
                "settled_amount": 196000.0,
                "payment_reference": "UTR-FINANCE-VERIFIED-777",
                "payment_mode": "MANUAL_BANK_TRANSFER",
                "provenance": "MANUAL_REVIEWED",
                "currency": "INR",
                "notes": "Audited and verified against HDFC corporate statement",
                "settlement_evidence_url": "https://vault.wefylabs.com/receipts/hdfc-stmt-777.pdf",
                "idempotency_key": "settle-finance-legit"
            },
            headers=finance_headers
        )
        assert res_legit_settle.status_code == 200
        settle_json = res_legit_settle.json()
        assert settle_json["commission_status"] == "PAID"
        assert settle_json["provenance"] == "MANUAL_REVIEWED"

        # Verify audit lineage and reviewer identity in database
        rev_events = (await db_session.execute(
            select(RevenueEvent).where(
                RevenueEvent.organization_id == org.id,
                RevenueEvent.opportunity_id == uuid.UUID(deal_id)
            )
        )).scalars().all()
        pay_event = next(e for e in rev_events if e.event_type == RevenueEventType.PAYMENT_RECEIVED)
        assert pay_event.payload.get("is_confirmed") is True
        assert pay_event.payload.get("reviewed_by_id") == str(finance_broker.id)
        assert pay_event.payload.get("reviewed_at") is not None
        assert pay_event.payload.get("settlement_evidence_url") == "https://vault.wefylabs.com/receipts/hdfc-stmt-777.pdf"


