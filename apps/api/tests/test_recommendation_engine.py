"""
Unit & Integration Test Suite for AI Property Recommendation Engine
====================================================================
Tests:
- FX Currency Normalization
- Hard Constraint Engine Filtering
- 8-Dimension Compatibility Scorer
- Diversity Reranking & Option Classification
- Grounded Match Explanations
"""

import pytest
import uuid
from app.models.property_models import PropertyListing
from app.models.recommendation_models import BuyerProfile
from app.modules.recommendation.scoring.FX_converter import FXConverter
from app.modules.recommendation.constraint_engine.hard_constraints import HardConstraintEngine
from app.modules.recommendation.scoring.compatibility_scorer import CompatibilityScorer
from app.modules.recommendation.ranking.diversity_reranker import DiversityReranker
from app.modules.recommendation.explanation.explanation_builder import ExplanationBuilder


def test_fx_converter():
    converter = FXConverter()
    amount_aed, meta = converter.convert_to_aed(100.0, "USD")
    assert amount_aed == pytest.approx(367.25, rel=1e-2)
    assert meta["confidence"] == 1.0

    inr_aed, _ = converter.convert_to_aed(1000000.0, "INR") # 10 Lakhs INR
    assert inr_aed > 0


def test_hard_constraint_budget_and_status():
    engine = HardConstraintEngine()

    buyer = BuyerProfile(
        lead_id=str(uuid.uuid4()),
        broker_id=str(uuid.uuid4()),
        organization_id="org_1",
        currency="AED",
        max_budget=2000000.0, # 2.0M AED max
        budget_flexibility_pct=10.0, # 2.2M hard ceiling
        min_bedrooms=2,
        max_bedrooms=4,
        excluded_developers=[],
        excluded_locations=[]
    )

    prop_valid = PropertyListing(
        id=uuid.uuid4(),
        broker_id=uuid.uuid4(),
        title="Valid 3BHK",
        description="Nice property",
        price=1900000.0, # Within budget
        currency="AED",
        built_up_area_sqft=1400.0,
        bedrooms=3,
        bathrooms=3,
        status="available"
    )

    prop_over_budget = PropertyListing(
        id=uuid.uuid4(),
        broker_id=uuid.uuid4(),
        title="Overpriced Villa",
        description="Luxury villa",
        price=3500000.0, # Exceeds budget ceiling
        currency="AED",
        built_up_area_sqft=3000.0,
        bedrooms=4,
        bathrooms=5,
        status="available"
    )

    prop_sold = PropertyListing(
        id=uuid.uuid4(),
        broker_id=uuid.uuid4(),
        title="Sold Unit",
        description="Unavailable",
        price=1800000.0,
        currency="AED",
        built_up_area_sqft=1200.0,
        bedrooms=3,
        bathrooms=2,
        status="sold"
    )

    valid, rejected = engine.filter_candidates([prop_valid, prop_over_budget, prop_sold], buyer)

    assert len(valid) == 1
    assert valid[0].title == "Valid 3BHK"
    assert len(rejected) == 2


def test_compatibility_scoring():
    scorer = CompatibilityScorer()

    buyer = BuyerProfile(
        lead_id=str(uuid.uuid4()),
        broker_id=str(uuid.uuid4()),
        organization_id="org_1",
        currency="AED",
        max_budget=2500000.0,
        min_budget=1500000.0,
        purchase_purpose="end_user",
        min_bedrooms=2,
        max_bedrooms=4,
        preferred_locations=["Dubai Marina"]
    )

    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=uuid.uuid4(),
        title="Marina 3BHK",
        description="Great view",
        price=2200000.0,
        currency="AED",
        built_up_area_sqft=1600.0,
        bedrooms=3,
        bathrooms=3,
        locality="Dubai Marina",
        city="Dubai",
        status="available"
    )

    score, breakdown = scorer.calculate_score(prop, buyer)

    assert score >= 80.0
    assert breakdown.budget_fit == 100.0
    assert breakdown.location_fit == 100.0


def test_diversity_reranker():
    reranker = DiversityReranker()

    prop1 = PropertyListing(id=uuid.uuid4(), title="Penthouse 1", price=2500000.0, project_name="Tower A")
    prop2 = PropertyListing(id=uuid.uuid4(), title="Penthouse 2", price=1800000.0, project_name="Tower A")
    prop3 = PropertyListing(id=uuid.uuid4(), title="Apartment 3", price=2100000.0, project_name="Tower B")

    items = [
        {"property": prop1, "match_score": 95.0, "breakdown": None},
        {"property": prop2, "match_score": 91.0, "breakdown": None},
        {"property": prop3, "match_score": 88.0, "breakdown": None},
    ]

    # Create dummy breakdowns for test
    from app.modules.recommendation.dto.recommendation_schemas import ScoreBreakdownDTO
    bd = ScoreBreakdownDTO(
        budget_fit=95.0, location_fit=90.0, property_fit=90.0, preference_fit=80.0,
        investment_fit=80.0, timeline_fit=80.0, payment_plan_fit=80.0, behavioral_fit=80.0
    )
    for it in items:
        it["breakdown"] = bd

    reranked = reranker.rerank_and_tag(items, top_k=3)

    assert len(reranked) == 3
    assert reranked[0]["recommendation_type"] == "BEST_OVERALL"
    assert reranked[0]["rank_position"] == 1


def test_explanation_builder():
    builder = ExplanationBuilder()

    buyer = BuyerProfile(
        lead_id=str(uuid.uuid4()),
        broker_id=str(uuid.uuid4()),
        organization_id="org_1",
        currency="AED",
        max_budget=2000000.0,
        min_bedrooms=3,
        max_bedrooms=3,
        preferred_locations=["Dubai Marina"],
        purchase_purpose="investment"
    )

    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=uuid.uuid4(),
        title="Marina Tower 3BHK",
        description="Luxury unit",
        price=1900000.0,
        currency="AED",
        built_up_area_sqft=1500.0,
        bedrooms=3,
        bathrooms=3,
        locality="Dubai Marina",
        city="Dubai",
        status="available",
        estimated_annual_roi_yield_pct=7.2,
        transaction_category="resale"
    )

    from app.modules.recommendation.dto.recommendation_schemas import ScoreBreakdownDTO
    bd = ScoreBreakdownDTO(
        budget_fit=100.0, location_fit=100.0, property_fit=100.0, preference_fit=80.0,
        investment_fit=90.0, timeline_fit=80.0, payment_plan_fit=80.0, behavioral_fit=80.0
    )

    exp = builder.build_explanation(prop, buyer, score=92.0, breakdown=bd, rec_type="BEST_OVERALL")

    assert len(exp["strong_matches"]) >= 2
    assert any("saving" in m.lower() or "budget" in m.lower() for m in exp["strong_matches"])
    assert any("dubai marina" in m.lower() for m in exp["strong_matches"])
    assert exp["suggested_next_action"] == "Schedule Site Visit / Viewing"
    assert len(exp["agent_talking_points"]) >= 1


@pytest.mark.asyncio
async def test_property_comparison_generation():
    from unittest.mock import AsyncMock, MagicMock
    from app.modules.recommendation.service import PropertyRecommendationService
    from app.modules.recommendation.dto.recommendation_schemas import PropertyComparisonRequestDTO

    db = AsyncMock()
    p1_id = uuid.uuid4()
    p2_id = uuid.uuid4()

    prop1 = PropertyListing(
        id=p1_id,
        title="Creek Waters 3BHK",
        price=2200000.0,
        currency="AED",
        built_up_area_sqft=1600.0,
        bedrooms=3,
        bathrooms=3,
        city="Dubai",
        locality="Dubai Creek",
        project_name="Creek Waters",
        amenities=["Pool", "Gym"],
        estimated_annual_roi_yield_pct=6.8,
        status="available"
    )
    prop2 = PropertyListing(
        id=p2_id,
        title="Marina Gate 2BHK",
        price=1800000.0,
        currency="AED",
        built_up_area_sqft=1250.0,
        bedrooms=2,
        bathrooms=2,
        city="Dubai",
        locality="Dubai Marina",
        project_name="Marina Gate",
        amenities=["Pool", "Concierge"],
        estimated_annual_roi_yield_pct=7.1,
        status="available"
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [prop1, prop2]
    db.execute.return_value = mock_res

    svc = PropertyRecommendationService(db)
    dto = PropertyComparisonRequestDTO(property_ids=[str(p1_id), str(p2_id)])
    comparison = await svc.compare_properties(dto)

    assert comparison["compared_count"] == 2
    assert len(comparison["properties"]) == 2
    assert comparison["properties"][0]["title"] == "Creek Waters 3BHK"
    assert comparison["properties"][1]["title"] == "Marina Gate 2BHK"


@pytest.mark.asyncio
async def test_demand_intelligence_aggregation():
    from unittest.mock import AsyncMock, MagicMock
    from app.modules.recommendation.demand_intelligence.demand_analyzer import PropertyDemandAnalyzer

    db = AsyncMock()

    b1 = BuyerProfile(
        lead_id="l1", broker_id="b1", organization_id="org_test",
        max_budget=1800000.0, preferred_locations=["Dubai Marina"], property_types=["apartment"]
    )
    b2 = BuyerProfile(
        lead_id="l2", broker_id="b1", organization_id="org_test",
        max_budget=2200000.0, preferred_locations=["Dubai Marina"], property_types=["apartment"]
    )

    mock_prof_res = MagicMock()
    mock_prof_res.scalars.return_value.all.return_value = [b1, b2]

    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1  # 1 available unit in Marina vs 2 buyers

    db.execute.side_effect = [mock_prof_res, mock_count_res, mock_count_res]

    analyzer = PropertyDemandAnalyzer(db)
    demand = await analyzer.analyze_demand(organization_id="org_test")

    assert demand["total_active_buyer_profiles"] == 2
    assert len(demand["top_demanded_locations"]) >= 1
    assert demand["top_demanded_locations"][0]["location"] == "Dubai Marina"
    assert demand["top_demanded_locations"][0]["buyer_count"] == 2


