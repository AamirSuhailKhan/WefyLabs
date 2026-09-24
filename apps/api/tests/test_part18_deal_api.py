"""
Part 18 — Real Estate Deal, Booking & Transaction OS: REST API Tests
====================================================================
Validates all versioned endpoints under /api/v1/deals:
  1. Pipeline summary metrics
  2. Create deal
  3. List deals with stage filtering
  4. Fetch deal workspace details
  5. Stage progression
  6. Offer submission and response (accept/counter)
  7. Property reservation
  8. Booking confirmation approval flow (request & sign-off)
  9. Commission recording with split details
  10. Closing creation & complete deal won
  11. Post-sale customer feedback & revenue learning signals
  12. Statutory document checklist attachment
  13. Immutable commercial audit trail retrieval
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token


@pytest.mark.asyncio
async def test_part18_deals_api_full_journey(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Pipeline Summary Initial
        res_sum = await ac.get("/api/v1/deals/summary", headers=headers)
        assert res_sum.status_code == 200
        sum_data = res_sum.json()
        assert "total_active_deals" in sum_data
        assert "deals_by_stage" in sum_data

        # 2. Create Deal
        deal_payload = {
            "lead_id": str(test_lead.id),
            "deal_title": "Emaar Beachfront Luxury Unit",
            "current_stage": "opportunity",
            "agreed_price": 4200000.0,
            "currency": "AED",
            "commission_percentage": 2.5,
            "tags": ["waterfront", "luxury"]
        }
        res_create = await ac.post("/api/v1/deals", json=deal_payload, headers=headers)
        assert res_create.status_code == 201
        deal_data = res_create.json()
        deal_id = deal_data["id"]
        assert deal_data["deal_title"] == "Emaar Beachfront Luxury Unit"
        assert deal_data["current_stage"] == "opportunity"
        assert deal_data["deal_reference"].startswith("WL-")

        # 3. List Deals
        res_list = await ac.get("/api/v1/deals", headers=headers)
        assert res_list.status_code == 200
        deals_list = res_list.json()
        assert len(deals_list) >= 1
        assert any(d["id"] == deal_id for d in deals_list)

        # 4. Advance Stage to Negotiation
        res_adv = await ac.post(
            f"/api/v1/deals/{deal_id}/stage",
            json={"target_stage": "negotiation", "reason": "Client requested in-person pricing meeting"},
            headers=headers
        )
        assert res_adv.status_code == 200
        assert res_adv.json()["current_stage"] == "negotiation"

        # 5. Submit Offer
        offer_payload = {
            "offer_price": 4000000.0,
            "currency": "AED",
            "listing_price": 4200000.0,
            "special_conditions": "Includes 2 parking bays"
        }
        res_offer = await ac.post(f"/api/v1/deals/{deal_id}/offers", json=offer_payload, headers=headers)
        assert res_offer.status_code == 201
        assert res_offer.json()["offer_status"] == "SUBMITTED"

        # 6. Counter & Accept Offer
        res_accept = await ac.post(
            f"/api/v1/deals/{deal_id}/offers/respond",
            json={"action": "ACCEPT"},
            headers=headers
        )
        assert res_accept.status_code == 200
        assert res_accept.json()["offer_status"] == "ACCEPTED"

        # 7. Advance to Reservation
        await ac.post(
            f"/api/v1/deals/{deal_id}/stage",
            json={"target_stage": "offer"},
            headers=headers
        )
        await ac.post(
            f"/api/v1/deals/{deal_id}/stage",
            json={"target_stage": "reservation"},
            headers=headers
        )

        # 8. Create Reservation
        res_reserve = await ac.post(
            f"/api/v1/deals/{deal_id}/reservations",
            json={
                "reservation_amount": 50000.0,
                "currency": "AED",
                "customer_name": "Test Client"
            },
            headers=headers
        )
        assert res_reserve.status_code == 201
        assert res_reserve.json()["status"] == "success"

        # 9. Request Booking Approval (Human-in-the-loop Gate)
        booking_payload = {
            "booked_price": 4000000.0,
            "currency": "AED",
            "token_amount": 200000.0,
            "payment_plan_type": "INSTALLMENT",
            "idempotency_key": f"bk-idemp-{uuid.uuid4()}"
        }
        res_bk_req = await ac.post(
            f"/api/v1/deals/{deal_id}/bookings/request",
            json=booking_payload,
            headers=headers
        )
        assert res_bk_req.status_code == 201
        approval_id = res_bk_req.json()["approval_id"]
        assert res_bk_req.json()["status"] == "PENDING_APPROVAL"

        # 10. Approve & Confirm Booking
        res_bk_confirm = await ac.post(
            f"/api/v1/deals/{deal_id}/bookings/confirm",
            json={"approval_id": approval_id, "review_notes": "Manager confirmed token payment"},
            headers=headers
        )
        assert res_bk_confirm.status_code == 201
        assert res_bk_confirm.json()["booking_status"] == "CONFIRMED"
        assert res_bk_confirm.json()["booking_reference"].startswith("BK-")

        # 11. Advance to Booking stage
        res_adv_bk = await ac.post(
            f"/api/v1/deals/{deal_id}/stage",
            json={"target_stage": "booking"},
            headers=headers
        )
        assert res_adv_bk.status_code == 200

        # 12. Record Commission
        comm_payload = {
            "transaction_price": 4000000.0,
            "currency": "AED",
            "commission_percentage": 2.5,
            "tax_deducted": 5000.0,
            "invoice_reference": "INV-EM-001",
            "idempotency_key": f"comm-idemp-{uuid.uuid4()}"
        }
        res_comm = await ac.post(f"/api/v1/deals/{deal_id}/commissions", json=comm_payload, headers=headers)
        assert res_comm.status_code == 201
        assert res_comm.json()["gross_commission"] == 100000.0
        assert res_comm.json()["net_commission"] == 95000.0

        # 13. Create Closing
        closing_payload = {
            "registration_authority": "DLD",
            "registration_number": "DLD-2026-9901",
            "title_deed_number": "TD-2026-0012"
        }
        res_closing = await ac.post(f"/api/v1/deals/{deal_id}/closings", json=closing_payload, headers=headers)
        assert res_closing.status_code == 201
        assert res_closing.json()["closing_status"] == "IN_PROGRESS"

        # 14. Complete Closing -> Deal Won
        res_complete = await ac.post(f"/api/v1/deals/{deal_id}/closings/complete", headers=headers)
        assert res_complete.status_code == 200
        assert res_complete.json()["deal_status"] == "CLOSED_WON"

        # 15. Record Post-Sale
        post_sale_payload = {
            "customer_satisfaction_score": 10,
            "nps_score": 90,
            "feedback_text": "World class real estate advisory",
            "referral_given": True,
            "success_factors": ["ai_agent_speed", "seamless_booking"]
        }
        res_ps = await ac.post(f"/api/v1/deals/{deal_id}/post-sale", json=post_sale_payload, headers=headers)
        assert res_ps.status_code == 201
        assert res_ps.json()["status"] == "success"

        # 16. Add Statutory Document
        doc_payload = {
            "document_type": "TITLE_DEED",
            "document_name": "Registered Title Deed.pdf",
            "required_at_stage": "closing",
            "file_url": "https://storage.wefylabs.com/deeds/td-0012.pdf"
        }
        res_doc = await ac.post(f"/api/v1/deals/{deal_id}/documents", json=doc_payload, headers=headers)
        assert res_doc.status_code == 201
        assert res_doc.json()["document_status"] == "UPLOADED"

        # 17. Get Full Deal Details
        res_detail = await ac.get(f"/api/v1/deals/{deal_id}", headers=headers)
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["id"] == deal_id
        assert detail_data["status"] == "CLOSED_WON"
        assert detail_data["offer"] is not None
        assert detail_data["reservation"] is not None
        assert detail_data["booking"] is not None
        assert detail_data["commission"] is not None
        assert detail_data["closing"] is not None
        assert detail_data["post_sale"] is not None
        assert len(detail_data["documents"]) >= 1

        # 18. Retrieve Commercial Audit Trail
        res_audit = await ac.get(f"/api/v1/deals/{deal_id}/audit", headers=headers)
        assert res_audit.status_code == 200
        audit_entries = res_audit.json()
        assert len(audit_entries) >= 5
        event_types = [e["event_type"] for e in audit_entries]
        assert "deal.created" in event_types
        assert "deal.closed_won" in event_types

    app.dependency_overrides.clear()
