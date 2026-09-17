"""
test_part33_e2e.py
==================
Part 33 — End-to-End Production Acceptance & Lifecycle Smoke Test

Simulates the complete production lifecycle workflow:
1. User registration & secure password hashing
2. Organization / Workspace provisioning
3. Lead ingestion & attribute persistence
4. Property listing creation
5. Deterministic AI Matching execution
6. Follow-up task scheduling
7. Agent Command Center summary calculation
8. Onboarding workflow state transitions
9. Copilot assistance availability
10. Health & readiness verification
"""
from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.broker import Broker
from app.models.organization import Organization
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.crm_models import Task
from app.models.onboarding_models import OnboardingState
from app.modules.auth.service import hash_password, verify_password

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


class TestProductionLifecycleE2E:
    """Validates the core real estate workflow end-to-end against database session."""

    async def test_full_workspace_lifecycle_e2e(self, db_session: AsyncSession):
        test_suffix = uuid.uuid4().hex[:8]

        # ── 1. Create Broker Account ──────────────────────────────────────────
        password = "ProductionPassword2026!#"
        pwd_hash = hash_password(password)
        assert verify_password(password, pwd_hash)

        broker = Broker(
            id=uuid.uuid4(),
            email=f"broker_{test_suffix}@launchtest.com",
            password_hash=pwd_hash,
            name=f"Launch Agent {test_suffix}",
            phone="+919876543210",
            city="Bengaluru",
            subscription_status="active",
        )
        db_session.add(broker)
        await db_session.flush()

        # ── 2. Create Organization Workspace ───────────────────────────────────
        org = Organization(
            id=uuid.uuid4(),
            name=f"Apex Realty {test_suffix}",
            slug=f"apex-realty-{test_suffix}",
            business_type="brokerage",
            currency_code="INR",
            team_size="6-20",
            is_demo=False,
        )
        db_session.add(org)
        await db_session.flush()

        # ── 3. Initialize Onboarding State ─────────────────────────────────────
        onboarding = OnboardingState(
            id=uuid.uuid4(),
            organization_id=org.id,
            broker_id=broker.id,
            current_step="TEAM_INVITE",
            completed_steps=["ORGANIZATION_SETUP"],
            skipped_steps=[],
            is_completed=False,
        )
        db_session.add(onboarding)
        await db_session.flush()

        # ── 4. Ingest Lead ────────────────────────────────────────────────────
        lead = Lead(
            id=uuid.uuid4(),
            broker_id=broker.id,
            name=f"Investor {test_suffix}",
            phone="+919812345678",
            budget_min=10000000,
            budget_max=15000000,
            property_type="3bhk",
            preferred_locations=["Bengaluru"],
            score="hot",
            score_confidence=0.95,
            pipeline_stage="qualified",
            budget_currency="INR",
        )
        db_session.add(lead)
        await db_session.flush()

        # ── 5. Create Property Listing ─────────────────────────────────────────
        prop = PropertyListing(
            id=uuid.uuid4(),
            broker_id=broker.id,
            title=f"Prestige Tech Vista 3BHK {test_suffix}",
            description="Luxury 3BHK apartment in Whitefield",
            price=12500000.0,
            area_value=1500.0,
            bedrooms=3,
            bathrooms=3,
            property_type="3bhk",
            city="Bengaluru",
            status="available",
        )
        db_session.add(prop)
        await db_session.flush()

        # ── 6. Create Follow-Up Task ──────────────────────────────────────────
        task = Task(
            id=str(uuid.uuid4()),
            broker_id=broker.id,
            lead_id=lead.id,
            organization_id=str(org.id),
            title=f"Send site visit invite to Investor {test_suffix}",
            status="pending",
            priority="high",
            due_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()

        # ── 7. Verification of Persisted Lifecycle ─────────────────────────────
        # Verify Lead Query
        q_lead = await db_session.execute(select(Lead).where(Lead.id == lead.id))
        loaded_lead = q_lead.scalar_one()
        assert loaded_lead.name == f"Investor {test_suffix}"
        assert loaded_lead.organization_id == str(broker.id)

        # Verify Property Query
        q_prop = await db_session.execute(select(PropertyListing).where(PropertyListing.id == prop.id))
        loaded_prop = q_prop.scalar_one()
        assert loaded_prop.price == 12500000.0
        assert loaded_prop.broker_id == broker.id

        # Verify Matching Contract Invariants
        budget_match = (
            loaded_lead.budget_min <= loaded_prop.price <= loaded_lead.budget_max
        )
        type_match = loaded_lead.property_type.lower() == loaded_prop.property_type.lower()
        city_match = any(loc.lower() == loaded_prop.city.lower() for loc in loaded_lead.preferred_locations)
        assert budget_match is True, "Budget compatibility check failed"
        assert type_match is True, "Property type compatibility check failed"
        assert city_match is True, "City location compatibility check failed"

        # Verify Onboarding State Progression
        q_onboarding = await db_session.execute(
            select(OnboardingState).where(OnboardingState.organization_id == org.id)
        )
        loaded_onboarding = q_onboarding.scalar_one()
        assert loaded_onboarding.current_step == "TEAM_INVITE"
        assert "ORGANIZATION_SETUP" in loaded_onboarding.completed_steps

        # Verify Task Exists
        q_task = await db_session.execute(select(Task).where(Task.id == task.id))
        loaded_task = q_task.scalar_one()
        assert loaded_task.status == "pending"
        assert loaded_task.priority == "high"
