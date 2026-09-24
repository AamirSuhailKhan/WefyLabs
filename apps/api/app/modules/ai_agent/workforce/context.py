"""
WefyLabs AI Workforce — Context Builder
Part 10 Shared Context & Bounded Memory Integration
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.agent_models import AgentSession, QualificationProfile, AgentMemory
from app.modules.ai_agent.workforce.enums import WorkforceRole
from app.modules.ai_agent.workforce.registry import get_agent_definition
from app.modules.ai_agent.workforce.policy import WorkforcePolicyEngine

logger = logging.getLogger("wefylabs.workforce.context")


class WorkforceContextBuilder:
    """
    Constructs bounded, role-specific, task-relevant context for specialist agents.
    Every agent gets only what its role requires within its configured token budget.
    """

    @classmethod
    async def build_context(
        cls,
        db: AsyncSession,
        role: WorkforceRole,
        organization_id: str,
        lead_id: str,
        session_id: Optional[str] = None,
        customer_message: Optional[str] = None,
        supplementary_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assemble bounded context slice according to agent definition."""
        defn = get_agent_definition(role)
        WorkforcePolicyEngine.validate_tenant_boundary(organization_id, organization_id)

        # 1. Base identity & session metadata
        ctx: Dict[str, Any] = {
            "role": role.value,
            "agent_name": defn.name,
            "organization_id": organization_id,
            "lead_id": lead_id,
            "session_id": session_id,
            "token_budget": defn.token_budget,
            "prompt_version": defn.prompt_version,
            "allowed_tools": defn.allowed_tools,
        }

        # 2. Add customer message (sanitized)
        if customer_message:
            sanitized, detected = WorkforcePolicyEngine.sanitize_untrusted_input(customer_message)
            ctx["customer_message"] = sanitized
            ctx["injection_attempt_detected"] = detected

        # 3. Pull Shared Memory (AIMemory / AgentMemory) with conflict resolution
        if "memory_facts" in defn.allowed_context or "lead_profile" in defn.allowed_context:
            memory_facts = await cls._load_resolved_memory(db, organization_id, lead_id)
            ctx["memory_facts"] = memory_facts

        # 4. Pull Qualification Profile if allowed
        if "qualification" in defn.allowed_context and session_id:
            qual_stmt = select(QualificationProfile).where(
                and_(
                    QualificationProfile.session_id == session_id,
                    QualificationProfile.organization_id == organization_id,
                )
            )
            qual_res = await db.execute(qual_stmt)
            qp = qual_res.scalar_one_or_none()
            if qp:
                ctx["qualification"] = {
                    "budget_min": qp.budget_min,
                    "budget_max": qp.budget_max,
                    "budget_currency": qp.budget_currency,
                    "bedrooms": qp.bedrooms,
                    "bathrooms": qp.bathrooms,
                    "property_type": qp.property_type,
                    "preferred_locations": qp.preferred_locations,
                    "purpose": qp.purpose,
                    "timeline": qp.timeline,
                    "is_qualified": qp.is_qualified,
                    "completion_pct": qp.completion_pct,
                }
            else:
                ctx["qualification"] = {}

        # 5. Attach supplementary domain data (e.g. properties, matches, calendar slots, revenue context)
        if supplementary_data:
            for k, v in supplementary_data.items():
                if k in defn.allowed_context or k in ("confirmed_action", "property_ids", "visit_details"):
                    ctx[k] = v

        return ctx

    @classmethod
    async def _load_resolved_memory(
        cls,
        db: AsyncSession,
        organization_id: str,
        lead_id: str,
    ) -> Dict[str, Any]:
        """
        Loads active memory facts for the customer.
        Conflict resolution rule: EXPLICIT CUSTOMER STATED > INFERRED SPECULATION.
        """
        stmt = select(AgentMemory).where(
            and_(
                AgentMemory.organization_id == organization_id,
                AgentMemory.lead_id == lead_id,
                AgentMemory.is_active == True,
            )
        )
        res = await db.execute(stmt)
        facts = res.scalars().all()

        resolved: Dict[str, Dict[str, Any]] = {}
        for f in facts:
            key = f.fact_key
            current = resolved.get(key)
            # Explicit customer facts take precedence over inferences
            is_explicit = f.source in ("customer_stated", "conversation", "user_explicit")
            confidence = f.confidence or 0.5

            if current is None:
                resolved[key] = {
                    "value": f.fact_value,
                    "source": f.source,
                    "confidence": confidence,
                    "is_explicit": is_explicit,
                }
            else:
                # If existing is inferred and new is explicit, explicit replaces inferred
                if not current["is_explicit"] and is_explicit:
                    resolved[key] = {
                        "value": f.fact_value,
                        "source": f.source,
                        "confidence": confidence,
                        "is_explicit": True,
                    }
                elif current["is_explicit"] and not is_explicit:
                    # Keep explicit; ignore speculative inference
                    pass
                elif confidence > current["confidence"]:
                    resolved[key] = {
                        "value": f.fact_value,
                        "source": f.source,
                        "confidence": confidence,
                        "is_explicit": is_explicit,
                    }

        return {k: v["value"] for k, v in resolved.items()}
