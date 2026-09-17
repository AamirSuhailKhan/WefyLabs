"""
PART 31 — Isolated Demo Mode & Synthetic Playground Service
============================================================
Spawns an ephemeral, multi-tenant isolated demo workspace populated with
realistic Indian real estate inventory, leads, AI matches, and tasks.

Tenant Isolation Guarantees:
- Dedicated Organization (is_demo=True)
- Dedicated Broker (is_demo=True)
- Zero cross-tenant queries
- No production customer data
- External side effects (Brevo email, WhatsApp, Razorpay, Calendar) strictly blocked
- Auto-expiring TTL with idempotent cleanup
"""
import uuid
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.broker import Broker
from app.models.organization import Organization, OrganizationMember
from app.models.property_models import PropertyListing
from app.models.lead import Lead
from app.models.recommendation_models import Recommendation, RecommendationItem
from app.models.crm_models import Task
from app.models.onboarding_models import OnboardingState, TenantActivation, DemoSession
from app.modules.onboarding.dto import DemoSessionResponseDTO
from app.services.audit_service import AuditLogService

logger = logging.getLogger("beetlelabs.onboarding.demo")

# Realistic Synthetic Properties for Demo Mode (Bengaluru, Mumbai, Gurugram)
SYNTHETIC_PROPERTIES = [
    {
        "title": "Sunlit 3BHK High-Rise at Indiranagar",
        "description": "Luxurious 3-bedroom apartment overlooking Defence Colony park with Italian marble flooring and automated lighting.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 24500000.0,
        "currency_code": "INR",
        "area_value": 1850.0,
        "area_unit": "sqft",
        "bedrooms": 3,
        "bathrooms": 3,
        "balconies": 2,
        "parking_spaces": 2,
        "city": "Bengaluru",
        "locality": "Indiranagar",
        "address": "12th Main, HAL 2nd Stage, Indiranagar",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "status": "available",
        "project_name": "Prestige Indiranagar Heights",
    },
    {
        "title": "Contemporary 2BHK in Whitefield Tech Corridor",
        "description": "Smart home enabled 2BHK adjacent to ITPL with clubhouse, infinity pool, and dedicated EV charging bay.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 9800000.0,
        "currency_code": "INR",
        "area_value": 1180.0,
        "area_unit": "sqft",
        "bedrooms": 2,
        "bathrooms": 2,
        "balconies": 1,
        "parking_spaces": 1,
        "city": "Bengaluru",
        "locality": "Whitefield",
        "address": "ECC Road, Near ITPL, Whitefield",
        "latitude": 12.9698,
        "longitude": 77.7500,
        "status": "available",
        "project_name": "Brigade Cosmopolis",
    },
    {
        "title": "Premium 4BHK Sky Villa with Sea Glimpse",
        "description": "Ultra-luxury residence in Bandra West with private deck, panoramic sea view, and concierge services.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 68000000.0,
        "currency_code": "INR",
        "area_value": 3100.0,
        "area_unit": "sqft",
        "bedrooms": 4,
        "bathrooms": 5,
        "balconies": 3,
        "parking_spaces": 3,
        "city": "Mumbai",
        "locality": "Bandra West",
        "address": "Perry Cross Road, Bandra West",
        "latitude": 19.0596,
        "longitude": 72.8295,
        "status": "available",
        "project_name": "Rustomjee Seasons",
    },
    {
        "title": "Spacious 3BHK Gated Community Villa at Sarjapur",
        "description": "Independent triplex villa with private landscaped garden, solar heating, and 30,000 sqft clubhouse amenities.",
        "property_category": "residential",
        "property_type": "villa",
        "transaction_category": "resale",
        "price": 32000000.0,
        "currency_code": "INR",
        "area_value": 2600.0,
        "area_unit": "sqft",
        "bedrooms": 3,
        "bathrooms": 4,
        "balconies": 2,
        "parking_spaces": 2,
        "city": "Bengaluru",
        "locality": "Sarjapur Road",
        "address": "Rainbow Drive Layout, Sarjapur Road",
        "latitude": 12.9105,
        "longitude": 77.6850,
        "status": "available",
        "project_name": "Adarsh Palm Retreat",
    },
    {
        "title": "Chic 2BHK High-Ceiling Flat at Powai",
        "description": "Vastu compliant corner apartment overlooking Powai Lake. Walking distance to Hiranandani gardens and cafes.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 18500000.0,
        "currency_code": "INR",
        "area_value": 920.0,
        "area_unit": "sqft",
        "bedrooms": 2,
        "bathrooms": 2,
        "balconies": 1,
        "parking_spaces": 1,
        "city": "Mumbai",
        "locality": "Powai",
        "address": "Central Avenue, Hiranandani Gardens, Powai",
        "latitude": 19.1197,
        "longitude": 72.9051,
        "status": "available",
        "project_name": "Hiranandani Heritage",
    },
    {
        "title": "Executive 3BHK Golf Course Road Flat",
        "description": "Air-conditioned luxury apartment near One Horizon Center with imported modular kitchen and servant quarters.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 41000000.0,
        "currency_code": "INR",
        "area_value": 2400.0,
        "area_unit": "sqft",
        "bedrooms": 3,
        "bathrooms": 3,
        "balconies": 2,
        "parking_spaces": 2,
        "city": "Gurugram",
        "locality": "Golf Course Road",
        "address": "Sector 54, Golf Course Road",
        "latitude": 28.4385,
        "longitude": 77.1065,
        "status": "available",
        "project_name": "DLF The Crest",
    },
    {
        "title": "Serene 3BHK Corner Home at Koramangala 4th Block",
        "description": "Boutique apartment building with single unit per floor, teakwood carpentry, and quiet tree-lined boulevard.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 28000000.0,
        "currency_code": "INR",
        "area_value": 2100.0,
        "area_unit": "sqft",
        "bedrooms": 3,
        "bathrooms": 3,
        "balconies": 2,
        "parking_spaces": 2,
        "city": "Bengaluru",
        "locality": "Koramangala",
        "address": "80 Feet Road, 4th Block, Koramangala",
        "latitude": 12.9345,
        "longitude": 77.6266,
        "status": "available",
        "project_name": "Sobha Magnolia",
    },
    {
        "title": "Affordable 2BHK Near Electronic City Phase 1",
        "description": "Ideal starter home for IT professionals with quick access to Wipro and Infosys campuses. Ready for possession.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 6200000.0,
        "currency_code": "INR",
        "area_value": 980.0,
        "area_unit": "sqft",
        "bedrooms": 2,
        "bathrooms": 2,
        "balconies": 1,
        "parking_spaces": 1,
        "city": "Bengaluru",
        "locality": "Electronic City",
        "address": "Velankani Drive, Electronic City Phase 1",
        "latitude": 12.8452,
        "longitude": 77.6602,
        "status": "available",
        "project_name": "Godrej E-City",
    },
    {
        "title": "Grand 4BHK Penthouse with Private Terrace Jacuzzi",
        "description": "Top-floor duplex with 1,200 sqft entertainment terrace, double-height ceiling living room, and Italian fittings.",
        "property_category": "residential",
        "property_type": "penthouse",
        "transaction_category": "resale",
        "price": 54000000.0,
        "currency_code": "INR",
        "area_value": 3800.0,
        "area_unit": "sqft",
        "bedrooms": 4,
        "bathrooms": 5,
        "balconies": 4,
        "parking_spaces": 3,
        "city": "Bengaluru",
        "locality": "Indiranagar",
        "address": "100 Feet Road, HAL 2nd Stage",
        "latitude": 12.9719,
        "longitude": 77.6412,
        "status": "available",
        "project_name": "Prestige Acropolis",
    },
    {
        "title": "Modern 2BHK Apartment at HSR Layout Sector 2",
        "description": "Well ventilated east-facing flat close to 27th Main high street. Low maintenance society with power backup.",
        "property_category": "residential",
        "property_type": "apartment",
        "transaction_category": "resale",
        "price": 12500000.0,
        "currency_code": "INR",
        "area_value": 1250.0,
        "area_unit": "sqft",
        "bedrooms": 2,
        "bathrooms": 2,
        "balconies": 2,
        "parking_spaces": 1,
        "city": "Bengaluru",
        "locality": "HSR Layout",
        "address": "19th Main, Sector 2, HSR Layout",
        "latitude": 12.9116,
        "longitude": 77.6474,
        "status": "available",
        "project_name": "Purva Fairmont",
    },
]

# Realistic Synthetic Leads for Demo Mode
SYNTHETIC_LEADS = [
    {
        "name": "Rahul Sharma",
        "phone": "+919820011111",
        "score": "hot",
        "score_confidence": 0.94,
        "budget_min": 20000000,
        "budget_max": 28000000,
        "property_type": "apartment",
        "preferred_locations": ["Indiranagar", "Koramangala"],
        "pipeline_stage": "site_visit",
        "status": "active",
        "timeline": "immediate",
    },
    {
        "name": "Priya Sundaram",
        "phone": "+919820022222",
        "score": "hot",
        "score_confidence": 0.91,
        "budget_min": 8500000,
        "budget_max": 11500000,
        "property_type": "apartment",
        "preferred_locations": ["Whitefield"],
        "pipeline_stage": "qualified",
        "status": "active",
        "timeline": "1_month",
    },
    {
        "name": "Vikram Malhotra",
        "phone": "+919820033333",
        "score": "warm",
        "score_confidence": 0.82,
        "budget_min": 25000000,
        "budget_max": 35000000,
        "property_type": "villa",
        "preferred_locations": ["Sarjapur Road", "HSR Layout"],
        "pipeline_stage": "negotiation",
        "status": "active",
        "timeline": "3_months",
    },
    {
        "name": "Ananya Sen",
        "phone": "+919820044444",
        "score": "hot",
        "score_confidence": 0.96,
        "budget_min": 50000000,
        "budget_max": 75000000,
        "property_type": "apartment",
        "preferred_locations": ["Bandra West", "Worli"],
        "pipeline_stage": "site_visit",
        "status": "active",
        "timeline": "immediate",
    },
    {
        "name": "Rohan Mehta",
        "phone": "+919820055555",
        "score": "warm",
        "score_confidence": 0.78,
        "budget_min": 15000000,
        "budget_max": 20000000,
        "property_type": "apartment",
        "preferred_locations": ["Powai"],
        "pipeline_stage": "new",
        "status": "active",
        "timeline": "3_months",
    },
    {
        "name": "Sneha Kulkarni",
        "phone": "+919820066666",
        "score": "warm",
        "score_confidence": 0.85,
        "budget_min": 35000000,
        "budget_max": 45000000,
        "property_type": "apartment",
        "preferred_locations": ["Golf Course Road"],
        "pipeline_stage": "qualified",
        "status": "active",
        "timeline": "1_month",
    },
    {
        "name": "Arjun Patel",
        "phone": "+919820077777",
        "score": "cold",
        "score_confidence": 0.65,
        "budget_min": 5500000,
        "budget_max": 7000000,
        "property_type": "apartment",
        "preferred_locations": ["Electronic City"],
        "pipeline_stage": "new",
        "status": "active",
        "timeline": "6_months",
    },
    {
        "name": "Divya Nair",
        "phone": "+919820088888",
        "score": "hot",
        "score_confidence": 0.93,
        "budget_min": 45000000,
        "budget_max": 60000000,
        "property_type": "penthouse",
        "preferred_locations": ["Indiranagar"],
        "pipeline_stage": "negotiation",
        "status": "active",
        "timeline": "immediate",
    },
]


class DemoModeService:
    """
    Manages generation, isolation, and teardown of ephemeral demo environments.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_demo_workspace(
        self,
        intended_agency_name: Optional[str] = None,
        operating_city: Optional[str] = "Bengaluru",
        client_ip: Optional[str] = None
    ) -> DemoSessionResponseDTO:
        """
        Spawns a dedicated demo tenant with seeded synthetic inventory, leads, matches, and tasks.
        Completely isolated; never exposes or touches production records.
        """
        token = secrets.token_urlsafe(32)
        demo_org_id = uuid.uuid4()
        demo_broker_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=48)

        agency_name = intended_agency_name or f"Apex Realty Demo ({operating_city})"

        # 1. Create Demo Organization
        demo_org = Organization(
            id=demo_org_id,
            name=agency_name,
            slug=f"demo-{token[:10]}",
            plan="enterprise",
            country_code="IN",
            currency_code="INR",
            reporting_currency_code="INR",
            default_timezone="Asia/Kolkata",
            business_type="agency",
            team_size="6-20",
            is_demo=True,
            settings={
                "city": operating_city,
                "is_demo": True,
                "simulation_notice": "Ephemeral Demo Playground"
            }
        )
        self.db.add(demo_org)

        # 2. Create Demo Broker
        demo_email = f"demo_{token[:8].lower()}@demo.wefylabs.internal"
        demo_broker = Broker(
            id=demo_broker_id,
            email=demo_email,
            name="Demo Broker Agent",
            agency_name=agency_name,
            city=operating_city,
            is_demo=True,
            subscription_status="active",
            onboarding_status="ONBOARDED",
            subscription_plan="pro_monthly"
        )
        self.db.add(demo_broker)

        # 3. Organization Membership
        membership = OrganizationMember(
            organization_id=demo_org_id,
            broker_id=demo_broker_id,
            role="owner"
        )
        self.db.add(membership)

        # 4. Demo Session Record
        session = DemoSession(
            demo_organization_id=demo_org_id,
            demo_broker_id=demo_broker_id,
            session_token=token,
            status="active",
            expires_at=expires_at,
            created_by_ip=client_ip,
            metadata_json={"agency_name": agency_name, "city": operating_city}
        )
        self.db.add(session)

        # 5. Onboarding State & Activation (Demo starts fully configured)
        onboarding_state = OnboardingState(
            organization_id=demo_org_id,
            broker_id=demo_broker_id,
            current_step="ACTIVATED",
            completed_steps=[
                "ORGANIZATION_SETUP", "DATA_SOURCE", "PROPERTY_SETUP",
                "LEAD_SETUP", "MATCH_SHOWCASE", "FOLLOWUP_SETUP",
                "TEAM_INVITE", "CALENDAR_CONNECT", "COPILOT_INTRO", "ACTIVATED"
            ],
            skipped_steps=[],
            is_completed=True,
            completed_at=now,
            step_data={"demo_initialized": True}
        )
        self.db.add(onboarding_state)

        activation_record = TenantActivation(
            organization_id=demo_org_id,
            is_activated=True,
            activation_score=100,
            completed_milestones=[
                "ORGANIZATION_CREATED", "FIRST_PROPERTY_CREATED",
                "FIRST_LEAD_CREATED", "FIRST_MATCH_GENERATED", "FIRST_FOLLOWUP_CREATED"
            ],
            activated_at=now,
            time_to_activate_seconds=30
        )
        self.db.add(activation_record)

        # 6. Seed Synthetic Properties
        created_properties: List[PropertyListing] = []
        for prop_data in SYNTHETIC_PROPERTIES:
            prop = PropertyListing(
                broker_id=demo_broker_id,
                title=prop_data["title"],
                description=prop_data["description"],
                property_category=prop_data["property_category"],
                property_type=prop_data["property_type"],
                transaction_category=prop_data["transaction_category"],
                price=prop_data["price"],
                currency_code=prop_data["currency_code"],
                area_value=prop_data["area_value"],
                area_unit=prop_data["area_unit"],
                bedrooms=prop_data["bedrooms"],
                bathrooms=prop_data["bathrooms"],
                balconies=prop_data["balconies"],
                parking_spaces=prop_data["parking_spaces"],
                city=prop_data["city"],
                locality=prop_data["locality"],
                address=prop_data["address"],
                latitude=prop_data["latitude"],
                longitude=prop_data["longitude"],
                status=prop_data["status"],
                project_name=prop_data["project_name"],
            )
            self.db.add(prop)
            created_properties.append(prop)

        # 7. Seed Synthetic Leads
        created_leads: List[Lead] = []
        for lead_data in SYNTHETIC_LEADS:
            lead = Lead(
                broker_id=demo_broker_id,
                name=lead_data["name"],
                phone=lead_data["phone"],
                score=lead_data["score"],
                score_confidence=lead_data["score_confidence"],
                budget_min=lead_data["budget_min"],
                budget_max=lead_data["budget_max"],
                property_type=lead_data["property_type"],
                preferred_locations=lead_data["preferred_locations"],
                pipeline_stage=lead_data["pipeline_stage"],
                status=lead_data["status"],
                timeline=lead_data["timeline"],
                source="demo_seed",
                country_code="IN"
            )
            self.db.add(lead)
            created_leads.append(lead)

        await self.db.flush()

        # 8. Seed Recommendations / Matches (Part 29)
        seeded_matches = 0
        if created_leads and created_properties:
            # Lead 0 (Rahul Sharma - Indiranagar 3BHK) matches Prop 0 & 8
            rec1 = Recommendation(
                lead_id=str(created_leads[0].id),
                broker_id=str(demo_broker_id),
                organization_id=str(demo_org_id),
                recommendation_mode="hybrid_matching",
                total_candidates_retrieved=len(created_properties),
                filtered_candidates_count=2
            )
            self.db.add(rec1)
            await self.db.flush()

            item1 = RecommendationItem(
                recommendation_id=str(rec1.id),
                property_id=str(created_properties[0].id),
                rank_position=1,
                recommendation_type="BEST_OVERALL",
                match_score=96.5,
                recommendation_confidence=0.95
            )
            item2 = RecommendationItem(
                recommendation_id=str(rec1.id),
                property_id=str(created_properties[8].id),
                rank_position=2,
                recommendation_type="BEST_PREMIUM",
                match_score=88.0,
                recommendation_confidence=0.90
            )
            self.db.add_all([item1, item2])

            # Lead 1 (Priya Sundaram - Whitefield 2BHK) matches Prop 1
            rec2 = Recommendation(
                lead_id=str(created_leads[1].id),
                broker_id=str(demo_broker_id),
                organization_id=str(demo_org_id),
                recommendation_mode="hybrid_matching",
                total_candidates_retrieved=len(created_properties),
                filtered_candidates_count=1
            )
            self.db.add(rec2)
            await self.db.flush()

            item3 = RecommendationItem(
                recommendation_id=str(rec2.id),
                property_id=str(created_properties[1].id),
                rank_position=1,
                recommendation_type="BEST_VALUE",
                match_score=94.2,
                recommendation_confidence=0.93
            )
            self.db.add(item3)
            seeded_matches = 3

        # 9. Seed Follow-ups and Tasks (Part 27 & CRM)
        task1 = Task(
            broker_id=demo_broker_id,
            lead_id=created_leads[0].id,
            organization_id=str(demo_org_id),
            title="Site Visit at Prestige Indiranagar Heights with Rahul Sharma",
            description="Client confirmed 11:00 AM visit. Ensure project brochure is shared.",
            due_at=now + timedelta(days=1),
            status="pending",
            priority="urgent"
        )
        task2 = Task(
            broker_id=demo_broker_id,
            lead_id=created_leads[1].id,
            organization_id=str(demo_org_id),
            title="Send Price Breakdown to Priya Sundaram (Brigade Cosmopolis)",
            description="Provide cost sheet including clubhouse and GST charges.",
            due_at=now + timedelta(hours=4),
            status="pending",
            priority="high"
        )
        task3 = Task(
            broker_id=demo_broker_id,
            lead_id=created_leads[2].id,
            organization_id=str(demo_org_id),
            title="Follow up on Loan Sanction with Vikram Malhotra",
            description="HDFC pre-approval status check for Sarjapur villa.",
            due_at=now + timedelta(days=2),
            status="pending",
            priority="normal"
        )
        self.db.add_all([task1, task2, task3])

        await self.db.flush()

        await AuditLogService.record(
            db=self.db,
            action="demo.workspace_created",
            resource_type="organization",
            actor_id=demo_broker_id,
            organization_id=demo_org_id,
            resource_id=str(demo_org_id),
            changes={"session_token_prefix": token[:8], "seeded_leads": len(created_leads), "seeded_properties": len(created_properties)},
            ip_address=client_ip
        )

        return DemoSessionResponseDTO(
            session_token=token,
            demo_organization_id=str(demo_org_id),
            demo_broker_id=str(demo_broker_id),
            demo_email=demo_email,
            agency_name=agency_name,
            expires_at=expires_at.isoformat(),
            seeded_leads_count=len(created_leads),
            seeded_properties_count=len(created_properties),
            seeded_matches_count=seeded_matches,
            seeded_tasks_count=3,
        )

    async def reset_demo_session(self, session_token: str) -> bool:
        """
        Safely purges an isolated demo workspace by session token.
        Strictly guards against purging non-demo tenants.
        """
        stmt = select(DemoSession).where(DemoSession.session_token == session_token)
        res = await self.db.execute(stmt)
        session = res.scalars().first()
        if not session:
            return False

        org_id = session.demo_organization_id
        org = await self.db.get(Organization, org_id)
        if not org or not org.is_demo:
            logger.error(f"[DEMO_SERVICE] Security Alert: Refused to delete non-demo organization {org_id}")
            return False

        # Cascade purge demo organization and broker
        broker_id = session.demo_broker_id

        # Delete leads, properties, recommendations, tasks explicitly for safety
        await self.db.execute(delete(Task).where(Task.organization_id == str(org_id)))
        await self.db.execute(delete(Recommendation).where(Recommendation.organization_id == str(org_id)))
        await self.db.execute(delete(Lead).where(Lead.broker_id == broker_id))
        await self.db.execute(delete(PropertyListing).where(PropertyListing.broker_id == broker_id))
        await self.db.execute(delete(OnboardingState).where(OnboardingState.organization_id == org_id))
        await self.db.execute(delete(TenantActivation).where(TenantActivation.organization_id == org_id))
        await self.db.execute(delete(DemoSession).where(DemoSession.id == session.id))
        await self.db.execute(delete(OrganizationMember).where(OrganizationMember.organization_id == org_id))
        await self.db.execute(delete(Organization).where(Organization.id == org_id))
        await self.db.execute(delete(Broker).where(Broker.id == broker_id))

        await self.db.flush()
        logger.info(f"[DEMO_SERVICE] Safely purged demo session {session_token[:8]} (org={org_id})")
        return True

    async def cleanup_expired_demo_sessions(self) -> int:
        """
        Scheduled background task to purge expired demo sessions.
        Idempotent and strictly limited to organizations where is_demo=True.
        """
        now = datetime.now(timezone.utc)
        stmt = select(DemoSession).where(
            and_(
                DemoSession.expires_at < now,
                DemoSession.status == "active"
            )
        )
        res = await self.db.execute(stmt)
        expired_sessions = res.scalars().all()

        purged_count = 0
        for sess in expired_sessions:
            try:
                success = await self.reset_demo_session(sess.session_token)
                if success:
                    purged_count += 1
            except Exception as e:
                logger.error(f"[DEMO_SERVICE] Failed to purge expired session {sess.id}: {e}")

        return purged_count
