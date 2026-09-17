"""
Part 30 — Unit Test Suite: AI Real-Estate Agent Daily Command Center
===================================================================
24 unit tests covering:
- Priority calculation (Critical, High, Medium, Low)
- First-contact SLA breach and impending expiry
- Meeting and site visit proximity thresholds
- Overdue follow-up severity bands
- Hot lead stagnation and strong match elevation
- Stale lead re-engagement scoring
- Deterministic priority ranking and dismissal filtering
- Inventory Intelligence demand heatmap aggregation
- Inventory gap identification and deficit severity
- Morning briefing deterministic synthesis and error fallback
"""
import uuid
from datetime import datetime, timezone, timedelta
import pytest

from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.modules.command_center.dto import PriorityItemDTO
from app.modules.command_center.priority_engine import CommandCenterPriorityEngine
from app.modules.command_center.inventory_intelligence import InventoryIntelligenceEngine
from app.modules.command_center.briefing_service import CommandCenterBriefingService


# ─── 1. Priority Calculation Tests ───────────────────────────────────────────

def test_priority_first_contact_sla_overdue_critical():
    """First-contact SLA breach must result in CRITICAL priority with score >= 95."""
    now = datetime.now(timezone.utc)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="first_contact",
        overdue_minutes=25,
        now=now
    )
    assert label == "CRITICAL"
    assert score >= 95.0


def test_priority_first_contact_sla_impending_high():
    """Impending SLA expiry (< 10 mins remaining) produces HIGH priority."""
    now = datetime.now(timezone.utc)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="first_contact",
        overdue_minutes=-8,  # 8 mins remaining
        now=now
    )
    assert label == "HIGH"
    assert score >= 90.0


def test_priority_site_visit_within_2_hours_high():
    """Site visit within 2 hours produces HIGH priority (score >= 90)."""
    now = datetime.now(timezone.utc)
    visit_time = now + timedelta(minutes=45)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="site_visit",
        due_at=visit_time,
        now=now
    )
    assert label == "HIGH"
    assert score >= 90.0


def test_priority_site_visit_within_4_hours_high():
    """Meeting within 4 hours produces HIGH priority (score >= 80)."""
    now = datetime.now(timezone.utc)
    meet_time = now + timedelta(hours=3)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="meeting",
        due_at=meet_time,
        now=now
    )
    assert label == "HIGH"
    assert score >= 80.0


def test_priority_site_visit_past_needing_outcome():
    """Past meeting produces MEDIUM priority with directive to record outcome."""
    now = datetime.now(timezone.utc)
    past_time = now - timedelta(hours=2)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="site_visit",
        due_at=past_time,
        now=now
    )
    assert label == "MEDIUM"
    assert score >= 70.0


def test_priority_followup_overdue_long_critical():
    """Follow-up task overdue by > 5 days escalates to CRITICAL (score >= 94)."""
    now = datetime.now(timezone.utc)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="overdue_followup",
        overdue_minutes=7200,  # 5 days
        now=now
    )
    assert label == "CRITICAL"
    assert score >= 94.0


def test_priority_followup_overdue_medium_high():
    """Follow-up task overdue by 2 days is HIGH priority."""
    now = datetime.now(timezone.utc)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="overdue_followup",
        overdue_minutes=2880,  # 2 days
        now=now
    )
    assert label == "HIGH"
    assert score >= 88.0


def test_priority_followup_overdue_short_medium():
    """Follow-up task overdue by a few hours is MEDIUM priority."""
    now = datetime.now(timezone.utc)
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="overdue_followup",
        overdue_minutes=180,  # 3 hours
        now=now
    )
    assert label == "MEDIUM"
    assert score >= 70.0


def test_priority_hot_lead_strong_match_high():
    """Hot lead with 90+ property match produces HIGH priority."""
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="hot_lead",
        is_hot_lead=True,
        match_score=94.0
    )
    assert label == "HIGH"
    assert score >= 85.0


def test_priority_hot_lead_inactive_high():
    """Hot lead inactive for 3+ days produces HIGH priority."""
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="hot_lead",
        is_hot_lead=True,
        days_inactive=4
    )
    assert label == "HIGH"
    assert score >= 80.0


def test_priority_strong_match_95_plus():
    """Match score >= 95 produces HIGH priority."""
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="strong_match",
        match_score=96.0
    )
    assert label == "HIGH"
    assert score >= 85.0


def test_priority_stale_lead_hot_elevated():
    """Stale lead marked as 'hot' receives elevated priority over standard stale leads."""
    label_hot, score_hot = CommandCenterPriorityEngine.evaluate_item_priority(
        category="stale_lead",
        is_hot_lead=True,
        days_inactive=14
    )
    label_norm, score_norm = CommandCenterPriorityEngine.evaluate_item_priority(
        category="stale_lead",
        is_hot_lead=False,
        days_inactive=14
    )
    assert score_hot > score_norm
    assert label_hot == "HIGH"


def test_priority_stale_lead_standard_medium():
    """Standard lead inactive for 30+ days is MEDIUM priority."""
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="stale_lead",
        is_hot_lead=False,
        days_inactive=35
    )
    assert label == "MEDIUM"
    assert score >= 60.0


def test_priority_inventory_opportunity_medium():
    """New inventory matching pipeline leads produces MEDIUM priority."""
    label, score = CommandCenterPriorityEngine.evaluate_item_priority(
        category="inventory_opportunity"
    )
    assert label == "MEDIUM"
    assert score >= 50.0


# ─── 2. Ranking and Dismissal Tests ──────────────────────────────────────────

def test_priority_ranking_order():
    """Items are deterministically ranked by priority score descending."""
    item1 = PriorityItemDTO(
        id="1", item_key="lead:1:fc", priority="MEDIUM", priority_score=70.0,
        category="stale_lead", title="Stale lead", description="idle",
        entity_type="lead", entity_id="1", recommended_action="OPEN_LEAD"
    )
    item2 = PriorityItemDTO(
        id="2", item_key="lead:2:fc", priority="CRITICAL", priority_score=98.0,
        category="first_contact", title="Urgent SLA", description="overdue",
        entity_type="lead", entity_id="2", recommended_action="CALL"
    )
    item3 = PriorityItemDTO(
        id="3", item_key="task:3:due", priority="HIGH", priority_score=88.0,
        category="overdue_followup", title="Task overdue", description="2 days",
        entity_type="task", entity_id="3", recommended_action="COMPLETE_TASK"
    )

    ranked = CommandCenterPriorityEngine.rank_and_filter_priorities([item1, item2, item3])
    assert [x.id for x in ranked] == ["2", "3", "1"]


def test_priority_filter_dismissed_keys():
    """Dismissed items are excluded from the priority queue."""
    item1 = PriorityItemDTO(
        id="1", item_key="lead:1:first_contact", priority="CRITICAL", priority_score=98.0,
        category="first_contact", title="Call", description="overdue",
        entity_type="lead", entity_id="1", recommended_action="CALL"
    )
    item2 = PriorityItemDTO(
        id="2", item_key="task:2:overdue", priority="HIGH", priority_score=85.0,
        category="overdue_followup", title="Task", description="overdue",
        entity_type="task", entity_id="2", recommended_action="COMPLETE_TASK"
    )

    dismissed = {"lead:1:first_contact"}
    ranked = CommandCenterPriorityEngine.rank_and_filter_priorities([item1, item2], dismissed_keys=dismissed)
    assert len(ranked) == 1
    assert ranked[0].id == "2"


# ─── 3. Inventory Intelligence Tests ─────────────────────────────────────────

def test_inventory_demand_heatmap_computation():
    """Demand heatmap computes counts for locations, BHK, and budget bands."""
    leads = [
        Lead(id=uuid.uuid4(), preferred_locations=["Whitefield"], property_type="3 BHK apartment", budget_max=12000000),
        Lead(id=uuid.uuid4(), preferred_locations=["Whitefield", "Indiranagar"], property_type="3 BHK apartment", budget_max=9500000),
        Lead(id=uuid.uuid4(), preferred_locations=["Indiranagar"], property_type="2 BHK apartment", budget_max=4500000),
    ]
    props = [
        PropertyListing(id=uuid.uuid4(), title="WF 3BHK", locality="Whitefield", bedrooms=3, price=11000000.0, status="available")
    ]
    heatmap = InventoryIntelligenceEngine.compute_demand_heatmap(leads, props)

    # Top location should be Whitefield (count 2)
    top_loc = heatmap.top_locations[0]
    assert top_loc["location"] == "Whitefield"
    assert top_loc["active_leads"] == 2

    # Top BHK should be 3 BHK (count 2)
    top_bhk = heatmap.top_bhk[0]
    assert top_bhk["bhk"] == "3 BHK"
    assert top_bhk["active_leads"] == 2


def test_inventory_demand_heatmap_empty_pipeline():
    """Empty pipeline returns empty lists with disclaimer intact."""
    heatmap = InventoryIntelligenceEngine.compute_demand_heatmap([], [])
    assert len(heatmap.top_locations) == 0
    assert "exclusively" in heatmap.disclaimer.lower()


def test_inventory_gap_identification():
    """Identifies deficit where lead demand exceeds available property supply."""
    leads = [
        Lead(id=uuid.uuid4(), preferred_locations=["Whitefield"], property_type="3 BHK apartment"),
        Lead(id=uuid.uuid4(), preferred_locations=["Whitefield"], property_type="3 BHK apartment"),
        Lead(id=uuid.uuid4(), preferred_locations=["Whitefield"], property_type="3 BHK apartment"),
    ]
    props = [
        # Only 1 available property in Whitefield for 3 BHK
        PropertyListing(id=uuid.uuid4(), title="WF 3BHK", locality="Whitefield", bedrooms=3, status="available")
    ]
    gaps = InventoryIntelligenceEngine.identify_inventory_gaps(leads, props)
    assert len(gaps) >= 1
    top_gap = gaps[0]
    assert "Whitefield" in top_gap.locality
    assert top_gap.demand_lead_count == 3
    assert top_gap.supply_property_count == 1
    assert top_gap.gap_deficit == 2


def test_inventory_gap_balanced_no_deficit():
    """When supply meets or exceeds demand, deficit gap is not returned."""
    leads = [
        Lead(id=uuid.uuid4(), preferred_locations=["Koramangala"], property_type="2 BHK apartment"),
    ]
    props = [
        PropertyListing(id=uuid.uuid4(), title="KM 2BHK 1", locality="Koramangala", bedrooms=2, status="available"),
        PropertyListing(id=uuid.uuid4(), title="KM 2BHK 2", locality="Koramangala", bedrooms=2, status="available")
    ]
    gaps = InventoryIntelligenceEngine.identify_inventory_gaps(leads, props)
    # Less than 2 leads or deficit <= 0 produces no gap
    assert not any("Koramangala" in g.locality for g in gaps)


def test_inventory_opportunity_lead_matching():
    """Associates compatible leads with recent listings."""
    leads = [
        Lead(id=uuid.uuid4(), preferred_locations=["Whitefield"], property_type="3 BHK apartment", budget_max=12000000),
        Lead(id=uuid.uuid4(), preferred_locations=["Electronic City"], property_type="2 BHK apartment", budget_max=6000000),
    ]
    props = [
        PropertyListing(
            id=uuid.uuid4(), title="New Launch Whitefield", locality="Whitefield",
            bedrooms=3, price=11000000.0, status="available", created_at=datetime.now(timezone.utc)
        )
    ]
    opps = InventoryIntelligenceEngine.identify_new_inventory_opportunities(props, leads)
    assert len(opps) == 1
    assert opps[0].potential_leads_count == 1
    assert opps[0].strong_matches_count == 1


# ─── 4. Daily Briefing Tests ─────────────────────────────────────────────────

def test_briefing_deterministic_fallback_full_facts():
    """Constructs comprehensive morning briefing using all verified counters."""
    briefing = CommandCenterBriefingService.generate_deterministic_briefing(
        broker_name="Vikram",
        critical_count=2,
        overdue_count=3,
        meetings_count=1,
        site_visits_count=2,
        hot_leads_count=4,
        strong_matches_count=3,
        top_directive="Contact Rahul Sharma",
        top_inventory_gap="3 BHK in Whitefield"
    )
    text = briefing.briefing_text
    assert "Vikram" in briefing.greeting
    assert "5 high-priority operational items" in text
    assert "2 lead(s) require urgent first contact" in text
    assert "3 client follow-up task(s) are overdue" in text
    assert "2 site visit(s)" in text
    assert "3 qualified buyers" in text
    assert "3 BHK in Whitefield" in text
    assert len(briefing.highlights) >= 3


def test_briefing_deterministic_fallback_empty_pipeline():
    """Generates polite message when pipeline is clean."""
    briefing = CommandCenterBriefingService.generate_deterministic_briefing(
        broker_name="Aamir",
        critical_count=0,
        overdue_count=0,
        meetings_count=0,
        site_visits_count=0,
        hot_leads_count=0,
        strong_matches_count=0
    )
    assert "zero overdue emergencies" in briefing.briefing_text.lower()


@pytest.mark.asyncio
async def test_briefing_ai_fallback_on_exception():
    """Gracefully falls back to deterministic briefing when AI raises an exception."""
    class FailingAIService:
        async def generate_text(self, *args, **kwargs):
            raise RuntimeError("Gemini rate limit exceeded")

    briefing = await CommandCenterBriefingService.generate_briefing(
        broker_name="Rahul",
        critical_count=1,
        overdue_count=2,
        meetings_count=0,
        site_visits_count=1,
        hot_leads_count=0,
        strong_matches_count=1,
        ai_service=FailingAIService()
    )
    assert briefing is not None
    assert "Rahul" in briefing.greeting
    assert not briefing.is_ai_generated
    assert "urgent first contact" in briefing.briefing_text
