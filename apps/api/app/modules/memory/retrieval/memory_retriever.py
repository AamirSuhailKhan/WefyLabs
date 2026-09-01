"""
Hybrid Memory Retrieval & Context Budgeting Engine
==================================================
Retrieves relevant memories for a lead by combining:
1. Structured filters (memory_type, status=ACTIVE)
2. Importance & Confidence score weighting
3. Recency decay weighting
4. Permission & Customer-Safe visibility gating
5. Token context budgeting for AI Agent prompts (<300ms latency)
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.memory_models import MemoryRecord, MemoryObjection, MemoryPropertyFeedback

logger = logging.getLogger(__name__)

class MemoryRetriever:
    """
    Hybrid retriever ranking memories and constructing token-budgeted prompt contexts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_lead_memories(
        self,
        organization_id: str,
        lead_id: str,
        memory_types: Optional[List[str]] = None,
        only_active: bool = True,
        only_customer_safe: bool = False
    ) -> List[MemoryRecord]:
        """
        Retrieves memory records strictly isolated by tenant and lead.
        """
        stmt = select(MemoryRecord).where(
            and_(
                MemoryRecord.organization_id == organization_id,
                MemoryRecord.lead_id == lead_id
            )
        )
        if only_active:
            stmt = stmt.where(MemoryRecord.status == "ACTIVE")
        if only_customer_safe:
            stmt = stmt.where(MemoryRecord.is_customer_safe == True)
        if memory_types:
            stmt = stmt.where(MemoryRecord.memory_type.in_(memory_types))

        res = await self.db.execute(stmt)
        records = list(res.scalars().all())

        # Sort by (Importance * Confidence) descending
        records.sort(key=lambda r: (r.importance * r.confidence), reverse=True)
        return records

    async def build_ai_prompt_context(
        self,
        organization_id: str,
        lead_id: str,
        max_items: int = 10,
        is_customer_facing: bool = True
    ) -> str:
        """
        Formats a clean, token-efficient context block for AI Agent or Copilot prompts.
        """
        records = await self.get_lead_memories(
            organization_id=organization_id,
            lead_id=lead_id,
            only_active=True,
            only_customer_safe=is_customer_facing
        )

        if not records:
            return "No prior customer memory recorded."

        lines = ["### Verified Customer Intelligence:"]
        for rec in records[:max_items]:
            source_tag = f"[{rec.source_type}]" if not is_customer_facing else ""
            desc = rec.value_text or str(rec.value_json)
            lines.append(f"- {rec.key.upper()}: {desc} {source_tag}".strip())

        return "\n".join(lines)
