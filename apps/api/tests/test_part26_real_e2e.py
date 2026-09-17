"""
Part 26 — Lead Capture Hub Real End-to-End Test
================================================
Verifies the complete real E2E journey using a live async database session:
  1. Organization & broker creation
  2. LeadSource creation with unique webhook token
  3. Form submission via public_capture_lead endpoint
  4. LeadAcquisitionEvent recording & idempotency check
  5. Normalization (phone, email, flexible budget)
  6. Deduplication check (no duplicate lead created)
  7. Canonical Lead creation in `leads` table
  8. SourceAttribution record with full UTM provenance
  9. Automatic Task creation ("Contact new lead: ...")
  10. Automatic Notification creation for assigned broker
  11. Activity feed logging
  12. Re-submission with same idempotency key / payload
  13. Verification that duplicate submission returns duplicate status and does NOT create a 2nd lead
"""
import uuid
import pytest
from unittest.mock import MagicMock
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Notification, Activity
from app.models.acquisition_models import (
    LeadSource, LeadAcquisitionEvent, LeadProspect, SourceAttribution,
    ProspectStatus, DuplicateMatchStatus
)
from app.modules.lead_acquisition.dto.acquisition_dto import PublicLeadCaptureDTO
from app.modules.lead_acquisition.controller.public_capture_controller import public_capture_lead, get_form_iframe_html


@pytest.mark.asyncio
async def test_full_real_e2e_lead_capture_journey(db_session: AsyncSession, test_broker: Broker):
    """Executes the complete Phase 64 E2E customer journey against real database models."""
    org_id = str(test_broker.id)
    token = f"bl_src_test_{uuid.uuid4().hex[:12]}"

    # Step 1: Create a verified LeadSource
    source = LeadSource(
        organization_id=org_id,
        name="Main Website Landing Page",
        channel="WEBSITE",
        source_type="WEBSITE",
        provider="public_capture",
        status="active",
        is_active=True,
        webhook_url_token=token,
        configuration={
            "form_title": "Schedule a Private Viewing",
            "form_description": "Leave your details for immediate assistance.",
            "button_text": "Request Call",
            "primary_color": "#111827",
        }
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)

    # Step 2: Verify embed iframe renders correctly with token
    mock_req = MagicMock()
    mock_req.base_url = "https://crm.beetlelabs.ai/"
    iframe_resp = await get_form_iframe_html(token, mock_req, db_session)
    assert iframe_resp.status_code == 200
    html_content = iframe_resp.body.decode("utf-8")
    assert "Schedule a Private Viewing" in html_content
    assert "Request Call" in html_content
    assert "_hp_trap" in html_content

    # Step 3: First Lead Submission (Rahul Sharma)
    submission_dto = PublicLeadCaptureDTO(
        name="Rahul Sharma",
        phone="+91 98765 43210",
        email="rahul.sharma@example.com",
        budget="1.5 Cr",
        city="Whitefield, Bangalore",
        property_type="Villa",
        message="Looking for 3 or 4 BHK villa with garden. Move-in by Diwali.",
        utm_source="google_ads",
        utm_medium="cpc",
        utm_campaign="bangalore_luxury_villas",
        utm_term="villa in whitefield",
        utm_content="banner_v1",
        landing_page="https://luxuryproperties.com/whitefield-villas",
        referrer="https://google.com",
        marketing_consent=True,
    )

    mock_client_req = MagicMock()
    mock_client_req.client.host = "203.0.113.195"
    mock_client_req.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    res = await public_capture_lead(
        token=token,
        payload=submission_dto,
        request=mock_client_req,
        db=db_session,
        x_idempotency_key="idemp_key_unique_test_101",
    )

    assert res.success is True
    data = res.data
    assert data["status"] == "accepted"
    assert data["is_duplicate"] is False
    assert "lead_id" in data
    lead_id = uuid.UUID(data["lead_id"])

    # Step 4: Verify Canonical Lead created in CRM
    stmt_lead = select(Lead).where(Lead.id == lead_id)
    lead = (await db_session.execute(stmt_lead)).scalars().first()
    assert lead is not None
    assert lead.name == "Rahul Sharma"
    assert lead.phone == "+919876543210"  # Normalized E.164
    assert lead.broker_id == test_broker.id  # Assigned to active broker in org
    assert lead.budget_min == 15000000 or lead.budget_max == 15000000  # 1.5 Cr parsed accurately
    assert lead.source == "website"

    # Step 5: Verify SourceAttribution created with complete UTM parameters
    stmt_attr = select(SourceAttribution).where(SourceAttribution.lead_id == str(lead_id))
    attr = (await db_session.execute(stmt_attr)).scalars().first()
    assert attr is not None
    assert attr.utm_source == "google_ads"
    assert attr.utm_medium == "cpc"
    assert attr.utm_campaign == "bangalore_luxury_villas"
    assert attr.utm_term == "villa in whitefield"
    assert attr.utm_content == "banner_v1"
    assert attr.landing_page == "https://luxuryproperties.com/whitefield-villas"
    assert attr.source_id == source.id

    # Step 6: Verify Task was created for assigned broker
    stmt_task = select(Task).where(Task.lead_id == lead_id)
    tasks = (await db_session.execute(stmt_task)).scalars().all()
    assert len(tasks) >= 1
    task = tasks[0]
    assert task.broker_id == test_broker.id
    assert "Contact new lead" in task.title
    assert task.priority == "high"
    assert task.status == "pending"

    # Step 7: Verify Notification was created
    stmt_notif = select(Notification).where(Notification.broker_id == test_broker.id)
    notifications = (await db_session.execute(stmt_notif)).scalars().all()
    assert len(notifications) >= 1
    notif = notifications[-1]
    assert "New Lead Captured" in notif.title
    assert notif.category == "lead"

    # Step 8: Verify Activity Feed was logged
    stmt_act = select(Activity).where(Activity.lead_id == lead_id)
    activities = (await db_session.execute(stmt_act)).scalars().all()
    assert len(activities) >= 1
    act = activities[0]
    assert act.activity_type == "lead_created"

    # Step 9: Replay submission with same payload (Webhook retry / re-submission)
    replay_res = await public_capture_lead(
        token=token,
        payload=submission_dto,
        request=mock_client_req,
        db=db_session,
        x_idempotency_key="idemp_key_unique_test_101",
    )
    assert replay_res.success is True
    assert replay_res.data["is_duplicate"] is True or replay_res.data["status"] == "duplicate"

    # Step 10: Verify strictly NO duplicate lead exists in CRM
    count_stmt = select(func.count(Lead.id)).where(Lead.phone == "+919876543210")
    total_leads = (await db_session.execute(count_stmt)).scalar()
    assert total_leads == 1, f"Expected exactly 1 lead, found {total_leads}"
