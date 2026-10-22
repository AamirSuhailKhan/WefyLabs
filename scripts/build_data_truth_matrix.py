import csv
import json

matrix_data = [
    {
        "METRIC/SCREEN": "Pilot Organizations",
        "DB_TABLE": "organizations",
        "DB_COUNT_ACTUAL": "11 total (1 pilot active)",
        "API_ENDPOINT": "GET /auth/me, dependencies.py",
        "API_FILTER_SCOPE": "organization_members.broker_id == current_broker.id",
        "FRONTEND_DISPLAY": "Aamir Suhail's Agency (org-9d0620)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Authoritative pilot organization resolved via organization_members.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Pilot Broker Profile",
        "DB_TABLE": "brokers",
        "DB_COUNT_ACTUAL": "11 total (1 pilot broker: Aamir Suhail)",
        "API_ENDPOINT": "GET /auth/me",
        "API_FILTER_SCOPE": "brokers.id == c193be18-4a6a-4030-9089-f94c42119189",
        "FRONTEND_DISPLAY": "Aamir Suhail (aamir.fresh@bmu.edu.in), Role: Owner",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Auth token resolves broker profile accurately.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Leads / Active Prospects",
        "DB_TABLE": "leads",
        "DB_COUNT_ACTUAL": "3 for pilot tenant (7 across all orgs)",
        "API_ENDPOINT": "GET /leads",
        "API_FILTER_SCOPE": "Lead.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "3 Leads (Amit Sharma, Vikram Malhotra, Rajesh Kumar)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. API strictly returns 3 tenant-scoped leads.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Properties / Supply Inventory",
        "DB_TABLE": "property_listings",
        "DB_COUNT_ACTUAL": "3 for pilot tenant (9 across all orgs)",
        "API_ENDPOINT": "GET /properties",
        "API_FILTER_SCOPE": "PropertyListing.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "3 Properties (Penthouse Marina Gate, Modern 2BHK, Sunny 2BHK)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. API returns exactly 3 tenant-scoped properties.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "AI Matching Candidate Properties",
        "DB_TABLE": "property_listings, qualification_facts",
        "DB_COUNT_ACTUAL": "3 properties eligible for matching",
        "API_ENDPOINT": "GET /leads/{id}/matches",
        "API_FILTER_SCOPE": "Matching engine scoped to tenant inventory and lead preferences",
        "FRONTEND_DISPLAY": "Matches returned with 8-D fit scores and grounded rationale",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Real candidates retrieved deterministically.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Site Visits / Appointments",
        "DB_TABLE": "site_visits",
        "DB_COUNT_ACTUAL": "1 (Vikram Malhotra at DLF Magnolias / Luxury 3BHK Penthouse)",
        "API_ENDPOINT": "GET /site-visits, GET /command-center/summary",
        "API_FILTER_SCOPE": "SiteVisit.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "1 Completed Site Visit (Attended by client with architect)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Site visit accurately linked to lead and deal.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Active Deals / Transactions",
        "DB_TABLE": "deals",
        "DB_COUNT_ACTUAL": "1 (DEAL-2026-001, Vikram Malhotra)",
        "API_ENDPOINT": "GET /deals, GET /deals/summary",
        "API_FILTER_SCOPE": "Deal.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "1 Deal in Booking Stage (Agreed: ₹22,000,000, Comm: ₹440,000)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "Remediated. Previously deal_controller used broker.id fallback.",
        "SEVERITY": "HIGH",
        "FIX": "Injected get_current_tenant dependency and dynamic organization_id resolution.",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Confirmed Bookings",
        "DB_TABLE": "deal_bookings",
        "DB_COUNT_ACTUAL": "1 (BKG-2026-001, Token: ₹1,100,000 paid)",
        "API_ENDPOINT": "GET /deals/{id}",
        "API_FILTER_SCOPE": "DealBooking.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "1 Confirmed Booking (TXN-BK-992819 Bank Transfer)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Booking lineage verified from lead to deal to booking.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Commission Invoicing",
        "DB_TABLE": "deal_commissions",
        "DB_COUNT_ACTUAL": "1 (INV-COM-2026-001, Gross: ₹440,000, Net: ₹396,000)",
        "API_ENDPOINT": "GET /deals/{id}",
        "API_FILTER_SCOPE": "DealCommission.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "Approved Commission Invoice (Status: APPROVED, 2% gross)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Tax deducted ₹44,000 correctly accounted.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Pipeline Value",
        "DB_TABLE": "deals",
        "DB_COUNT_ACTUAL": "₹22,000,000.00",
        "API_ENDPOINT": "GET /deals/summary",
        "API_FILTER_SCOPE": "Sum of Deal.agreed_price where status == ACTIVE",
        "FRONTEND_DISPLAY": "₹22,000,000 (INR)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "Remediated hardcoded AED currency to dynamic INR.",
        "SEVERITY": "MEDIUM",
        "FIX": "Updated DealService.get_pipeline_summary to resolve deal currency.",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Realized Revenue (Stage 1)",
        "DB_TABLE": "deals, deal_commissions",
        "DB_COUNT_ACTUAL": "₹0 collected / ₹440,000 invoiced pending payment",
        "API_ENDPOINT": "GET /revenue-intelligence/overview",
        "API_FILTER_SCOPE": "Deal.status == CLOSED_WON and commission status == PAID",
        "FRONTEND_DISPLAY": "₹0 Realized (Deal in booking stage, payment pending)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "Legitimate real zero. Transaction is confirmed booking, not yet paid.",
        "SEVERITY": "NONE",
        "FIX": "Preserved authentic accounting truth without fabricating realized revenue.",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Causal AI Revenue",
        "DB_TABLE": "pilot_tenants, autonomous_loop_executions",
        "DB_COUNT_ACTUAL": "₹0 (Stage 1 Shadow Mode, Autonomy 0)",
        "API_ENDPOINT": "GET /autonomous-loop/status, GET /revenue-intelligence/overview",
        "API_FILTER_SCOPE": "Autonomous attribution flags",
        "FRONTEND_DISPLAY": "₹0 (Attributed to human operator)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "Strict governance rule: human transactions are never converted to AI revenue.",
        "SEVERITY": "NONE",
        "FIX": "Preserved absolute Stage 1 isolation.",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Active Communications / Inbox",
        "DB_TABLE": "omnichannel_conversations",
        "DB_COUNT_ACTUAL": "0 active conversation threads",
        "API_ENDPOINT": "GET /communication/v2/inbox",
        "API_FILTER_SCOPE": "OmnichannelConversation.organization_id == tenant.organization_id",
        "FRONTEND_DISPLAY": "0 Active Conversations (Quick-action cards for 3 leads displayed)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "Remediated missing columns in DB schema, verified genuine zero.",
        "SEVERITY": "HIGH",
        "FIX": "Added identity_id and external_conversation_id to omnichannel_conversations.",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Operational Tasks & Reminders",
        "DB_TABLE": "tasks",
        "DB_COUNT_ACTUAL": "10 tasks total (3 re-engagement tasks for pilot tenant)",
        "API_ENDPOINT": "GET /tasks",
        "API_FILTER_SCOPE": "Task.broker_id == c193be18-4a6a-4030-9089-f94c42119189",
        "FRONTEND_DISPLAY": "3 Pending Tasks for Amit Sharma, Vikram Malhotra, Rajesh Kumar",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Tasks accurately reflect lead re-engagement triggers.",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    },
    {
        "METRIC/SCREEN": "Pilot Observations & Decisions",
        "DB_TABLE": "pilot_observations, pilot_human_decisions",
        "DB_COUNT_ACTUAL": "1 observation, 1 human decision",
        "API_ENDPOINT": "GET /autonomous-loop/queue",
        "API_FILTER_SCOPE": "PilotObservation.organization_id == a0317351-e076-493e-8b84-182f8c43666e",
        "FRONTEND_DISPLAY": "1 Logged Shadow Observation (Rajesh Kumar, SUMMARIZE_LEAD)",
        "STATUS": "MATCH",
        "DISCREPANCY_REASON": "None. Verified decision count matches checkpoint truth (1/50).",
        "SEVERITY": "NONE",
        "FIX": "N/A",
        "VERIFIED": "TRUE"
    }
]

with open("PHASE2C_6C_DATA_TRUTH_MATRIX.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "METRIC/SCREEN", "DB_TABLE", "DB_COUNT_ACTUAL", "API_ENDPOINT",
        "API_FILTER_SCOPE", "FRONTEND_DISPLAY", "STATUS", "DISCREPANCY_REASON",
        "SEVERITY", "FIX", "VERIFIED"
    ])
    writer.writeheader()
    writer.writerows(matrix_data)

print(f"Generated PHASE2C_6C_DATA_TRUTH_MATRIX.csv with {len(matrix_data)} entries.")
