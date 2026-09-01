"""
Knowledge Freshness Service
==============================
Enforces freshness constraints on retrieved chunks.

A chunk is considered stale if:
  - expires_at has passed (UTC)
  - is_expired flag is True (set by background Beat task)
  - The document's status is EXPIRED or DELETED

A stale chunk is NEVER served to any AI consumer.
Stale facts must not appear in any answer, even internal.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

logger = logging.getLogger(__name__)


class KnowledgeFreshnessService:
    """
    Filters retrieved results to exclude expired/stale knowledge.
    Also provides freshness scoring for the reranker.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def filter_expired(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove expired chunks from results.
        Checks both the is_expired flag and expires_at timestamp.
        """
        now = datetime.now(timezone.utc)
        fresh = []
        expired_count = 0

        for result in results:
            metadata = result.get("metadata", {})

            # Check is_expired flag
            if result.get("is_expired") or metadata.get("is_expired"):
                expired_count += 1
                continue

            # Check expires_at timestamp
            expires_at = metadata.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    try:
                        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        if expires_dt <= now:
                            expired_count += 1
                            continue
                    except Exception:
                        pass  # If parse fails, allow through
                elif isinstance(expires_at, datetime) and expires_at <= now:
                    expired_count += 1
                    continue


            fresh.append(result)

        if expired_count:
            logger.debug(
                f"[FRESHNESS FILTER] removed {expired_count} expired chunks"
            )

        return fresh

    def compute_freshness_days(
        self,
        effective_at: Optional[datetime],
        updated_at: Optional[datetime],
    ) -> int:
        """Compute how many days since the document was last effective/updated."""
        now = datetime.now(timezone.utc)
        reference = effective_at or updated_at
        if not reference:
            return 999  # Unknown age — treated as old
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        delta = now - reference
        return max(0, delta.days)

    async def get_document_freshness_days(
        self,
        organization_id: str,
        document_id: str,
    ) -> Optional[int]:
        """Return the age in days of a document."""
        from app.models.knowledge_models import KnowledgeDocument
        result = await self.db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.organization_id == organization_id,
            )
        )
        doc = result.scalars().first()
        if not doc:
            return None
        return self.compute_freshness_days(doc.effective_at, doc.updated_at)
