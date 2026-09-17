"""
Part 30 — AI Real-Estate Agent Daily Command Center FastAPI REST Router
========================================================================
Endpoints:
    GET  /api/v1/command-center                        # Full operational command center
    GET  /api/v1/command-center/summary                # Lightweight dashboard counters
    GET  /api/v1/command-center/priorities             # Ordered priority actions
    GET  /api/v1/command-center/today                  # Today's schedule (meetings & site visits)
    GET  /api/v1/command-center/inventory-intelligence # Demand heatmap & supply gap opportunities
    GET  /api/v1/command-center/briefing               # Grounded morning briefing
    GET  /api/v1/command-center/start-my-day           # Sequential interactive action steps
    POST /api/v1/command-center/items/dismiss          # Dismiss or snooze priority items
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.command_center.service import CommandCenterService
from app.modules.command_center.dto import (
    CommandCenterResponseDTO,
    CommandCenterSummaryDTO,
    PriorityItemDTO,
    TodayScheduleItemDTO,
    DailyBriefingDTO,
    DismissItemRequestDTO,
    StartMyDayResponseDTO
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/command-center", tags=["AI Agent Daily Command Center"])


@router.get(
    "",
    response_model=CommandCenterResponseDTO,
    summary="Fetch Operational Command Center Data",
)
async def get_command_center_endpoint(
    timezone: str = Query("Asia/Kolkata"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Primary operational endpoint: returns today's prioritized directives,
    meetings, site visits, overdue follow-ups, hot leads, inventory gaps, and AI briefing.
    """
    service = CommandCenterService(db)
    try:
        return await service.get_command_center_data(broker=current_broker, timezone_str=timezone)
    except Exception as exc:
        logger.error(f"[COMMAND_CENTER_ROUTER] get_command_center_data failed: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/summary",
    response_model=CommandCenterSummaryDTO,
    summary="Fetch Command Center Summary Counters",
)
async def get_command_center_summary_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Returns top-level counters for urgent actions, SLA breaches, and meetings."""
    service = CommandCenterService(db)
    data = await service.get_command_center_data(broker=current_broker)
    return data.summary


@router.get(
    "/priorities",
    response_model=List[PriorityItemDTO],
    summary="Fetch Ordered Priority Queue",
)
async def get_priorities_endpoint(
    limit: int = Query(25, ge=1, le=100),
    priority_filter: Optional[str] = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW"),
    entity_type: Optional[str] = Query(None, description="lead | task | meeting | match"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Returns the deterministic priority queue sorted by urgency."""
    service = CommandCenterService(db)
    return await service.get_priority_queue(
        broker=current_broker,
        limit=limit,
        priority_filter=priority_filter,
        entity_type=entity_type
    )


@router.get(
    "/today",
    response_model=List[TodayScheduleItemDTO],
    summary="Fetch Today's Meetings & Site Visits",
)
async def get_today_schedule_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Returns all scheduled site visits and client meetings for today."""
    service = CommandCenterService(db)
    data = await service.get_command_center_data(broker=current_broker)
    return data.today_schedule


@router.get(
    "/inventory-intelligence",
    summary="Fetch Demand Heatmap & Supply Gaps",
)
async def get_inventory_intelligence_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Calculates internal CRM demand heatmap and inventory gap opportunities."""
    service = CommandCenterService(db)
    return await service.get_inventory_intelligence(broker=current_broker)


@router.get(
    "/briefing",
    response_model=DailyBriefingDTO,
    summary="Fetch Grounded Morning Briefing",
)
async def get_daily_briefing_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Returns the grounded morning briefing."""
    service = CommandCenterService(db)
    data = await service.get_command_center_data(broker=current_broker)
    return data.daily_briefing


@router.get(
    "/start-my-day",
    response_model=StartMyDayResponseDTO,
    summary="Fetch Interactive Start My Day Action Steps",
)
async def get_start_my_day_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Constructs a sequential, step-by-step queue for the agent's workday."""
    service = CommandCenterService(db)
    return await service.get_start_my_day_sequence(broker=current_broker)


@router.post(
    "/items/dismiss",
    summary="Dismiss or Snooze Priority Item",
)
async def dismiss_item_endpoint(
    dto: DismissItemRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """Records dismissal or snooze state without mutating underlying CRM records."""
    service = CommandCenterService(db)
    return await service.dismiss_or_snooze_item(broker=current_broker, dto=dto)
