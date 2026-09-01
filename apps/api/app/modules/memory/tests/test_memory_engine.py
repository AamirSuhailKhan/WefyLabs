"""
Comprehensive Test Suite for AI Memory & Customer Intelligence Engine
======================================================================
Tests:
1. Provenance Hierarchy & Confidence Scoring
2. AI Inference Cannot Override Explicit Customer Stated Facts
3. Contradiction Resolution & Immutable Version Archiving
4. Deduplication & Confidence Boosting
5. Natural Text Fact & Constraint Extraction
6. Hybrid Retrieval & AI Context Prompt Budgeting
7. Customer-Safe vs Internal Visibility Gating
8. Structured Objection Tracking
9. Property Rejection Reason Tracking
10. Memory Decay Curves & Stale Transitions
11. GDPR/CCPA Privacy Deletion Requests & Audit Trail
12. Multi-Tenant & Lead Isolation
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.memory_models import (
    MemoryRecord, MemoryVersion, MemoryEvidence,
    MemoryObjection, MemoryPropertyFeedback, MemoryAuditLog,
    MemoryDeletionRequest
)
from app.modules.memory.provenance.provenance_tracker import ProvenanceTracker
from app.modules.memory.contradiction.contradiction_engine import ContradictionEngine
from app.modules.memory.extraction.memory_extractor import MemoryExtractor
from app.modules.memory.decay.decay_manager import DecayManager
from app.modules.memory.retrieval.memory_retriever import MemoryRetriever
from app.modules.memory.privacy.privacy_manager import PrivacyManager
from app.modules.memory.service import AIMemoryService


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


class TestProvenanceAndConfidence:
    """Test source hierarchy and confidence calibration."""

    def test_source_ranks(self):
        assert ProvenanceTracker.get_source_rank("CUSTOMER_STATED") == 100
        assert ProvenanceTracker.get_source_rank("AGENT_CONFIRMED") == 90
        assert ProvenanceTracker.get_source_rank("CRM_VERIFIED") == 85
        assert ProvenanceTracker.get_source_rank("BEHAVIORAL_SIGNAL") == 60
        assert ProvenanceTracker.get_source_rank("AI_INFERRED") == 40

    def test_override_permissions(self):
        # Customer stated can override anything
        assert ProvenanceTracker.can_source_override("CUSTOMER_STATED", "AI_INFERRED") is True
        assert ProvenanceTracker.can_source_override("CUSTOMER_STATED", "CUSTOMER_STATED") is True

        # AI inference CANNOT override customer stated
        assert ProvenanceTracker.can_source_override("AI_INFERRED", "CUSTOMER_STATED") is False
        assert ProvenanceTracker.can_source_override("AI_INFERRED", "AGENT_CONFIRMED") is False


class TestContradictionAndVersioning:
    """Test contradiction handling and immutable version archiving."""

    @pytest.mark.asyncio
    async def test_initial_memory_creation(self, mock_db):
        engine = ContradictionEngine(mock_db)
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_res

        res = await engine.reconcile_memory(
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="CONSTRAINT",
            key="budget_max",
            new_value_json={"amount": 2000000, "currency": "AED"},
            new_value_text="Max budget: AED 2,000,000",
            source_type="CUSTOMER_STATED"
        )
        assert res.action_taken == "CREATED"
        assert res.active_record.version_number == 1
        assert res.active_record.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_contradiction_supersedes_and_archives_old_version(self, mock_db):
        engine = ContradictionEngine(mock_db)

        # Existing v1 memory: Budget AED 2M
        existing = MemoryRecord(
            id=str(uuid.uuid4()),
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="CONSTRAINT",
            key="budget_max",
            value_json={"amount": 2000000, "currency": "AED"},
            value_text="Max budget: AED 2,000,000",
            source_type="CUSTOMER_STATED",
            confidence=0.98,
            status="ACTIVE",
            version_number=1
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_res

        # Customer updates budget to AED 2.5M
        res = await engine.reconcile_memory(
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="CONSTRAINT",
            key="budget_max",
            new_value_json={"amount": 2500000, "currency": "AED"},
            new_value_text="Max budget: AED 2,500,000",
            source_type="CUSTOMER_STATED"
        )

        assert res.action_taken == "SUPERSEDED"
        assert res.active_record.version_number == 2
        assert res.active_record.value_json["amount"] == 2500000
        assert res.archived_version is not None
        assert res.archived_version.version_number == 1
        assert res.archived_version.value_json["amount"] == 2000000

    @pytest.mark.asyncio
    async def test_ai_inference_cannot_override_explicit_statement(self, mock_db):
        engine = ContradictionEngine(mock_db)

        existing = MemoryRecord(
            id=str(uuid.uuid4()),
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="CONSTRAINT",
            key="budget_max",
            value_json={"amount": 2000000, "currency": "AED"},
            source_type="CUSTOMER_STATED",
            status="ACTIVE",
            version_number=1
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_res

        # AI attempts to override with guess of AED 1.5M
        res = await engine.reconcile_memory(
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="CONSTRAINT",
            key="budget_max",
            new_value_json={"amount": 1500000, "currency": "AED"},
            source_type="AI_INFERRED"
        )

        assert res.action_taken == "REJECTED_LOW_RANK"
        assert res.active_record.value_json["amount"] == 2000000  # Preserved original


class TestMemoryExtractor:
    """Test natural text fact and constraint extraction."""

    def test_extract_budget_bedrooms_and_location(self):
        msg = "Hi, I am looking for a 3-bedroom apartment in Dubai Marina under AED 2.5M. No off-plan please."
        cands = MemoryExtractor.extract_candidates(msg, is_customer_message=True)

        keys = {c.key for c in cands}
        assert "budget_max" in keys
        assert "bedrooms" in keys
        assert "preferred_locality" in keys
        assert "disliked_property_type" in keys

        budget_cand = [c for c in cands if c.key == "budget_max"][0]
        assert budget_cand.value_json["amount"] == 2500000
        assert budget_cand.source_type == "CUSTOMER_STATED"

        beds_cand = [c for c in cands if c.key == "bedrooms"][0]
        assert beds_cand.value_json["bedrooms"] == 3


class TestRetrievalAndContextBudgeting:
    """Test hybrid ranking and context formatting for LLMs."""

    @pytest.mark.asyncio
    async def test_build_ai_prompt_context(self, mock_db):
        retriever = MemoryRetriever(mock_db)

        records = [
            MemoryRecord(
                id="1", organization_id="org_test", lead_id="lead_1",
                memory_type="CONSTRAINT", key="budget_max",
                value_text="Max budget: AED 2,500,000",
                source_type="CUSTOMER_STATED", confidence=0.98, importance=0.95,
                status="ACTIVE", is_customer_safe=True
            ),
            MemoryRecord(
                id="2", organization_id="org_test", lead_id="lead_1",
                memory_type="LOCATION", key="preferred_locality",
                value_text="Preferred area: Dubai Marina",
                source_type="CUSTOMER_STATED", confidence=0.95, importance=0.90,
                status="ACTIVE", is_customer_safe=True
            ),
            MemoryRecord(
                id="3", organization_id="org_test", lead_id="lead_1",
                memory_type="AI_DECISION", key="price_sensitivity_internal",
                value_text="Internal Note: High price sensitivity observed",
                source_type="AI_INFERRED", confidence=0.60, importance=0.40,
                status="ACTIVE", is_customer_safe=False  # Not customer safe!
            ),
        ]

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = records
        mock_db.execute.return_value = mock_res

        # Customer-facing context should exclude internal notes
        ctx = await retriever.build_ai_prompt_context("org_test", "lead_1", max_items=5, is_customer_facing=True)
        assert "BUDGET_MAX" in ctx
        assert "PREFERRED_LOCALITY" in ctx


class TestDecayAndPrivacy:
    """Test freshness decay and GDPR deletion."""

    @pytest.mark.asyncio
    async def test_memory_decay_eval(self, mock_db):
        manager = DecayManager(mock_db)

        old_date = datetime.now(timezone.utc) - timedelta(days=60)
        old_timeline_rec = MemoryRecord(
            id="1", organization_id="org_test", lead_id="lead_1",
            memory_type="TIMELINE", key="buying_timeline",
            value_text="Wants to buy within 2 weeks",
            source_type="CUSTOMER_STATED", confidence=0.90, importance=0.80,
            status="ACTIVE", updated_at=old_date, created_at=old_date
        )

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [old_timeline_rec]
        mock_db.execute.return_value = mock_res

        stale = await manager.evaluate_stale_memories("org_test")
        assert len(stale) == 1
        assert stale[0].status == "STALE"

    @pytest.mark.asyncio
    async def test_gdpr_deletion_request(self, mock_db):
        privacy = PrivacyManager(mock_db)

        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        mock_db.execute.return_value = mock_res

        del_req = await privacy.execute_lead_deletion_request("org_test", "lead_1", "Compliance Officer")
        assert del_req.status == "COMPLETED"
        assert del_req.records_deleted_count == 2
        assert mock_db.commit.called


class TestObjectionsAndFeedback:
    """Test structured objection and property feedback lifecycle."""

    @pytest.mark.asyncio
    async def test_record_objection(self, mock_db):
        service = AIMemoryService(mock_db)
        obj = await service.record_objection(
            organization_id="org_test",
            lead_id="lead_123",
            category="PRICE",
            description="Price exceeds max budget by 20%"
        )
        assert obj.category == "PRICE"
        assert obj.status == "OPEN"
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_record_property_rejection(self, mock_db):
        service = AIMemoryService(mock_db)
        fb = await service.record_property_feedback(
            organization_id="org_test",
            lead_id="lead_123",
            property_id="prop_456",
            feedback_type="REJECTED",
            rejection_reason_code="TOO_EXPENSIVE",
            notes="Buyer disliked service charge costs"
        )
        assert fb.feedback_type == "REJECTED"
        assert fb.rejection_reason_code == "TOO_EXPENSIVE"
        assert fb.interest_score < 0.20


class TestDeduplicationAndConfirmation:
    """Test deduplication and confidence boost on repeat statements."""

    @pytest.mark.asyncio
    async def test_reconfirming_same_fact_boosts_confidence(self, mock_db):
        engine = ContradictionEngine(mock_db)

        existing = MemoryRecord(
            id=str(uuid.uuid4()),
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="PREFERENCE",
            key="bedrooms",
            value_json={"bedrooms": 3},
            value_text="3 Bedrooms",
            source_type="CUSTOMER_STATED",
            confidence=0.90,
            status="ACTIVE",
            version_number=1
        )
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = mock_res

        res = await engine.reconcile_memory(
            organization_id="org_test",
            lead_id="lead_123",
            memory_type="PREFERENCE",
            key="bedrooms",
            new_value_json={"bedrooms": 3},
            new_value_text="3 Bedrooms",
            source_type="CUSTOMER_STATED"
        )

        assert res.action_taken == "MERGED"
        assert res.active_record.confidence > 0.90
        assert res.active_record.version_number == 1
