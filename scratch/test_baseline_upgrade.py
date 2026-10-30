import os
import sys
import ast

API_DIR = os.path.abspath("apps/api")
VERSIONS_DIR = os.path.join(API_DIR, "alembic", "versions")

files = sorted([f for f in os.listdir(VERSIONS_DIR) if f.endswith(".py")])

# Determine which tables are created by 0015..0047
post_merge_files = [
    "0015_sales_loop_orchestration.py",
    "0016_lead_sources_alignment.py",
    "0017_razorpay_billing.py",
    "0018_pre_branding_blockers.py",
    "0019_copilot_conversations.py",
    "0020_followup_automation_engine.py",
    "0021_property_inventory_crm.py",
    "0022_ai_matching_engine.py",
    "0023_agent_command_center.py",
    "0024_onboarding_activation_demo.py",
    "0025_property_total_floors.py",
    "0026_revenue_autopilot.py",
    "0027_customer_identity_canonical.py",
    "0028_revenue_intelligence.py",
    "0029_native_crm_indexes.py",
    "0030_enterprise_runtime.py",
    "0031_deal_booking_transaction_os.py",
    "0032_supply_side_inventory_os.py",
    "0033_marketing_os.py",
    "0034_customer_portal_os.py",
    "0035_canonical_tenant_foundation.py",
    "0036_build07_workitem_commitment.py",
    "0038_build08_sales_pipeline.py",
    "0039_build09_revenue_intelligence.py",
    "0040_master_build_13_billing.py",
    "0041_master_build_14_intelligence.py",
    "0042_phase2c_pilot_tables.py",
    "0043_schema_drift_remediation.py",
    "0044_token_blacklist_revocation.py",
    "0045_broker_auth_version.py",
    "0046_broker_google_subject.py",
    "0047_webhook_event_claims.py",
]

post_merge_created = set()
for fname in post_merge_files:
    fpath = os.path.join(VERSIONS_DIR, fname)
    with open(fpath, "r", encoding="utf-8") as fp:
        tree = ast.parse(fp.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = ""
            if isinstance(node.func, ast.Attribute):
                fn = node.func.attr
            elif isinstance(node.func, ast.Name):
                fn = node.func.id
            if fn == "create_table" and node.args and isinstance(node.args[0], ast.Constant):
                post_merge_created.add(node.args[0].value)

print(f"Total tables created by 0015-0047: {len(post_merge_created)}")

if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.database import Base
import app.models

all_orm_tables = set(Base.metadata.tables.keys())
print(f"Total ORM tables: {len(all_orm_tables)}")

# Baseline tables that must be created in 9999 if not already existing
baseline_tables = all_orm_tables - post_merge_created
print(f"Baseline tables to create in 9999: {len(baseline_tables)}")
print(f"Post-merge will create: {len(post_merge_created.intersection(all_orm_tables))}")
print(f"Sum = {len(baseline_tables) + len(post_merge_created.intersection(all_orm_tables))}")
