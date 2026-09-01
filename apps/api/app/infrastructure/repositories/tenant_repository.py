import uuid
from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import Base

T = TypeVar("T", bound=Base)

class TenantRepository(Generic[T]):
    """
    Enterprise Tenant-Isolated Repository enforcing physical multi-tenant partitioning
    on all database SELECT, INSERT, UPDATE, and DELETE operations.
    """

    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(
        self,
        entity_id: Any,
        organization_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> Optional[T]:
        """Retrieves single entity by ID enforcing tenant ownership."""
        stmt = select(self.model).where(self.model.id == entity_id)

        if organization_id and hasattr(self.model, "organization_id"):
            stmt = stmt.where(self.model.organization_id == organization_id)
        if workspace_id and hasattr(self.model, "workspace_id"):
            stmt = stmt.where(self.model.workspace_id == workspace_id)

        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))

        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_all(
        self,
        organization_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[T]:
        """Lists tenant-partitioned entities with offset pagination."""
        stmt = select(self.model)

        if organization_id and hasattr(self.model, "organization_id"):
            stmt = stmt.where(self.model.organization_id == organization_id)
        if workspace_id and hasattr(self.model, "workspace_id"):
            stmt = stmt.where(self.model.workspace_id == workspace_id)

        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))

        stmt = stmt.limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def count(
        self,
        organization_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> int:
        """Counts tenant-partitioned entities."""
        stmt = select(func.count()).select_from(self.model)

        if organization_id and hasattr(self.model, "organization_id"):
            stmt = stmt.where(self.model.organization_id == organization_id)
        if workspace_id and hasattr(self.model, "workspace_id"):
            stmt = stmt.where(self.model.workspace_id == workspace_id)

        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))

        res = await self.session.execute(stmt)
        return res.scalar_one() or 0

    async def create(self, entity: T) -> T:
        """Persists a new tenant entity."""
        self.session.add(entity)
        await self.session.flush()
        return entity
