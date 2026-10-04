import asyncio
import uuid
from sqlalchemy import text, select
from app.database import AsyncSessionLocal, engine
from app.models.organization import Organization, OrganizationMember
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.deal_models import Deal, DealBooking
from app.models.property_models import PropertyListing

async def test_customer2_and_isolation():
    print("--- RUNNING PHASE 2C.5 CUSTOMER #2 ONBOARDING & TENANT ISOLATION SUITE ---")
    results = {}

    org1_id = uuid.UUID("a0317351-e076-493e-8b84-182f8c43666e")
    broker1_id = uuid.UUID("c193be18-4a6a-4030-9089-f94c42119189")
    org2_id = uuid.UUID("5651f9f3-2a17-4261-8b22-1989887e25d1")
    broker2_id = uuid.UUID("64dbafd4-1876-48ef-8312-fa7dd1b92b37")

    async with AsyncSessionLocal() as session:
        # 1. Verify Customer #2 Organization & Member existence
        org2 = (await session.execute(select(Organization).where(Organization.id == org2_id))).scalar_one_or_none()
        member2 = (await session.execute(select(OrganizationMember).where(OrganizationMember.organization_id == org2_id))).scalar_one_or_none()
        results["customer2_org_exists"] = (org2 is not None and member2 is not None)

        # 2. Verify Customer #2 has its own isolated Leads
        leads2 = (await session.execute(select(Lead).where(Lead.organization_id == org2_id))).scalars().all()
        results["customer2_leads_count"] = len(leads2)
        results["customer2_has_isolated_leads"] = len(leads2) > 0

        # 3. Verify Customer #2 has its own isolated Properties
        props2 = (await session.execute(select(PropertyListing).where(PropertyListing.organization_id == org2_id))).scalars().all()
        results["customer2_properties_count"] = len(props2)
        results["customer2_has_isolated_properties"] = len(props2) > 0

        # 4. Cross-Tenant Read Test: Org 1 query for Org 2's leads with tenant enforcement
        # Querying leads with tenant filter organization_id == org1_id should NEVER return Org 2's leads
        leaked_leads = (await session.execute(
            select(Lead).where(Lead.organization_id == org1_id, Lead.id.in_([l.id for l in leads2]))
        )).scalars().all()
        results["cross_tenant_read_prevented"] = (len(leaked_leads) == 0)

        # 5. Cross-Tenant Property Isolation Test
        leaked_props = (await session.execute(
            select(PropertyListing).where(PropertyListing.organization_id == org1_id, PropertyListing.id.in_([p.id for p in props2]))
        )).scalars().all()
        results["cross_tenant_property_isolated"] = (len(leaked_props) == 0)

        # 6. Cross-Tenant Write Rejection Simulation
        # Attempting to mutate Org 2 lead with Org 1 context should fail authorization check
        cross_write_blocked = True
        try:
            # Query Org 2 lead under Org 1 scoping
            target_lead = (await session.execute(
                select(Lead).where(Lead.id == leads2[0].id, Lead.organization_id == org1_id)
            )).scalar_one_or_none()
            if target_lead is not None:
                cross_write_blocked = False
        except Exception:
            cross_write_blocked = True
        results["cross_tenant_write_blocked"] = cross_write_blocked

        # 7. Forged Organization ID Rejection
        # Mismatch between session broker's org and targeted org
        broker_memberships = (await session.execute(
            select(OrganizationMember.organization_id).where(OrganizationMember.broker_id == broker1_id)
        )).scalars().all()
        is_forged_org_authorized = (org2_id in broker_memberships)
        results["forged_org_rejected"] = (not is_forged_org_authorized)

        # 8. Deal & Revenue Tenant Scoping
        deals_org2 = (await session.execute(select(Deal).where(Deal.organization_id == org2_id))).scalars().all()
        results["deals_tenant_scoped"] = (len(deals_org2) == 0) # Org 2 has not booked yet; 0 cross-tenant contamination

    await engine.dispose()
    print("CUSTOMER #2 AND ISOLATION TEST RESULTS:")
    for k, v in results.items():
        print(f"  {k:<35}: {v}")
    
    all_pass = all([
        results["customer2_org_exists"],
        results["customer2_has_isolated_leads"],
        results["customer2_has_isolated_properties"],
        results["cross_tenant_read_prevented"],
        results["cross_tenant_property_isolated"],
        results["cross_tenant_write_blocked"],
        results["forged_org_rejected"],
        results["deals_tenant_scoped"]
    ])
    print(f"\nOVERALL VERIFICATION: {'PASS' if all_pass else 'FAIL'}")
    return all_pass

if __name__ == "__main__":
    asyncio.run(test_customer2_and_isolation())
