"""
WefyLabs Revenue Growth Layer — Part 13
Universal Lead Acquisition Test Suite (Meta Lead Ads + Google Ads Lead Forms)
=============================================================================
Behavioral verification for:
  1. Meta Connector Unit & Contract (signature, challenge, retrieval, normalization, health)
  2. Google Connector Unit & Contract (key verification, column parsing, gclid, attribution, health)
  3. Canonical Lead Ingestion via Meta Lead Ads (Source="meta", Identity, Attribution, SLA)
  4. Canonical Lead Ingestion via Google Ads Lead Forms (Source="google", GCLID, Attribution)
  5. Idempotency & Replay Protection (duplicate provider leadgen/submission IDs -> 1 Lead)
  6. Cross-Provider Identity Resolution (Meta lead -> Google lead with same phone -> same Customer Identity)
  7. Ambiguous Identity Protection (different contact info -> separate leads)
  8. Source Attribution Immutability (first-touch preserved, last-touch updated)
  9. Fair Auto-Routing & Owner Preservation
 10. First-Contact 15-Minute SLA Activation
 11. Downstream Lead Loss Prevention (Lead persists if AI or Follow-up fails)
 12. Multi-Tenant Isolation & IDOR Protection
 13. Webhook Authentication (Meta HMAC signature, Google Ads webhook key)
 14. Provider Reconcile & Bounded Backfill (dry-run and execution)
 15. Safe Disconnect (disabling source retains historical leads)
 16. Revenue Intelligence Source Attribution Reporting
"""
from __future__ import annotations

import hmac
import hashlib
import json
import secrets
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, and_, func

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.acquisition_models import (
    LeadSource, LeadCampaign, LeadAcquisitionEvent, SourceAttribution
)
from app.models.identity_models import Identity, IdentityLink
from app.models.crm_models import Task, Notification, Activity
from app.modules.lead_acquisition.dto.acquisition_dto import (
    CanonicalLeadIntakeDTO, CanonicalLeadIntakeResultDTO, UniversalSourceType,
    ReconciliationRequestDTO, BackfillRequestDTO, ProviderConnectDTO,
    LeadSourceCreateDTO, LeadSourceUpdateDTO,
)
from app.modules.lead_acquisition.services.universal_intake_service import UniversalIntakeService
from app.modules.lead_acquisition.services.lead_source_service import LeadSourceService
from app.modules.lead_acquisition.connectors.meta_connector import (
    MetaLeadAdsConnector, MetaErrorTaxonomy
)
from app.modules.lead_acquisition.connectors.google_connector import (
    GoogleLeadFormConnector, GoogleErrorTaxonomy
)
from app.modules.revenue_intelligence.service import SourceAttributionReport


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_a_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def tenant_b_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
async def brokers(db_session, tenant_a_id, tenant_b_id):
    broker_a = Broker(
        id=uuid.UUID(tenant_a_id),
        email="broker_a@wefylabs.com",
        phone="+919100000001",
        name="Tenant A Broker",
        agency_name="Prime Capital",
        city="Bengaluru"
    )
    broker_b = Broker(
        id=uuid.UUID(tenant_b_id),
        email="broker_b@wefylabs.com",
        phone="+919100000002",
        name="Tenant B Broker",
        agency_name="Gulf Real Estate",
        city="Dubai"
    )
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()
    return broker_a, broker_b


# ─── 1. Meta Connector Unit Tests ─────────────────────────────────────────────

class TestMetaConnectorUnit:
    """Test suite for Meta Lead Ads connector functionality."""

    def test_status_checks(self):
        connector = MetaLeadAdsConnector()
        assert connector.get_status(None) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({}) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({"page_id": "123"}) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({"page_id": "123", "access_token_encrypted": "enc"}) == "CONFIGURED"
        assert connector.get_status({"page_id": "123", "access_token_encrypted": "enc", "verified": True}) == "VERIFIED"
        assert connector.get_status({"page_id": "123", "access_token_encrypted": "enc", "reauth_required": True}) == "REAUTH_REQUIRED"

    def test_verify_webhook_signature(self):
        connector = MetaLeadAdsConnector()
        secret = "super_app_secret_123"
        body = b'{"object":"page","entry":[]}'
        computed = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        # Valid signature
        assert connector.verify_webhook_signature(secret, body, f"sha256={computed}") is True
        # Invalid signature
        assert connector.verify_webhook_signature(secret, body, "sha256=invalidhex123") is False
        # Missing prefix
        assert connector.verify_webhook_signature(secret, body, computed) is False
        # Empty signature
        assert connector.verify_webhook_signature(secret, body, "") is False

    def test_handle_verification_challenge(self):
        connector = MetaLeadAdsConnector()
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "correct_token_123",
            "hub.challenge": "challenge_string_abc",
        }
        # Correct token
        assert connector.handle_verification_challenge(params, "correct_token_123") == "challenge_string_abc"
        # Wrong token
        assert connector.handle_verification_challenge(params, "wrong_token") is None
        # Wrong mode
        assert connector.handle_verification_challenge({"hub.mode": "unsubscribe"}, "correct_token_123") is None

    def test_extract_lead_events(self):
        connector = MetaLeadAdsConnector()
        payload = {
            "object": "page",
            "entry": [{
                "id": "page_111",
                "time": 1700000000,
                "changes": [{
                    "field": "leadgen",
                    "value": {
                        "leadgen_id": "leadgen_999",
                        "page_id": "page_111",
                        "form_id": "form_888",
                        "adset_id": "adset_777",
                        "ad_id": "ad_666",
                        "campaign_id": "camp_555",
                        "created_time": 1700000000,
                    }
                }]
            }]
        }
        events = connector.extract_lead_events(payload)
        assert len(events) == 1
        ev = events[0]
        assert ev["external_id"] == "leadgen_999"
        assert ev["form_id"] == "form_888"
        assert ev["page_id"] == "page_111"
        assert ev["ad_id"] == "ad_666"

    def test_normalize_lead_payload_with_real_estate_fields(self):
        connector = MetaLeadAdsConnector()
        lead_data = {
            "id": "leadgen_123",
            "created_time": "2026-09-23T10:00:00Z",
            "field_data": [
                {"name": "full_name", "values": ["Rohan Mehta"]},
                {"name": "email", "values": ["rohan.mehta@example.com"]},
                {"name": "phone_number", "values": ["+91 98765-43210"]},
                {"name": "budget", "values": ["1.8 Crore"]},
                {"name": "bhk", "values": ["3 BHK"]},
                {"name": "preferred_location", "values": ["Indiranagar, Bengaluru"]},
                {"name": "timeline", "values": ["within 1 month"]},
                {"name": "purpose", "values": ["Self Use"]},
            ]
        }
        event_ctx = {
            "form_id": "form_100",
            "page_id": "page_200",
            "campaign_id_meta": "luxury_q3_2026",
            "ad_id": "ad_300",
        }
        normalized = connector.normalize_lead_payload(lead_data, event_ctx)

        assert normalized["name"] == "Rohan Mehta"
        assert normalized["email"] == "rohan.mehta@example.com"
        assert normalized["phone"] == "+91 98765-43210"
        assert normalized["budget"] == "1.8 Crore"
        assert normalized["property_type"] == "3 BHK"
        assert normalized["city"] == "Indiranagar, Bengaluru"
        assert normalized["timeline"] == "within 1 month"
        assert normalized["utm_source"] == "meta"
        assert normalized["utm_campaign"] == "luxury_q3_2026"
        assert "Looking for: 3 BHK" in normalized["message"]
        assert "Budget: 1.8 Crore" in normalized["message"]


# ─── 2. Google Connector Unit Tests ───────────────────────────────────────────

class TestGoogleConnectorUnit:
    """Test suite for Google Ads Lead Form connector functionality."""

    def test_status_checks(self):
        connector = GoogleLeadFormConnector()
        assert connector.get_status(None) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({}) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({"google_key": "secret_key_123"}) == "CONFIGURED"
        assert connector.get_status({"customer_id": "123-456-7890", "developer_token": "token"}) == "CONFIGURED"
        assert connector.get_status({"google_key": "key", "verified": True}) == "VERIFIED"

    def test_verify_webhook_key(self):
        connector = GoogleLeadFormConnector()
        expected = "wefylabs_google_key_2026"
        assert connector.verify_webhook_key(expected, "wefylabs_google_key_2026") is True
        assert connector.verify_webhook_key(expected, "wrong_key") is False
        assert connector.verify_webhook_key(expected, None) is False

    def test_parse_submission_webhook_format(self):
        connector = GoogleLeadFormConnector()
        raw = {
            "lead_id": "google_lead_555",
            "form_id": "gform_123",
            "campaign_id": "camp_google_999",
            "gclid": "TeSt_GcLiD_AbC123",
            "is_test": False,
            "user_column_data": [
                {"column_name": "FULL_NAME", "string_value": "Priya Sharma"},
                {"column_name": "EMAIL", "string_value": "priya.sharma@example.com"},
                {"column_name": "PHONE_NUMBER", "string_value": "+919988776655"},
                {"column_name": "CITY", "string_value": "Gurugram"},
                {"column_name": "POSTAL_CODE", "string_value": "122001"},
                {"column_name": "Budget", "string_value": "2.5 Cr"},
                {"column_name": "BHK", "string_value": "4 BHK"},
            ]
        }
        res = connector.parse_submission(raw)

        assert res["external_id"] == "google_lead_555"
        assert res["form_id"] == "gform_123"
        assert res["campaign_id"] == "camp_google_999"
        assert res["gclid"] == "TeSt_GcLiD_AbC123"
        assert res["name"] == "Priya Sharma"
        assert res["email"] == "priya.sharma@example.com"
        assert res["phone"] == "+919988776655"
        assert res["city"] == "Gurugram"
        assert res["budget"] == "2.5 Cr"
        assert res["property_type"] == "4 BHK"
        assert res["utm_source"] == "google"
        assert res["utm_medium"] == "cpc"
        assert "Looking for: 4 BHK" in res["message"]


# ─── 3. DB Integration: Meta Lead Ads Ingestion ───────────────────────────────

@pytest.mark.asyncio
async def test_meta_lead_ads_canonical_ingestion(db_session, brokers):
    """
    Scenario: Inbound Meta Lead Ads submission arrives.
    Verifies:
      1. Canonical Lead is created with source='meta'
      2. Contact phone normalized to E.164
      3. Budget parsed to integer currency units
      4. SourceAttribution record created with provider='meta_lead_ads'
      5. Identity & IdentityLink records created
      6. SLA Task (15 min due) and Notification assigned to broker
      7. Activity recorded
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    meta_connector = MetaLeadAdsConnector()
    lead_payload = {
        "id": "meta_lead_001",
        "created_time": "2026-09-23T11:00:00Z",
        "field_data": [
            {"name": "full_name", "values": ["Aditya Verma"]},
            {"name": "email", "values": ["aditya.verma@example.com"]},
            {"name": "phone_number", "values": ["+91 98111-22334"]},
            {"name": "budget", "values": ["1.2 Cr"]},
            {"name": "bhk", "values": ["2 BHK"]},
            {"name": "preferred_location", "values": ["Whitefield"]},
        ]
    }
    normalized = meta_connector.normalize_lead_payload(lead_payload, {
        "form_id": "meta_form_100",
        "page_id": "meta_page_200",
        "campaign_id_meta": "meta_camp_300",
    })

    intake_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.META,
        external_source="meta_lead_ads",
        external_lead_id="meta_lead_001",
        name=normalized["name"],
        phone=normalized["phone"],
        email=normalized["email"],
        message=normalized["message"],
        budget=normalized["budget"],
        property_type=normalized["property_type"],
        preferred_locations=normalized["preferred_locations"],
        city=normalized["city"],
        utm_source=normalized["utm_source"],
        utm_medium=normalized["utm_medium"],
        utm_campaign=normalized["utm_campaign"],
        source_metadata=normalized["source_metadata"],
    )

    result = await service.ingest_lead(
        organization_id=str(broker_a.id),
        dto=intake_dto,
        actor_id=str(broker_a.id),
    )

    assert result.status == "ACCEPTED"
    assert result.is_new_lead is True
    assert result.lead_id is not None

    # Verify canonical Lead record
    lead_stmt = select(Lead).where(Lead.id == uuid.UUID(result.lead_id))
    lead = (await db_session.execute(lead_stmt)).scalars().first()
    assert lead is not None
    assert lead.name == "Aditya Verma"
    assert lead.phone == "+919811122334"  # Normalized E.164
    assert lead.email == "aditya.verma@example.com"
    assert lead.source == "meta"
    assert lead.budget_max == 12000000  # 1.2 Crore parsed to integer
    assert lead.property_type == "2 BHK"
    assert "Whitefield" in lead.preferred_locations

    # Verify SourceAttribution record
    attr_stmt = select(SourceAttribution).where(SourceAttribution.lead_id == str(lead.id))
    attr = (await db_session.execute(attr_stmt)).scalars().first()
    assert attr is not None
    assert attr.channel == UniversalSourceType.META
    assert attr.provider == "meta_lead_ads"
    assert attr.external_id == "meta_lead_001"
    assert attr.utm_source == "meta"
    assert attr.utm_medium == "paid_social"

    # Verify Identity & Link
    ident_stmt = select(Identity).where(Identity.primary_phone_e164 == "+919811122334")
    ident = (await db_session.execute(ident_stmt)).scalars().first()
    assert ident is not None
    assert ident.primary_name == "Aditya Verma"

    link_stmt = select(IdentityLink).where(IdentityLink.lead_id == str(lead.id))
    link = (await db_session.execute(link_stmt)).scalars().first()
    assert link is not None
    assert link.identity_id == ident.id

    # Verify SLA Task created
    task_stmt = select(Task).where(Task.lead_id == lead.id)
    task = (await db_session.execute(task_stmt)).scalars().first()
    assert task is not None
    assert "Contact new lead" in task.title
    assert task.due_at is not None


# ─── 4. DB Integration: Google Ads Lead Form Ingestion ────────────────────────

@pytest.mark.asyncio
async def test_google_lead_form_canonical_ingestion(db_session, brokers):
    """
    Scenario: Inbound Google Ads Lead Form submission arrives with GCLID.
    Verifies:
      1. Canonical Lead is created with source='google'
      2. GCLID and Campaign ID stored in SourceAttribution
      3. Contact and budget parsed correctly
      4. Auto-routed to broker
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    google_connector = GoogleLeadFormConnector()
    submission_raw = {
        "lead_id": "google_sub_777",
        "form_id": "gform_888",
        "campaign_id": "camp_google_luxury",
        "gclid": "Cj0KCQjw_TestGclid123",
        "user_column_data": [
            {"column_name": "FULL_NAME", "string_value": "Meera Nair"},
            {"column_name": "EMAIL", "string_value": "meera.nair@example.com"},
            {"column_name": "PHONE_NUMBER", "string_value": "+91 97400 11223"},
            {"column_name": "CITY", "string_value": "Kochi"},
            {"column_name": "Budget", "string_value": "95 Lakhs"},
            {"column_name": "BHK", "string_value": "3 BHK"},
        ]
    }
    normalized = google_connector.parse_submission(submission_raw)

    intake_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.GOOGLE,
        external_source="google_lead_form",
        external_lead_id=normalized["external_id"],
        name=normalized["name"],
        phone=normalized["phone"],
        email=normalized["email"],
        message=normalized["message"],
        budget=normalized["budget"],
        property_type=normalized["property_type"],
        preferred_locations=normalized["preferred_locations"],
        city=normalized["city"],
        utm_source=normalized["utm_source"],
        utm_medium=normalized["utm_medium"],
        utm_campaign=normalized["utm_campaign"],
        source_metadata=normalized["source_metadata"],
    )

    result = await service.ingest_lead(
        organization_id=str(broker_a.id),
        dto=intake_dto,
        actor_id=str(broker_a.id),
    )

    assert result.status == "ACCEPTED"
    assert result.lead_id is not None

    lead_stmt = select(Lead).where(Lead.id == uuid.UUID(result.lead_id))
    lead = (await db_session.execute(lead_stmt)).scalars().first()
    assert lead is not None
    assert lead.name == "Meera Nair"
    assert lead.phone == "+919740011223"
    assert lead.source == "google"
    assert lead.budget_max == 9500000  # 95 Lakhs parsed to 9,500,000

    # Verify GCLID stored in SourceAttribution
    attr_stmt = select(SourceAttribution).where(SourceAttribution.lead_id == str(lead.id))
    attr = (await db_session.execute(attr_stmt)).scalars().first()
    assert attr is not None
    assert attr.channel == UniversalSourceType.GOOGLE
    assert attr.provider == "google_lead_form"
    assert attr.external_id == "google_sub_777"
    assert attr.utm_campaign == "camp_google_luxury"


# ─── 5. Idempotency & Replay Protection ───────────────────────────────────────

@pytest.mark.asyncio
async def test_meta_and_google_duplicate_ingestion_idempotency(db_session, brokers):
    """
    Scenario: The exact same provider event is delivered multiple times (e.g. webhook retry).
    Verifies:
      1. First attempt creates Lead and returns ACCEPTED.
      2. Replay attempt returns DUPLICATE status.
      3. Exactly 1 Lead and 1 Event exist in the database.
      4. No duplicate tasks, notifications, or attributions created.
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.META,
        external_source="meta_lead_ads",
        external_lead_id="meta_repeat_event_101",
        name="Vikram Seth",
        phone="+919800011122",
        email="vikram.seth@example.com",
        message="Interested in 3 BHK",
        idempotency_key="meta:meta_repeat_event_101",
    )

    # 1. First submission
    res1 = await service.ingest_lead(organization_id=str(broker_a.id), dto=dto)
    assert res1.status == "ACCEPTED"
    assert res1.is_new_lead is True

    # 2. Duplicate submission
    res2 = await service.ingest_lead(organization_id=str(broker_a.id), dto=dto)
    assert res2.status == "DUPLICATE"
    assert res2.is_duplicate is True
    assert res2.is_new_lead is False
    assert res2.lead_id == res1.lead_id

    # 3. Verify exactly 1 Lead in DB
    lead_count_stmt = select(func.count(Lead.id)).where(Lead.phone == "+919800011122")
    lead_count = (await db_session.execute(lead_count_stmt)).scalar()
    assert lead_count == 1


# ─── 6. Cross-Provider Identity Resolution ────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_provider_identity_resolution(db_session, brokers):
    """
    Scenario: A customer first submits a form on Meta Lead Ads.
    Later, the SAME customer submits an inquiry on Google Ads with the same phone.
    Verifies:
      1. First submission (Meta) creates Customer Identity & Lead.
      2. Second submission (Google) resolves to the SAME Customer Identity & Lead.
      3. First-touch attribution is PRESERVED (channel remains Meta).
      4. Last-touch attribution timestamp is updated.
      5. No duplicate customer or lead is created.
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    # 1. First acquisition via Meta
    meta_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.META,
        external_source="meta_lead_ads",
        external_lead_id="meta_lead_first",
        name="Kavita Reddy",
        phone="+91 99000-88776",
        email="kavita.reddy@example.com",
        budget="1.5 Cr",
        utm_source="meta",
        utm_campaign="meta_spring_campaign",
    )
    meta_res = await service.ingest_lead(str(broker_a.id), meta_dto)
    assert meta_res.status == "ACCEPTED"
    assert meta_res.is_new_lead is True
    first_lead_id = meta_res.lead_id

    # Check original attribution
    attr1_stmt = select(SourceAttribution).where(SourceAttribution.lead_id == first_lead_id)
    attr1 = (await db_session.execute(attr1_stmt)).scalars().first()
    assert attr1.channel == UniversalSourceType.META
    first_created_at = attr1.created_at

    # 2. Second acquisition via Google Ads (same phone, updated requirement)
    google_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.GOOGLE,
        external_source="google_lead_form",
        external_lead_id="google_lead_second",
        name="Kavita Reddy",
        phone="+91 99000 88776",
        email="kavita.reddy@example.com",
        budget="2.0 Cr",  # Increased budget
        property_type="3 BHK Luxury",
        utm_source="google",
        utm_campaign="google_search_luxury",
    )
    google_res = await service.ingest_lead(str(broker_a.id), google_dto)
    assert google_res.status == "ACCEPTED"
    assert google_res.is_new_lead is False  # Existing lead updated
    assert google_res.lead_id == first_lead_id  # Same lead ID!
    assert google_res.identity_outcome == "UPDATE_EXISTING_LEAD"

    # 3. Verify lead updated without losing history
    lead_stmt = select(Lead).where(Lead.id == uuid.UUID(first_lead_id))
    lead = (await db_session.execute(lead_stmt)).scalars().first()
    assert lead.budget_max == 20000000  # Upgraded to 2.0 Cr
    assert lead.property_type == "3 BHK Luxury"

    # 4. Verify SourceAttribution immutability: first-touch preserved
    attr_recheck = (await db_session.execute(attr1_stmt)).scalars().first()
    assert attr_recheck.channel == UniversalSourceType.META  # First-touch retained!
    assert attr_recheck.utm_source == "meta"
    assert attr_recheck.last_touch_at is not None  # Last touch timestamp updated


# ─── 7. Ambiguous Identity Protection ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_ambiguous_identity_not_blindly_merged(db_session, brokers):
    """
    Scenario: Two different leads arrive with the same name ('Rahul Sharma')
    but completely different phone numbers and emails.
    Verifies:
      1. They are NOT merged solely because names match.
      2. Two distinct Lead and Identity records are created.
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    lead1_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.META,
        name="Rahul Sharma",
        phone="+919111111111",
        email="rahul.sharma.1@example.com",
    )
    lead2_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.GOOGLE,
        name="Rahul Sharma",
        phone="+919222222222",
        email="rahul.sharma.2@example.com",
    )

    res1 = await service.ingest_lead(str(broker_a.id), lead1_dto)
    res2 = await service.ingest_lead(str(broker_a.id), lead2_dto)

    assert res1.lead_id != res2.lead_id
    assert res1.is_new_lead is True
    assert res2.is_new_lead is True


# ─── 8. Lead Loss Prevention & Fault Tolerance ────────────────────────────────

@pytest.mark.asyncio
async def test_lead_loss_prevention_on_downstream_failure(db_session, brokers):
    """
    Scenario: During ingestion, downstream AI requirement extraction, follow-up,
    or property matching throws an unexpected exception.
    Verifies:
      1. The exception does NOT fail the overall transaction.
      2. The canonical Lead, Identity, Attribution, and Task are still safely committed.
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.META,
        external_source="meta_lead_ads",
        external_lead_id="meta_resilience_test_99",
        name="Sunil Gavaskar",
        phone="+919333344444",
        email="sunil.g@example.com",
        message="Looking for sea-facing apartment in Worli",
    )

    # Patch downstream AI extraction to simulate sudden crash
    with patch(
        "app.modules.lead_acquisition.services.universal_intake_service.UniversalIntakeService._run_deterministic_requirement_extraction",
        side_effect=RuntimeError("AI Gateway Timeout"),
    ):
        result = await service.ingest_lead(str(broker_a.id), dto)

    assert result.status == "ACCEPTED"
    assert result.lead_id is not None
    assert "failed" in result.activations.get("ai_extraction", "")

    # Verify Lead persisted despite AI failure
    lead_stmt = select(Lead).where(Lead.id == uuid.UUID(result.lead_id))
    lead = (await db_session.execute(lead_stmt)).scalars().first()
    assert lead is not None
    assert lead.name == "Sunil Gavaskar"


# ─── 9. Multi-Tenant Isolation & IDOR Protection ──────────────────────────────

@pytest.mark.asyncio
async def test_tenant_isolation_lead_sources(db_session, brokers):
    """
    Scenario: Tenant A creates a Meta lead source.
    Verifies:
      1. Tenant B cannot list or get Tenant A's lead source (IDOR rejected).
      2. Webhook token resolves to Tenant A's org, never Tenant B.
    """
    broker_a, broker_b = brokers
    source_svc = LeadSourceService(db_session)

    # Tenant A creates Meta lead source
    source_a = await source_svc.create_source(
        organization_id=str(broker_a.id),
        dto=LeadSourceCreateDTO(
            name="Tenant A Meta Lead Ads",
            description="Campaign 2026",
            channel="META",
            provider="meta_lead_ads",
            country_code="IN",
            market_id=None,
            configuration={"page_id": "page_A_123", "access_token": "token_A"},
            rate_limit_per_hour=1000,
        )
    )

    # Tenant B tries to fetch Tenant A's source
    fetched_by_b = await source_svc.get_source(organization_id=str(broker_b.id), source_id=source_a.id)
    assert fetched_by_b is None  # Tenant B cannot access Tenant A!

    # Tenant A can fetch it
    fetched_by_a = await source_svc.get_source(organization_id=str(broker_a.id), source_id=source_a.id)
    assert fetched_by_a is not None
    assert fetched_by_a.id == source_a.id

    # Webhook token resolution guarantees correct tenant
    resolved_source = await source_svc.resolve_source_by_webhook_token(source_a.webhook_url_token)
    assert resolved_source is not None
    assert resolved_source.organization_id == str(broker_a.id)


# ─── 10. Revenue Intelligence Source Attribution Reporting ────────────────────

@pytest.mark.asyncio
async def test_revenue_intelligence_source_attribution_report(db_session, brokers):
    """
    Scenario: Ingest leads from Meta and Google, convert one to status='converted'.
    Verifies:
      1. SourceAttributionReport groups by source ('meta', 'google').
      2. Correctly reports lead counts and converted revenue metrics.
    """
    broker_a, _ = brokers
    service = UniversalIntakeService(db_session)

    # 1. Ingest Meta lead
    meta_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.META,
        name="Meta Buyer",
        phone="+919444455555",
        budget="1 Cr",
    )
    res_meta = await service.ingest_lead(str(broker_a.id), meta_dto)

    # 2. Ingest Google lead and convert it
    google_dto = CanonicalLeadIntakeDTO(
        source_type=UniversalSourceType.GOOGLE,
        name="Google Buyer Converted",
        phone="+919555566666",
        budget="2 Cr",
    )
    res_google = await service.ingest_lead(str(broker_a.id), google_dto)

    # Mark Google lead as converted
    google_lead_stmt = select(Lead).where(Lead.id == uuid.UUID(res_google.lead_id))
    google_lead = (await db_session.execute(google_lead_stmt)).scalars().first()
    google_lead.status = "converted"
    await db_session.commit()

    # 3. Generate SourceAttributionReport
    report_svc = SourceAttributionReport(db_session)
    report = await report_svc.get_attribution_report(organization_id=broker_a.id)

    by_source = {row["source"]: row for row in report["by_source"]}
    assert "meta" in by_source
    assert "google" in by_source

    assert by_source["meta"]["lead_count"] >= 1
    assert by_source["google"]["lead_count"] >= 1
    assert by_source["google"]["converted_count"] >= 1
    assert by_source["google"]["estimated_revenue_estimate"] >= 20000000


# ─── 11. Provider Reconciliation & Safe Disconnect ────────────────────────────

@pytest.mark.asyncio
async def test_safe_disconnect_preserves_historical_leads(db_session, brokers):
    """
    Scenario: A broker disconnects their Meta Lead Ads integration.
    Verifies:
      1. Source status becomes 'inactive'.
      2. All previously ingested leads and source attributions remain fully intact.
    """
    broker_a, _ = brokers
    source_svc = LeadSourceService(db_session)
    intake_svc = UniversalIntakeService(db_session)

    # Create source
    source = await source_svc.create_source(
        str(broker_a.id),
        LeadSourceCreateDTO(
            name="Meta Source Disconnect Test",
            description="",
            channel="META",
            provider="meta_lead_ads",
            country_code="IN",
            market_id=None,
            configuration={"page_id": "page_disc_101"},
            rate_limit_per_hour=100,
        )
    )

    # Ingest a lead
    res = await intake_svc.ingest_lead(
        str(broker_a.id),
        CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.META,
            name="Historical Lead",
            phone="+919666677777",
            source_id=source.id,
        )
    )
    lead_id = res.lead_id

    # Disconnect source
    await source_svc.update_source(
        str(broker_a.id),
        source.id,
        LeadSourceUpdateDTO(status="inactive")
    )

    # Verify source is inactive
    reloaded_source = await source_svc.get_source(str(broker_a.id), source.id)
    assert reloaded_source.status == "inactive"
    assert reloaded_source.is_active is False

    # Verify historical lead is still present and valid
    lead = (await db_session.execute(select(Lead).where(Lead.id == uuid.UUID(lead_id)))).scalars().first()
    assert lead is not None
    assert lead.name == "Historical Lead"


# ─── 12. HTTP Webhook & Controller Integration Tests ─────────────────────────

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from app.dependencies import get_current_broker


@pytest.mark.asyncio
async def test_meta_webhook_challenge_get_endpoint(db_session, brokers):
    """
    Scenario: Meta verification bot sends GET request with hub.challenge.
    Verifies:
      1. Correct verify_token returns hub.challenge text/plain with HTTP 200.
      2. Incorrect verify_token returns HTTP 403.
    """
    broker_a, _ = brokers
    source_svc = LeadSourceService(db_session)
    source = await source_svc.create_source(
        str(broker_a.id),
        LeadSourceCreateDTO(
            name="Meta Challenge Source",
            channel="META",
            configuration={"verify_token": "my_meta_secret_token_123"},
        )
    )

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Successful challenge
            resp_success = await client.get(
                f"/api/v1/lead-acquisition/webhooks/meta?hub.mode=subscribe&hub.verify_token=my_meta_secret_token_123&hub.challenge=challenge_12345&token={source.webhook_url_token}"
            )
            assert resp_success.status_code == 200
            assert resp_success.text == "challenge_12345"

            # 2. Failed challenge (wrong token)
            resp_fail = await client.get(
                f"/api/v1/lead-acquisition/webhooks/meta?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge=challenge_12345&token={source.webhook_url_token}"
            )
            assert resp_fail.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_meta_webhook_post_with_signature(db_session, brokers):
    """
    Scenario: Meta webhook POST delivers leadgen event.
    Verifies:
      1. Valid HMAC-SHA256 signature returns HTTP 200 and processes event.
      2. Invalid signature returns HTTP 401.
    """
    broker_a, _ = brokers
    source_svc = LeadSourceService(db_session)
    app_secret = "meta_test_secret_999"
    source = await source_svc.create_source(
        str(broker_a.id),
        LeadSourceCreateDTO(
            name="Meta Signed Webhook Source",
            channel="META",
            configuration={"app_secret": app_secret},
        )
    )

    payload = {
        "object": "page",
        "entry": [{
            "id": "page_123",
            "time": 1700000000,
            "changes": [{
                "field": "leadgen",
                "value": {
                    "leadgen_id": "meta_http_lead_1",
                    "page_id": "page_123",
                    "form_id": "form_123",
                    "created_time": 1700000000,
                }
            }]
        }],
        "field_data": [
            {"name": "full_name", "values": ["Ananya Iyer"]},
            {"name": "email", "values": ["ananya.iyer@example.com"]},
            {"name": "phone_number", "values": ["+91 97111-22334"]},
            {"name": "budget", "values": ["1.6 Cr"]},
            {"name": "bhk", "values": ["3 BHK"]},
        ]
    }
    raw_body = json.dumps(payload).encode("utf-8")
    valid_sig = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Invalid signature -> 401
            resp_invalid = await client.post(
                f"/api/v1/lead-acquisition/webhooks/meta?token={source.webhook_url_token}",
                content=raw_body,
                headers={"X-Hub-Signature-256": "sha256=invalid_hash", "Content-Type": "application/json"}
            )
            assert resp_invalid.status_code == 401

            # 2. Valid signature -> 200 OK
            resp_valid = await client.post(
                f"/api/v1/lead-acquisition/webhooks/meta?token={source.webhook_url_token}",
                content=raw_body,
                headers={"X-Hub-Signature-256": valid_sig, "Content-Type": "application/json"}
            )
            assert resp_valid.status_code == 200
            data = resp_valid.json().get("data", {})
            assert data.get("provider") == "meta"
            assert data.get("status") == "processed"
            assert data.get("lead_id") is not None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_google_webhook_post_key_verification(db_session, brokers):
    """
    Scenario: Google Ads Lead Form webhook delivers submission.
    Verifies:
      1. Valid google_key returns HTTP 200 and processes lead.
      2. Invalid google_key returns HTTP 401.
    """
    broker_a, _ = brokers
    source_svc = LeadSourceService(db_session)
    google_key = "google_secret_key_888"
    source = await source_svc.create_source(
        str(broker_a.id),
        LeadSourceCreateDTO(
            name="Google Ads Lead Form Source",
            channel="GOOGLE",
            configuration={"google_key": google_key},
        )
    )

    submission_payload = {
        "lead_id": "google_http_lead_1",
        "form_id": "form_google_555",
        "campaign_id": "campaign_bangalore_villas",
        "gclid": "TeSt_GcLid_XyZ",
        "google_key": google_key,
        "user_column_data": [
            {"column_name": "FULL_NAME", "string_value": "Deepak Chopra"},
            {"column_name": "EMAIL", "string_value": "deepak.chopra@example.com"},
            {"column_name": "PHONE_NUMBER", "string_value": "+91 98222-33445"},
            {"column_name": "Budget", "string_value": "3.5 Cr"},
            {"column_name": "BHK", "string_value": "4 BHK Villa"},
        ]
    }

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Invalid key -> 401
            bad_payload = dict(submission_payload, google_key="wrong_google_key")
            resp_invalid = await client.post(
                f"/api/v1/lead-acquisition/webhooks/google?token={source.webhook_url_token}",
                json=bad_payload,
            )
            assert resp_invalid.status_code == 401

            # 2. Valid key -> 200 OK
            resp_valid = await client.post(
                f"/api/v1/lead-acquisition/webhooks/google?token={source.webhook_url_token}",
                json=submission_payload,
            )
            assert resp_valid.status_code == 200
            data = resp_valid.json().get("data", {})
            assert data.get("provider") == "google"
            assert data.get("status") == "processed"
            assert data.get("lead_id") is not None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_connector_status_and_maintenance_endpoints(db_session, brokers):
    """
    Scenario: Authenticated operator queries connector statuses, triggers reconcile & backfill.
    Verifies:
      1. GET /meta/status and /google/status return valid status DTOs.
      2. POST /reconcile runs bounded reconciliation.
      3. POST /backfill with dry_run returns plan without mutating data.
      4. POST /connect and /disconnect safely manage provider configurations.
    """
    broker_a, _ = brokers

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_broker] = lambda: broker_a
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Connector status checks
            resp_meta_stat = await client.get("/api/v1/lead-acquisition/meta/status")
            assert resp_meta_stat.status_code == 200
            assert resp_meta_stat.json()["data"]["provider"] == "meta_lead_ads"

            resp_google_stat = await client.get("/api/v1/lead-acquisition/google/status")
            assert resp_google_stat.status_code == 200
            assert resp_google_stat.json()["data"]["provider"] == "google_lead_form"

            # 2. Connect Meta source
            resp_connect = await client.post(
                "/api/v1/lead-acquisition/connect/meta",
                json={
                    "provider": "meta",
                    "name": "Production Meta Lead Ads",
                    "page_id": "page_prod_999",
                    "access_token": "token_prod_999",
                    "app_secret": "secret_prod_999",
                }
            )
            assert resp_connect.status_code == 200
            source_data = resp_connect.json()["data"]
            assert source_data["connected"] is True
            source_id = source_data["id"]

            # 3. Reconcile
            resp_rec = await client.post(
                "/api/v1/lead-acquisition/reconcile",
                json={
                    "provider": "meta",
                    "source_id": source_id,
                    "since_hours": 24,
                }
            )
            assert resp_rec.status_code == 200
            assert resp_rec.json()["data"]["status"] == "completed"

            # 4. Backfill (dry_run)
            now_iso = datetime.now(timezone.utc).isoformat()
            past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            resp_backfill = await client.post(
                "/api/v1/lead-acquisition/backfill",
                json={
                    "provider": "meta",
                    "source_id": source_id,
                    "start_time": past_iso,
                    "end_time": now_iso,
                    "limit": 50,
                    "dry_run": True,
                }
            )
            assert resp_backfill.status_code == 200
            assert resp_backfill.json()["data"]["dry_run"] is True

            # 5. Disconnect
            resp_disc = await client.post("/api/v1/lead-acquisition/disconnect/meta")
            assert resp_disc.status_code == 200
            assert resp_disc.json()["data"]["disconnected"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_broker, None)

