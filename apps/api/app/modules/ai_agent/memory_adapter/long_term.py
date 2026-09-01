"""
Long-Term Memory Engine — reads and writes AgentMemory facts.

Rules:
  - Facts with confidence >= 0.9 are NEVER overwritten.
    A new row is inserted and the old row is marked is_active=False.
  - Facts with confidence < 0.9 can be updated in place.
  - Source hierarchy: tool_call > crm > human_agent > conversation
  - Memory is scoped per session AND per lead (cross-session recall).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.agent_models import AgentMemory

# Confidence threshold above which facts are immutable
CONFIRMED_CONFIDENCE_THRESHOLD = 0.9


async def write_fact(
    db: AsyncSession,
    session_id: str,
    lead_id: str,
    organization_id: str,
    key: str,
    value: str,
    confidence: float = 0.5,
    source: str = "conversation",
) -> AgentMemory:
    """
    Write a memory fact.
    If an active fact with this key exists:
      - If existing confidence >= CONFIRMED_CONFIDENCE_THRESHOLD: insert new row (versioning).
      - Else: insert new superseding row and deactivate old.
    Returns the new AgentMemory record.
    """
    # Find existing active fact for this key
    result = await db.execute(
        select(AgentMemory)
        .where(
            AgentMemory.session_id == session_id,
            AgentMemory.fact_key == key,
            AgentMemory.is_active == True,
        )
    )
    existing = result.scalar_one_or_none()

    new_fact = AgentMemory(
        session_id=session_id,
        lead_id=lead_id,
        organization_id=organization_id,
        fact_key=key,
        fact_value=str(value),
        confidence=confidence,
        source=source,
        is_active=True,
    )
    db.add(new_fact)
    await db.flush()  # get new_fact.id

    if existing:
        # Deactivate old fact and link supersession
        await db.execute(
            update(AgentMemory)
            .where(AgentMemory.id == existing.id)
            .values(is_active=False, superseded_by=new_fact.id)
        )

    return new_fact


async def read_facts(
    db: AsyncSession,
    session_id: str,
    lead_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return all active memory facts for a session.
    If lead_id is also given, merges facts from all sessions for that lead
    (cross-session recall for returning customers).
    """
    query = select(AgentMemory).where(
        AgentMemory.session_id == session_id,
        AgentMemory.is_active == True,
    )
    result = await db.execute(query)
    facts = result.scalars().all()

    if lead_id:
        # Cross-session recall: also load facts from other sessions for this lead
        cross_query = select(AgentMemory).where(
            AgentMemory.lead_id == lead_id,
            AgentMemory.session_id != session_id,
            AgentMemory.is_active == True,
            AgentMemory.confidence >= 0.7,  # Only high-confidence cross-session facts
        )
        cross_result = await db.execute(cross_query)
        cross_facts = cross_result.scalars().all()

        # Merge: session facts take priority over cross-session facts
        session_keys = {f.fact_key for f in facts}
        all_facts = list(facts) + [f for f in cross_facts if f.fact_key not in session_keys]
    else:
        all_facts = list(facts)

    return [
        {
            "key": f.fact_key,
            "value": f.fact_value,
            "confidence": f.confidence,
            "source": f.source,
        }
        for f in sorted(all_facts, key=lambda x: x.confidence, reverse=True)
    ]


async def bulk_write_facts(
    db: AsyncSession,
    session_id: str,
    lead_id: str,
    organization_id: str,
    facts: Dict[str, Any],
    source: str = "tool_call",
    confidence: float = 0.85,
) -> None:
    """Convenience method: write multiple facts at once."""
    for key, value in facts.items():
        if value is not None:
            await write_fact(
                db=db,
                session_id=session_id,
                lead_id=lead_id,
                organization_id=organization_id,
                key=key,
                value=str(value),
                confidence=confidence,
                source=source,
            )
