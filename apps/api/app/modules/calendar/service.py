"""
Calendar, Meeting & Scheduling Intelligence Orchestrator Service
================================================================
Universal facade coordinating availability queries, slot holds, booking,
rescheduling, cancellations, viewing itineraries, briefs, outcomes, and no-show prediction.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.calendar_models import Meeting, CalendarConflict
from app.modules.calendar.booking_lock.lock_manager import BookingLockManager
from app.modules.calendar.availability.availability_engine import AvailabilityEngine
from app.modules.calendar.slot_generation.slot_generator import SlotGenerator
from app.modules.calendar.booking.booking_service import BookingService
from app.modules.calendar.viewing.viewing_service import ViewingService
from app.modules.calendar.rescheduling.rescheduling_service import ReschedulingService
from app.modules.calendar.cancellation.cancellation_service import CancellationService
from app.modules.calendar.no_show.no_show_service import NoShowPredictionService
from app.modules.calendar.preparation.preparation_brief_service import PreparationBriefService
from app.modules.calendar.post_meeting.post_meeting_service import PostMeetingIntelligenceService
from app.modules.calendar.providers.provider_interface import CalendarProvider, MockCalendarProvider
from app.modules.calendar.providers.calendar_provider_factory import resolve_calendar_provider
from app.modules.calendar.dto.calendar_schemas import (
    SlotSearchRequestDTO, SlotSearchResponseDTO, BookingRequestDTO, BookingResponseDTO,
    RescheduleRequestDTO, CancellationRequestDTO, ItineraryRequestDTO, ItineraryResponseDTO,
    RecordOutcomeRequestDTO, MeetingOutcomeDTO, MeetingPreparationBriefDTO,
    NoShowPredictionDTO, CalendarConflictDTO
)

logger = logging.getLogger(__name__)

class SchedulingOrchestratorService:
    """
    Enterprise scheduling orchestrator.
    """

    def __init__(self, db: AsyncSession, provider: Optional[CalendarProvider] = None):
        self.db = db
        self.provider = resolve_calendar_provider(provider)
        self.lock_manager = BookingLockManager(db)
        self.availability_engine = AvailabilityEngine(db, self.provider)
        self.slot_generator = SlotGenerator(db, self.availability_engine)
        self.booking_service = BookingService(db, self.lock_manager, self.provider)
        self.viewing_service = ViewingService(db)
        self.rescheduling_service = ReschedulingService(db, self.provider)
        self.cancellation_service = CancellationService(db, self.provider)
        self.no_show_service = NoShowPredictionService(db)
        self.preparation_service = PreparationBriefService(db)
        self.post_meeting_service = PostMeetingIntelligenceService(db)

    async def search_available_slots(self, req: SlotSearchRequestDTO, organization_id: str) -> SlotSearchResponseDTO:
        return await self.slot_generator.search_slots(req, organization_id)

    async def book_meeting(self, dto: BookingRequestDTO, organization_id: str, broker_id: str) -> BookingResponseDTO:
        return await self.booking_service.book_appointment(dto, organization_id, broker_id)

    async def reschedule_meeting(self, meeting_id: str, dto: RescheduleRequestDTO) -> BookingResponseDTO:
        return await self.rescheduling_service.reschedule_meeting(meeting_id, dto)

    async def cancel_meeting(self, meeting_id: str, dto: CancellationRequestDTO) -> bool:
        return await self.cancellation_service.cancel_meeting(meeting_id, dto)

    async def calculate_viewing_itinerary(self, dto: ItineraryRequestDTO, organization_id: str) -> ItineraryResponseDTO:
        return await self.viewing_service.calculate_itinerary(dto, organization_id)

    async def get_or_generate_brief(self, meeting_id: str) -> MeetingPreparationBriefDTO:
        brief = await self.preparation_service.generate_brief(meeting_id)
        return MeetingPreparationBriefDTO.model_validate(brief)

    async def predict_no_show(self, meeting_id: str) -> NoShowPredictionDTO:
        pred = await self.no_show_service.predict_no_show_risk(meeting_id)
        return NoShowPredictionDTO.model_validate(pred)

    async def record_meeting_outcome(self, meeting_id: str, dto: RecordOutcomeRequestDTO) -> MeetingOutcomeDTO:
        return await self.post_meeting_service.record_outcome(meeting_id, dto)

    async def list_conflicts(self, organization_id: str) -> List[CalendarConflictDTO]:
        stmt = (
            select(CalendarConflict)
            .join(Meeting)
            .where(Meeting.organization_id == organization_id)
        )
        res = await self.db.execute(stmt)
        conflicts = res.scalars().all()
        return [CalendarConflictDTO.model_validate(c) for c in conflicts]
