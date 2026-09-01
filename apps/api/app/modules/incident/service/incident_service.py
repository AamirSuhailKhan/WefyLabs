import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observability_models import Incident

logger = logging.getLogger(__name__)


class IncidentCreateDTO(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    severity: str = Field(default="P2", pattern="^(P0|P1|P2|P3)$")
    service_affected: str = Field(..., example="database")
    organization_id: Optional[str] = None
    owner_id: Optional[str] = None
    root_cause: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IncidentUpdateDTO(BaseModel):
    status: Optional[str] = Field(None, pattern="^(detected|investigating|mitigated|resolved)$")
    owner_id: Optional[str] = None
    root_cause: Optional[str] = None
    mitigation_steps: Optional[str] = None
    postmortem_url: Optional[str] = None


class IncidentService:
    """Enterprise Incident Management Service for SRE teams."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_incident(self, dto: IncidentCreateDTO) -> Incident:
        # Generate auto-incrementing INC number
        count_stmt = select(func.count(Incident.id))
        count = (await self.db.execute(count_stmt)).scalar_one()
        inc_number = f"INC-{1001 + count}"

        incident = Incident(
            incident_number=inc_number,
            title=dto.title,
            severity=dto.severity,
            status="detected",
            service_affected=dto.service_affected,
            organization_id=dto.organization_id,
            owner_id=dto.owner_id,
            root_cause=dto.root_cause,
            metadata_json=dto.metadata_json or {},
        )
        self.db.add(incident)
        await self.db.commit()
        logger.error(f"[INCIDENT CREATED] {inc_number} ({dto.severity}) - {dto.title} on {dto.service_affected}")
        return incident

    async def update_incident(self, incident_id: str, dto: IncidentUpdateDTO) -> Optional[Incident]:
        stmt = select(Incident).where(Incident.id == incident_id)
        incident = (await self.db.execute(stmt)).scalars().first()
        if not incident:
            return None

        now = datetime.now(timezone.utc)
        if dto.status:
            incident.status = dto.status
            if dto.status == "mitigated" and not incident.mitigated_at:
                incident.mitigated_at = now
            elif dto.status == "resolved" and not incident.resolved_at:
                incident.resolved_at = now

        if dto.owner_id: incident.owner_id = dto.owner_id
        if dto.root_cause: incident.root_cause = dto.root_cause
        if dto.mitigation_steps: incident.mitigation_steps = dto.mitigation_steps
        if dto.postmortem_url: incident.postmortem_url = dto.postmortem_url
        incident.updated_at = now

        await self.db.commit()
        logger.info(f"[INCIDENT UPDATED] {incident.incident_number} -> Status: {incident.status}")
        return incident

    async def list_incidents(
        self, severity: Optional[str] = None, status: Optional[str] = None, limit: int = 50
    ) -> List[Incident]:
        conditions = []
        if severity: conditions.append(Incident.severity == severity)
        if status: conditions.append(Incident.status == status)

        stmt = select(Incident)
        if conditions:
            from sqlalchemy import and_
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Incident.created_at.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())
