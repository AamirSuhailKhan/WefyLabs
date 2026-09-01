from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response
from app.modules.incident.service.incident_service import IncidentService, IncidentCreateDTO, IncidentUpdateDTO

router = APIRouter(prefix="/v1/incidents", tags=["Incident Management"])


@router.get("", response_model=APIResponse)
async def list_incidents(
    severity: Optional[str] = Query(None, pattern="^(P0|P1|P2|P3)$"),
    status: Optional[str] = Query(None, pattern="^(detected|investigating|mitigated|resolved)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = IncidentService(db)
    items = await svc.list_incidents(severity=severity, status=status, limit=limit)
    return create_success_response(data=[
        {
            "id": i.id,
            "incident_number": i.incident_number,
            "title": i.title,
            "severity": i.severity,
            "status": i.status,
            "service_affected": i.service_affected,
            "owner_id": i.owner_id,
            "detected_at": i.detected_at,
            "mitigated_at": i.mitigated_at,
            "resolved_at": i.resolved_at,
        } for i in items
    ])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    dto: IncidentCreateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = IncidentService(db)
    inc = await svc.create_incident(dto)
    return create_success_response(data={
        "id": inc.id,
        "incident_number": inc.incident_number,
        "title": inc.title,
        "severity": inc.severity,
        "status": inc.status,
    })


@router.put("/{incident_id}", response_model=APIResponse)
async def update_incident(
    incident_id: str,
    dto: IncidentUpdateDTO,
    db: AsyncSession = Depends(get_db),
    current_broker=Depends(get_current_broker),
):
    svc = IncidentService(db)
    inc = await svc.update_incident(incident_id, dto)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return create_success_response(data={
        "id": inc.id,
        "incident_number": inc.incident_number,
        "status": inc.status,
        "mitigated_at": inc.mitigated_at,
        "resolved_at": inc.resolved_at,
    })
