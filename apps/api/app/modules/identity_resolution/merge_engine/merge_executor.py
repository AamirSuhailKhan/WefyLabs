"""
Merge Executor — Executes identity merges (auto or manual).
Handles field-level conflict resolution, IdentityLink migration, alias aggregation.
Produces MergeOperation record with full pre-merge snapshot for undo.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.identity_models import (
    Identity, IdentityLink, IdentityAlias,
    IdentityConflict, MergeOperation, MergeHistory
)

logger = logging.getLogger(__name__)

# Fields that can be merged (copied from source to target if target is empty)
MERGEABLE_FIELDS = [
    "primary_email", "primary_phone_e164", "primary_name",
    "primary_whatsapp", "primary_telegram",
    "location_profile", "financial_profile", "intent_profile",
]


class MergeExecutor:
    """
    Executes identity merge operations.

    Merge Strategy:
    - Target identity is the "winner" (kept active)
    - Source identity is marked merged (is_merged=True, merged_into_id=target.id)
    - All source IdentityLinks are migrated to target
    - All source IdentityAliases are migrated to target
    - Field conflicts are detected and stored (never silently overwritten)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_merge(
        self,
        source_identity_id: str,
        target_identity_id: str,
        organization_id: str,
        merge_confidence: float,
        merge_type: str = "auto",
        actor_id: Optional[str] = None,
        fields_to_merge: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a full identity merge.

        Returns:
            {
                "merge_operation_id": "...",
                "status": "completed",
                "conflicts_detected": 2,
                "fields_merged": [...],
            }
        """
        # ── Load both identities ──────────────────────────────────────────────
        source = await self._get_identity(source_identity_id)
        target = await self._get_identity(target_identity_id)

        if not source or not target:
            raise ValueError(f"Identity not found: source={source_identity_id} target={target_identity_id}")

        if source.is_merged:
            raise ValueError(f"Source identity {source_identity_id} is already merged.")

        # ── Snapshot pre-merge state ──────────────────────────────────────────
        source_snapshot = self._snapshot_identity(source)
        target_snapshot = self._snapshot_identity(target)
        source_links = await self._get_identity_links(source_identity_id)
        source_links_snapshot = [
            {"id": l.id, "lead_id": l.lead_id, "source": l.source, "link_method": l.link_method}
            for l in source_links
        ]

        # ── Create MergeOperation ─────────────────────────────────────────────
        merge_op = MergeOperation(
            organization_id=organization_id,
            source_identity_id=source_identity_id,
            target_identity_id=target_identity_id,
            source_snapshot=source_snapshot,
            target_snapshot=target_snapshot,
            source_links_snapshot=source_links_snapshot,
            merge_type=merge_type,
            merge_confidence=merge_confidence,
            actor_id=actor_id,
            status="completed",
        )
        self.db.add(merge_op)
        await self.db.flush()  # Get merge_op.id

        # ── Detect and record field conflicts ─────────────────────────────────
        conflicts, merged_fields = await self._resolve_fields(
            source, target, merge_op.id, organization_id, fields_to_merge
        )
        merge_op.conflicts_detected = len(conflicts)
        merge_op.fields_merged = merged_fields

        # ── Migrate IdentityLinks from source → target ────────────────────────
        for link in source_links:
            link.identity_id = target_identity_id
            link.is_primary = False
            link.link_method = "merge_migrated"

        # ── Migrate IdentityAliases from source → target ──────────────────────
        await self._migrate_aliases(source_identity_id, target_identity_id)

        # ── Mark source as merged ─────────────────────────────────────────────
        source.is_merged = True
        source.merged_into_id = target_identity_id

        # ── Update target lead_count ──────────────────────────────────────────
        target.lead_count = (target.lead_count or 0) + (source.lead_count or 0)
        target.updated_at = datetime.now(timezone.utc)

        # ── Write MergeHistory entry ──────────────────────────────────────────
        self.db.add(MergeHistory(
            merge_operation_id=merge_op.id,
            organization_id=organization_id,
            action="merge_completed",
            actor_id=actor_id,
            actor_type="user" if actor_id else "system",
            details={
                "source": source_identity_id,
                "target": target_identity_id,
                "confidence": merge_confidence,
                "fields_merged": merged_fields,
                "conflicts": len(conflicts),
            },
        ))

        await self.db.commit()
        logger.info(
            f"[MERGE_EXECUTOR] Merged {source_identity_id} → {target_identity_id} "
            f"(confidence={merge_confidence:.2%}, conflicts={len(conflicts)})"
        )

        return {
            "merge_operation_id": merge_op.id,
            "status": "completed",
            "conflicts_detected": len(conflicts),
            "fields_merged": merged_fields,
            "source_identity_id": source_identity_id,
            "target_identity_id": target_identity_id,
        }

    async def _resolve_fields(
        self,
        source: Identity,
        target: Identity,
        merge_op_id: str,
        organization_id: str,
        fields_to_merge: Optional[List[str]],
    ) -> tuple:
        """Merge fields from source to target. Record conflicts. Return (conflicts, merged_fields)."""
        fields = fields_to_merge or MERGEABLE_FIELDS
        conflicts = []
        merged_fields = []

        for field in fields:
            source_val = getattr(source, field, None)
            target_val = getattr(target, field, None)

            # If target has no value, copy from source
            if not target_val and source_val:
                setattr(target, field, source_val)
                merged_fields.append(field)

            # If both have values and they differ — record conflict, don't overwrite
            elif source_val and target_val and source_val != target_val:
                conflict = IdentityConflict(
                    identity_id=target.id,
                    merge_operation_id=merge_op_id,
                    organization_id=organization_id,
                    field_name=field,
                    original_value=str(target_val) if target_val else None,
                    incoming_value=str(source_val) if source_val else None,
                    winner_value=str(target_val) if target_val else None,
                    winner_source="original",
                    resolution_reason="Target value preserved; incoming value recorded as conflict.",
                    status="pending",
                )
                self.db.add(conflict)
                conflicts.append(field)

        return conflicts, merged_fields

    async def _migrate_aliases(self, source_id: str, target_id: str):
        """Move all aliases from source identity to target identity."""
        stmt = select(IdentityAlias).where(IdentityAlias.identity_id == source_id)
        result = await self.db.execute(stmt)
        for alias in result.scalars().all():
            alias.identity_id = target_id

    async def _get_identity(self, identity_id: str) -> Optional[Identity]:
        result = await self.db.execute(select(Identity).where(Identity.id == identity_id))
        return result.scalar_one_or_none()

    async def _get_identity_links(self, identity_id: str) -> List[IdentityLink]:
        result = await self.db.execute(
            select(IdentityLink).where(IdentityLink.identity_id == identity_id, IdentityLink.is_active == True)
        )
        return result.scalars().all()

    @staticmethod
    def _snapshot_identity(identity: Identity) -> Dict[str, Any]:
        return {
            "id": identity.id,
            "primary_email": identity.primary_email,
            "primary_phone_e164": identity.primary_phone_e164,
            "primary_name": identity.primary_name,
            "primary_whatsapp": identity.primary_whatsapp,
            "primary_telegram": identity.primary_telegram,
            "location_profile": identity.location_profile,
            "financial_profile": identity.financial_profile,
            "intent_profile": identity.intent_profile,
            "health_score": identity.health_score,
            "lead_count": identity.lead_count,
            "is_merged": identity.is_merged,
            "merged_into_id": identity.merged_into_id,
        }
