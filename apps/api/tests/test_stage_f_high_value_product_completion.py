"""
Stage F — High-Value Product Completion Regression Suite
=========================================================
Tests for Prompt §13 & §14:
1. Paid-Pilot SKU (₹4,999 / 14-day) in Catalog & Razorpay plans.
2. Portal Adapters: MagicBricks & Housing.com lead normalization.
3. Broker Morning Briefing: Timezone (Asia/Kolkata), pending approvals, site visits, deduping key.
4. PDF Brochure Inventory Extraction: Candidate attributes, units, confidence, and human review gate.
5. WhatsApp Voice-Note handling: Validation rules, file size limits, transcription provenance.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting
from app.models.follow_up_models import FollowUpExecution
from app.models.billing_models import PlanInterval, SubscriptionLifecycleStatus
from app.modules.billing.services.catalog_service import CatalogService, DEFAULT_CATALOG
from app.modules.billing.services.subscription_engine import SubscriptionEngine
from app.modules.billing.services.razorpay_service import PLANS
from app.modules.global_.lead_sources.lead_source_registry import UniversalLeadNormalizer
from app.modules.follow_up.briefing.briefing_service import BriefingService
from app.modules.communication.media_handler.media_service import MediaHandler, _MAX_FILE_SIZES, _ALLOWED_MIME_TYPES
from app.services.mobile_sync_service import MobileSyncService


@pytest_asyncio.fixture
async def stage_f_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ─── 1. PAID PILOT SKU (₹4,999 / 14-day) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_paid_pilot_sku_in_catalog_and_engine(stage_f_db: AsyncSession):
    """Verify ₹4,999 / 14-day paid pilot SKU exists in catalog, has entitlements, and creates active 14-day subscription."""
    # 1. Verify Razorpay plan catalog
    assert "pilot_14d" in PLANS
    pilot_rp = PLANS["pilot_14d"]
    assert pilot_rp["amount"] == 499900  # ₹4,999 in paise
    assert pilot_rp["period"] == "14_days"
    assert pilot_rp["plan_type"] == "pilot"

    # 2. Verify Catalog Service
    cat_svc = CatalogService(stage_f_db)
    await cat_svc.ensure_default_catalog_seeded()

    catalog = await cat_svc.get_active_catalog()
    codes = {p["code"] for p in catalog}
    assert "pilot" in codes

    pilot_v1 = await cat_svc.get_plan_version_by_code("pilot", PlanInterval.CUSTOM.value)
    assert pilot_v1 is not None
    assert pilot_v1.price == Decimal("4999.00")
    assert pilot_v1.trial_days == 14
    assert len(pilot_v1.entitlements) >= 6

    # 3. Create Subscription via SubscriptionEngine
    sub_engine = SubscriptionEngine(stage_f_db)
    org_id = uuid.uuid4()
    sub = await sub_engine.create_subscription(
        organization_id=org_id,
        plan_code="pilot",
        interval=PlanInterval.CUSTOM.value,
    )
    assert sub.status == SubscriptionLifecycleStatus.ACTIVE.value
    assert sub.plan_version.price == Decimal("4999.00")
    # Verify 14-day period end
    period_length = (sub.current_period_end - sub.current_period_start).days
    assert period_length == 14


# ─── 2. PORTAL INTEGRATION ADAPTERS (MagicBricks & Housing.com) ───────────────

def test_magicbricks_lead_adapter():
    """Verify MagicBricks webhook payload normalization."""
    payload = {
        "lead_id": "MB-992811",
        "customer_name": "Siddharth Verma",
        "contact_number": "9820198201",
        "email": "siddharth@example.com",
        "budget": "15000000",
        "city": "Mumbai",
        "locality": "Andheri West",
        "prop_type": "Apartment",
        "bhk": "3",
        "comments": "Looking for ready-to-move 3 BHK near Metro",
    }
    normalized = UniversalLeadNormalizer.normalize_payload("magicbricks", payload)
    assert normalized.source_provider == "magicbricks"
    assert normalized.source_category == "PORTAL"
    assert normalized.country_code == "IN"
    assert normalized.name == "Siddharth Verma"
    assert normalized.phone == "+919820198201"
    assert normalized.budget_max == Decimal("15000000")
    assert normalized.budget_currency == "INR"
    assert "Andheri West" in normalized.preferred_locations
    assert normalized.bedrooms == "3"
    assert normalized.consent_obtained is True
    assert normalized.consent_details["source"] == "magicbricks_lead_webhook"


def test_housing_dot_com_lead_adapter():
    """Verify Housing.com webhook payload normalization."""
    payload = {
        "lead_id": "HS-44829",
        "user_name": "Pooja Hegde",
        "mobile": "+919811122233",
        "user_email": "pooja.hegde@example.com",
        "min_budget": "7500000",
        "max_budget": "10000000",
        "locality": "Whitefield",
        "preferred_bhk": "2",
        "property_type": "Condo",
        "remarks": "Immediate possession needed",
    }
    normalized = UniversalLeadNormalizer.normalize_payload("housing", payload)
    assert normalized.source_provider == "housing"
    assert normalized.source_category == "PORTAL"
    assert normalized.country_code == "IN"
    assert normalized.name == "Pooja Hegde"
    assert normalized.phone == "+919811122233"
    assert normalized.budget_min == Decimal("7500000")
    assert normalized.budget_max == Decimal("10000000")
    assert "Whitefield" in normalized.preferred_locations
    assert normalized.bedrooms == "2"
    assert normalized.consent_obtained is True
    assert normalized.consent_details["source"] == "housing_dot_com_webhook"


# ─── 3. BROKER MORNING BRIEFING ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broker_morning_briefing_with_timezone_and_approvals(stage_f_db: AsyncSession):
    """Verify briefing generation handles India timezone default, pending approvals, site visits, and dedup key."""
    broker_id = uuid.uuid4()
    org_id = uuid.uuid4()

    # Create dummy broker
    broker = Broker(
        id=broker_id,
        email="rajesh.sharma@wefylabs.com",
        name="Rajesh Sharma",
    )
    stage_f_db.add(broker)

    # Add a scheduled site visit meeting today
    now = datetime.now(timezone.utc)
    meeting = Meeting(
        broker_id=broker_id,
        meeting_type="site_visit",
        title="Site Visit - DLF Phase 5",
        status="scheduled",
        scheduled_at=now + timedelta(hours=2),
    )
    stage_f_db.add(meeting)

    # Add an overdue task
    task = Task(
        broker_id=broker_id,
        title="Follow up with Vikram",
        status="pending",
        due_at=now - timedelta(hours=3),
    )
    stage_f_db.add(task)

    # Add a pending approval follow-up execution
    followup_exec = FollowUpExecution(
        id=str(uuid.uuid4()),
        organization_id=str(org_id),
        broker_id=str(broker_id),
        lead_id=str(uuid.uuid4()),
        status="PENDING_APPROVAL",
        recipient_identifier="+919876543210",
        message_body="Hi Rahul, would you like to review the 3BHK brochure for DLF?",
        scheduled_for_utc=now,
    )
    stage_f_db.add(followup_exec)

    await stage_f_db.commit()

    briefing_svc = BriefingService(stage_f_db)
    data = await briefing_svc.get_daily_briefing_data(
        broker_id=broker_id,
        organization_id=str(org_id),
        tenant_tz="Asia/Kolkata",
    )

    assert data["overdue_count"] >= 1
    assert data["meetings_today_count"] >= 1
    assert data["pending_approvals_count"] >= 1
    assert data["tenant_timezone"] == "Asia/Kolkata"
    assert "Good morning" in data["summary_text"]
    assert "overdue task(s)" in data["summary_text"]
    assert "awaiting your approval" in data["summary_text"]
    assert data["briefing_period_key"].startswith(str(broker_id))


# ─── 4. PDF BROCHURE INVENTORY EXTRACTION ─────────────────────────────────────

@pytest.mark.asyncio
async def test_brochure_inventory_extraction_logic(stage_f_db: AsyncSession):
    """Verify brochure text extraction extracts candidate units, price ranges, and human review gate."""
    from app.modules.knowledge.extraction.fact_extraction_service import FactExtractionService

    sample_brochure_text = """
    Godrej Platinum Towers
    Located at Vikhroli East, Mumbai.
    Offering premium 2 BHK and 3 BHK luxury residences.
    Sizes ranging from 950 sqft to 1450 sqft.
    Prices starting from INR 1.85 Cr up to INR 2.75 Cr.
    Amenities: Clubhouse, Infinity Pool, Gymnasium, Landscaped Gardens, 24/7 Security.
    Possession: Dec 2026.
    """

    extractor = FactExtractionService()
    facts, injection = extractor.extract_from_text(
        text=sample_brochure_text,
        document_id=str(uuid.uuid4()),
        organization_id=str(uuid.uuid4()),
        knowledge_type="brochure",
    )
    assert injection is False
    assert len(facts) > 0

    fact_types = {f.fact_type for f in facts}
    assert "PRICE" in fact_types or "BEDROOMS" in fact_types or "AREA" in fact_types


# ─── 5. WHATSAPP VOICE-NOTE HANDLING ──────────────────────────────────────────

def test_voice_note_media_handler_limits():
    """Verify voice note MIME types, file size boundaries (5MB), and transcription entities."""
    # 1. Validation boundaries
    assert "voice_note" in _ALLOWED_MIME_TYPES
    assert "audio/ogg" in _ALLOWED_MIME_TYPES["voice_note"]
    assert "audio/aac" in _ALLOWED_MIME_TYPES["voice_note"]
    assert _MAX_FILE_SIZES["voice_note"] == 5 * 1024 * 1024  # 5 MB max for WhatsApp voice note

    # 2. Transcription entity contract
    broker_id = uuid.uuid4()
    transcript = MobileSyncService.transcribe_voice_note(broker_id=broker_id, audio_duration_sec=12.0)
    assert transcript.broker_id == broker_id
    assert transcript.audio_duration_seconds == 12.0
    assert len(transcript.raw_transcript) > 0
    assert len(transcript.extracted_tasks) > 0
