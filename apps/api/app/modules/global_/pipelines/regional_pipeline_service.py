"""
RegionalPipelineService — Market-Configurable Pipeline Stage Engine
====================================================================
Replaces hardcoded pipeline stage enums with DB-driven configurable pipelines.

Example:
  India: New → Qualified → Site Visit → Negotiation → Booked → Won
  UAE:   New → Qualified → Viewing → Offer → Reservation → Closed → Won

Rules:
  - Stage transitions validated against allowed_next_stages
  - Hardcoded stage checks (e.g. `if stage == "Site Visit"`) are PROHIBITED
  - Terminal stages cannot transition further
  - Won/Lost are always terminal
  - Pipelines are versioned — historical records retain original stage
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


@dataclass
class PipelineStageInfo:
    stage_key: str
    label: str
    sort_order: int
    is_terminal: bool
    is_won: bool
    allowed_next_stages: List[str]
    pipeline_id: str


@dataclass
class StageTransitionResult:
    success: bool
    from_stage: str
    to_stage: str
    message: str
    blocked_reason: Optional[str] = None


class RegionalPipelineService:
    """
    Manages pipeline stage lookups and transition validations per market.

    Usage:
        service = RegionalPipelineService(db)
        stages = await service.get_pipeline_stages(market_id="dubai", org_id="org-1")
        result = await service.validate_transition("new", "viewing", market_id="dubai", org_id="org-1")
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._stage_cache: Dict[str, List[PipelineStageInfo]] = {}

    async def get_default_pipeline(
        self,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """Return the default pipeline ID for a market/org."""
        from app.models.global_models import RegionalPipeline
        conditions = [RegionalPipeline.is_default == True, RegionalPipeline.is_active == True]
        if organization_id:
            conditions.append(RegionalPipeline.organization_id == organization_id)
        if market_id:
            conditions.append(RegionalPipeline.market_id == market_id)

        stmt = select(RegionalPipeline).where(and_(*conditions)).limit(1)
        result = await self._db.execute(stmt)
        pipeline = result.scalar_one_or_none()
        return str(pipeline.id) if pipeline else None

    async def get_pipeline_stages(
        self,
        pipeline_id: Optional[str] = None,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> List[PipelineStageInfo]:
        """
        Return all stages for a pipeline, ordered by sort_order.
        Falls back to default pipeline for market/org if pipeline_id not given.
        """
        if not pipeline_id:
            pipeline_id = await self.get_default_pipeline(market_id, organization_id)

        if not pipeline_id:
            logger.warning(f"[PipelineService] No pipeline found for market={market_id} org={organization_id}. Returning empty.")
            return []

        # Check cache
        if pipeline_id in self._stage_cache:
            return self._stage_cache[pipeline_id]

        from app.models.global_models import RegionalPipelineStage
        stmt = (
            select(RegionalPipelineStage)
            .where(RegionalPipelineStage.pipeline_id == pipeline_id)
            .order_by(RegionalPipelineStage.sort_order)
        )
        result = await self._db.execute(stmt)
        rows = result.scalars().all()

        stages = [
            PipelineStageInfo(
                stage_key=row.stage_key,
                label=row.label,
                sort_order=row.sort_order,
                is_terminal=row.is_terminal,
                is_won=row.is_won,
                allowed_next_stages=row.allowed_next_stages or [],
                pipeline_id=str(row.pipeline_id),
            )
            for row in rows
        ]

        self._stage_cache[pipeline_id] = stages
        return stages

    async def validate_transition(
        self,
        from_stage_key: str,
        to_stage_key: str,
        pipeline_id: Optional[str] = None,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> StageTransitionResult:
        """
        Validate whether a stage transition is permitted.

        Enforcement rules:
        - Same stage transition is always valid (no-op)
        - Terminal stages cannot transition to anything
        - Only allowed_next_stages transitions are permitted
        - Both stages must exist in the pipeline
        """
        # Same stage — no-op is always valid
        if from_stage_key == to_stage_key:
            return StageTransitionResult(
                success=True,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message="Same stage — no-op.",
            )

        stages = await self.get_pipeline_stages(pipeline_id, market_id, organization_id)

        if not stages:
            # No pipeline configured — permissive fallback (log warning)
            logger.warning(f"[PipelineService] No stages configured — transition {from_stage_key}→{to_stage_key} not validated.")
            return StageTransitionResult(
                success=True,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message="No pipeline configured — transition permitted (unvalidated).",
            )

        stage_map: Dict[str, PipelineStageInfo] = {s.stage_key: s for s in stages}

        # Same stage — no-op is always valid
        if from_stage_key == to_stage_key:
            return StageTransitionResult(
                success=True,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message="Same stage — no-op.",
            )

        # from_stage must exist
        from_stage = stage_map.get(from_stage_key)
        if not from_stage:
            return StageTransitionResult(
                success=False,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message=f"Stage '{from_stage_key}' not found in pipeline.",
                blocked_reason="INVALID_FROM_STAGE",
            )

        # to_stage must exist
        if to_stage_key not in stage_map:
            return StageTransitionResult(
                success=False,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message=f"Stage '{to_stage_key}' not found in pipeline.",
                blocked_reason="INVALID_TO_STAGE",
            )

        # Terminal stage cannot go anywhere
        if from_stage.is_terminal:
            return StageTransitionResult(
                success=False,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message=f"Stage '{from_stage_key}' is terminal — cannot transition.",
                blocked_reason="TERMINAL_STAGE",
            )

        # Check allowed next stages
        if from_stage.allowed_next_stages and to_stage_key not in from_stage.allowed_next_stages:
            return StageTransitionResult(
                success=False,
                from_stage=from_stage_key,
                to_stage=to_stage_key,
                message=f"Transition '{from_stage_key}' → '{to_stage_key}' not allowed. Allowed: {from_stage.allowed_next_stages}",
                blocked_reason="TRANSITION_NOT_ALLOWED",
            )

        return StageTransitionResult(
            success=True,
            from_stage=from_stage_key,
            to_stage=to_stage_key,
            message="Transition permitted.",
        )

    async def get_stage_info(
        self,
        stage_key: str,
        pipeline_id: Optional[str] = None,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[PipelineStageInfo]:
        """Get metadata for a specific stage."""
        stages = await self.get_pipeline_stages(pipeline_id, market_id, organization_id)
        return next((s for s in stages if s.stage_key == stage_key), None)

    async def get_initial_stage(
        self,
        pipeline_id: Optional[str] = None,
        market_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Optional[str]:
        """Return the first (lowest sort_order) stage key for a pipeline."""
        stages = await self.get_pipeline_stages(pipeline_id, market_id, organization_id)
        return stages[0].stage_key if stages else None

    async def seed_default_pipelines(self):
        """
        Seed built-in market pipelines for India and UAE.
        Called during market activation.
        """
        from app.models.global_models import RegionalPipeline, RegionalPipelineStage, Market
        from sqlalchemy import select as sa_select

        india_stages = [
            {"stage_key": "new",          "label": "New",          "sort_order": 0, "is_terminal": False, "is_won": False, "allowed_next_stages": ["qualified", "disqualified"]},
            {"stage_key": "qualified",    "label": "Qualified",    "sort_order": 1, "is_terminal": False, "is_won": False, "allowed_next_stages": ["site_visit", "disqualified"]},
            {"stage_key": "site_visit",   "label": "Site Visit",   "sort_order": 2, "is_terminal": False, "is_won": False, "allowed_next_stages": ["negotiation", "disqualified"]},
            {"stage_key": "negotiation",  "label": "Negotiation",  "sort_order": 3, "is_terminal": False, "is_won": False, "allowed_next_stages": ["booked", "disqualified"]},
            {"stage_key": "booked",       "label": "Booked",       "sort_order": 4, "is_terminal": False, "is_won": False, "allowed_next_stages": ["won", "lost"]},
            {"stage_key": "won",          "label": "Won",          "sort_order": 5, "is_terminal": True,  "is_won": True,  "allowed_next_stages": []},
            {"stage_key": "lost",         "label": "Lost",         "sort_order": 6, "is_terminal": True,  "is_won": False, "allowed_next_stages": []},
            {"stage_key": "disqualified", "label": "Disqualified", "sort_order": 7, "is_terminal": True,  "is_won": False, "allowed_next_stages": []},
        ]

        uae_stages = [
            {"stage_key": "new",         "label": "New",         "sort_order": 0, "is_terminal": False, "is_won": False, "allowed_next_stages": ["qualified", "disqualified"]},
            {"stage_key": "qualified",   "label": "Qualified",   "sort_order": 1, "is_terminal": False, "is_won": False, "allowed_next_stages": ["viewing", "disqualified"]},
            {"stage_key": "viewing",     "label": "Viewing",     "sort_order": 2, "is_terminal": False, "is_won": False, "allowed_next_stages": ["offer", "disqualified"]},
            {"stage_key": "offer",       "label": "Offer",       "sort_order": 3, "is_terminal": False, "is_won": False, "allowed_next_stages": ["reservation", "disqualified"]},
            {"stage_key": "reservation", "label": "Reservation", "sort_order": 4, "is_terminal": False, "is_won": False, "allowed_next_stages": ["closed", "lost"]},
            {"stage_key": "closed",      "label": "Closed",      "sort_order": 5, "is_terminal": True,  "is_won": True,  "allowed_next_stages": []},
            {"stage_key": "lost",        "label": "Lost",        "sort_order": 6, "is_terminal": True,  "is_won": False, "allowed_next_stages": []},
            {"stage_key": "disqualified","label": "Disqualified","sort_order": 7, "is_terminal": True,  "is_won": False, "allowed_next_stages": []},
        ]

        market_pipeline_map = [
            ("IN", "India Residential", "india-residential", india_stages),
            ("AE", "Dubai Freehold", "dubai-freehold", uae_stages),
        ]

        for country_iso, pipeline_name, slug, stage_defs in market_pipeline_map:
            # Find the first active market for this country
            market_stmt = (
                sa_select(Market)
                .join(sa_select(Market).where(Market.is_enabled == True))
                .limit(1)
            )
            # Skip seeding if market not found (will be seeded after market activation)
            pipeline = RegionalPipeline(
                name=pipeline_name,
                slug=slug,
                is_default=True,
                is_active=True,
            )
            self._db.add(pipeline)
            await self._db.flush()

            for sd in stage_defs:
                self._db.add(RegionalPipelineStage(
                    pipeline_id=pipeline.id,
                    **sd,
                ))

        await self._db.flush()
        logger.info("[PipelineService] Default India + UAE pipelines seeded.")
