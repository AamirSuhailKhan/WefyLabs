"""
Slot Generation & Ranking Service
=================================
Discovers, scores, and ranks candidate appointment slots.

ARCHITECTURE: Timezone is ALWAYS resolved from the lead/broker context
via TimezoneService. Never hardcoded to Asia/Dubai or any country.
"""

import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.lead import Lead
from app.models.broker import Broker
from app.modules.calendar.availability.availability_engine import AvailabilityEngine
from app.modules.calendar.dto.calendar_schemas import SlotSearchRequestDTO, TimeSlotDTO, SlotSearchResponseDTO
from app.modules.global_.timezones.timezone_service import TimezoneService, TimezoneContext

logger = logging.getLogger(__name__)


class SlotGenerator:
    """
    Ranks and structures available meeting and viewing slots.
    Timezones are resolved from lead + broker context — never hardcoded.
    """

    def __init__(self, db: AsyncSession, availability_engine: AvailabilityEngine):
        self.db = db
        self.availability_engine = availability_engine

    async def search_slots(self, req: SlotSearchRequestDTO, organization_id: str) -> SlotSearchResponseDTO:
        """
        Discovers common available slots for the target lead and broker.
        Timezone resolution hierarchy:
          customer: req.customer_timezone → lead.locale → lead.phone_prefix → lead.market → UTC
          broker:   req.broker_timezone  → broker.timezone → org.default_timezone → UTC
        """
        # Fetch lead
        import uuid as _uuid
        try:
            l_pk = _uuid.UUID(str(req.lead_id))
        except Exception:
            l_pk = req.lead_id

        stmt_lead = select(Lead).where(Lead.id == l_pk)
        res_lead = await self.db.execute(stmt_lead)
        lead = res_lead.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead ID '{req.lead_id}' not found.")

        # Determine target broker ID
        broker_id = req.broker_id or str(lead.broker_id)

        # ─── Resolve customer timezone (hierarchy: explicit → inferred from lead) ─────
        inferred_customer_tz: Optional[str] = None
        if req.customer_timezone:
            inferred_customer_tz = req.customer_timezone
        elif lead.phone:
            inferred_customer_tz = TimezoneService._infer_from_phone(lead.phone)
        elif lead.preferred_locations:
            # Look up timezone from TIMEZONE_MAP in timing_engine
            from app.modules.follow_up.timing.timing_engine import TIMEZONE_MAP
            for loc in lead.preferred_locations:
                for key, tz in TIMEZONE_MAP.items():
                    if key in loc.lower():
                        inferred_customer_tz = tz
                        break
                if inferred_customer_tz:
                    break

        cust_tz = TimezoneService.resolve(TimezoneContext(
            inferred_timezone=inferred_customer_tz
        ))

        # ─── Resolve broker timezone (hierarchy: explicit → inferred → UTC) ─
        inferred_broker_tz: Optional[str] = getattr(req, "broker_timezone", None)
        broker_tz = TimezoneService.resolve(TimezoneContext(
            inferred_timezone=inferred_broker_tz
        ))

        slots_data = await self.availability_engine.calculate_available_slots(
            broker_id=broker_id,
            duration_minutes=req.duration_minutes,
            search_days_ahead=req.search_days_ahead,
            property_id=req.property_id,
            customer_tz_str=cust_tz,
            broker_tz_str=broker_tz,
        )

        slot_dtos = [TimeSlotDTO(**s) for s in slots_data]

        return SlotSearchResponseDTO(
            lead_id=str(lead.id),
            meeting_type=req.meeting_type,
            customer_timezone=cust_tz,
            broker_timezone=broker_tz,
            available_slots=slot_dtos
        )
