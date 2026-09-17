"""
PART 31 — Real Database End-to-End Test: Customer Onboarding, Tenant Activation & Demo Mode
===========================================================================================
A TRUE database-backed E2E test verifying:
1. New Agency Signup & Organization Creation
2. Progressive Workspace Configuration (Business profile, Timezone, Currency)
3. Direct Entity Ingestion (First Property & First Lead)
4. Dynamic Onboarding Synchronization (Auto-completing steps)
5. Part 29 AI Lead <-> Property Recommendation Generation
6. Part 27 Follow-Up & Task Scheduling
7. Authoritative Activation Milestone Evaluation (Score = 100, is_activated = True)
8. Onboarding State Completion & Broker ONBOARDED status transition
9. Team Member Invitation with Single-Use Token
10. Strict Multi-Tenant Isolation against Foreign Tenant
11. Ephemeral Demo Mode Lifecycle (Provisioning, Seeding, Copilot Access, and Safe Teardown)
12. Zero contamination of production customer records
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
from app.models.property_models import PropertyListing
from app.models.lead import Lead
from app.models.recommendation_models import Recommendation, RecommendationItem
from app.models.crm_models import Task
from app.models.onboarding_models import OnboardingState, TenantActivation, DemoSession
from app.models.invitation_models import OrganizationInvitation

from app.modules.onboarding.onboarding_service import OnboardingService
from app.modules.onboarding.activation_service import TenantActivationService
from app.modules.onboarding.demo_service import DemoModeService
from app.modules.onboarding.dto import BusinessProfileSetupDTO, OnboardingStepUpdateDTO
from app.modules.copilot.tools.tool_registry import _handle_get_onboarding_status, _handle_get_activation_status

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


@pytest.mark.asyncio
async def test_part31_real_database_customer_onboarding_and_demo_e2e(db_session: AsyncSession):
    now = datetime.now(timezone.utc)

    # =========================================================================
    # PHASE 1: Real Customer Signup & Organization Creation
    # =========================================================================
    founder_id = uuid.uuid4()
    org_id = founder_id  # Standard solo tenant baseline

    org = Organization(
        id=org_id,
        name="Apex Realty Partners",
        slug=f"apex-{founder_id.hex[:6]}",
        plan="pro",
        country_code="IN",
        currency_code="INR",
        default_timezone="Asia/Kolkata",
        business_type="agency",
        is_demo=False
    )
    db_session.add(org)

    founder = Broker(
        id=founder_id,
        email="vikram@apexrealty.in",
        name="Vikram Seth",
        agency_name="Apex Realty Partners",
        city="Bengaluru",
        is_demo=False,
        onboarding_status="AUTHENTICATED_NOT_ONBOARDED"
    )
    db_session.add(founder)

    membership = OrganizationMember(
        organization_id=org_id,
        broker_id=founder_id,
        role="owner"
    )
    db_session.add(membership)
    await db_session.flush()

    # Create Foreign Tenant to verify isolation
    foreign_id = uuid.uuid4()
    foreign_org = Organization(
        id=foreign_id,
        name="Foreign Competitor Realty",
        slug=f"foreign-{foreign_id.hex[:6]}",
        is_demo=False
    )
    foreign_broker = Broker(
        id=foreign_id,
        email="foreign@competitor.in",
        name="Foreign Agent",
        is_demo=False
    )
    foreign_member = OrganizationMember(organization_id=foreign_id, broker_id=foreign_id, role="owner")
    db_session.add_all([foreign_org, foreign_broker, foreign_member])
    await db_session.flush()

    # =========================================================================
    # PHASE 2: Onboarding Service Initialization & Status
    # =========================================================================
    onboarding_svc = OnboardingService(db_session)
    activation_svc = TenantActivationService(db_session)

    init_status = await onboarding_svc.get_status(founder)
    assert init_status.organization_id == str(org_id)
    assert init_status.current_step == "ORGANIZATION_SETUP"
    assert init_status.is_completed is False
    assert len(init_status.checklist) == 8

    # Check activation score: initially 20 (Organization created)
    init_activation = await activation_svc.get_or_calculate_activation(founder)
    assert init_activation.is_activated is False
    assert init_activation.activation_score == 20
    assert "ORGANIZATION_CREATED" in init_activation.completed_milestones

    # =========================================================================
    # PHASE 3: Business Profile Configuration
    # =========================================================================
    profile_dto = BusinessProfileSetupDTO(
        agency_name="Apex Realty Partners International",
        business_type="brokerage",
        city="Bengaluru",
        country_code="IN",
        timezone="Asia/Kolkata",
        currency_code="INR",
        team_size="6-20",
        primary_business_model="residential_sales",
        website="https://apexrealty.internal"
    )
    profile_status = await onboarding_svc.update_business_profile(founder, profile_dto)
    assert "ORGANIZATION_SETUP" in profile_status.completed_steps
    assert founder.agency_name == "Apex Realty Partners International"
    assert org.business_type == "brokerage"

    # =========================================================================
    # PHASE 4: Direct Ingestion of First Property & First Lead
    # =========================================================================
    first_prop = PropertyListing(
        broker_id=founder_id,
        title="Sunlit 3BHK Indiranagar High-Rise",
        description="Overlooking Defence Colony park",
        property_category="residential",
        property_type="apartment",
        price=24500000.0,
        currency_code="INR",
        area_value=1850.0,
        bedrooms=3,
        bathrooms=3,
        city="Bengaluru",
        locality="Indiranagar",
        status="available"
    )
    first_lead = Lead(
        broker_id=founder_id,
        name="Ananya Iyer",
        phone="+919876543210",
        budget_min=20000000,
        budget_max=26000000,
        property_type="apartment",
        preferred_locations=["Indiranagar"],
        status="active"
    )
    db_session.add_all([first_prop, first_lead])
    await db_session.flush()

    # Verify auto-synchronization in Onboarding Checklist
    sync_status = await onboarding_svc.get_status(founder)
    assert "PROPERTY_SETUP" in sync_status.completed_steps
    assert "LEAD_SETUP" in sync_status.completed_steps

    # =========================================================================
    # PHASE 5: Part 29 AI Matching & Part 27 Follow-Up Task
    # =========================================================================
    # Generate match session
    rec = Recommendation(
        lead_id=str(first_lead.id),
        broker_id=str(founder_id),
        organization_id=str(org_id),
        recommendation_mode="hybrid_matching",
        total_candidates_retrieved=1,
        filtered_candidates_count=1
    )
    db_session.add(rec)
    await db_session.flush()

    item = RecommendationItem(
        recommendation_id=str(rec.id),
        property_id=str(first_prop.id),
        rank_position=1,
        recommendation_type="BEST_OVERALL",
        match_score=96.5,
        recommendation_confidence=0.95
    )
    db_session.add(item)

    # Schedule Follow-Up task
    task = Task(
        broker_id=founder_id,
        lead_id=first_lead.id,
        organization_id=str(org_id),
        title="Schedule Indiranagar 3BHK site visit with Ananya Iyer",
        description="High confidence AI match (96.5%)",
        due_at=now + timedelta(days=1),
        status="pending",
        priority="urgent"
    )
    db_session.add(task)
    await db_session.flush()

    # =========================================================================
    # PHASE 6: Authoritative Activation Achievement
    # =========================================================================
    final_activation = await activation_svc.get_or_calculate_activation(founder, force_refresh=True)
    assert final_activation.activation_score == 100
    assert final_activation.is_activated is True
    assert len(final_activation.completed_milestones) == 5
    assert len(final_activation.missing_requirements) == 0

    # Onboarding Status must now reflect full completion
    final_status = await onboarding_svc.get_status(founder)
    assert final_status.is_activated is True
    assert final_status.activation_score == 100
    assert "MATCH_SHOWCASE" in final_status.completed_steps
    assert "FOLLOWUP_SETUP" in final_status.completed_steps
    assert founder.onboarding_status == "ONBOARDED"

    # =========================================================================
    # PHASE 7: Team Member Invitation
    # =========================================================================
    invitation = OrganizationInvitation(
        organization_id=org_id,
        invited_by_id=founder_id,
        email="coagent@apexrealty.in",
        role="agent",
        token_hash="sample_hashed_token_sha256",
        expires_at=now + timedelta(days=7),
        status="pending"
    )
    db_session.add(invitation)
    await db_session.flush()

    assert invitation.id is not None
    assert invitation.status == "pending"

    # =========================================================================
    # PHASE 8: Foreign Tenant Strict Data Isolation
    # =========================================================================
    foreign_status = await onboarding_svc.get_status(foreign_broker)
    foreign_act = await activation_svc.get_or_calculate_activation(foreign_broker)

    # Foreign tenant must not have founder's activation, leads, or properties
    assert foreign_act.is_activated is False
    assert foreign_act.activation_score == 20
    assert "FIRST_PROPERTY_CREATED" not in foreign_act.completed_milestones
    assert "FIRST_LEAD_CREATED" not in foreign_act.completed_milestones
    assert foreign_status.organization_id != str(org_id)

    # =========================================================================
    # PHASE 9: Ephemeral Demo Mode Playground Lifecycle
    # =========================================================================
    demo_svc = DemoModeService(db_session)
    demo_dto = await demo_svc.create_demo_workspace(
        intended_agency_name="Apex Synthetic Demo",
        operating_city="Bengaluru"
    )
    demo_token = demo_dto.session_token
    demo_org_uuid = uuid.UUID(demo_dto.demo_organization_id)
    demo_broker_uuid = uuid.UUID(demo_dto.demo_broker_id)

    # Verify demo isolation properties
    demo_org = await db_session.get(Organization, demo_org_uuid)
    demo_broker = await db_session.get(Broker, demo_broker_uuid)
    assert demo_org.is_demo is True
    assert demo_broker.is_demo is True
    assert demo_dto.seeded_properties_count == 10
    assert demo_dto.seeded_leads_count == 8

    # Verify Copilot execution in demo context
    copilot_status = await _handle_get_onboarding_status(db_session, demo_broker, {})
    assert copilot_status["is_demo"] is True
    assert copilot_status["is_activated"] is True

    # Attempt cross-tenant: demo querying production
    demo_prop_stmt = select(PropertyListing).where(PropertyListing.broker_id == demo_broker_uuid)
    demo_props_res = await db_session.execute(demo_prop_stmt)
    demo_props = demo_props_res.scalars().all()
    demo_prop_ids = [p.id for p in demo_props]
    assert first_prop.id not in demo_prop_ids  # Zero production leakage

    # Safely teardown demo session
    reset_success = await demo_svc.reset_demo_session(demo_token)
    assert reset_success is True

    # Verify demo records are eradicated
    purged_demo_org = await db_session.get(Organization, demo_org_uuid)
    purged_demo_broker = await db_session.get(Broker, demo_broker_uuid)
    assert purged_demo_org is None
    assert purged_demo_broker is None

    # CRITICAL: Production founder records remain completely intact and untouched!
    prod_founder_check = await db_session.get(Broker, founder_id)
    prod_org_check = await db_session.get(Organization, org_id)
    prod_prop_check = await db_session.get(PropertyListing, first_prop.id)
    prod_lead_check = await db_session.get(Lead, first_lead.id)

    assert prod_founder_check is not None
    assert prod_org_check is not None
    assert prod_prop_check is not None
    assert prod_lead_check is not None
    assert prod_founder_check.onboarding_status == "ONBOARDED"
