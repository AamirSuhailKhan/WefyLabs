"""
AI Memory & Customer Intelligence Unified Orchestration Service
===============================================================
Central entry point for:
- Provenance tracking & contradiction-aware memory reconciliation
- Automated fact & constraint extraction
- Hybrid multi-dimensional memory retrieval (<300ms)
- Token context budgeting for AI Agent & Copilot
- Objection & Property feedback lifecycles
- GDPR / Privacy compliance & audit logging
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.memory_models import (
    MemoryRecord, MemoryVersion, MemoryEvidence,
    MemoryObjection, MemoryPropertyFeedback, MemoryAuditLog,
    MemoryDeletionRequest
)
from app.modules.memory.provenance.provenance_tracker import ProvenanceTracker
from app.modules.memory.contradiction.contradiction_engine import ContradictionEngine
from app.modules.memory.extraction.memory_extractor import MemoryExtractor, MemoryCandidateDTO
from app.modules.memory.decay.decay_manager import DecayManager
from app.modules.memory.retrieval.memory_retriever import MemoryRetriever
from app.modules.memory.privacy.privacy_manager import PrivacyManager

logger = logging.getLogger(__name__)

class AIMemoryService:
    """
    Unified AI Memory & Customer Intelligence Service.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.contradiction_engine = ContradictionEngine(db)
        self.decay_manager = DecayManager(db)
        self.retriever = MemoryRetriever(db)
        self.privacy_manager = PrivacyManager(db)

    # ─── Memory Recording & Reconciliation ─────────────────────────────────────

    async def record_memory(
        self,
        organization_id: str,
        lead_id: str,
        memory_type: str,
        key: str,
        value_json: Dict[str, Any],
        value_text: Optional[str] = None,
        source_type: str = "CUSTOMER_STATED",
        source_id: Optional[str] = None,
        confidence: Optional[float] = None,
        importance: float = 0.80,
        is_customer_safe: bool = True,
        actor: str = "system"
    ) -> MemoryRecord:
        """
        Records or supersedes a memory fact with contradiction versioning and audit trail.
        """
        res = await self.contradiction_engine.reconcile_memory(
            organization_id=organization_id,
            lead_id=lead_id,
            memory_type=memory_type,
            key=key,
            new_value_json=value_json,
            new_value_text=value_text,
            source_type=source_type,
            source_id=source_id,
            confidence=confidence,
            importance=importance,
            is_customer_safe=is_customer_safe,
            actor=actor
        )
        return res.active_record

    # ─── Automated Extraction ──────────────────────────────────────────────────

    async def extract_and_store_from_text(
        self,
        organization_id: str,
        lead_id: str,
        text: str,
        source_id: Optional[str] = None,
        is_customer_message: bool = True,
        actor: str = "system"
    ) -> List[MemoryRecord]:
        """
        Extracts structured facts from conversation text and records them.
        """
        candidates: List[MemoryCandidateDTO] = MemoryExtractor.extract_candidates(text, is_customer_message)
        stored_records: List[MemoryRecord] = []

        for cand in candidates:
            rec = await self.record_memory(
                organization_id=organization_id,
                lead_id=lead_id,
                memory_type=cand.memory_type,
                key=cand.key,
                value_json=cand.value_json,
                value_text=cand.value_text,
                source_type=cand.source_type,
                source_id=source_id,
                confidence=cand.confidence,
                importance=cand.importance,
                is_customer_safe=cand.is_customer_safe,
                actor=actor
            )
            stored_records.append(rec)

        return stored_records

    # ─── Retrieval & Context ───────────────────────────────────────────────────

    async def get_lead_memories(
        self,
        organization_id: str,
        lead_id: str,
        memory_types: Optional[List[str]] = None,
        only_active: bool = True,
        only_customer_safe: bool = False
    ) -> List[MemoryRecord]:
        return await self.retriever.get_lead_memories(
            organization_id=organization_id,
            lead_id=lead_id,
            memory_types=memory_types,
            only_active=only_active,
            only_customer_safe=only_customer_safe
        )

    async def get_ai_prompt_context(
        self,
        organization_id: str,
        lead_id: str,
        max_items: int = 10,
        is_customer_facing: bool = True
    ) -> str:
        return await self.retriever.build_ai_prompt_context(
            organization_id=organization_id,
            lead_id=lead_id,
            max_items=max_items,
            is_customer_facing=is_customer_facing
        )

    # ─── Objections & Property Rejections ──────────────────────────────────────

    async def record_objection(
        self,
        organization_id: str,
        lead_id: str,
        category: str,
        description: str,
        status: str = "OPEN"
    ) -> MemoryObjection:
        """Records a customer objection."""
        obj = MemoryObjection(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            category=category.upper(),
            description=description,
            status=status
        )
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def record_property_feedback(
        self,
        organization_id: str,
        lead_id: str,
        property_id: str,
        feedback_type: str,
        rejection_reason_code: Optional[str] = None,
        notes: Optional[str] = None
    ) -> MemoryPropertyFeedback:
        """Records property view or rejection with structured reasons."""
        fb = MemoryPropertyFeedback(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            lead_id=lead_id,
            property_id=property_id,
            feedback_type=feedback_type.upper(),
            rejection_reason_code=rejection_reason_code,
            feedback_notes=notes,
            interest_score=0.10 if feedback_type.upper() == "REJECTED" else 0.85
        )
        self.db.add(fb)
        await self.db.commit()
        await self.db.refresh(fb)
        return fb

    # ─── Decay & Privacy Deletion ──────────────────────────────────────────────

    async def evaluate_memory_decay(self, organization_id: Optional[str] = None) -> List[MemoryRecord]:
        return await self.decay_manager.evaluate_stale_memories(organization_id)

    async def execute_lead_deletion(self, organization_id: str, lead_id: str, requested_by: str) -> MemoryDeletionRequest:
        return await self.privacy_manager.execute_lead_deletion_request(organization_id, lead_id, requested_by)
