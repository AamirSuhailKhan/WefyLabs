import math
import logging
import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.repository.audit_repository import AuditRepository
from app.modules.audit.dto.audit_dto import AuditCreateDTO, AuditSearchDTO, AuditResponseDTO

logger = logging.getLogger(__name__)


class AuditService:
    """
    Enterprise Audit Service — immutable, never-failing append-only log writer.
    Wraps all write failures silently to never block request processing.
    """

    def __init__(self, db: AsyncSession):
        self.repo = AuditRepository(db)
        self.db = db

    async def record(self, dto: AuditCreateDTO) -> None:
        """Write an immutable audit entry. Never raises on failure."""
        try:
            await self.repo.create(
                action=dto.action,
                resource_type=dto.resource_type,
                actor_id=dto.actor_id,
                organization_id=dto.organization_id,
                resource_id=dto.resource_id,
                previous_values=dto.previous_values,
                new_values=dto.new_values,
                changes=dto.changes,
                ip_address=dto.ip_address,
                user_agent=dto.user_agent,
                request_id=dto.request_id,
                correlation_id=dto.correlation_id,
                session_id=dto.session_id,
                actor_type=dto.actor_type,
                api_key_id=dto.api_key_id,
            )
            await self.db.commit()
            logger.info(f"[AUDIT] {dto.action} on {dto.resource_type}/{dto.resource_id} by {dto.actor_id}")
        except Exception as exc:
            logger.error(f"[AUDIT WRITE FAILURE] {exc}", exc_info=True)

    async def log(self, dto: AuditCreateDTO) -> None:
        """Alias for record() ensuring cross-module compatibility."""
        await self.record(dto)

    async def search(self, dto: AuditSearchDTO) -> dict:
        """Search audit logs with pagination."""
        items, total = await self.repo.search(
            organization_id=dto.organization_id,
            action=dto.action,
            resource_type=dto.resource_type,
            resource_id=dto.resource_id,
            actor_id=dto.actor_id,
            page=dto.page,
            limit=dto.limit,
        )
        pages = math.ceil(total / dto.limit) if total > 0 else 0
        return {
            "items": [AuditResponseDTO.model_validate(item) for item in items],
            "total": total,
            "page": dto.page,
            "pages": pages,
            "limit": dto.limit,
        }

    async def get_by_id(self, audit_id: uuid.UUID) -> Optional[AuditResponseDTO]:
        item = await self.repo.get_by_id(audit_id)
        if not item:
            return None
        return AuditResponseDTO.model_validate(item)


AuditLogService = AuditService
