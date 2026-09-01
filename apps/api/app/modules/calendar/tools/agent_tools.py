"""
Controlled AI Sales Agent Calendar & Scheduling Tools
=====================================================
Exposes verified, safe scheduling tools to the AI Sales Agent.
The AI Agent NEVER accesses raw calendar provider APIs directly.
All operations are routed strictly through SchedulingOrchestratorService.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.calendar.service import SchedulingOrchestratorService
from app.modules.calendar.dto.calendar_schemas import (
    SlotSearchRequestDTO, BookingRequestDTO, RescheduleRequestDTO,
    CancellationRequestDTO, RecordOutcomeRequestDTO
)

logger = logging.getLogger(__name__)

class AIAgentCalendarTools:
    """
    Controlled tool wrapper for AI agent conversational workflows.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = SchedulingOrchestratorService(db)

    async def find_available_slots(
        self,
        lead_id: str,
        organization_id: str,
        meeting_type: str = "PROPERTY_VIEWING",
        property_id: Optional[str] = None,
        duration_minutes: int = 45
    ) -> Dict[str, Any]:
        """Tool: findAvailableSlots — searches and proposes candidate slots."""
        req = SlotSearchRequestDTO(
            lead_id=lead_id,
            meeting_type=meeting_type,
            property_id=property_id,
            duration_minutes=duration_minutes
        )
        res = await self.service.search_available_slots(req, organization_id)
        return {
            "lead_id": res.lead_id,
            "meeting_type": res.meeting_type,
            "customer_timezone": res.customer_timezone,
            "slots": [
                {
                    "start_utc": s.start_utc.isoformat(),
                    "customer_time": s.customer_local_start,
                    "broker_time": s.broker_local_start
                }
                for s in res.available_slots[:3]
            ]
        }

    async def hold_slot(
        self,
        broker_id: str,
        lead_id: str,
        slot_start_utc: datetime,
        duration_minutes: int = 45
    ) -> Dict[str, Any]:
        """Tool: holdSlot — acquires 5-minute temporary collision lock."""
        from datetime import timedelta
        hold = await self.service.lock_manager.acquire_hold(
            broker_id=broker_id,
            lead_id=lead_id,
            slot_start_utc=slot_start_utc,
            slot_end_utc=slot_start_utc + timedelta(minutes=duration_minutes)
        )
        if not hold:
            return {"success": False, "reason": "Slot collision: Slot already held or booked"}
        return {
            "success": True,
            "hold_id": hold.id,
            "expires_at_utc": hold.expires_at_utc.isoformat()
        }

    async def book_viewing(
        self,
        lead_id: str,
        organization_id: str,
        broker_id: str,
        property_id: str,
        slot_start_utc: datetime,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool: bookViewing — books property viewing with building access preclearance."""
        dto = BookingRequestDTO(
            lead_id=lead_id,
            broker_id=broker_id,
            meeting_type="PROPERTY_VIEWING",
            property_id=property_id,
            slot_start_utc=slot_start_utc,
            notes=notes
        )
        res = await self.service.book_meeting(dto, organization_id, broker_id)
        return {
            "booking_id": res.id,
            "title": res.title,
            "status": res.status,
            "start_utc": res.start_utc.isoformat(),
            "location": res.location_address
        }

    async def reschedule_meeting(
        self,
        meeting_id: str,
        new_slot_start_utc: datetime,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool: rescheduleMeeting — reschedules appointment."""
        dto = RescheduleRequestDTO(new_slot_start_utc=new_slot_start_utc, reason=reason)
        res = await self.service.reschedule_meeting(meeting_id, dto)
        return {
            "meeting_id": res.id,
            "status": res.status,
            "new_start_utc": res.start_utc.isoformat()
        }

    async def cancel_meeting(
        self,
        meeting_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """Tool: cancelMeeting — cancels appointment."""
        dto = CancellationRequestDTO(reason=reason, cancelled_by="AI_AGENT")
        success = await self.service.cancel_meeting(meeting_id, dto)
        return {"success": success, "meeting_id": meeting_id, "status": "CANCELLED"}

    async def get_meeting_preparation(self, meeting_id: str) -> Dict[str, Any]:
        """Tool: getMeetingPreparation — retrieves AI briefing for sales agent."""
        brief = await self.service.get_or_generate_brief(meeting_id)
        return {
            "meeting_id": brief.meeting_id,
            "buyer_summary": brief.buyer_summary,
            "budget": brief.verified_budget,
            "next_best_action": brief.next_best_action
        }

    async def record_meeting_outcome(
        self,
        meeting_id: str,
        outcome_category: str,
        interest_level: int = 3,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tool: recordMeetingOutcome — records post-meeting feedback and updates pipeline."""
        dto = RecordOutcomeRequestDTO(
            outcome_category=outcome_category,
            buyer_interest_level=interest_level,
            detailed_feedback=feedback
        )
        outcome = await self.service.record_meeting_outcome(meeting_id, dto)
        return {
            "outcome_id": outcome.id,
            "category": outcome.outcome_category,
            "interest_level": outcome.buyer_interest_level
        }
