import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import sys
sys.path.insert(0, 'apps/api')
from app.modules.autonomous_loop.phase2c_context_builder import Phase2CContextBuilder
from sqlalchemy.ext.asyncio import AsyncSession

async def audit_loaders():
    url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(url, poolclass=NullPool)
    
    lead_id = "1d3d636e-1460-4507-bc3c-2ac0f19f7250"
    org_id = "a0317351-e076-493e-8b84-182f8c43666e"
    
    async with AsyncSession(engine) as session:
        builder = Phase2CContextBuilder(session)
        print(f"=== TESTING CONTEXT LOADERS FOR LEAD {lead_id} ===")
        
        # 1. Lead Loader
        print("\n1. Testing _load_lead:")
        try:
            lead_data = await builder._load_lead(org_id, lead_id)
            print("  Result:", lead_data)
            print("  Classification: LOADED")
        except Exception as e:
            print("  Error:", type(e), e)
            print("  Classification: FAILED")

        # 2. Consent Loader
        print("\n2. Testing _load_consent:")
        try:
            consent_data = await builder._load_consent(lead_id, org_id)
            print("  Result:", consent_data)
            src = consent_data.get("source")
            if src == "lead_automation_state":
                cls = "LOADED"
            elif src == "missing_automation_state":
                cls = "EMPTY_BY_BUSINESS_STATE"
            elif "error" in consent_data:
                cls = "UNAVAILABLE_SCHEMA" if "UndefinedTable" in consent_data.get("error", "") or "UndefinedColumn" in consent_data.get("error", "") else "FAILED"
            else:
                cls = "UNKNOWN"
            print(f"  Classification: {cls}")
        except Exception as e:
            print("  Error:", type(e), e)
            print("  Classification: FAILED")

        # 3. Qualification Loader
        print("\n3. Testing _load_qualification:")
        try:
            qual_data = await builder._load_qualification(lead_id, org_id)
            print("  Result:", qual_data)
            if qual_data is not None:
                cls = "LOADED"
            else:
                # Check if qualification_profiles table exists and has 0 rows for this lead
                check = await session.execute(text("SELECT COUNT(*) FROM qualification_profiles WHERE lead_id = :lid"), {"lid": lead_id})
                cnt = check.scalar()
                cls = "EMPTY_BY_BUSINESS_STATE" if cnt == 0 else "UNAVAILABLE_DATA"
            print(f"  Classification: {cls}")
        except Exception as e:
            print("  Error:", type(e), e)
            print("  Classification: FAILED")

        # 4. Property Shortlist Loader
        print("\n4. Testing _load_property_shortlist:")
        try:
            prop_data = await builder._load_property_shortlist(lead_id, org_id)
            print("  Result:", prop_data)
            if len(prop_data) > 0:
                cls = "LOADED"
            else:
                # Check if recommendations table exists and has 0 rows
                check = await session.execute(text("SELECT COUNT(*) FROM recommendations WHERE lead_id = :lid"), {"lid": lead_id})
                cnt = check.scalar()
                cls = "EMPTY_BY_BUSINESS_STATE" if cnt == 0 else "UNAVAILABLE_DATA"
            print(f"  Classification: {cls}")
        except Exception as e:
            print("  Error:", type(e), e)
            print("  Classification: FAILED")

        # 5. Recent Conversation Loader
        print("\n5. Testing _load_recent_conversation:")
        try:
            conv_data = await builder._load_recent_conversation(lead_id, org_id)
            print("  Result:", conv_data)
            if len(conv_data) > 0:
                cls = "LOADED"
            else:
                # Check channel_messages
                check = await session.execute(text("SELECT COUNT(*) FROM channel_messages WHERE lead_id = :lid"), {"lid": lead_id})
                cnt = check.scalar()
                cls = "EMPTY_BY_BUSINESS_STATE" if cnt == 0 else "UNAVAILABLE_DATA"
            print(f"  Classification: {cls}")
        except Exception as e:
            print("  Error:", type(e), e)
            print("  Classification: FAILED")

        # 6. Deal Loader
        print("\n6. Testing _load_current_deal:")
        try:
            deal_data = await builder._load_current_deal(lead_id, org_id)
            print("  Result:", deal_data)
            if deal_data is not None:
                cls = "LOADED"
            else:
                check = await session.execute(text("SELECT COUNT(*) FROM deals WHERE lead_id = :lid"), {"lid": lead_id})
                cnt = check.scalar()
                cls = "EMPTY_BY_BUSINESS_STATE" if cnt == 0 else "UNAVAILABLE_DATA"
            print(f"  Classification: {cls}")
        except Exception as e:
            print("  Error:", type(e), e)
            print("  Classification: FAILED")

        # 7. Full Context Build
        print("\n7. Testing full build:")
        ctx = await builder.build(
            organization_id=org_id,
            lead_id=lead_id
        )
        print("  Context org:", ctx.organization_id)
        print("  Context lead:", ctx.lead_id)
        print("  Lead summary:", ctx.lead_summary)
        print("  Consent state:", ctx.consent_state)
        print("  Property shortlist count:", len(ctx.property_shortlist))
        print("  Recent conversation count:", len(ctx.recent_conversation))
        print("  Current deal:", ctx.current_deal)
        print("  Policy summary:", ctx.policy_summary)

if __name__ == '__main__':
    asyncio.run(audit_loaders())
