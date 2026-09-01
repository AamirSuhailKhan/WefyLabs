"""
Part 21.2 — Discovery Campaign Service
========================================
Management of AI discovery campaigns with multi-country criteria and property matching.
"""
from __future__ import annotations
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.discovery_models import DiscoveryCampaign, DiscoveryCampaignStatus
from app.modules.discovery.dto.discovery_dto import (
    DiscoveryCampaignCreateDTO, DiscoveryCampaignUpdateDTO
)

logger = logging.getLogger(__name__)


class DiscoveryCampaignService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_campaign(
        self, organization_id: str, dto: DiscoveryCampaignCreateDTO
    ) -> DiscoveryCampaign:
        """Create a new AI discovery campaign."""
        campaign = DiscoveryCampaign(
            organization_id=organization_id,
            name=dto.name,
            description=dto.description,
            market_id=dto.market_id,
            country_code=dto.country_code,
            cities=dto.cities or [],
            property_types=dto.property_types or [],
            transaction_types=dto.transaction_types or [],
            lead_types=dto.lead_types or [],
            budget_min=dto.budget_min,
            budget_max=dto.budget_max,
            currency=dto.currency.upper() if dto.currency else None,
            timeline=dto.timeline,
            languages=dto.languages or [],
            intent_threshold=dto.intent_threshold,
            minimum_confidence=dto.minimum_confidence,
            source_ids=dto.source_ids or [],
            daily_discovery_limit=dto.daily_discovery_limit,
            status=DiscoveryCampaignStatus.DRAFT,
            campaign_metadata=dto.campaign_metadata,
        )
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)
        logger.info(f"[DISCOVERY_CAMPAIGN] Created campaign '{campaign.name}' org={organization_id}")
        return campaign

    async def get_campaign(self, organization_id: str, campaign_id: str) -> Optional[DiscoveryCampaign]:
        """Get campaign by ID with tenant isolation."""
        stmt = select(DiscoveryCampaign).where(
            and_(DiscoveryCampaign.id == campaign_id, DiscoveryCampaign.organization_id == organization_id)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_campaigns(
        self,
        organization_id: str,
        status: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> List[DiscoveryCampaign]:
        """List discovery campaigns for the organization."""
        conditions = [DiscoveryCampaign.organization_id == organization_id]
        if status:
            conditions.append(DiscoveryCampaign.status == status)
        if country_code:
            conditions.append(DiscoveryCampaign.country_code == country_code.upper())
        stmt = select(DiscoveryCampaign).where(and_(*conditions)).order_by(DiscoveryCampaign.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def update_campaign(
        self, organization_id: str, campaign_id: str, dto: DiscoveryCampaignUpdateDTO
    ) -> Optional[DiscoveryCampaign]:
        """Update campaign configuration."""
        campaign = await self.get_campaign(organization_id, campaign_id)
        if not campaign:
            return None

        if dto.name is not None:
            campaign.name = dto.name
        if dto.description is not None:
            campaign.description = dto.description
        if dto.market_id is not None:
            campaign.market_id = dto.market_id
        if dto.country_code is not None:
            campaign.country_code = dto.country_code
        if dto.cities is not None:
            campaign.cities = dto.cities
        if dto.property_types is not None:
            campaign.property_types = dto.property_types
        if dto.transaction_types is not None:
            campaign.transaction_types = dto.transaction_types
        if dto.lead_types is not None:
            campaign.lead_types = dto.lead_types
        if dto.budget_min is not None:
            campaign.budget_min = dto.budget_min
        if dto.budget_max is not None:
            campaign.budget_max = dto.budget_max
        if dto.currency is not None:
            campaign.currency = dto.currency.upper()
        if dto.timeline is not None:
            campaign.timeline = dto.timeline
        if dto.languages is not None:
            campaign.languages = dto.languages
        if dto.intent_threshold is not None:
            campaign.intent_threshold = dto.intent_threshold
        if dto.minimum_confidence is not None:
            campaign.minimum_confidence = dto.minimum_confidence
        if dto.source_ids is not None:
            campaign.source_ids = dto.source_ids
        if dto.daily_discovery_limit is not None:
            campaign.daily_discovery_limit = dto.daily_discovery_limit
        if dto.status is not None:
            campaign.status = dto.status
        if dto.campaign_metadata is not None:
            campaign.campaign_metadata = dto.campaign_metadata

        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign

    async def set_campaign_status(
        self, organization_id: str, campaign_id: str, status: str
    ) -> Optional[DiscoveryCampaign]:
        """Pause, activate, or complete a campaign."""
        campaign = await self.get_campaign(organization_id, campaign_id)
        if not campaign:
            return None
        campaign.status = status
        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign
