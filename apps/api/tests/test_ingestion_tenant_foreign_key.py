"""
Tests for LeadIngestionPipeline tenant foreign key resolution and idempotency.
Verifies that when an Organization ID is supplied during lead ingestion,
the lead is associated with a valid primary member broker so database foreign
key integrity is strictly preserved.
"""
import uuid
import pytest
from sqlalchemy import select

from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.lead import Lead
from app.modules.ingestion.pipeline.ingestion_pipeline import LeadIngestionPipeline


@pytest.mark.asyncio
async def test_lead_ingestion_resolves_organization_member_broker(db_session):
    # 1. Setup Organization, Broker, and Member
    org = Organization(
        id=uuid.uuid4(),
        name="Apex Properties",
        slug="apex-props"
    )
    broker = Broker(
        id=uuid.uuid4(),
        email="apex.owner@example.com",
        name="Apex Owner",
        agency_name="Apex Properties",
        city="Bengaluru",
        whatsapp_number="+919876500112"
    )
    member = OrganizationMember(
        organization_id=org.id,
        broker_id=broker.id,
        role="owner"
    )
    db_session.add_all([org, broker, member])
    await db_session.commit()

    # 2. Ingest lead using organization_id (string format as received by API)
    pipeline = LeadIngestionPipeline(db_session)
    raw_payload = {
        "phone": "+919876543299",
        "name": "Priya Sharma",
        "city": "Bengaluru",
        "property_type": "2bhk",
        "notes": "Looking for 2BHK in Indiranagar under 1.2 Cr",
        "source": "website"
    }

    res = await pipeline.ingest_lead(
        source="website",
        raw_payload=raw_payload,
        organization_id=str(org.id),
        user_id="test_user"
    )

    assert res.status == "ingested"
    assert res.lead_id is not None

    # 3. Verify lead was persisted with broker.id
    lead_uuid = uuid.UUID(res.lead_id)
    lead_stmt = select(Lead).where(Lead.id == lead_uuid)
    lead = (await db_session.execute(lead_stmt)).scalars().first()

    assert lead is not None
    assert lead.broker_id == broker.id
    assert lead.phone == "+919876543299"
    assert lead.name == "Priya Sharma"

    # 4. Ingest again with the exact same payload (Idempotency verification)
    res_dup = await pipeline.ingest_lead(
        source="website",
        raw_payload=raw_payload,
        organization_id=str(org.id),
        user_id="test_user"
    )

    assert res_dup.status == "duplicate"
    assert res_dup.lead_id == str(lead.id)
