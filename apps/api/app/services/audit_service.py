import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.crm_models import Notification
import logging

logger = logging.getLogger(__name__)


class AuditLogService:
    """
    Immutable Audit Log Writer for SOC2 Type II and GDPR compliance.
    Records every entity mutation, auth event, export, and admin action.
    Never raises — logging failures must never block request processing.
    """

    @classmethod
    async def record(
        cls,
        db: AsyncSession,
        action: str,
        resource_type: str,
        actor_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        resource_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Persists an immutable audit log entry.

        Args:
            action: Dot-notation action code (e.g. 'lead.create', 'auth.login', 'lead.export')
            resource_type: Entity type ('lead' | 'broker' | 'organization' | 'deal')
            actor_id: UUID of the authenticated broker performing the action
            organization_id: UUID of the tenant organization
            resource_id: String ID of the affected entity
            changes: Dict of field-level changes {field: {before, after}}
            ip_address: Client IP address from request context
            user_agent: Client user-agent string
        """
        try:
            entry = AuditLog(
                actor_id=actor_id,
                organization_id=organization_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                changes=changes,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(entry)
            await db.flush()
            logger.info(
                f"[AUDIT] action={action} resource={resource_type}/{resource_id} "
                f"actor={actor_id} org={organization_id}"
            )
        except Exception as exc:
            # Audit failures must NEVER block the primary request
            logger.error(f"[AUDIT ERROR] Failed to write audit log: {exc}")


class NotificationService:
    """
    In-app notification delivery service.
    Creates persisted notification records with category routing and read-tracking.
    """

    @classmethod
    async def send(
        cls,
        db: AsyncSession,
        broker_id: str,
        title: str,
        category: str = "system",
        body: Optional[str] = None,
        action_url: Optional[str] = None,
        organization_id: Optional[str] = None
    ) -> Notification:
        """
        Creates a notification for a broker with category routing.

        Categories: lead | deal | task | meeting | billing | system
        """
        notification = Notification(
            broker_id=broker_id,
            organization_id=organization_id,
            category=category,
            title=title,
            body=body,
            action_url=action_url
        )
        db.add(notification)
        await db.flush()
        logger.info(
            f"[NOTIFICATION] broker={broker_id} category={category} title={title!r}"
        )
        return notification

    @classmethod
    async def mark_read(
        cls,
        db: AsyncSession,
        notification_id: str,
        broker_id: str
    ) -> None:
        """Marks a specific notification as read for a broker."""
        from sqlalchemy import select, update
        stmt = (
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.broker_id == broker_id
            )
            .values(
                is_read=True,
                read_at=datetime.now(timezone.utc)
            )
        )
        await db.execute(stmt)
        await db.flush()
