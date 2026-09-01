"""
Part 21.2 — Discovery Evidence & Signal Service
================================================
Preserves immutable factual evidence records and extracts structured intent signals.

Rule: LLM responses alone are NEVER evidence. Only concrete provider records qualify.
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.discovery_models import DiscoveryEvidence, DiscoverySignal

logger = logging.getLogger(__name__)


class EvidenceSignalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_evidence(
        self,
        organization_id: str,
        candidate_id: str,
        source_id: Optional[str],
        field_name: str,
        value_reference: str,
        source_timestamp: Optional[datetime] = None,
        confidence: float = 1.0,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> DiscoveryEvidence:
        """Record concrete factual evidence linking candidate to source."""
        evidence = DiscoveryEvidence(
            organization_id=organization_id,
            candidate_id=candidate_id,
            source_id=source_id,
            field_name=field_name,
            value_reference=str(value_reference),
            source_timestamp=source_timestamp,
            retrieved_at=datetime.now(timezone.utc),
            confidence=confidence,
            provenance=provenance,
        )
        self.db.add(evidence)
        await self.db.flush()
        return evidence

    async def record_signal(
        self,
        organization_id: str,
        candidate_id: str,
        signal_type: str,
        source: str,
        observed_at: datetime,
        strength: float = 1.0,
        confidence: float = 1.0,
        evidence_id: Optional[str] = None,
        signal_payload: Optional[Dict[str, Any]] = None,
    ) -> DiscoverySignal:
        """Record a structured buying/selling signal."""
        signal = DiscoverySignal(
            organization_id=organization_id,
            candidate_id=candidate_id,
            evidence_id=evidence_id,
            signal_type=signal_type,
            source=source,
            observed_at=observed_at,
            strength=strength,
            confidence=confidence,
            signal_payload=signal_payload,
        )
        self.db.add(signal)
        await self.db.flush()
        return signal

    async def get_candidate_evidence(
        self, organization_id: str, candidate_id: str
    ) -> List[DiscoveryEvidence]:
        """Get all evidence records for a candidate (tenant-isolated)."""
        stmt = select(DiscoveryEvidence).where(
            and_(
                DiscoveryEvidence.candidate_id == candidate_id,
                DiscoveryEvidence.organization_id == organization_id,
            )
        ).order_by(DiscoveryEvidence.created_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_candidate_signals(
        self, organization_id: str, candidate_id: str
    ) -> List[DiscoverySignal]:
        """Get all signals for a candidate (tenant-isolated)."""
        stmt = select(DiscoverySignal).where(
            and_(
                DiscoverySignal.candidate_id == candidate_id,
                DiscoverySignal.organization_id == organization_id,
            )
        ).order_by(DiscoverySignal.observed_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())
