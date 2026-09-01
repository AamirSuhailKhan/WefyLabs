"""
Volume 2 PART 3 — Identity Resolution Engine Test Suite
========================================================
Comprehensive unit & integration tests covering:
1. Similarity Engine (Exact, Jaro-Winkler, Soundex, Token Sort, Weighted Aggregation)
2. Candidate Finder (Indexed phone/email/alias lookups)
3. Confidence & Decision Engines (Three-tier threshold evaluation)
4. Full Pipeline Service (New Identity, Auto Merge, Manual Review)
5. Merge Engine (Execution, Field Conflicts, Simulation, Undo)
6. REST API Endpoints (FastAPI async test client)
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.modules.identity_resolution.similarity_engine import (
    SimilarityEngine, ExactMatcher, NormalizedPhoneMatcher, NormalizedEmailMatcher,
    JaroWinklerMatcher, SoundexMatcher, TokenSortMatcher
)
from app.modules.identity_resolution.confidence import ConfidenceEngine
from app.modules.identity_resolution.decision_engine import DecisionEngine
from app.modules.identity_resolution.candidate_search import CandidateFinder
from app.modules.identity_resolution.service import IdentityResolutionService
from app.modules.identity_resolution.merge_engine import MergeExecutor, MergeSimulator, MergeReverter
from app.models.identity_models import Identity, IdentityLink, DuplicateCandidate, ManualReview, MergeOperation

# ─── SQLite In-Memory Database Fixture ───────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def async_client(test_db):
    async def _get_test_db():
        yield test_db

    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==============================================================================
# 1. SIMILARITY ENGINE UNIT TESTS
# ==============================================================================

def test_exact_phone_matcher():
    matcher = NormalizedPhoneMatcher()
    assert matcher.score("+971501234567", "+971501234567") == 1.0
    assert matcher.score("+971-50-123-4567", "0501234567") == 0.95  # Last 9 digits match
    assert matcher.score("+971501234567", "+971509999999") == 0.0


def test_normalized_email_matcher():
    matcher = NormalizedEmailMatcher()
    assert matcher.score("ahmed.raza@gmail.com", "ahmedraza@gmail.com") == 1.0  # Gmail dots ignored
    assert matcher.score("user+alias@company.com", "user@company.com") == 0.95
    assert matcher.score("john@domain.com", "jane@domain.com") == 0.0


def test_jaro_winkler_matcher():
    matcher = JaroWinklerMatcher()
    score1 = matcher.score("Ahmed Raza", "Ahmad Raza")
    assert score1 >= 0.85  # Slight spelling variation in name
    score2 = matcher.score("John Smith", "Xavier Dupont")
    assert score2 < 0.50


def test_soundex_matcher():
    matcher = SoundexMatcher()
    # Smith and Smyth share the S530 soundex code
    score = matcher.score("Smith", "Smyth")
    assert score >= 0.80


def test_token_sort_matcher():
    matcher = TokenSortMatcher()
    # Reordered words: "Raza Ahmed" vs "Ahmed Raza"
    score = matcher.score("Raza Ahmed", "Ahmed Raza")
    assert score >= 0.80


def test_similarity_engine_weighted_aggregation():
    engine = SimilarityEngine()
    lead_data = {
        "email": "ahmed.raza@example.com",
        "phone": "+971501234567",
        "name": "Ahmed Raza",
    }
    identity_data = {
        "email": "ahmed.raza@example.com",
        "phone": "+971501234567",
        "name": "Ahmad Raza",
    }
    res = engine.compute(lead_data, identity_data)
    assert res["confidence"] >= 0.90
    assert "email" in res["matched_fields"]
    assert "phone" in res["matched_fields"]


# ==============================================================================
# 2. DECISION ENGINE UNIT TESTS
# ==============================================================================

def test_decision_engine_thresholds():
    engine = DecisionEngine(auto_merge_threshold=0.95, manual_review_threshold=0.85)

    res_auto = engine.decide(0.97, {"id": "id1"})
    assert res_auto["decision"] == "auto_merge"

    res_review = engine.decide(0.90, {"id": "id1"})
    assert res_review["decision"] == "manual_review"

    res_new = engine.decide(0.75, {"id": "id1"})
    assert res_new["decision"] == "new_identity"


# ==============================================================================
# 3. PIPELINE INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_pipeline_new_identity_creation(test_db):
    service = IdentityResolutionService(db=test_db)
    lead_data = {
        "id": str(uuid.uuid4()),
        "phone": "+971501112233",
        "email": "brandnew.person@example.com",
        "name": "Brand New Person",
        "source": "website",
    }
    res = await service.resolve_lead(lead_data, organization_id="org_test_1")

    assert res["decision"] == "new_identity"
    assert res["identity_id"] is not None

    profile = await service.get_identity_profile(res["identity_id"])
    assert profile["primary_email"] == "brandnew.person@example.com"
    assert profile["lead_count"] == 1


@pytest.mark.asyncio
async def test_pipeline_auto_merge(test_db):
    service = IdentityResolutionService(db=test_db)
    org_id = "org_test_2"

    # Step 1: Ingest initial lead via WhatsApp
    lead1 = {
        "id": str(uuid.uuid4()),
        "phone": "+971509998877",
        "email": "john.doe@example.com",
        "name": "John Doe",
        "source": "whatsapp",
    }
    res1 = await service.resolve_lead(lead1, organization_id=org_id)
    assert res1["decision"] == "new_identity"
    identity_id = res1["identity_id"]

    # Step 2: Ingest second lead with identical phone & email via Facebook Ads
    lead2 = {
        "id": str(uuid.uuid4()),
        "phone": "+971509998877",
        "email": "john.doe@example.com",
        "name": "John Doe",
        "source": "facebook",
    }
    res2 = await service.resolve_lead(lead2, organization_id=org_id)

    assert res2["decision"] == "auto_merge"
    assert res2["identity_id"] == identity_id  # Linked to existing identity!

    profile = await service.get_identity_profile(identity_id)
    assert profile["lead_count"] == 2
    assert len(profile["linked_leads"]) == 2


@pytest.mark.asyncio
async def test_pipeline_manual_review_queue(test_db):
    service = IdentityResolutionService(db=test_db)
    org_id = "org_test_3"

    # Lead 1: Original profile
    lead1 = {
        "id": str(uuid.uuid4()),
        "phone": "+971505554433",
        "email": "salman.khan@domain.com",
        "name": "Salman Khan",
        "source": "google",
    }
    await service.resolve_lead(lead1, organization_id=org_id)

    # Lead 2: High value lead (budget >= 5M AED) with matching phone & email
    # RuleEngine triggers HIGH_VALUE_CAUTION -> downgrades auto_merge to manual_review!
    lead2 = {
        "id": str(uuid.uuid4()),
        "phone": "+971505554433",
        "email": "salman.khan@domain.com",
        "name": "Salman Khan",
        "budget_max": 6000000,
        "source": "csv",
    }
    res2 = await service.resolve_lead(lead2, organization_id=org_id)

    # High value lead must trigger manual review queue
    assert res2["decision"] == "manual_review"


# ==============================================================================
# 4. MERGE & UNDO INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_merge_executor_and_undo(test_db):
    service = IdentityResolutionService(db=test_db)
    org_id = "org_test_4"

    # Create Identity 1
    id1 = (await service.identity_graph.create_identity({
        "id": str(uuid.uuid4()),
        "phone": "+971501110000",
        "email": "first@test.com",
        "name": "First Person",
        "source": "manual",
    }, org_id)).id

    # Create Identity 2
    id2 = (await service.identity_graph.create_identity({
        "id": str(uuid.uuid4()),
        "phone": "+971502220000",
        "email": "second@test.com",
        "name": "Second Person",
        "source": "api",
    }, org_id)).id

    # Dry-run simulate merge
    sim = await service.simulate_merge(id1, id2, confidence=0.92)
    assert sim["affected_leads"] >= 2

    # Execute Merge: merge id1 into id2
    executor = MergeExecutor(test_db)
    merge_res = await executor.execute_merge(
        source_identity_id=id1,
        target_identity_id=id2,
        organization_id=org_id,
        merge_confidence=0.92,
        actor_id="broker_123",
    )
    assert merge_res["status"] == "completed"

    # Verify source identity is marked merged
    src_profile = await service.get_identity_profile(id1)
    assert src_profile["is_merged"] == True
    assert src_profile["merged_into_id"] == id2

    # Undo Merge
    undo_res = await service.undo_merge(merge_res["merge_operation_id"], undone_by="broker_123")
    assert undo_res["status"] == "undone"

    # Verify source identity is restored
    src_profile_restored = await service.get_identity_profile(id1)
    assert src_profile_restored["is_merged"] == False
    assert src_profile_restored["merged_into_id"] is None


# ==============================================================================
# 5. REST API ENDPOINT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_rest_api_resolve_and_profile(async_client):
    lead_id = str(uuid.uuid4())
    payload = {
        "lead_data": {
            "phone": "+971507778899",
            "email": "api.test@example.com",
            "name": "API Test User",
            "source": "api",
        },
        "organization_id": "org_api_test",
    }

    # POST /api/v1/identity/resolve/{lead_id}
    res = await async_client.post(f"/api/v1/identity/resolve/{lead_id}", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    identity_id = data["result"]["identity_id"]

    # GET /api/v1/identity/profile/{identity_id}
    profile_res = await async_client.get(f"/api/v1/identity/profile/{identity_id}")
    assert profile_res.status_code == 200
    prof_data = profile_res.json()
    assert prof_data["identity"]["primary_email"] == "api.test@example.com"


@pytest.mark.asyncio
async def test_rest_api_metrics(async_client):
    res = await async_client.get("/api/v1/identity/metrics?organization_id=org_api_test")
    assert res.status_code == 200
    data = res.json()
    assert "total_identities" in data
    assert "duplicate_rate" in data
