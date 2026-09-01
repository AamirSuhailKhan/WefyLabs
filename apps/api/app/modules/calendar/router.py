"""
FastAPI Router for Calendar, Meeting, Viewing & Scheduling Intelligence Engine
================================================================================
Exposes production REST APIs for finding available slots, booking appointments,
rescheduling, cancellations, multi-property itineraries, AI briefs, outcomes, and conflicts.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.calendar_models import Meeting
from app.modules.calendar.service import SchedulingOrchestratorService
from app.modules.calendar.dto.calendar_schemas import (
    SlotSearchRequestDTO, SlotSearchResponseDTO, BookingRequestDTO, BookingResponseDTO,
    RescheduleRequestDTO, CancellationRequestDTO, ItineraryRequestDTO, ItineraryResponseDTO,
    RecordOutcomeRequestDTO, MeetingOutcomeDTO, MeetingPreparationBriefDTO,
    NoShowPredictionDTO, CalendarConflictDTO
)

router = APIRouter(prefix="/calendar", tags=["Calendar, Meeting & Scheduling Intelligence Engine"])


@router.post("/slots/search", response_model=SlotSearchResponseDTO)
async def search_available_slots_endpoint(
    req: SlotSearchRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Finds verified common meeting and viewing slots across broker working hours and property access windows.
    """
    try:
        service = SchedulingOrchestratorService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.search_available_slots(req, org_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/book", response_model=BookingResponseDTO)
async def book_appointment_endpoint(
    dto: BookingRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Acquires 5-minute collision hold, creates external calendar event, and confirms appointment.
    """
    try:
        service = SchedulingOrchestratorService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        broker_id = str(current_broker.id)
        return await service.book_meeting(dto, org_id, broker_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/bookings/{meeting_id}", response_model=BookingResponseDTO)
async def get_booking_details_endpoint(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves appointment details, status, virtual link, and location.
    """
    stmt = select(Meeting).where(Meeting.id == meeting_id)
    res = await db.execute(stmt)
    meeting = res.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found.")
    return BookingResponseDTO.model_validate(meeting)


@router.post("/bookings/{meeting_id}/reschedule", response_model=BookingResponseDTO)
async def reschedule_booking_endpoint(
    meeting_id: str,
    dto: RescheduleRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Atomically reschedules appointment and updates external calendar events.
    """
    try:
        service = SchedulingOrchestratorService(db)
        return await service.reschedule_meeting(meeting_id, dto)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/bookings/{meeting_id}/cancel")
async def cancel_booking_endpoint(
    meeting_id: str,
    dto: CancellationRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Cancels appointment and removes external calendar events.
    """
    try:
        service = SchedulingOrchestratorService(db)
        await service.cancel_meeting(meeting_id, dto)
        return {"status": "cancelled", "meeting_id": meeting_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/itineraries", response_model=ItineraryResponseDTO)
async def calculate_viewing_itinerary_endpoint(
    dto: ItineraryRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Optimizes multi-property viewing itinerary and calculates transit travel windows.
    """
    service = SchedulingOrchestratorService(db)
    org_id = str(current_broker.organization_id or current_broker.id)
    return await service.calculate_viewing_itinerary(dto, org_id)


@router.get("/bookings/{meeting_id}/brief", response_model=MeetingPreparationBriefDTO)
async def get_meeting_brief_endpoint(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves or generates the pre-meeting AI preparation brief for the sales agent.
    """
    try:
        service = SchedulingOrchestratorService(db)
        return await service.get_or_generate_brief(meeting_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/bookings/{meeting_id}/no-show", response_model=NoShowPredictionDTO)
async def get_no_show_prediction_endpoint(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Evaluates no-show propensity and returns preventative confirmation recommendations.
    """
    try:
        service = SchedulingOrchestratorService(db)
        return await service.predict_no_show(meeting_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/bookings/{meeting_id}/outcome", response_model=MeetingOutcomeDTO)
async def record_meeting_outcome_endpoint(
    meeting_id: str,
    dto: RecordOutcomeRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Records post-meeting outcome, feedback, and updates CRM pipeline stage.
    """
    try:
        service = SchedulingOrchestratorService(db)
        return await service.record_meeting_outcome(meeting_id, dto)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/conflicts", response_model=List[CalendarConflictDTO])
async def list_calendar_conflicts_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Lists external calendar synchronization conflicts for review.
    """
    service = SchedulingOrchestratorService(db)
    org_id = str(current_broker.organization_id or current_broker.id)
    return await service.list_conflicts(org_id)


# ─── Google Calendar OAuth & Token Management Endpoints ─────────────────────────

from pydantic import BaseModel

class GoogleCalendarConnectResponse(BaseModel):
    auth_url: str
    state: str

class GoogleCalendarCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: Optional[str] = None

class GoogleCalendarStatusResponse(BaseModel):
    is_connected: bool
    provider: str = "GOOGLE"
    account_email: Optional[str] = None
    status: str
    connected_at: Optional[str] = None
    last_sync_at: Optional[str] = None


@router.get("/google/connect", response_model=GoogleCalendarConnectResponse)
async def get_google_calendar_connect_url(
    redirect_uri: Optional[str] = None,
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Generates a secure OAuth 2.0 authorization URL for connecting Google Calendar.
    Requires broker authentication and generates a CSRF-signed state token.
    """
    from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
    try:
        auth_url, state = CalendarOAuthService.generate_calendar_auth_url(current_broker, redirect_uri)
        return GoogleCalendarConnectResponse(auth_url=auth_url, state=state)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/google/callback")
async def exchange_google_calendar_callback(
    req: GoogleCalendarCallbackRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Validates CSRF state, exchanges authorization code for tokens, encrypts credentials,
    and establishes the broker's active Google Calendar connection.
    """
    from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
    try:
        cal_account = await CalendarOAuthService.exchange_calendar_oauth_code(
            db=db,
            broker=current_broker,
            code=req.code,
            state=req.state,
            redirect_uri=req.redirect_uri
        )
        return {
            "success": True,
            "provider": "GOOGLE",
            "account_email": cal_account.account_email,
            "is_connected": True,
            "message": f"Successfully connected Google Calendar for {cal_account.account_email}."
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/google/status", response_model=GoogleCalendarStatusResponse)
async def get_google_calendar_status(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Returns connection status and connected Google Calendar account email for authenticated broker.
    """
    from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
    status_data = await CalendarOAuthService.get_calendar_status(db, current_broker)
    return GoogleCalendarStatusResponse(**status_data)


@router.post("/google/disconnect")
async def disconnect_google_calendar(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Disconnects Google Calendar and purges stored encrypted tokens while preserving historical meeting records.
    """
    from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
    await CalendarOAuthService.disconnect_calendar(db, current_broker)
    return {
        "success": True,
        "is_connected": False,
        "message": "Google Calendar integration successfully disconnected."
    }


@router.post("/google/reauthorize", response_model=GoogleCalendarConnectResponse)
async def reauthorize_google_calendar(
    redirect_uri: Optional[str] = None,
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Generates a new OAuth consent URL to re-authorize an expired or revoked connection.
    """
    from app.modules.calendar.auth.calendar_oauth_service import CalendarOAuthService
    try:
        auth_url, state = CalendarOAuthService.generate_calendar_auth_url(current_broker, redirect_uri)
        return GoogleCalendarConnectResponse(auth_url=auth_url, state=state)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

