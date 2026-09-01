import uuid
import math
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.modules.audit.interfaces.repository_interface import IAuditRepository


class AuditRepository(IAuditRepository):
    """SQLAlchemy Async persistence layer for AuditLog. Append-only — no updates or deletes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        action: str,
        resource_type: str,
        actor_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        resource_id: Optional[str] = None,
        previous_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        changes: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        actor_type: str = "user",
        api_key_id: Optional[str] = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_id=actor_id,
            actor_type=actor_type,
            organization_id=organization_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_values=previous_values,
            new_values=new_values,
            changes=changes,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            correlation_id=correlation_id,
            session_id=session_id,
            api_key_id=api_key_id,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def search(
        self,
        organization_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[AuditLog], int]:
        conditions = []
        if organization_id:
            conditions.append(AuditLog.organization_id == organization_id)
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if actor_id:
            conditions.append(AuditLog.actor_id == actor_id)

        base_query = select(AuditLog)
        if conditions:
            base_query = base_query.where(and_(*conditions))

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * limit
        stmt = base_query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        results = await self.db.execute(stmt)
        return list(results.scalars().all()), total

    async def get_by_id(self, audit_id: uuid.UUID) -> Optional[AuditLog]:
        result = await self.db.execute(select(AuditLog).where(AuditLog.id == audit_id))
        return result.scalars().first()
