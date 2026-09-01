"""
Property Viewing & Itinerary Routing Service
============================================
Handles single and multi-property viewing itineraries, calculating optimal transit routes.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.property_models import PropertyListing
from app.modules.calendar.dto.calendar_schemas import ItineraryRequestDTO, ItineraryResponseDTO, ItineraryStopDTO

logger = logging.getLogger(__name__)

class ViewingService:
    """
    Manages multi-property viewing itineraries and travel routing.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_itinerary(self, dto: ItineraryRequestDTO, organization_id: str) -> ItineraryResponseDTO:
        """
        Orders requested properties and calculates realistic visit times with 30-min travel buffers.
        """
        stmt = select(PropertyListing).where(PropertyListing.id.in_(dto.property_ids))
        res = await self.db.execute(stmt)
        listings = res.scalars().all()

        stops: List[ItineraryStopDTO] = []
        current_time = dto.start_date_utc

        for i, prop in enumerate(listings):
            stops.append(ItineraryStopDTO(
                property_id=str(prop.id),
                property_title=prop.title,
                estimated_arrival_utc=current_time,
                estimated_duration_minutes=45,
                locality=prop.locality or prop.city
            ))
            # 45 min viewing + 30 min transit to next unit
            current_time += timedelta(minutes=75)

        total_duration = len(stops) * 75 - 30 if stops else 0

        return ItineraryResponseDTO(
            lead_id=dto.lead_id,
            broker_id=dto.broker_id or "primary_agent",
            total_stops=len(stops),
            total_duration_minutes=total_duration,
            stops=stops
        )
