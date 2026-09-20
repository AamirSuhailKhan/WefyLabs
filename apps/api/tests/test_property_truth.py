"""
Test Suite: Property Truth & Anti-Hallucination Grounding
Verifies:
  1. No hallucinated inventory: searching non-matching criteria returns 0 results, never invented properties.
  2. No fabricated payment plans: listings without verified payment plans return source_verified=False.
  3. Response Safety Guard: detects and flags unverified financial guarantees or hallucinated specs.
  4. Comparison truth: non-existent property IDs are placed in missing_ids rather than fabricated.
"""
import uuid
import pytest
from app.models.property_models import PropertyListing
from app.modules.ai_agent.tool_executor.services import PropertyService, ComparisonService
from app.modules.ai_agent.response_generator.safety_guard import ResponseSafetyGuard


@pytest.mark.asyncio
async def test_search_never_fabricates_properties(db_session, test_broker):
    """When no properties match in DB, returns empty list with verified status, never fake units."""
    svc = PropertyService(db_session)
    # Search for an impossible criteria in this empty DB
    results = await svc.search(
        property_type="penthouse",
        bedrooms=10,
        budget_max=1000000.0,
        organization_id=str(test_broker.id),
    )
    assert results["total"] == 0
    assert len(results["properties"]) == 0
    assert results["source_verified"] is True


@pytest.mark.asyncio
async def test_unverified_payment_plan_rejected(db_session, test_broker):
    """
    When a listing has no developer payment plan configured in DB,
    get_payment_plan returns source_verified=False and never fabricates a 40/60 plan.
    """
    prop = PropertyListing(
        id=uuid.uuid4(),
        broker_id=test_broker.id,
        title="Listing Without Plan",
        description="Standard unit",
        property_type="apartment",
        price=10000000.0,
        currency_code="INR",
        bedrooms=2,
        locality="Koramangala",
        city="Bengaluru",
        area_value=1200.0,
    )
    db_session.add(prop)
    await db_session.commit()

    svc = PropertyService(db_session)
    plan_data = await svc.get_payment_plan(str(prop.id), organization_id=str(test_broker.id))
    assert plan_data["source_verified"] is False
    assert plan_data["plan"] is None
    assert "No verified payment plan" in plan_data["message"]


def test_safety_guard_flags_unauthorized_financial_guarantees():
    """ResponseSafetyGuard flags messages promising guaranteed returns or financial returns."""
    guard = ResponseSafetyGuard(require_tool_grounding=False)

    # Hallucinated guarantee
    bad_message = "If you invest in this DLF unit today, we guarantee a 25% annual return on your capital."
    res = guard.validate(bad_message, tool_results=[])
    assert len(res.violations) > 0
    assert any("guarantee" in v.lower() or "financial" in v.lower() for v in res.violations)

    # Compliant grounded message
    clean_message = (
        "Based on verified developer data, Prestige Palms 3BHK has 1,850 sq.ft. "
        "Would you like to schedule a site visit to inspect the property?"
    )
    clean_res = guard.validate(clean_message, tool_results=[])
    assert len(clean_res.violations) == 0


@pytest.mark.asyncio
async def test_comparison_tracks_missing_ids(db_session, test_broker):
    """ComparisonService truthfully marks non-existent property IDs as missing_ids."""
    svc = ComparisonService(db_session)
    fake_id_1 = str(uuid.uuid4())
    fake_id_2 = str(uuid.uuid4())

    res = await svc.compare(
        property_ids=[fake_id_1, fake_id_2],
        organization_id=str(test_broker.id),
    )
    assert res["total"] == 0
    assert len(res["properties"]) == 0
    assert fake_id_1 in res["missing_ids"]
    assert fake_id_2 in res["missing_ids"]
    assert res["source_verified"] is True
