"""
Knowledge Permission Service
==============================
Enforces multi-layer permission checks on retrieved knowledge chunks.

Layers (in order):
  1. Tenant isolation  — organization_id must match
  2. Visibility level  — PUBLIC | INTERNAL | MANAGER_ONLY | ADMIN_ONLY | CUSTOMER
  3. AI allowed        — ai_allowed flag on chunk
  4. Customer-facing   — customer_facing_allowed when channel=customer_facing
  5. Role-based        — caller's RBAC role must satisfy minimum requirement

CRITICAL: Permission is enforced HERE, not just in the LLM prompt.
A chunk that fails any layer is silently excluded from results.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Role hierarchy (higher = more access)
_ROLE_HIERARCHY = {
    "CUSTOMER": 0,
    "AGENT": 1,
    "BROKER": 1,
    "MANAGER": 2,
    "ADMIN": 3,
    "SUPER_ADMIN": 4,
}

# Minimum role required per visibility level
_VISIBILITY_MIN_ROLE = {
    "PUBLIC": 0,
    "CUSTOMER": 0,
    "INTERNAL": 1,      # AGENT or higher
    "MANAGER_ONLY": 2,  # MANAGER or higher
    "ADMIN_ONLY": 3,    # ADMIN or higher
}


class KnowledgePermissionService:
    """
    Filters knowledge results based on permission rules.
    Every rule is checked. Fails silently — never reveals why a chunk was excluded.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def filter_results(
        self,
        results: List[Dict[str, Any]],
        organization_id: str,
        channel: str = "internal",
        role: str = "INTERNAL",
    ) -> List[Dict[str, Any]]:
        """
        Filter results by permission rules.
        Returns only the results the caller is allowed to see.
        """
        is_customer_facing = channel in ("customer_facing", "whatsapp", "telegram", "website")
        caller_rank = _ROLE_HIERARCHY.get(role.upper(), 1)

        allowed = []
        denied = 0

        for result in results:
            metadata = result.get("metadata", {})

            # ── Layer 1: Tenant isolation ─────────────────────────────────────
            result_org = result.get("organization_id") or metadata.get("organization_id")
            if result_org and result_org != organization_id:
                denied += 1
                continue

            # ── Layer 2: AI allowed ───────────────────────────────────────────
            if not metadata.get("ai_allowed", True):
                denied += 1
                continue

            # ── Layer 3: Customer-facing channel check ────────────────────────
            if is_customer_facing and not metadata.get("customer_facing_allowed", False):
                denied += 1
                continue

            # ── Layer 4: Visibility check ─────────────────────────────────────
            visibility = metadata.get("visibility", "INTERNAL")
            min_rank = _VISIBILITY_MIN_ROLE.get(visibility, 1)
            if caller_rank < min_rank:
                denied += 1
                continue

            allowed.append(result)

        if denied:
            logger.debug(
                f"[PERMISSION FILTER] org={organization_id} channel={channel} "
                f"allowed={len(allowed)} denied={denied}"
            )

        return allowed

    async def check_document_access(
        self,
        organization_id: str,
        document_id: str,
        user_id: str,
        role: str,
        action: str = "read",
    ) -> bool:
        """
        Check if a user has access to a specific document.
        Used by admin API endpoints before returning document details.
        """
        from sqlalchemy import select
        from app.models.knowledge_models import KnowledgeDocument

        result = await self.db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.organization_id == organization_id,
            )
        )
        doc = result.scalars().first()
        if not doc:
            return False

        caller_rank = _ROLE_HIERARCHY.get(role.upper(), 0)
        visibility = doc.visibility or "INTERNAL"
        min_rank = _VISIBILITY_MIN_ROLE.get(visibility, 1)

        return caller_rank >= min_rank
