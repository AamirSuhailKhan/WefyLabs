from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
import uuid
from app.models.audit_log import AuditLog


class IAuditRepository(ABC):
    """Persistence-only interface for immutable audit log entries."""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_by_id(self, audit_id: uuid.UUID) -> Optional[AuditLog]:
        pass
