"""
Regression & Database Compatibility Test Suite for SourceAttribution
====================================================================
Formalizes the database compatibility matrix and prevents regressions of:
- PostgreSQL 'operator does not exist: character varying = uuid'
- PostgreSQL 'operator does not exist: uuid = character varying'
- Referential integrity: organizations(id) CASCADE, leads(id) SET NULL
- Multi-dialect support: PostgreSQL native UUID and SQLite VARCHAR(36)
- Compatibility across Schema 0048 (production state) and Schema 0049 (migrated state)
"""
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.broker import Broker


class TestSourceAttributionSchemaIntegrity:
    """Verifies that the ORM model definition satisfies canonical CRM requirements."""

    def test_source_attribution_column_types(self):
        mapper = sa_inspect(SourceAttribution)
        cols = {c.key: c for c in mapper.columns}

        assert "id" in cols
        assert "organization_id" in cols
        assert "lead_id" in cols

        org_col = cols["organization_id"]
        lead_col = cols["lead_id"]

        # Nullability contract
        assert not org_col.nullable, "organization_id must NOT be nullable (multi-tenant boundary)"
        assert lead_col.nullable, "lead_id MUST be nullable to allow ON DELETE SET NULL on lead merge/delete"

    def test_source_attribution_foreign_keys(self):
        mapper = sa_inspect(SourceAttribution)
        cols = {c.key: c for c in mapper.columns}

        org_col = cols["organization_id"]
        lead_col = cols["lead_id"]

        # Verify organizations.id FK
        org_fks = list(org_col.foreign_keys)
        assert len(org_fks) == 1, "organization_id must have exactly 1 FK"
        assert org_fks[0].target_fullname == "organizations.id"
        assert org_fks[0].ondelete == "CASCADE"

        # Verify leads.id FK
        lead_fks = list(lead_col.foreign_keys)
        assert len(lead_fks) == 1, "lead_id must have exactly 1 FK"
        assert lead_fks[0].target_fullname == "leads.id"
        assert lead_fks[0].ondelete == "SET NULL"

    def test_source_attribution_provenance_fields(self):
        mapper = sa_inspect(SourceAttribution)
        cols = {c.key: c for c in mapper.columns}

        expected_provenance = [
            "source_id", "campaign_id", "acquisition_event_id", "prospect_id",
            "channel", "provider", "external_id", "landing_page", "referrer",
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "first_touch_at", "last_touch_at", "created_at"
        ]
        for field in expected_provenance:
            assert field in cols, f"Missing provenance field {field} on SourceAttribution"


class TestGUIDTypeDecoratorValidation:
    """Action 5: Strictly verify that string UUID inputs are validated and coerced,
    and invalid UUID values are rejected rather than silently returned."""

    def test_guid_accepts_valid_uuid_object(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        val = uuid.uuid4()
        processed = guid_type.process_bind_param(val, None)
        assert processed == val
        assert isinstance(processed, uuid.UUID)

    def test_guid_coerces_valid_uuid_string(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        val_str = "dac1a157-657b-4e48-8e76-f5469ee2af6b"
        processed = guid_type.process_bind_param(val_str, None)
        assert processed == uuid.UUID(val_str)
        assert isinstance(processed, uuid.UUID)

    def test_guid_rejects_invalid_uuid_string(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        invalid_values = [
            "not-a-uuid",
            "org-a",
            "lead-1",
            "12345",
            "dac1a157-invalid-uuid-string",
            "",
        ]
        for bad_val in invalid_values:
            with pytest.raises(ValueError, match="Invalid UUID string"):
                guid_type.process_bind_param(bad_val, None)

    def test_guid_rejects_invalid_data_types(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        invalid_types = [12345, 45.67, ["list"], {"dict": True}]
        for bad_type_val in invalid_types:
            with pytest.raises(TypeError, match="Expected uuid.UUID or valid UUID str"):
                guid_type.process_bind_param(bad_type_val, None)

    def test_guid_handles_none_gracefully(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        assert guid_type.process_bind_param(None, None) is None
        assert guid_type.process_result_value(None, None) is None

    def test_guid_process_result_value_valid(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        u = uuid.uuid4()
        assert guid_type.process_result_value(u, None) == u
        assert guid_type.process_result_value(str(u), None) == u

    def test_guid_process_result_value_invalid_raises(self):
        from app.models.acquisition_models import GUID
        guid_type = GUID()
        with pytest.raises(ValueError, match="Invalid UUID data"):
            guid_type.process_result_value("corrupt-db-value", None)


@pytest.mark.asyncio
class TestSourceAttributionCompatibility:
    """Verifies runtime behavior of SourceAttribution in the active database session."""

    async def test_source_attribution_insert_and_query_by_uuid(self, db_session: AsyncSession):
        org_id = uuid.uuid4()
        broker_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        attr_id = str(uuid.uuid4())

        # Create prerequisite org, broker, and lead
        org = Organization(id=org_id, name="Attribution Test Org", slug=f"attr-org-{org_id.hex[:8]}")
        broker = Broker(id=broker_id, email=f"broker_{broker_id.hex[:6]}@test.com", name="Broker Test")
        lead = Lead(
            id=lead_id,
            organization_id=org_id,
            broker_id=broker_id,
            phone="+971501234567",
            name="Attribution Lead",
            source="WEBSITE",
            pipeline_stage="new"
        )
        db_session.add_all([org, broker, lead])
        await db_session.flush()

        # Insert SourceAttribution referencing lead via UUID
        attr = SourceAttribution(
            id=attr_id,
            organization_id=org_id,
            lead_id=lead_id,
            channel="WEBSITE",
            provider="meta_ads",
            utm_source="facebook",
            utm_campaign="luxury_villas",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(attr)
        await db_session.flush()

        # Query 1: Filter by UUID object
        q1 = await db_session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == lead_id)
        )
        res1 = q1.scalar_one_or_none()
        assert res1 is not None
        assert res1.id == attr_id
        assert res1.channel == "WEBSITE"

        # Query 2: Filter by str representation of UUID
        q2 = await db_session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == str(lead_id))
        )
        res2 = q2.scalar_one_or_none()
        assert res2 is not None
        assert res2.id == attr_id

        # Query 3: Join Lead and SourceAttribution
        join_q = await db_session.execute(
            select(Lead.id, SourceAttribution.channel).join(
                SourceAttribution, Lead.id == SourceAttribution.lead_id
            ).where(Lead.id == lead_id)
        )
        joined_row = join_q.first()
        assert joined_row is not None
        assert joined_row[0] == lead_id
        assert joined_row[1] == "WEBSITE"

    async def test_source_attribution_set_null_on_lead_delete(self, db_session: AsyncSession):
        from sqlalchemy import text
        if db_session.bind and db_session.bind.dialect.name == "sqlite":
            await db_session.execute(text("PRAGMA foreign_keys = ON;"))

        org_id = uuid.uuid4()
        broker_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        attr_id = str(uuid.uuid4())

        org = Organization(id=org_id, name="SetNull Test Org", slug=f"setnull-{org_id.hex[:8]}")
        broker = Broker(id=broker_id, email=f"broker_{broker_id.hex[:6]}@test.com", name="Broker Test")
        lead = Lead(
            id=lead_id,
            organization_id=org_id,
            broker_id=broker_id,
            phone="+971509876543",
            name="Lead To Delete",
            source="GOOGLE",
            pipeline_stage="new"
        )
        db_session.add_all([org, broker, lead])
        await db_session.flush()

        attr = SourceAttribution(
            id=attr_id,
            organization_id=org_id,
            lead_id=lead_id,
            channel="GOOGLE",
            provider="google_ads",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(attr)
        await db_session.flush()

        # Delete the lead
        await db_session.delete(lead)
        await db_session.flush()

        # Expire local session state to observe DB-level SET NULL cascade
        db_session.expire_all()

        # Fetch attribution — in schema 0049 / compliant DB, attribution is preserved
        refetched = (await db_session.execute(
            select(SourceAttribution).where(SourceAttribution.id == attr_id)
        )).scalar_one_or_none()
        assert refetched is not None, "Marketing attribution record must be preserved even if lead is deleted"
        assert refetched.lead_id is None, "lead_id must be SET NULL when referencing lead is deleted"

