import math
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict
from sqlalchemy import select, func, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm_models import Notification
from app.modules.notifications.channels.notification_channels import (
    INotificationChannel, InAppChannelAdapter, EmailChannelAdapter,
    WhatsAppChannelAdapter, TelegramChannelAdapter, SMSChannelAdapter,
    NotificationPayload,
)
from app.modules.notifications.dto.notification_dto import (
    NotificationSendDTO, NotificationResponseDTO, NotificationSearchDTO
)

logger = logging.getLogger(__name__)


class NotificationEngine:
    """
    Enterprise Multi-Channel Notification Engine.
    Dispatches notifications via registered channel adapters.
    Channels are pluggable — new channels register without changing this service.
    """

    CHANNEL_REGISTRY: Dict[str, INotificationChannel] = {
        "in_app": InAppChannelAdapter(),
        "email": EmailChannelAdapter(),
        "whatsapp": WhatsAppChannelAdapter(),
        "telegram": TelegramChannelAdapter(),
        "sms": SMSChannelAdapter(),
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send(self, dto: NotificationSendDTO) -> NotificationResponseDTO:
        """
        Send a notification across one or more channels.
        In-App notifications are persisted to DB. All channels dispatched concurrently.
        """
        # Always create in-app notification in DB
        notification = Notification(
            broker_id=dto.recipient_id,
            organization_id=dto.organization_id,
            category=dto.category,
            title=dto.title,
            body=dto.body,
            action_url=dto.action_url,
        )
        self.db.add(notification)
        await self.db.flush()

        # Dispatch to all requested channels concurrently
        tasks = []
        for channel_name in dto.channels:
            adapter = self.CHANNEL_REGISTRY.get(channel_name)
            if adapter:
                payload = NotificationPayload(
                    recipient_id=dto.recipient_id,
                    title=dto.title,
                    body=dto.body,
                    channel=channel_name,
                    category=dto.category,
                    action_url=dto.action_url,
                    metadata=dto.metadata,
                )
                tasks.append(adapter.send(payload))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error(f"[NOTIFY CHANNEL ERROR] {dto.channels[i]}: {res}")

        await self.db.commit()
        logger.info(f"[NOTIFY] Sent '{dto.title}' to {dto.recipient_id} via {dto.channels}")
        return NotificationResponseDTO.model_validate(notification)

    async def list_notifications(
        self, broker_id: str, search_dto: NotificationSearchDTO
    ) -> dict:
        conditions = [Notification.broker_id == broker_id]
        if search_dto.is_read is not None:
            conditions.append(Notification.is_read == search_dto.is_read)
        if search_dto.category:
            conditions.append(Notification.category == search_dto.category)

        base = select(Notification).where(and_(*conditions))
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        offset = (search_dto.page - 1) * search_dto.limit
        stmt = base.order_by(Notification.created_at.desc()).offset(offset).limit(search_dto.limit)
        items = list((await self.db.execute(stmt)).scalars().all())

        pages = math.ceil(total / search_dto.limit) if total > 0 else 0
        return {
            "items": [NotificationResponseDTO.model_validate(n) for n in items],
            "total": total,
            "page": search_dto.page,
            "pages": pages,
            "unread_count": await self._unread_count(broker_id),
        }

    async def mark_read(self, notification_id: str, broker_id: str) -> bool:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.broker_id == broker_id)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return True

    async def mark_all_read(self, broker_id: str) -> int:
        stmt = (
            update(Notification)
            .where(Notification.broker_id == broker_id, Notification.is_read == False)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def _unread_count(self, broker_id: str) -> int:
        stmt = select(func.count()).where(
            Notification.broker_id == broker_id,
            Notification.is_read == False
        )
        return (await self.db.execute(stmt)).scalar_one()
