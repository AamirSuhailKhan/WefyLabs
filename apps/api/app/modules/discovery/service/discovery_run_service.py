"""
Part 21.2 — Discovery Run Service
===================================
Orchestration and state tracking for campaign execution runs.
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.discovery_models import DiscoveryRun, DiscoveryRunStatus, DiscoveryCampaign
from app.modules.discovery.dto.discovery_dto import DiscoveryRunCreateDTO

logger = logging.getLogger(__name__)


class DiscoveryRunService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_run(
        self, organization_id: str, campaign: DiscoveryCampaign, dto: Optional[DiscoveryRunCreateDTO] = None
    ) -> DiscoveryRun:
        """Create a new discovery run for a campaign."""
        run = DiscoveryRun(
            organization_id=organization_id,
            campaign_id=campaign.id,
            status=DiscoveryRunStatus.QUEUED,
            started_at=datetime.now(timezone.utc),
            cursor_position=dto.cursor if dto else None,
            run_metadata=dto.run_metadata if dto else None,
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        logger.info(f"[DISCOVERY_RUN] Created run {run.id} for campaign={campaign.id} org={organization_id}")
        return run

    async def get_run(self, organization_id: str, run_id: str) -> Optional[DiscoveryRun]:
        """Get run by ID with tenant isolation."""
        stmt = select(DiscoveryRun).where(
            and_(DiscoveryRun.id == run_id, DiscoveryRun.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_runs(
        self,
        organization_id: str,
        campaign_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DiscoveryRun]:
        """List runs for an organization."""
        conditions = [DiscoveryRun.organization_id == organization_id]
        if campaign_id:
            conditions.append(DiscoveryRun.campaign_id == campaign_id)
        if status:
            conditions.append(DiscoveryRun.status == status)
        stmt = (
            select(DiscoveryRun)
            .where(and_(*conditions))
            .order_by(DiscoveryRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def mark_running(self, run: DiscoveryRun) -> None:
        run.status = DiscoveryRunStatus.RUNNING
        if not run.started_at:
            run.started_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def update_counters(
        self,
        run: DiscoveryRun,
        scanned: int = 0,
        found: int = 0,
        rejected: int = 0,
        duplicates: int = 0,
        new_prospects: int = 0,
        errors: Optional[List[str]] = None,
        next_cursor: Optional[str] = None,
    ) -> None:
        run.records_scanned += scanned
        run.candidates_found += found
        run.candidates_rejected += rejected
        run.duplicates_found += duplicates
        run.new_prospects += new_prospects
        if next_cursor:
            run.cursor_position = next_cursor
        if errors:
            current_errors = list(run.errors or [])
            current_errors.extend(errors)
            run.errors = current_errors
        await self.db.flush()

    async def complete_run(self, run: DiscoveryRun) -> None:
        run.status = DiscoveryRunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(run)

    async def fail_run(self, run: DiscoveryRun, error_message: str) -> None:
        run.status = DiscoveryRunStatus.FAILED
        run.completed_at = datetime.now(timezone.utc)
        current_errors = list(run.errors or [])
        current_errors.append(error_message)
        run.errors = current_errors
        await self.db.commit()
        await self.db.refresh(run)
