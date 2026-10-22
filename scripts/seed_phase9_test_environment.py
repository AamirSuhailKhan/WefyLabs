import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add apps/api to path
api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv('apps/api/.env')

from sqlalchemy import select, delete
from app.database import async_session_maker
from app.models.broker import Broker, default_trial_ends_at
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.property_models import PropertyListing
from app.models.lead import Lead
from app.modules.auth.service import hash_password, create_access_token

async def seed():
    print("=== SEEDING PHASE 9 TEST ENVIRONMENT ===")
    
    async with async_session_maker() as session:
        # Check if already exists, clean up if needed
        for email in ["broker.alpha.test@wefylabs.internal", "broker.beta.test@wefylabs.internal", "broker.gamma.test@wefylabs.internal"]:
            b_stmt = select(Broker).where(Broker.email == email)
            existing_broker = (await session.execute(b_stmt)).scalars().first()
            if existing_broker:
                # Clean up existing test records
                await session.execute(delete(Lead).where(Lead.broker_id == existing_broker.id))
                await session.execute(delete(PropertyListing).where(PropertyListing.broker_id == existing_broker.id))
                await session.execute(delete(OrganizationMember).where(OrganizationMember.broker_id == existing_broker.id))
                await session.execute(delete(User).where(User.id == existing_broker.id))
                await session.execute(delete(Broker).where(Broker.id == existing_broker.id))
                await session.flush()
        
        # 1. Organization Alpha
        org_a_id = uuid.uuid4()
        broker_a_id = uuid.uuid4()
        
        org_a = Organization(
            id=org_a_id,
            name="Alpha Realty Partners",
            slug=f"org-alpha-{uuid.uuid4().hex[:6]}",
            plan="pro",
            country_code="IN",
            currency_code="INR"
        )
        session.add(org_a)
        await session.flush()

        broker_a = Broker(
            id=broker_a_id,
            email="broker.alpha.test@wefylabs.internal",
            name="Priya Sharma",
            phone="+919999000001",
            agency_name="Alpha Realty Partners",
            city="Bengaluru",
            whatsapp_number="+919999000001",
            password_hash=hash_password("TestPassword123!"),
            subscription_status="active",
            trial_ends_at=default_trial_ends_at(),
            onboarding_status="ONBOARDED"
        )
        session.add(broker_a)
        await session.flush()

        member_a = OrganizationMember(
            organization_id=org_a_id,
            broker_id=broker_a_id,
            role="owner"
        )
        session.add(member_a)

        user_a = User(
            id=broker_a_id,
            email=broker_a.email,
            name=broker_a.name,
            phone=broker_a.phone,
            whatsapp_number=broker_a.whatsapp_number,
            organization_id=str(org_a_id),
            auth_provider="email",
            subscription_status="active"
        )
        session.add(user_a)

        # Property for Alpha
        prop_a = PropertyListing(
            id=uuid.uuid4(),
            organization_id=org_a_id,
            broker_id=broker_a_id,
            property_code="PROP-ALPHA-001",
            title="Prestige Lakeside 3BHK Penthouse",
            description="Ultra luxury lake-facing penthouse with terrace garden in Whitefield.",
            property_category="residential",
            property_type="apartment",
            transaction_category="resale",
            listing_type="exclusive",
            status="available",
            price=18500000.0,
            area_value=2250.0,
            area_unit="sqft",
            bedrooms=3,
            bathrooms=3,
            balconies=2,
            parking_spaces=2,
            currency_code="INR"
        )
        session.add(prop_a)

        # Lead for Alpha
        lead_a = Lead(
            id=uuid.uuid4(),
            organization_id=org_a_id,
            broker_id=broker_a_id,
            name="Rohan Verma",
            phone="+919876543210",
            email="rohan.verma@example.com",
            source="manual",
            score="hot",
            score_confidence=0.92,
            budget_min=15000000,
            budget_max=20000000,
            property_type="3bhk",
            transaction_type="buy",
            preferred_locations=["Whitefield"],
            pipeline_stage="new"
        )
        session.add(lead_a)

        # 2. Organization Beta
        org_b_id = uuid.uuid4()
        broker_b_id = uuid.uuid4()

        org_b = Organization(
            id=org_b_id,
            name="Beta Prime Properties",
            slug=f"org-beta-{uuid.uuid4().hex[:6]}",
            plan="pro",
            country_code="IN",
            currency_code="INR"
        )
        session.add(org_b)
        await session.flush()

        broker_b = Broker(
            id=broker_b_id,
            email="broker.beta.test@wefylabs.internal",
            name="Arjun Kapoor",
            phone="+919999000002",
            agency_name="Beta Prime Properties",
            city="Bengaluru",
            whatsapp_number="+919999000002",
            password_hash=hash_password("TestPassword123!"),
            subscription_status="active",
            trial_ends_at=default_trial_ends_at(),
            onboarding_status="ONBOARDED"
        )
        session.add(broker_b)
        await session.flush()

        member_b = OrganizationMember(
            organization_id=org_b_id,
            broker_id=broker_b_id,
            role="owner"
        )
        session.add(member_b)

        user_b = User(
            id=broker_b_id,
            email=broker_b.email,
            name=broker_b.name,
            phone=broker_b.phone,
            whatsapp_number=broker_b.whatsapp_number,
            organization_id=str(org_b_id),
            auth_provider="email",
            subscription_status="active"
        )
        session.add(user_b)

        # Property for Beta
        prop_b = PropertyListing(
            id=uuid.uuid4(),
            organization_id=org_b_id,
            broker_id=broker_b_id,
            property_code="PROP-BETA-001",
            title="Sobha Dream Acres 2BHK",
            description="Modern 2BHK flat with world-class amenities in Panathur.",
            property_category="residential",
            property_type="apartment",
            transaction_category="resale",
            listing_type="exclusive",
            status="available",
            price=8500000.0,
            area_value=1200.0,
            area_unit="sqft",
            bedrooms=2,
            bathrooms=2,
            balconies=1,
            parking_spaces=1,
            currency_code="INR"
        )
        session.add(prop_b)

        # Lead for Beta
        lead_b = Lead(
            id=uuid.uuid4(),
            organization_id=org_b_id,
            broker_id=broker_b_id,
            name="Ananya Deshmukh",
            phone="+919876543222",
            email="ananya.deshmukh@example.com",
            source="manual",
            score="warm",
            score_confidence=0.78,
            budget_min=7500000,
            budget_max=9500000,
            property_type="2bhk",
            transaction_type="buy",
            preferred_locations=["Panathur"],
            pipeline_stage="new"
        )
        session.add(lead_b)

        # 3. Organization Gamma (Dubai, UAE - AED)
        org_g_id = uuid.uuid4()
        broker_g_id = uuid.uuid4()

        org_g = Organization(
            id=org_g_id,
            name="Gamma Emirates Luxury Properties",
            slug=f"org-gamma-{uuid.uuid4().hex[:6]}",
            plan="enterprise",
            country_code="AE",
            currency_code="AED"
        )
        session.add(org_g)
        await session.flush()

        broker_g = Broker(
            id=broker_g_id,
            email="broker.gamma.test@wefylabs.internal",
            name="Tariq Mansoor",
            phone="+971501234567",
            agency_name="Gamma Emirates Luxury Properties",
            city="Dubai",
            whatsapp_number="+971501234567",
            password_hash=hash_password("TestPassword123!"),
            subscription_status="active",
            trial_ends_at=default_trial_ends_at(),
            onboarding_status="ONBOARDED"
        )
        session.add(broker_g)
        await session.flush()

        member_g = OrganizationMember(
            organization_id=org_g_id,
            broker_id=broker_g_id,
            role="owner"
        )
        session.add(member_g)

        user_g = User(
            id=broker_g_id,
            email=broker_g.email,
            name=broker_g.name,
            phone=broker_g.phone,
            whatsapp_number=broker_g.whatsapp_number,
            organization_id=str(org_g_id),
            auth_provider="email",
            subscription_status="active"
        )
        session.add(user_g)

        # Property for Gamma
        prop_g = PropertyListing(
            id=uuid.uuid4(),
            organization_id=org_g_id,
            broker_id=broker_g_id,
            property_code="PROP-GAMMA-001",
            title="Downtown Dubai Burj View 2BHK",
            description="Luxury apartment with unobstructed views of the Burj Khalifa and Dubai Fountain.",
            property_category="residential",
            property_type="apartment",
            transaction_category="resale",
            listing_type="exclusive",
            status="available",
            price=2750000.0,
            area_value=1450.0,
            area_unit="sqft",
            bedrooms=2,
            bathrooms=3,
            balconies=1,
            parking_spaces=1,
            currency_code="AED"
        )
        session.add(prop_g)

        # Lead for Gamma
        lead_g = Lead(
            id=uuid.uuid4(),
            organization_id=org_g_id,
            broker_id=broker_g_id,
            name="Alexander Wright",
            phone="+971509876543",
            email="alexander.wright@example.com",
            source="manual",
            score="hot",
            score_confidence=0.95,
            budget_min=2500000,
            budget_max=3200000,
            budget_currency="AED",
            property_type="2bhk",
            transaction_type="buy",
            preferred_locations=["Downtown Dubai"],
            pipeline_stage="new"
        )
        session.add(lead_g)

        await session.commit()

        token_a = create_access_token({
            "sub": str(broker_a_id),
            "email": broker_a.email,
            "broker_id": str(broker_a_id),
            "org_id": str(org_a_id),
            "organization_id": str(org_a_id)
        })

        token_b = create_access_token({
            "sub": str(broker_b_id),
            "email": broker_b.email,
            "broker_id": str(broker_b_id),
            "org_id": str(org_b_id),
            "organization_id": str(org_b_id)
        })

        token_g = create_access_token({
            "sub": str(broker_g_id),
            "email": broker_g.email,
            "broker_id": str(broker_g_id),
            "org_id": str(org_g_id),
            "organization_id": str(org_g_id)
        })

        print("\n--- SEEDING COMPLETED SUCCESSFULLY ---")
        print(f"ORGANIZATION ALPHA: id={org_a_id}, name={org_a.name}")
        print(f"BROKER ALPHA: email={broker_a.email}, password=TestPassword123!")
        print(f"PROPERTY ALPHA: id={prop_a.id}, title={prop_a.title}")
        print(f"LEAD ALPHA: id={lead_a.id}, name={lead_a.name}")
        print(f"TOKEN ALPHA: {token_a}")
        print(f"\nORGANIZATION BETA: id={org_b_id}, name={org_b.name}")
        print(f"BROKER BETA: email={broker_b.email}, password=TestPassword123!")
        print(f"PROPERTY BETA: id={prop_b.id}, title={prop_b.title}")
        print(f"LEAD BETA: id={lead_b.id}, name={lead_b.name}")
        print(f"TOKEN BETA: {token_b}")
        print(f"\nORGANIZATION GAMMA: id={org_g_id}, name={org_g.name}")
        print(f"BROKER GAMMA: email={broker_g.email}, password=TestPassword123!")
        print(f"PROPERTY GAMMA: id={prop_g.id}, title={prop_g.title}")
        print(f"LEAD GAMMA: id={lead_g.id}, name={lead_g.name}")
        print(f"TOKEN GAMMA: {token_g}")

if __name__ == "__main__":
    asyncio.run(seed())
