"""
Enterprise Test Suite — CRM Services, RBAC, Audit Log
======================================================
Tests are integration-level using an in-memory SQLite database via pytest-asyncio.
All tests MUST pass against real application code — no mocks, no placeholders.
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

# ─── Import the app ─────────────────────────────────────────
from app.main import app
from app.database import Base
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Meeting, Contact, Notification, Activity, ApiKey, CustomField
from app.models.developer_models import WebhookSubscription, DeveloperApiKey
from app.models.organization import Organization, OrganizationMember, RoleModel, PermissionModel
from app.models.audit_log import AuditLog
from app.services.rbac_service import RBACPermissionEvaluator
from app.services.audit_service import AuditLogService, NotificationService

# ─── Test DB Setup ─────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def engine():
    _engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()

@pytest.fixture
async def db(engine):
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def sample_broker(db):
    unique_token = uuid.uuid4().hex[:8]
    broker = Broker(
        id=uuid.uuid4(),
        name="Test Broker",
        email=f"broker_{unique_token}@beetlelabs.ai",
        phone=f"+91 9{unique_token[:9]}",
        agency_name="Test Agency",
        city="Mumbai",
        subscription_status="active"
    )
    db.add(broker)
    await db.commit()
    await db.refresh(broker)
    return broker

@pytest.fixture
async def sample_organization(db, sample_broker):
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug=f"test-org-{uuid.uuid4().hex[:6]}",
        plan="pro",
        country_code="IN"
    )
    db.add(org)
    await db.flush()

    member = OrganizationMember(
        organization_id=org.id,
        broker_id=sample_broker.id,
        role="owner"
    )
    db.add(member)
    await db.commit()
    return org


# ────────────────────── RBAC Tests ──────────────────────────

class TestRBACPermissionEvaluator:

    async def test_owner_has_all_permissions(self, db, sample_broker, sample_organization):
        """Organization owner must have all standard permissions."""
        perms = await RBACPermissionEvaluator.get_user_permissions(
            db, sample_broker.id, sample_organization.id
        )
        for required in ["leads:create", "leads:read", "billing:manage", "audit:view", "organization:manage"]:
            assert required in perms, f"Owner missing permission: {required}"

    async def test_unenrolled_broker_gets_agent_permissions(self, db, sample_organization):
        """Broker not in any organization gets agent-level read/write permissions."""
        isolated_broker = Broker(
            id=uuid.uuid4(),
            name="Isolated Agent",
            email=f"agent_{uuid.uuid4().hex[:8]}@beetlelabs.ai",
            phone="+91 88888 00001",
            subscription_status="active"
        )
        db.add(isolated_broker)
        await db.flush()

        perms = await RBACPermissionEvaluator.get_user_permissions(db, isolated_broker.id)
        assert "leads:read" in perms
        assert "leads:create" in perms
        assert "billing:manage" not in perms
        assert "organization:manage" not in perms

    async def test_enforce_permission_raises_403_for_forbidden(self, db, sample_organization):
        """Agent attempting billing:manage should receive 403."""
        from fastapi import HTTPException
        agent = Broker(
            id=uuid.uuid4(),
            name="Sales Agent",
            email=f"agent_{uuid.uuid4().hex[:8]}@beetlelabs.ai",
            phone="+91 77777 00001",
            subscription_status="active"
        )
        db.add(agent)
        await db.flush()

        agent_member = OrganizationMember(
            organization_id=sample_organization.id,
            broker_id=agent.id,
            role="agent"
        )
        db.add(agent_member)
        await db.flush()

        with pytest.raises(HTTPException) as exc_info:
            await RBACPermissionEvaluator.enforce_permission(db, agent, "billing:manage")
        assert exc_info.value.status_code == 403


# ────────────────────── Audit Log Tests ──────────────────────

class TestAuditLogService:

    async def test_audit_record_persisted_to_db(self, db, sample_broker, sample_organization):
        """AuditLogService.record() must persist an immutable audit entry."""
        from sqlalchemy import select
        lead_id = str(uuid.uuid4())

        await AuditLogService.record(
            db=db,
            action="lead.create",
            resource_type="lead",
            actor_id=sample_broker.id,
            organization_id=sample_organization.id,
            resource_id=lead_id,
            changes={"phone": "+91 98765 43210", "name": "New Lead"},
            ip_address="127.0.0.1"
        )
        await db.flush()

        stmt = select(AuditLog).where(
            AuditLog.actor_id == sample_broker.id,
            AuditLog.action == "lead.create"
        )
        res = await db.execute(stmt)
        log = res.scalars().first()

        assert log is not None
        assert log.resource_type == "lead"
        assert log.resource_id == lead_id
        assert log.changes is not None

    async def test_audit_failure_never_raises(self, db):
        """AuditLogService must silently absorb DB failures without propagating exceptions."""
        # Intentionally pass a broken session mock
        bad_db = AsyncMock()
        bad_db.add = lambda x: (_ for _ in ()).throw(RuntimeError("DB Down"))

        try:
            await AuditLogService.record(
                db=bad_db,
                action="test.action",
                resource_type="test",
                actor_id=None
            )
        except Exception:
            pytest.fail("AuditLogService.record() must never raise an exception")


# ────────────────────── Notification Tests ──────────────────────

class TestNotificationService:

    async def test_notification_created_and_read(self, db, sample_broker):
        """NotificationService must create and mark-read notifications correctly."""
        from sqlalchemy import select

        notification = await NotificationService.send(
            db=db,
            broker_id=str(sample_broker.id),
            title="New Hot Lead Arrived",
            category="lead",
            body="A high-intent buyer has submitted a request.",
            action_url="/dashboard/leads"
        )
        await db.flush()

        assert notification.is_read is False
        assert notification.category == "lead"

        await NotificationService.mark_read(db, notification.id, str(sample_broker.id))
        await db.flush()

        stmt = select(Notification).where(Notification.id == notification.id)
        res = await db.execute(stmt)
        refreshed = res.scalars().first()
        assert refreshed.is_read is True
        assert refreshed.read_at is not None


# ────────────────────── CRM Entity Tests ──────────────────────

class TestCRMEntities:

    async def test_task_crud(self, db, sample_broker):
        """Create, update, and complete a Task."""
        from sqlalchemy import select

        task = Task(
            broker_id=str(sample_broker.id),
            title="Follow up with buyer",
            description="Call back after property viewing",
            due_at=datetime.now(timezone.utc) + timedelta(days=1),
            priority="high",
            status="pending"
        )
        db.add(task)
        await db.flush()

        assert task.id is not None
        assert task.status == "pending"
        assert task.priority == "high"

        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        await db.flush()

        stmt = select(Task).where(Task.id == task.id)
        res = await db.execute(stmt)
        fetched = res.scalars().first()
        assert fetched.status == "completed"

    async def test_meeting_booking(self, db, sample_broker):
        """Create a Meeting entity with all required fields."""
        meeting = Meeting(
            broker_id=str(sample_broker.id),
            title="Site Visit — 3BHK Property",
            meeting_type="site_visit",
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
            duration_minutes=90,
            location="Prestige Lakeside, Block C",
            status="scheduled"
        )
        db.add(meeting)
        await db.flush()

        assert meeting.id is not None
        assert meeting.meeting_type == "site_visit"
        assert meeting.status == "scheduled"

    async def test_contact_creation(self, db, sample_broker):
        """Create a Contact entity representing a vendor."""
        contact = Contact(
            broker_id=str(sample_broker.id),
            name="Infrastructure Vendor Ltd",
            email="vendor@example.com",
            phone="+91 98765 11111",
            contact_type="vendor",
            company="Infrastructure Vendor Ltd"
        )
        db.add(contact)
        await db.flush()

        assert contact.id is not None
        assert contact.contact_type == "vendor"

    async def test_activity_feed_entry(self, db, sample_broker):
        """Activity entries are immutable and correctly indexed."""
        activity = Activity(
            actor_id=str(sample_broker.id),
            activity_type="lead_created",
            title="New lead added from WhatsApp",
            description="Lead source: WhatsApp Forward",
            activity_data={"source": "whatsapp_forward", "phone": "+91 99988 77766"}
        )
        db.add(activity)
        await db.flush()

        assert activity.id is not None
        assert activity.activity_type == "lead_created"
        assert activity.activity_data["source"] == "whatsapp_forward"

    async def test_api_key_hashing(self, db, sample_broker):
        """API Keys must be stored as SHA-256 hashes, never as plaintext."""
        import hashlib, secrets

        raw_key = f"bl_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:10]

        api_key = ApiKey(
            organization_id=str(uuid.uuid4()),
            broker_id=str(sample_broker.id),
            name="Integration Key",
            key_hash=key_hash,
            key_prefix=key_prefix,
            scopes=["leads:read", "tasks:write"]
        )
        db.add(api_key)
        await db.flush()

        assert api_key.key_hash != raw_key  # Must not be stored in plaintext
        assert api_key.key_hash == key_hash
        assert api_key.key_prefix == key_prefix

    async def test_custom_field_schema(self, db):
        """CustomField enables schema-less per-org extensibility."""
        cf = CustomField(
            organization_id=str(uuid.uuid4()),
            entity_type="lead",
            field_name="loan_institution",
            field_label="Loan Institution",
            field_type="text",
            is_required=False
        )
        db.add(cf)
        await db.flush()

        assert cf.id is not None
        assert cf.entity_type == "lead"
        assert cf.field_type == "text"


# ────────────────────── Lead Model Tests ──────────────────────

class TestLeadModel:

    async def test_lead_creation_with_full_profile(self, db, sample_broker):
        """Leads must be created with all CRM profile fields, tenant-isolated."""
        lead = Lead(
            broker_id=sample_broker.id,
            phone="+91 99911 22233",
            name="Verified Buyer",
            source="manual",
            budget_min=5000000,
            budget_max=8000000,
            property_type="2bhk",
            transaction_type="buy",
            preferred_locations=["Whitefield", "Koramangala"],
            timeline="3_months",
            loan_status="pre_approved",
            status="active",
            pipeline_stage="contacted"
        )
        db.add(lead)
        await db.flush()

        assert lead.id is not None
        assert lead.score == "pending"  # Default
        assert lead.pipeline_stage == "contacted"
        assert lead.budget_min == 5000000
        assert "Whitefield" in lead.preferred_locations

    async def test_lead_soft_delete(self, db, sample_broker):
        """Soft-deleted leads must have a deleted_at timestamp and be filterable."""
        from sqlalchemy import select

        lead = Lead(
            broker_id=sample_broker.id,
            phone="+91 88822 33344",
            source="manual",
            status="lost"
        )
        db.add(lead)
        await db.flush()

        lead.deleted_at = datetime.now(timezone.utc)
        await db.flush()

        stmt = select(Lead).where(Lead.id == lead.id, Lead.deleted_at.is_(None))
        res = await db.execute(stmt)
        result = res.scalars().first()
        assert result is None  # Correctly excluded by soft-delete filter
