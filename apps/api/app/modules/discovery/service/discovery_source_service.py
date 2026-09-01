"""
Part 21.2 — Discovery Source Service
======================================
CRUD and health management for DiscoverySource entities (tenant-isolated).
"""
from __future__ import annotations
import logging
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.discovery_models import DiscoverySource, ProviderStatus
from app.modules.discovery.dto.discovery_dto import (
    DiscoverySourceCreateDTO, DiscoverySourceUpdateDTO
)
from app.modules.discovery.connectors.provider_registry import get_discovery_provider

logger = logging.getLogger(__name__)


class DiscoverySourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_source(
        self, organization_id: str, dto: DiscoverySourceCreateDTO
    ) -> DiscoverySource:
        """Create a new discovery source for an organization."""
        # Initial health check if provider is registered
        provider_impl = get_discovery_provider(dto.provider)
        initial_status = ProviderStatus.CONFIGURATION_REQUIRED
        if provider_impl:
            health = await provider_impl.health_check(dto.configuration)
            initial_status = health.status

        source = DiscoverySource(
            organization_id=organization_id,
            name=dto.name,
            description=dto.description,
            provider=dto.provider.lower(),
            source_type=dto.source_type.upper(),
            status=initial_status,
            configuration=dto.configuration,
            country_code=dto.country_code,
            market_id=dto.market_id,
            rate_limit_per_minute=dto.rate_limit_per_minute or 60,
            daily_limit=dto.daily_limit or 1000,
            monthly_limit=dto.monthly_limit or 25000,
            is_active=True,
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        logger.info(f"[DISCOVERY_SOURCE] Created source '{source.name}' org={organization_id} provider={source.provider}")
        return source

    async def get_source(self, organization_id: str, source_id: str) -> Optional[DiscoverySource]:
        """Get source by ID with tenant isolation."""
        stmt = select(DiscoverySource).where(
            and_(DiscoverySource.id == source_id, DiscoverySource.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_sources(
        self,
        organization_id: str,
        provider: Optional[str] = None,
        source_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[DiscoverySource]:
        """List sources for the organization with filters."""
        conditions = [DiscoverySource.organization_id == organization_id]
        if provider:
            conditions.append(DiscoverySource.provider == provider.lower())
        if source_type:
            conditions.append(DiscoverySource.source_type == source_type.upper())
        if status:
            conditions.append(DiscoverySource.status == status)
        stmt = select(DiscoverySource).where(and_(*conditions)).order_by(DiscoverySource.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def update_source(
        self, organization_id: str, source_id: str, dto: DiscoverySourceUpdateDTO
    ) -> Optional[DiscoverySource]:
        """Update source details."""
        source = await self.get_source(organization_id, source_id)
        if not source:
            return None

        if dto.name is not None:
            source.name = dto.name
        if dto.description is not None:
            source.description = dto.description
        if dto.status is not None:
            source.status = dto.status
        if dto.configuration is not None:
            source.configuration = dto.configuration
            # Re-evaluate health
            provider_impl = get_discovery_provider(source.provider)
            if provider_impl:
                health = await provider_impl.health_check(dto.configuration)
                source.status = health.status
                if health.is_healthy:
                    source.last_success_at = datetime.now(timezone.utc)
                else:
                    source.last_error_at = datetime.now(timezone.utc)
                    source.last_error_message = health.message
        if dto.rate_limit_per_minute is not None:
            source.rate_limit_per_minute = dto.rate_limit_per_minute
        if dto.daily_limit is not None:
            source.daily_limit = dto.daily_limit
        if dto.monthly_limit is not None:
            source.monthly_limit = dto.monthly_limit
        if dto.is_active is not None:
            source.is_active = dto.is_active

        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def check_quota_and_rate_limit(self, source: DiscoverySource) -> tuple[bool, str]:
        """Check if source has remaining daily/monthly quota and rate limits."""
        if not source.is_active or source.status == ProviderStatus.DISABLED:
            return False, "Discovery source is disabled"

        if source.daily_limit and source.usage_today >= source.daily_limit:
            return False, f"Daily discovery limit reached ({source.usage_today}/{source.daily_limit})"

        if source.monthly_limit and source.usage_month >= source.monthly_limit:
            return False, f"Monthly discovery limit reached ({source.usage_month}/{source.monthly_limit})"

        return True, "OK"

    async def increment_usage(self, source: DiscoverySource, count: int = 1) -> None:
        """Increment usage counters and record timestamp."""
        source.usage_today += count
        source.usage_month += count
        source.last_success_at = datetime.now(timezone.utc)
        await self.db.flush()
