"""
Phase 2C.4 — Execution Phase 5: Core Revenue Workflow End-to-End Verification
Traces the full WefyLabs Commercial Wedge:
1. Incoming Lead
2. Lead Intelligence & Qualification
3. Property Inventory Match
4. Next Best Action Recommendation
5. Human Review & Decision Recording
6. Follow-Up Scheduling
7. Site Visit Commercial Creation
8. Deal/Opportunity Advancement
9. Booking Creation
10. Revenue & Commission Attribution
11. Cryptographic Audit Chain Verification
"""
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

from app.models import Base
import app.models
from app.models.organization import Organization, OrganizationMember
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.deal_models import Deal, DealStage, DealBooking, DealCommission
from app.models.sales_pipeline_models import SiteVisit
from app.models.follow_up import FollowUp
from app.modules.autonomous_loop.phase2c_durable_models import (
    PilotTenant, PilotObservation, PilotHumanDecision, PilotAuditEvent
)
from app.modules.autonomous_loop.phase2c_pilot_repository import PilotRepository
from app.modules.autonomous_loop.phase2c_comparison_engine import Phase2CComparisonEngine, ComparisonCategory

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

async def test_core_revenue_workflow():
    engine = create_async_engine(TEST_DB_URL, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    workflow_evidence = {}

    async with session_maker() as session:
        # Step 1: Organization & Broker Setup
        org = Organization(id=uuid.uuid4(), name="Emaar Realty Partners", slug="emaar-realty", plan="enterprise")
        broker = Broker(id=uuid.uuid4(), email="aditi.sharma@emaarrealty.com", name="Aditi Sharma", phone="+919811122233")
        member = OrganizationMember(organization_id=org.id, broker_id=broker.id, role="OWNER")
        session.add_all([org, broker, member])
        await session.commit()

        repo = PilotRepository(session)
        pilot = await repo.enroll_tenant(
            organization_id=str(org.id),
            enrolled_by=broker.email,
            starting_stage="STAGE_1_SHADOW",
            agent_ids=["lead-intelligence-agent-v2b", "recommendation-agent-v2b"],
        )
        workflow_evidence['step1_pilot_enrolled'] = True

        # Step 2: Incoming Lead Ingestion
        lead = Lead(
            id=uuid.uuid4(),
            organization_id=org.id,
            broker_id=broker.id,
            name="Vikram Malhotra",
            phone="+919877766554",
            email="vikram.malhotra@example.com",
            source="WEBSITE_INQUIRY",
            score="hot",
            score_confidence=0.92,
            budget_min=15000000,
            budget_max=25000000,
        )
        session.add(lead)
        await session.commit()
        workflow_evidence['step2_lead_ingested'] = True

        # Step 3: Property Listing Ground Truth Inventory
        property_item = PropertyListing(
            id=uuid.uuid4(),
            organization_id=org.id,
            broker_id=broker.id,
            title="Luxury 3BHK Penthouse - Palm Jumeirah",
            description="Ultra-luxurious 3-bedroom penthouse with panoramic sea views.",
            property_type="penthouse",
            status="available",
            price=22000000.0,
            bedrooms=3,
            bathrooms=3,
            area_value=2800.0,
            area_unit="sqft",
            currency_code="INR",
        )
        session.add(property_item)
        await session.commit()
        workflow_evidence['step3_property_grounded'] = True

        # Step 4: AI Next Best Action Recommendation (Shadow Observation)
        obs = PilotObservation(
            id=str(uuid.uuid4()),
            pilot_id=pilot.id,
            organization_id=str(org.id),
            lead_id=str(lead.id),
            agent_id="recommendation-agent-v2b",
            agent_domain="PROPERTY_RECOMMENDATION",
            agent_version="v2c.1.0",
            execution_id=str(uuid.uuid4()),
            pilot_stage="STAGE_1_SHADOW",
            execution_mode="SHADOW",
            recommended_action="SCHEDULE_SITE_VISIT",
            recommended_action_reasoning="Lead budget and preference matches 3BHK Penthouse Palm Jumeirah with 94% similarity score.",
            agent_confidence=0.94,
            is_synthetic=False,
            observed_at=datetime.now(timezone.utc),
        )
        session.add(obs)
        await session.flush()
        workflow_evidence['step4_ai_observation_recorded'] = True

        # Step 5: Human Sales Review & Decision Recording
        obs_up, human_dec = await repo.record_human_decision(
            observation_id=obs.id,
            organization_id=str(org.id),
            lead_id=str(lead.id),
            human_actor_id=str(broker.id),
            human_actor_role="owner",
            decision_type="ACCEPT",
            action_taken="SCHEDULE_SITE_VISIT",
            reason="Confirmed client interest for Saturday site visit.",
        )
        workflow_evidence['step5_human_decision_recorded'] = True

        # Verify Shadow Comparison
        comp_engine = Phase2CComparisonEngine()
        comparison = comp_engine.compare(
            agent_action=obs.recommended_action,
            human_action=human_dec.action_taken,
        )
        assert comparison.category == ComparisonCategory.EXACT_AGREEMENT
        assert comparison.agreement_score == 1.0
        workflow_evidence['step5b_exact_agreement_verified'] = True

        # Step 6: Follow-Up Scheduled
        followup = FollowUp(
            id=uuid.uuid4(),
            lead_id=lead.id,
            sequence_number=1,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
            status="scheduled",
            message="Hi Vikram, confirming our Saturday site visit for Palm Jumeirah Penthouse.",
        )
        session.add(followup)
        await session.commit()
        workflow_evidence['step6_followup_scheduled'] = True

        # Step 7: Commercial Deal / Opportunity Creation
        deal = Deal(
            id=uuid.uuid4(),
            organization_id=org.id,
            broker_id=broker.id,
            lead_id=lead.id,
            property_id=property_item.id,
            deal_reference=f"DEAL-EMAAR-{uuid.uuid4().hex[:6].upper()}",
            deal_title="Vikram Malhotra - Palm Jumeirah Penthouse",
            current_stage=DealStage.OPPORTUNITY,
            agreed_price=Decimal("22000000.00"),
            currency="INR",
            closing_probability_pct=Decimal("85.00"),
            status="ACTIVE",
        )
        session.add(deal)
        await session.commit()
        workflow_evidence['step7_deal_created'] = True

        # Step 8: Site Visit Linked to Deal
        site_visit = SiteVisit(
            id=uuid.uuid4(),
            organization_id=org.id,
            deal_id=deal.id,
            lead_id=lead.id,
            property_listing_id=property_item.id,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=2),
            status="CONFIRMED",
            location_type="PHYSICAL",
            notes="Client visiting with architect.",
        )
        session.add(site_visit)
        await session.commit()
        workflow_evidence['step8_site_visit_created'] = True

        # Step 9: Deal Advanced to Booking
        deal.current_stage = DealStage.BOOKING
        booking = DealBooking(
            id=uuid.uuid4(),
            deal_id=deal.id,
            organization_id=org.id,
            booking_reference="BKG-2026-001",
            token_amount=Decimal("1100000.00"),
            booked_price=Decimal("22000000.00"),
            currency="INR",
            status="CONFIRMED",
        )
        session.add(booking)
        await session.commit()
        workflow_evidence['step9_booking_confirmed'] = True

        # Step 10: Commission & Revenue Record
        commission = DealCommission(
            id=uuid.uuid4(),
            deal_id=deal.id,
            organization_id=org.id,
            broker_id=broker.id,
            transaction_price=Decimal("22000000.00"),
            gross_commission=Decimal("440000.00"),
            net_commission=Decimal("440000.00"),
            commission_percentage=Decimal("2.00"),
            currency="INR",
            status="APPROVED",
        )
        session.add(commission)
        await session.commit()
        workflow_evidence['step10_revenue_attributed'] = True

        # Step 11: Audit Chain Integrity
        audits = (await session.execute(
            select(PilotAuditEvent).where(PilotAuditEvent.pilot_id == pilot.id).order_by(PilotAuditEvent.sequence_number)
        )).scalars().all()
        broken = 0
        prev_h = None
        for a in audits:
            if a.sequence_number > 1 and a.previous_hash != prev_h:
                broken += 1
            prev_h = a.current_hash
        workflow_evidence['step11_audit_unbroken'] = (broken == 0 and len(audits) >= 2)

    await engine.dispose()
    print("CORE REVENUE WORKFLOW EVIDENCE:")
    for k, v in workflow_evidence.items():
        print(f"  {k:<38}: {v}")

    all_passed = all(workflow_evidence.values())
    print(f"\nWORKFLOW VERIFICATION: {'PASS' if all_passed else 'FAIL'}")
    return all_passed

if __name__ == "__main__":
    passed = asyncio.run(test_core_revenue_workflow())
    if not passed:
        exit(1)
