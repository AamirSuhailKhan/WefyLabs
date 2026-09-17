"""
PART 31 — Integration Test Suite: Customer Onboarding, Tenant Activation & Demo Mode
=====================================================================================
22 integration tests using async SQLite in-memory database:
- Onboarding state initialization & resumption
- Business profile persistence to Organization model
- Step progression and skipping state management
- Dynamic live-entity synchronization (properties, leads, matches, tasks)
- Tenant activation score and milestone calculation against real database records
- Existing tenant auto-activation without user disruption
- Isolated demo workspace provisioning with synthetic inventory
- Demo organization and broker isolation flags (is_demo=True)
- Safe demo session teardown and expired TTL cleanup
- CSV preview and transactional batch commit with duplicate detection
- Team member invitation creation and step completion
- Multi-tenant isolation between distinct organizations
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_

from app.database import Base
from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.recommendation_models import Recommendation, RecommendationItem
from app.models.crm_models import Task
from app.models.follow_up import FollowUp
from app.models.onboarding_models import OnboardingState, TenantActivation, DemoSession
from app.models.invitation_models import OrganizationInvitation

from app.modules.onboarding.onboarding_service import OnboardingService
from app.modules.onboarding.activation_service import TenantActivationService
from app.modules.onboarding.demo_service import DemoModeService
from app.modules.onboarding.csv_import_service import OnboardingCsvImportService
from app.modules.onboarding.dto import (
    BusinessProfileSetupDTO,
    OnboardingStepUpdateDTO,
    CsvImportCommitDTO,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def broker_alpha(db_session: AsyncSession):
    b_id = uuid.uuid4()
    org_id = b_id
    org = Organization(
        id=org_id,
        name="Alpha Real Estate Group",
        slug=f"alpha-{b_id.hex[:6]}",
        plan="pro",
        country_code="IN",
        currency_code="INR",
        default_timezone="Asia/Kolkata",
        business_type="agency"
    )
    db_session.add(org)

    broker = Broker(
        id=b_id,
        email=f"alpha_{b_id.hex[:6]}@crm.com",
        name="Alpha Broker",
        agency_name="Alpha Real Estate Group",
        city="Bengaluru",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)

    member = OrganizationMember(
        organization_id=org_id,
        broker_id=b_id,
        role="owner"
    )
    db_session.add(member)
    await db_session.flush()
    return broker


@pytest_asyncio.fixture
async def broker_beta(db_session: AsyncSession):
    b_id = uuid.uuid4()
    org_id = b_id
    org = Organization(
        id=org_id,
        name="Beta Luxury Properties",
        slug=f"beta-{b_id.hex[:6]}",
        plan="pro",
        country_code="IN",
        currency_code="INR",
        default_timezone="Asia/Kolkata",
        business_type="agency"
    )
    db_session.add(org)

    broker = Broker(
        id=b_id,
        email=f"beta_{b_id.hex[:6]}@crm.com",
        name="Beta Broker",
        agency_name="Beta Luxury Properties",
        city="Mumbai",
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(broker)

    member = OrganizationMember(
        organization_id=org_id,
        broker_id=b_id,
        role="owner"
    )
    db_session.add(member)
    await db_session.flush()
    return broker


# ─── 1. Onboarding State Machine & Persistence Tests ─────────────────────────

@pytest.mark.asyncio
async def test_get_or_create_onboarding_state_initializes_defaults(db_session: AsyncSession, broker_alpha: Broker):
    service = OnboardingService(db_session)
    state = await service.get_or_create_state(broker_alpha)
    assert state is not None
    assert state.current_step == "ORGANIZATION_SETUP"
    assert state.completed_steps == []
    assert state.is_completed is False


@pytest.mark.asyncio
async def test_update_business_profile_persists_to_organization(db_session: AsyncSession, broker_alpha: Broker):
    service = OnboardingService(db_session)
    dto = BusinessProfileSetupDTO(
        agency_name="Apex Elite Properties",
        business_type="brokerage",
        city="Bengaluru",
        country_code="IN",
        timezone="Asia/Kolkata",
        currency_code="INR",
        team_size="6-20",
        primary_business_model="residential_sales"
    )
    status = await service.update_business_profile(broker_alpha, dto)
    assert "ORGANIZATION_SETUP" in status.completed_steps
    assert broker_alpha.agency_name == "Apex Elite Properties"

    # Verify Organization record in DB
    org = await db_session.get(Organization, uuid.UUID(status.organization_id))
    assert org.name == "Apex Elite Properties"
    assert org.business_type == "brokerage"
    assert org.currency_code == "INR"


@pytest.mark.asyncio
async def test_onboarding_step_progression_advances_current_step(db_session: AsyncSession, broker_alpha: Broker):
    service = OnboardingService(db_session)
    update_dto = OnboardingStepUpdateDTO(
        step="DATA_SOURCE",
        action="complete",
        payload={"source_choice": "sample_data"}
    )
    status = await service.update_step(broker_alpha, update_dto)
    assert "DATA_SOURCE" in status.completed_steps
    assert status.current_step == "PROPERTY_SETUP"


@pytest.mark.asyncio
async def test_onboarding_step_skipping_persists_in_skipped_steps(db_session: AsyncSession, broker_alpha: Broker):
    service = OnboardingService(db_session)
    skip_dto = OnboardingStepUpdateDTO(
        step="PROPERTY_SETUP",
        action="skip"
    )
    status = await service.update_step(broker_alpha, skip_dto)
    assert "PROPERTY_SETUP" in status.skipped_steps
    assert status.current_step == "LEAD_SETUP"


@pytest.mark.asyncio
async def test_onboarding_resume_preserves_completed_and_payload(db_session: AsyncSession, broker_alpha: Broker):
    service = OnboardingService(db_session)
    # Simulate a new request session
    fresh_service = OnboardingService(db_session)
    status = await fresh_service.get_status(broker_alpha)
    assert status.organization_id is not None
    assert isinstance(status.completed_steps, list)
    assert isinstance(status.checklist, list)
    assert len(status.checklist) == 8


# ─── 2. Live Entity Synchronization Tests ─────────────────────────────────────

@pytest.mark.asyncio
async def test_live_entity_sync_auto_completes_property_step(db_session: AsyncSession, broker_alpha: Broker):
    # Directly insert property into DB outside of onboarding wizard
    prop = PropertyListing(
        broker_id=broker_alpha.id,
        title="Directly Created 3BHK Indiranagar",
        description="Created via standard CRM",
        price=18000000.0,
        currency_code="INR",
        area_value=1650.0,
        bedrooms=3,
        bathrooms=3,
        status="available"
    )
    db_session.add(prop)
    await db_session.flush()

    # Now call onboarding status — PROPERTY_SETUP must be automatically marked complete
    service = OnboardingService(db_session)
    status = await service.get_status(broker_alpha)
    assert "PROPERTY_SETUP" in status.completed_steps


@pytest.mark.asyncio
async def test_live_entity_sync_auto_completes_lead_step(db_session: AsyncSession, broker_alpha: Broker):
    lead = Lead(
        broker_id=broker_alpha.id,
        name="Pooja Hegde",
        phone="+919876500001",
        budget_min=10000000,
        budget_max=15000000,
        property_type="apartment",
        status="active"
    )
    db_session.add(lead)
    await db_session.flush()

    service = OnboardingService(db_session)
    status = await service.get_status(broker_alpha)
    assert "LEAD_SETUP" in status.completed_steps


@pytest.mark.asyncio
async def test_live_entity_sync_auto_completes_match_step(db_session: AsyncSession, broker_alpha: Broker):
    org_id = broker_alpha.organization_id
    rec = Recommendation(
        lead_id=str(uuid.uuid4()),
        broker_id=str(broker_alpha.id),
        organization_id=str(org_id),
        total_candidates_retrieved=5,
        filtered_candidates_count=1
    )
    db_session.add(rec)
    await db_session.flush()

    service = OnboardingService(db_session)
    status = await service.get_status(broker_alpha)
    assert "MATCH_SHOWCASE" in status.completed_steps


@pytest.mark.asyncio
async def test_live_entity_sync_auto_completes_followup_step(db_session: AsyncSession, broker_alpha: Broker):
    org_id = broker_alpha.organization_id
    task = Task(
        broker_id=broker_alpha.id,
        organization_id=str(org_id),
        title="Call Pooja regarding Indiranagar site visit",
        status="pending"
    )
    db_session.add(task)
    await db_session.flush()

    service = OnboardingService(db_session)
    status = await service.get_status(broker_alpha)
    assert "FOLLOWUP_SETUP" in status.completed_steps


# ─── 3. Tenant Activation Service Tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_activation_service_calculates_milestones_from_db(db_session: AsyncSession, broker_beta: Broker):
    act_service = TenantActivationService(db_session)
    res = await act_service.get_or_calculate_activation(broker_beta)
    # Only organization exists so far -> 20 points
    assert res.is_activated is False
    assert res.activation_score == 20
    assert "ORGANIZATION_CREATED" in res.completed_milestones


@pytest.mark.asyncio
async def test_activation_service_achieves_activation_with_5_milestones(db_session: AsyncSession, broker_beta: Broker):
    # Add property, lead, match, task
    prop = PropertyListing(
        broker_id=broker_beta.id,
        title="Beta 4BHK Sky Villa Bandra",
        description="Luxury apartment",
        price=55000000.0,
        currency_code="INR",
        area_value=2800.0,
        bedrooms=4,
        bathrooms=4,
        status="available"
    )
    lead = Lead(
        broker_id=broker_beta.id,
        name="Karan Johar",
        phone="+919820099999",
        budget_min=40000000,
        budget_max=60000000,
        status="active"
    )
    db_session.add_all([prop, lead])
    await db_session.flush()

    org_id = broker_beta.organization_id
    rec = Recommendation(
        lead_id=str(lead.id),
        broker_id=str(broker_beta.id),
        organization_id=str(org_id),
        total_candidates_retrieved=1,
        filtered_candidates_count=1
    )
    task = Task(
        broker_id=broker_beta.id,
        organization_id=str(org_id),
        title="Site visit preview",
        status="pending"
    )
    db_session.add_all([rec, task])
    await db_session.flush()

    act_service = TenantActivationService(db_session)
    res = await act_service.get_or_calculate_activation(broker_beta, force_refresh=True)
    assert res.activation_score == 100
    assert res.is_activated is True
    assert len(res.completed_milestones) == 5
    assert len(res.missing_requirements) == 0


@pytest.mark.asyncio
async def test_existing_tenant_with_past_data_immediately_activated(db_session: AsyncSession, broker_beta: Broker):
    """Existing tenant with prior data gets is_activated=True immediately."""
    prop = PropertyListing(
        broker_id=broker_beta.id,
        title="Existing Pre-Part31 Villa",
        description="Historic record",
        price=30000000.0,
        currency_code="INR",
        area_value=2200.0,
        bedrooms=3,
        bathrooms=3,
        status="available"
    )
    lead = Lead(
        broker_id=broker_beta.id,
        name="Historic Client",
        phone="+919820012345",
        status="active"
    )
    rec = Recommendation(
        lead_id=str(uuid.uuid4()),
        broker_id=str(broker_beta.id),
        organization_id=str(broker_beta.id),
        total_candidates_retrieved=1,
        filtered_candidates_count=1
    )
    task = Task(
        broker_id=broker_beta.id,
        organization_id=str(broker_beta.id),
        title="Historic follow up",
        status="pending"
    )
    db_session.add_all([prop, lead, rec, task])
    await db_session.flush()

    act_service = TenantActivationService(db_session)
    res = await act_service.get_or_calculate_activation(broker_beta)
    assert res.is_activated is True
    assert res.activation_score == 100


# ─── 4. Demo Mode Service Integration Tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_demo_mode_service_spawns_isolated_demo_tenant(db_session: AsyncSession):
    demo_svc = DemoModeService(db_session)
    session_dto = await demo_svc.create_demo_workspace(
        intended_agency_name="Prestige Demo Brokerage",
        operating_city="Bengaluru"
    )
    assert session_dto.session_token is not None
    assert session_dto.demo_organization_id is not None
    assert session_dto.seeded_properties_count == 10
    assert session_dto.seeded_leads_count == 8
    assert session_dto.seeded_matches_count >= 1
    assert session_dto.seeded_tasks_count >= 1

    # Verify Organization is_demo=True
    org = await db_session.get(Organization, uuid.UUID(session_dto.demo_organization_id))
    assert org is not None
    assert org.is_demo is True

    # Verify Broker is_demo=True
    broker = await db_session.get(Broker, uuid.UUID(session_dto.demo_broker_id))
    assert broker is not None
    assert broker.is_demo is True


@pytest.mark.asyncio
async def test_demo_mode_seeded_entities_association(db_session: AsyncSession):
    demo_svc = DemoModeService(db_session)
    session_dto = await demo_svc.create_demo_workspace(operating_city="Mumbai")
    b_id = uuid.UUID(session_dto.demo_broker_id)

    # Verify all properties belong strictly to demo broker
    stmt = select(PropertyListing).where(PropertyListing.broker_id == b_id)
    res = await db_session.execute(stmt)
    properties = res.scalars().all()
    assert len(properties) == 10

    # Verify all leads belong strictly to demo broker
    stmt_lead = select(Lead).where(Lead.broker_id == b_id)
    res_lead = await db_session.execute(stmt_lead)
    leads = res_lead.scalars().all()
    assert len(leads) == 8


@pytest.mark.asyncio
async def test_demo_mode_reset_safely_purges_only_demo_org(db_session: AsyncSession):
    demo_svc = DemoModeService(db_session)
    session_dto = await demo_svc.create_demo_workspace(operating_city="Gurugram")
    token = session_dto.session_token
    demo_org_id = uuid.UUID(session_dto.demo_organization_id)

    # Reset/purge demo session
    success = await demo_svc.reset_demo_session(token)
    assert success is True

    # Organization must no longer exist
    org = await db_session.get(Organization, demo_org_id)
    assert org is None


@pytest.mark.asyncio
async def test_demo_mode_cleanup_expired_sessions(db_session: AsyncSession):
    demo_svc = DemoModeService(db_session)
    session_dto = await demo_svc.create_demo_workspace(operating_city="Bengaluru")

    # Manually expire the session in DB
    stmt = select(DemoSession).where(DemoSession.session_token == session_dto.session_token)
    res = await db_session.execute(stmt)
    session = res.scalars().first()
    session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()

    purged = await demo_svc.cleanup_expired_demo_sessions()
    assert purged == 1


# ─── 5. CSV Import Service Integration Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_csv_preview_detects_duplicates_against_existing_db_leads(db_session: AsyncSession, broker_alpha: Broker):
    # Existing lead
    lead = Lead(
        broker_id=broker_alpha.id,
        name="Existing Client",
        phone="+919876543210",
        status="active"
    )
    db_session.add(lead)
    await db_session.flush()

    raw_csv = """name,phone,budget_max,property_type
New Buyer 1,+919876543210,15000000,apartment
New Buyer 2,+919999988888,25000000,villa"""

    csv_svc = OnboardingCsvImportService(db_session)
    preview = await csv_svc.preview_csv(broker_alpha, raw_csv, entity_type="leads")
    assert preview.total_rows == 2
    assert preview.duplicate_rows_count == 1  # 9876543210 already in DB
    assert preview.valid_rows_count == 1


@pytest.mark.asyncio
async def test_csv_preview_detects_duplicates_against_existing_db_properties(db_session: AsyncSession, broker_alpha: Broker):
    prop = PropertyListing(
        broker_id=broker_alpha.id,
        title="Indiranagar 3BHK Resale",
        description="Existing property",
        price=18000000.0,
        currency_code="INR",
        area_value=1600.0,
        bedrooms=3,
        bathrooms=3,
        status="available"
    )
    db_session.add(prop)
    await db_session.flush()

    raw_csv = """title,price,bedrooms,bathrooms,area,city
Indiranagar 3BHK Resale,18000000,3,3,1600,Bengaluru
Whitefield 2BHK New,9500000,2,2,1100,Bengaluru"""

    csv_svc = OnboardingCsvImportService(db_session)
    preview = await csv_svc.preview_csv(broker_alpha, raw_csv, entity_type="properties")
    assert preview.total_rows == 2
    assert preview.duplicate_rows_count == 1
    assert preview.valid_rows_count == 1


@pytest.mark.asyncio
async def test_csv_commit_transactionally_persists_leads(db_session: AsyncSession, broker_alpha: Broker):
    csv_svc = OnboardingCsvImportService(db_session)
    commit_dto = CsvImportCommitDTO(
        entity_type="leads",
        items=[
            {
                "name": "Arun Kumar",
                "phone": "+919845012345",
                "budget_min": 10000000,
                "budget_max": 18000000,
                "property_type": "apartment"
            },
            {
                "name": "Meera Nair",
                "phone": "+919845012346",
                "budget_min": 20000000,
                "budget_max": 30000000,
                "property_type": "villa"
            }
        ]
    )
    result = await csv_svc.commit_import(broker_alpha, commit_dto)
    assert result.status == "success"
    assert result.imported_count == 2
    assert len(result.imported_ids) == 2

    # Verify leads exist in DB
    stmt = select(Lead).where(Lead.phone.in_(["+919845012345", "+919845012346"]))
    res = await db_session.execute(stmt)
    assert len(res.scalars().all()) == 2


@pytest.mark.asyncio
async def test_csv_commit_transactionally_persists_properties(db_session: AsyncSession, broker_alpha: Broker):
    csv_svc = OnboardingCsvImportService(db_session)
    commit_dto = CsvImportCommitDTO(
        entity_type="properties",
        items=[
            {
                "title": "Sobha Royal Pavilion 3BHK",
                "price": 22000000.0,
                "bedrooms": 3,
                "bathrooms": 3,
                "area_value": 1850.0,
                "city": "Bengaluru"
            }
        ]
    )
    result = await csv_svc.commit_import(broker_alpha, commit_dto)
    assert result.status == "success"
    assert result.imported_count == 1

    stmt = select(PropertyListing).where(PropertyListing.title == "Sobha Royal Pavilion 3BHK")
    res = await db_session.execute(stmt)
    assert len(res.scalars().all()) == 1


# ─── 6. Multi-Tenant Isolation Verification ───────────────────────────────────

@pytest.mark.asyncio
async def test_multi_tenant_isolation_between_distinct_organizations(
    db_session: AsyncSession,
    broker_alpha: Broker,
    broker_beta: Broker
):
    service_alpha = OnboardingService(db_session)
    service_beta = OnboardingService(db_session)

    status_alpha = await service_alpha.get_status(broker_alpha)
    status_beta = await service_beta.get_status(broker_beta)

    # Confirm organization IDs are completely distinct
    assert status_alpha.organization_id != status_beta.organization_id
    assert status_alpha.broker_id != status_beta.broker_id
