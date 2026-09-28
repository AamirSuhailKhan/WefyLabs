"""
MASTER BUILD 02 TEST SUITE
===========================
Universal Lead Ingestion, Real-Time Identity Resolution & Lead Intelligence Foundation

Validates:
  1. Phone Normalization (E.164, Indian 10/11/12-digit, WhatsApp identifiers, country inference, tuple unpack)
  2. Email Normalization (syntax, lowercase, canonical representation, fingerprint)
  3. IndiaMART Lead Push Connector (key verification, real-estate extraction, status)
  4. 99acres Real Estate Portal Connector (key verification, BHK/budget mapping, status)
  5. Raw Event Preservation (OriginalPayload immutable storage prior to normalization)
  6. Transactional Outbox (OutboxEvent atomic persistence in same transaction as Lead)
  7. Deterministic Idempotency (repeated webhook delivery creates zero duplicate leads or side effects)
  8. Cross-Channel Identity Resolution (Meta + Google + IndiaMART + 99acres linked to single Identity node)
  9. First-Touch Source Attribution Immutability
 10. Multi-Tenant Boundary & Fail-Closed Scoping
"""
from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import select, and_, func

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.acquisition_models import (
    LeadSource, LeadAcquisitionEvent, SourceAttribution
)
from app.models.identity_models import Identity, IdentityLink
from app.models.ingestion_models import OriginalPayload, IngestionLog
from app.models.outbox_models import OutboxEvent, OutboxStatus
from app.modules.lead_acquisition.dto.acquisition_dto import (
    CanonicalLeadIntakeDTO, UniversalSourceType
)
from app.modules.lead_acquisition.services.normalization_service import (
    normalize_phone, normalize_email, PhoneNormalizationResult
)
from app.modules.lead_acquisition.services.universal_intake_service import UniversalIntakeService
from app.modules.lead_acquisition.connectors.indiamart_connector import IndiaMartConnector
from app.modules.lead_acquisition.connectors.ninety_nine_acres_connector import NinetyNineAcresConnector


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_1_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def tenant_2_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
async def setup_brokers(db_session, tenant_1_id, tenant_2_id):
    broker_1 = Broker(
        id=uuid.UUID(tenant_1_id),
        email="broker1@wefylabs.com",
        phone="+919870000001",
        name="Broker Tenant 1",
        agency_name="Agency 1",
        city="Gurgaon"
    )
    broker_2 = Broker(
        id=uuid.UUID(tenant_2_id),
        email="broker2@wefylabs.com",
        phone="+919870000002",
        name="Broker Tenant 2",
        agency_name="Agency 2",
        city="Mumbai"
    )
    db_session.add_all([broker_1, broker_2])
    await db_session.commit()
    return broker_1, broker_2


# ─── 1. Phone & Email Normalization Pipeline Tests ────────────────────────────

class TestNormalizationPipeline:
    """Validates Section 9 & 10 phone and email normalization requirements."""

    def test_e164_indian_formats(self):
        # 10 digits standard Indian mobile
        res = normalize_phone("9876543210")
        assert res.normalized_phone == "+919876543210"
        assert res.phone_country == "IN"
        assert res.normalization_status == "formatted"
        assert res.confidence >= 0.8

        # 11 digits with trunk 0
        res0 = normalize_phone("09876543210")
        assert res0.normalized_phone == "+919876543210"
        assert res0.phone_country == "IN"
        assert res0.normalization_status == "formatted"

        # 12 digits with 91 prefix
        res91 = normalize_phone("919876543210")
        assert res91.normalized_phone == "+919876543210"
        assert res91.phone_country == "IN"
        assert res91.normalization_status == "formatted"

        # Already valid E.164
        res_e164 = normalize_phone("+919876543210")
        assert res_e164.normalized_phone == "+919876543210"
        assert res_e164.phone_country == "IN"
        assert res_e164.normalization_status == "valid"
        assert res_e164.confidence == 1.0

    def test_whatsapp_and_uri_normalization(self):
        # WhatsApp JID @c.us
        res_wa = normalize_phone("919876543210@c.us")
        assert res_wa.normalized_phone == "+919876543210"
        assert res_wa.phone_country == "IN"

        # whatsapp: URI
        res_uri = normalize_phone("whatsapp:+919876543210")
        assert res_uri.normalized_phone == "+919876543210"

    def test_international_prefix_00(self):
        # UAE number with 00 prefix
        res_uae = normalize_phone("00971501234567")
        assert res_uae.normalized_phone == "+971501234567"
        assert res_uae.phone_country == "AE"
        assert res_uae.normalization_status == "formatted"

    def test_phone_tuple_unpack_backwards_compatibility(self):
        # Existing call sites use `phone_e164, phone_conf = normalize_phone(phone)`
        phone_e164, phone_conf = normalize_phone("9876543210")
        assert phone_e164 == "+919876543210"
        assert isinstance(phone_conf, float)
        assert phone_conf > 0.8

    def test_invalid_and_uncertain_phones(self):
        # Too short -> None, 0.0, invalid
        res_invalid = normalize_phone("1234")
        assert res_invalid.normalized_phone is None
        assert res_invalid.normalization_status == "invalid"
        assert res_invalid.confidence == 0.0

        # Empty / None
        res_none = normalize_phone(None)
        assert res_none.normalized_phone is None
        assert res_none.confidence == 0.0

    def test_email_normalization(self):
        norm_email, fp = normalize_email("  Rahul.Sharma+invest@WefyLabs.com  ")
        assert norm_email == "rahul.sharma+invest@wefylabs.com"
        assert len(fp) == 64  # SHA256 hex digest
        assert fp == normalize_email("rahulsharma@wefylabs.com")[1]


# ─── 2. IndiaMART Connector Tests ─────────────────────────────────────────────

class TestIndiaMartConnector:
    """Validates Section 5 & Master Build 02 IndiaMART connector specifications."""

    def test_connector_status(self):
        connector = IndiaMartConnector()
        assert connector.get_status(None) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({}) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({"glusr_crm_key": "secret123"}) == "CONFIGURED"
        assert connector.get_status({"glusr_crm_key": "secret123", "verified": True}) == "VERIFIED"

    def test_webhook_key_verification(self):
        connector = IndiaMartConnector()
        assert connector.verify_webhook_key("my_secret_key", "my_secret_key") is True
        assert connector.verify_webhook_key("my_secret_key", "wrong_key") is False
        assert connector.verify_webhook_key("my_secret_key", None) is False

    def test_parse_indiamart_payload(self):
        connector = IndiaMartConnector()
        payload = {
            "UNIQUEQUERYID": "IM-998877",
            "SENDER_NAME": "Vikram Malhotra",
            "SENDER_MOBILE": "9811223344",
            "SENDER_EMAIL": "vikram@malhotra.in",
            "QUERY_PRODUCT_NAME": "3 BHK Luxury Apartment in DLF Phase 5",
            "QUERY_MESSAGE": "Looking to buy within 2 months, budget around 2.5 Cr",
            "SENDER_CITY": "Gurgaon",
            "SENDER_STATE": "Haryana",
            "SENDER_COMPANY": "Malhotra Enterprises",
            "QUERY_TIME": "2026-09-25 11:30:00",
        }
        normalized = connector.parse_submission(payload)
        assert normalized["external_id"] == "IM-998877"
        assert normalized["name"] == "Vikram Malhotra"
        assert normalized["phone"] == "9811223344"
        assert normalized["email"] == "vikram@malhotra.in"
        assert normalized["property_type"] == "3 BHK Apartment"
        assert normalized["city"] == "Gurgaon"
        assert normalized["budget"] == "2.5 Cr"
        assert normalized["utm_source"] == "indiamart"
        assert normalized["source_metadata"]["provider"] == "indiamart"


# ─── 3. 99acres Portal Connector Tests ─────────────────────────────────────────

class TestNinetyNineAcresConnector:
    """Validates Section 5 & Master Build 02 99acres connector specifications."""

    def test_connector_status(self):
        connector = NinetyNineAcresConnector()
        assert connector.get_status(None) == "CONFIGURATION_REQUIRED"
        assert connector.get_status({"portal_key": "portal_secret_key"}) == "CONFIGURED"

    def test_webhook_key_verification(self):
        connector = NinetyNineAcresConnector()
        assert connector.verify_webhook_key("key_123", "key_123") is True
        assert connector.verify_webhook_key("key_123", "key_456") is False

    def test_parse_99acres_payload(self):
        connector = NinetyNineAcresConnector()
        payload = {
            "enquiry_id": "99A-445566",
            "name": "Pooja Hegde",
            "phone": "+91 99887 76655",
            "email": "pooja@hegde.com",
            "property_id": "PROP-GURGAON-401",
            "property_type": "4 BHK Penthouse",
            "budget": "4.5 Cr",
            "city": "Gurgaon",
            "locality": "Golf Course Extension",
            "query": "Is ready to move or under construction?",
        }
        normalized = connector.parse_submission(payload)
        assert normalized["external_id"] == "99A-445566"
        assert normalized["name"] == "Pooja Hegde"
        assert normalized["phone"] == "+91 99887 76655"
        assert normalized["property_id"] == "PROP-GURGAON-401"
        assert normalized["property_type"] == "4 BHK Penthouse"
        assert normalized["budget"] == "4.5 Cr"
        assert "Golf Course Extension" in normalized["preferred_locations"]
        assert normalized["utm_source"] == "99acres"


# ─── 4. Raw Event Preservation & Transactional Outbox Tests ────────────────────

@pytest.mark.asyncio
class TestRawEventPreservationAndTransactionalOutbox:
    """Validates Section 6 (Raw Event Preservation) and Transactional Outbox."""

    async def test_raw_payload_preservation_and_outbox_event(self, db_session, tenant_1_id, setup_brokers):
        u_svc = UniversalIntakeService(db_session)
        raw_test_payload = {
            "leadgen_id": "meta_lead_12345",
            "form_id": "form_999",
            "field_data": [
                {"name": "full_name", "values": ["Sunil Chhetri"]},
                {"name": "phone_number", "values": ["+919876500001"]},
                {"name": "email", "values": ["sunil@bengaluru.fc"]},
                {"name": "budget", "values": ["2 Cr"]},
            ]
        }

        intake_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.META,
            external_source="meta_lead_ads",
            external_lead_id="meta_lead_12345",
            name="Sunil Chhetri",
            phone="+919876500001",
            email="sunil@bengaluru.fc",
            budget="2 Cr",
            idempotency_key="meta:meta_lead_12345",
        )

        res = await u_svc.ingest_lead(
            organization_id=tenant_1_id,
            dto=intake_dto,
            ip_address="103.21.244.1",
            user_agent="Meta-Hook/1.0",
            raw_payload=raw_test_payload,
        )

        assert res.status == "ACCEPTED"
        assert res.is_new_lead is True

        # 1. Verify Raw Event Preservation (OriginalPayload table)
        orig_stmt = select(OriginalPayload).where(
            OriginalPayload.organization_id == tenant_1_id,
            OriginalPayload.source == UniversalSourceType.META
        )
        orig_rec = (await db_session.execute(orig_stmt)).scalars().first()
        assert orig_rec is not None
        assert orig_rec.raw_payload_json["leadgen_id"] == "meta_lead_12345"
        assert orig_rec.ip_address == "103.21.244.1"

        # 2. Verify Transactional Outbox (OutboxEvent table)
        outbox_stmt = select(OutboxEvent).where(
            OutboxEvent.tenant_id == tenant_1_id,
            OutboxEvent.aggregate_id == res.lead_id
        )
        outbox_rec = (await db_session.execute(outbox_stmt)).scalars().first()
        assert outbox_rec is not None
        assert outbox_rec.aggregate_type == "Lead"
        assert outbox_rec.event_type == "lead.ingested"
        assert outbox_rec.status == OutboxStatus.PENDING
        assert outbox_rec.payload["lead_id"] == res.lead_id
        assert outbox_rec.payload["source"] == UniversalSourceType.META

        # 3. Verify IngestionLog table
        log_stmt = select(IngestionLog).where(
            IngestionLog.organization_id == tenant_1_id,
            IngestionLog.lead_id == res.lead_id
        )
        log_rec = (await db_session.execute(log_stmt)).scalars().first()
        assert log_rec is not None
        assert log_rec.status == "success"

        # 4. Verify Lead organization_id
        lead_stmt = select(Lead).where(Lead.id == uuid.UUID(res.lead_id))
        lead_rec = (await db_session.execute(lead_stmt)).scalars().first()
        assert lead_rec is not None
        assert str(lead_rec.organization_id) == tenant_1_id


# ─── 5. Deterministic Idempotency Tests ────────────────────────────────────────

@pytest.mark.asyncio
class TestDeterministicIdempotency:
    """Validates Section 7: Same event must never create duplicate leads or side effects."""

    async def test_repeated_delivery_idempotency(self, db_session, tenant_1_id, setup_brokers):
        u_svc = UniversalIntakeService(db_session)
        idem_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.GOOGLE,
            external_source="google_lead_form",
            external_lead_id="google_lead_sub_777",
            name="Ananya Panday",
            phone="9876512345",
            email="ananya@panday.in",
            budget="3.5 Cr",
            idempotency_key="google:google_lead_sub_777",
        )

        # Delivery 1
        res1 = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=idem_dto)
        assert res1.status == "ACCEPTED"
        assert res1.is_new_lead is True
        lead_id = res1.lead_id

        # Delivery 2 (Exact same idempotency key)
        res2 = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=idem_dto)
        assert res2.is_duplicate is True
        assert res2.lead_id == lead_id

        # Delivery 3
        res3 = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=idem_dto)
        assert res3.is_duplicate is True
        assert res3.lead_id == lead_id

        # Verify only 1 Lead exists in database
        lead_count_stmt = select(func.count()).select_from(Lead).where(
            Lead.organization_id == uuid.UUID(tenant_1_id),
            Lead.phone == "+919876512345"
        )
        lead_count = (await db_session.execute(lead_count_stmt)).scalar()
        assert lead_count == 1


# ─── 6. Cross-Channel Identity Deduplication Tests ──────────────────────────────

@pytest.mark.asyncio
class TestCrossChannelIdentityDeduplication:
    """Validates Section 11 & 12: Real-time identity resolution across Meta, Google, IndiaMART, 99acres."""

    async def test_convergence_across_four_channels_to_single_identity(self, db_session, tenant_1_id, setup_brokers):
        u_svc = UniversalIntakeService(db_session)
        canonical_phone = "9876599999"  # Raw local Indian format

        # ── Step 1: Meta Ads Lead Ingestion ──
        dto_meta = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.META,
            external_source="meta_lead_ads",
            external_lead_id="meta_lead_001",
            name="Arjun Kapoor",
            phone=canonical_phone,
            email="arjun@kapoor.com",
            budget="2 Cr",
            idempotency_key="meta:meta_lead_001",
        )
        res_meta = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=dto_meta)
        assert res_meta.is_new_lead is True
        lead_id_meta = res_meta.lead_id

        # Check Identity node created
        ident_stmt = select(Identity).where(
            Identity.organization_id == tenant_1_id,
            Identity.primary_phone_e164 == "+919876599999"
        )
        identity_node = (await db_session.execute(ident_stmt)).scalars().first()
        assert identity_node is not None
        assert identity_node.lead_count == 1
        identity_id = identity_node.id

        # Check Attribution is META
        attr_stmt = select(SourceAttribution).where(SourceAttribution.lead_id == lead_id_meta)
        attr_1 = (await db_session.execute(attr_stmt)).scalars().first()
        assert attr_1.channel == UniversalSourceType.META

        # ── Step 2: Google Ads Ingestion with formatted phone ──
        dto_google = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.GOOGLE,
            external_source="google_lead_form",
            external_lead_id="google_sub_002",
            name="Arjun K",
            phone="+91 98765 99999",  # with spaces
            email="arjun@kapoor.com",
            budget="2.5 Cr",
            idempotency_key="google:google_sub_002",
        )
        res_google = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=dto_google)
        assert res_google.is_duplicate is True
        assert res_google.lead_id == lead_id_meta

        # First-touch attribution MUST remain META
        await db_session.refresh(attr_1)
        assert attr_1.channel == UniversalSourceType.META
        assert attr_1.last_touch_at is not None

        # ── Step 3: IndiaMART Ingestion with 0 trunk prefix ──
        dto_indiamart = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.INDIAMART,
            external_source="indiamart",
            external_lead_id="im_query_003",
            name="Arjun Kapoor",
            phone="09876599999",  # 0 trunk prefix
            property_type="3 BHK Villa",
            idempotency_key="indiamart:im_query_003",
        )
        res_indiamart = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=dto_indiamart)
        assert res_indiamart.is_duplicate is True
        assert res_indiamart.lead_id == lead_id_meta

        # ── Step 4: 99acres Ingestion with 91 prefix ──
        dto_99acres = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.NINETY_NINE_ACRES,
            external_source="99acres",
            external_lead_id="99a_enq_004",
            name="Arjun Kapoor",
            phone="919876599999",  # 91 prefix
            property_id="PROP-DLF-01",
            idempotency_key="99acres:99a_enq_004",
        )
        res_99acres = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=dto_99acres)
        assert res_99acres.is_duplicate is True
        assert res_99acres.lead_id == lead_id_meta

        # Re-check identity node
        await db_session.refresh(identity_node)
        assert identity_node.id == identity_id

        # Total Leads in DB remains 1
        total_leads = (await db_session.execute(
            select(func.count()).select_from(Lead).where(Lead.organization_id == uuid.UUID(tenant_1_id))
        )).scalar()
        assert total_leads == 1


# ─── 7. Multi-Tenant Scoping & Fail-Closed Tests ───────────────────────────────

@pytest.mark.asyncio
class TestTenantIsolation:
    """Validates Section 4 & 8: organization_id fail-closed boundary."""

    async def test_tenant_lead_isolation(self, db_session, tenant_1_id, tenant_2_id, setup_brokers):
        u_svc = UniversalIntakeService(db_session)
        shared_phone = "9876577777"

        # Tenant 1 ingests lead
        dto1 = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.WEBSITE,
            name="Tenant 1 Customer",
            phone=shared_phone,
            idempotency_key=f"t1:{shared_phone}",
        )
        res1 = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=dto1)
        assert res1.status == "ACCEPTED"
        assert res1.is_new_lead is True

        # Tenant 2 ingests lead with SAME phone number
        dto2 = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.WEBSITE,
            name="Tenant 2 Customer",
            phone=shared_phone,
            idempotency_key=f"t2:{shared_phone}",
        )
        res2 = await u_svc.ingest_lead(organization_id=tenant_2_id, dto=dto2)
        assert res2.status == "ACCEPTED"
        assert res2.is_new_lead is True
        assert res2.lead_id != res1.lead_id  # Isolated across tenants!

        # Verify each lead has correct organization_id
        lead1 = (await db_session.execute(select(Lead).where(Lead.id == uuid.UUID(res1.lead_id)))).scalars().first()
        lead2 = (await db_session.execute(select(Lead).where(Lead.id == uuid.UUID(res2.lead_id)))).scalars().first()

        assert str(lead1.organization_id) == tenant_1_id
        assert str(lead2.organization_id) == tenant_2_id

    async def test_invalid_tenant_id_fails_closed(self, db_session):
        u_svc = UniversalIntakeService(db_session)
        dto = CanonicalLeadIntakeDTO(source_type=UniversalSourceType.WEBSITE, phone="9876500000")
        with pytest.raises(ValueError, match="Invalid organization_id format"):
            await u_svc.ingest_lead(organization_id="not-a-valid-uuid", dto=dto)


# ─── 8. Section 47 Golden Path E2E Multi-Source Ingestion ──────────────────────

@pytest.mark.asyncio
class TestSection47GoldenPathE2E:
    """
    Validates Section 47 Golden Path End-to-End:
    Meta Lead Ads → Raw Event → Normalization → Tenant Resolution → Identity Creation →
    Lead Creation → Attribution → Outbox → SLA Task → Activity.
    Followed by cross-channel consolidation across:
    WhatsApp → Website → IndiaMART → 99acres to a single Identity node.
    """

    async def test_golden_path_multi_source_convergence(self, db_session, tenant_1_id, setup_brokers):
        u_svc = UniversalIntakeService(db_session)
        person_phone = "9900112233"
        person_email = "kabir.khan@wefylabs.com"

        # ── Stage 1: Meta Lead Ads Ingestion (Primary Inflow) ──
        meta_raw = {
            "leadgen_id": "meta_lead_golden_001",
            "page_id": "page_wefy_1",
            "form_id": "form_luxury_1",
            "field_data": [
                {"name": "full_name", "values": ["Kabir Khan"]},
                {"name": "phone_number", "values": [person_phone]},
                {"name": "email", "values": [person_email]},
                {"name": "budget", "values": ["3.5 Cr"]},
            ]
        }
        meta_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.META,
            external_source="meta_lead_ads",
            external_lead_id="meta_lead_golden_001",
            name="Kabir Khan",
            phone=person_phone,
            email=person_email,
            budget="3.5 Cr",
            property_type="Penthouse",
            city="Gurgaon",
            idempotency_key="meta:meta_lead_golden_001",
        )

        res_meta = await u_svc.ingest_lead(
            organization_id=tenant_1_id,
            dto=meta_dto,
            ip_address="157.240.241.35",
            user_agent="Meta-Hook/2.0",
            raw_payload=meta_raw,
        )

        assert res_meta.status == "ACCEPTED"
        assert res_meta.is_new_lead is True
        golden_lead_id = res_meta.lead_id

        # 1. Verify Raw Event Preservation
        orig_rec = (await db_session.execute(
            select(OriginalPayload).where(OriginalPayload.ingestion_id == res_meta.event_id)
        )).scalars().first()
        assert orig_rec is not None
        assert orig_rec.raw_payload_json["leadgen_id"] == "meta_lead_golden_001"

        # 2. Verify Identity Graph Node
        ident_node = (await db_session.execute(
            select(Identity).where(
                Identity.organization_id == tenant_1_id,
                Identity.primary_phone_e164 == "+919900112233"
            )
        )).scalars().first()
        assert ident_node is not None
        assert ident_node.lead_count == 1
        golden_identity_id = ident_node.id

        # 3. Verify First-Touch Attribution
        attr_rec = (await db_session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == golden_lead_id)
        )).scalars().first()
        assert attr_rec is not None
        assert attr_rec.channel == UniversalSourceType.META

        # 4. Verify Transactional Outbox Event
        outbox_rec = (await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == tenant_1_id,
                OutboxEvent.aggregate_id == golden_lead_id
            )
        )).scalars().first()
        assert outbox_rec is not None
        assert outbox_rec.event_type == "lead.ingested"
        assert outbox_rec.status == OutboxStatus.PENDING

        # ── Stage 2: Website Ingestion for Same Person ──
        web_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.WEBSITE,
            external_source="website_inquiry_modal",
            external_lead_id="web_sub_002",
            name="Kabir Khan",
            phone="+91 99001 12233",  # E.164 spaced
            email=person_email,
            message="Interested in DLF Privana",
            idempotency_key="website:web_sub_002",
        )
        res_web = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=web_dto)
        assert res_web.is_duplicate is True
        assert res_web.lead_id == golden_lead_id

        # Verify First-Touch attribution was NOT overwritten
        await db_session.refresh(attr_rec)
        assert attr_rec.channel == UniversalSourceType.META
        assert attr_rec.last_touch_at is not None

        # ── Stage 3: WhatsApp Inflow with URI format ──
        wa_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.WHATSAPP if hasattr(UniversalSourceType, "WHATSAPP") else UniversalSourceType.WEBHOOK,
            external_source="whatsapp_cloud_api",
            external_lead_id="wa_msg_003",
            name="Kabir",
            phone="whatsapp:+919900112233",  # WhatsApp URI prefix
            message="Can you share brochure on WhatsApp?",
            idempotency_key="wa:wa_msg_003",
        )
        res_wa = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=wa_dto)
        assert res_wa.is_duplicate is True
        assert res_wa.lead_id == golden_lead_id

        # ── Stage 4: IndiaMART Ingestion with trunk 0 ──
        im_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.INDIAMART,
            external_source="indiamart",
            external_lead_id="im_lead_004",
            name="Kabir Khan",
            phone="09900112233",  # 0 trunk
            budget="4 Cr",
            property_type="Villa",
            idempotency_key="indiamart:im_lead_004",
        )
        res_im = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=im_dto)
        assert res_im.is_duplicate is True
        assert res_im.lead_id == golden_lead_id

        # ── Stage 5: 99acres Ingestion with 91 prefix ──
        acres_dto = CanonicalLeadIntakeDTO(
            source_type=UniversalSourceType.NINETY_NINE_ACRES,
            external_source="99acres",
            external_lead_id="99a_lead_005",
            name="Kabir Khan",
            phone="919900112233",  # 91 prefix
            property_id="PROP-DLF-PRIVANA",
            idempotency_key="99acres:99a_lead_005",
        )
        res_acres = await u_svc.ingest_lead(organization_id=tenant_1_id, dto=acres_dto)
        assert res_acres.is_duplicate is True
        assert res_acres.lead_id == golden_lead_id

        # ── Final Invariant Verifications ──
        # 1. Single Lead in Database for this tenant
        total_leads = (await db_session.execute(
            select(func.count()).select_from(Lead).where(
                Lead.organization_id == uuid.UUID(tenant_1_id),
                Lead.phone == "+919900112233"
            )
        )).scalar()
        assert total_leads == 1

        # 2. Single Identity Node consolidating all 5 touchpoints
        await db_session.refresh(ident_node)
        assert ident_node.id == golden_identity_id
        assert ident_node.primary_phone_e164 == "+919900112233"

        # 3. Exactly 1 OutboxEvent for creation, and OutboxEvents for reengagements
        outbox_events = (await db_session.execute(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == tenant_1_id,
                OutboxEvent.aggregate_id == golden_lead_id
            )
        )).scalars().all()
        assert len(outbox_events) >= 2  # Created + reengaged
        event_types = [e.event_type for e in outbox_events]
        assert "lead.ingested" in event_types
        assert "lead.reengaged" in event_types

