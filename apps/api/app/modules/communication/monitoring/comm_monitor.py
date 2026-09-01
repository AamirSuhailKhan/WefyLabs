"""
Communication Monitor — KPI Tracker
=======================================
Tracks and aggregates key performance indicators for the communication platform.

Metrics:
- Messages/minute
- Delivery rate (sent → delivered %)
- Read rate (delivered → read %)
- Failure rate
- Retry rate
- Provider latency (avg ms)
- Conversation length (avg turns)
- AI vs Human response rate
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import (
    ChannelMessage, DeliveryStatusRecord, OmnichannelConversation, OutboundQueue
)

logger = logging.getLogger(__name__)


class CommunicationMonitor:
    """
    Aggregates real-time KPIs from communication DB tables.
    Called by monitoring endpoints and exportable to Prometheus.
    """

    async def get_dashboard_stats(
        self,
        organization_id: str,
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Return comprehensive KPI dashboard for an organization.
        Covers the last N hours.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        total_messages = await self._count_messages(db, organization_id, since)
        outbound_count = await self._count_by_direction(db, organization_id, "outbound", since)
        inbound_count = await self._count_by_direction(db, organization_id, "inbound", since)
        delivered_count = await self._count_by_status(db, organization_id, "delivered", since)
        read_count = await self._count_by_status(db, organization_id, "read", since)
        failed_count = await self._count_by_status(db, organization_id, "failed", since)
        ai_sent_count = await self._count_ai_messages(db, organization_id, since)

        delivery_rate = round(delivered_count / outbound_count * 100, 2) if outbound_count > 0 else 0.0
        read_rate = round(read_count / delivered_count * 100, 2) if delivered_count > 0 else 0.0
        failure_rate = round(failed_count / outbound_count * 100, 2) if outbound_count > 0 else 0.0
        ai_rate = round(ai_sent_count / outbound_count * 100, 2) if outbound_count > 0 else 0.0

        avg_latency = await self._avg_delivery_latency(db, organization_id, since)
        active_conversations = await self._count_active_conversations(db, organization_id)
        dead_letter_count = await self._count_dead_letter(db, organization_id)
        retry_count = await self._count_retry_queue(db, organization_id)
        channel_breakdown = await self._channel_breakdown(db, organization_id, since)

        return {
            "period_hours": hours,
            "since": since.isoformat(),
            "organization_id": organization_id,
            "messages": {
                "total": total_messages,
                "inbound": inbound_count,
                "outbound": outbound_count,
                "per_hour": round(total_messages / max(hours, 1), 2),
            },
            "delivery": {
                "delivered": delivered_count,
                "read": read_count,
                "failed": failed_count,
                "delivery_rate_pct": delivery_rate,
                "read_rate_pct": read_rate,
                "failure_rate_pct": failure_rate,
                "avg_latency_ms": avg_latency,
            },
            "ai": {
                "ai_sent": ai_sent_count,
                "ai_rate_pct": ai_rate,
            },
            "queues": {
                "dead_letter": dead_letter_count,
                "pending_retry": retry_count,
            },
            "conversations": {
                "active": active_conversations,
            },
            "channels": channel_breakdown,
        }

    async def get_provider_health(
        self,
        organization_id: str,
        db: AsyncSession,
        minutes: int = 60,
    ) -> Dict[str, Any]:
        """Return per-provider health metrics."""
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        stmt = (
            select(
                DeliveryStatusRecord.provider_name,
                DeliveryStatusRecord.status,
                func.count().label("count"),
                func.avg(DeliveryStatusRecord.latency_ms).label("avg_latency"),
            )
            .where(
                DeliveryStatusRecord.organization_id == organization_id,
                DeliveryStatusRecord.created_at >= since,
            )
            .group_by(DeliveryStatusRecord.provider_name, DeliveryStatusRecord.status)
        )
        result = await db.execute(stmt)
        rows = result.all()

        providers: Dict[str, Dict] = {}
        for row in rows:
            pname = row.provider_name
            if pname not in providers:
                providers[pname] = {"status_breakdown": {}, "avg_latency_ms": 0}
            providers[pname]["status_breakdown"][row.status] = row.count
            if row.avg_latency:
                providers[pname]["avg_latency_ms"] = round(float(row.avg_latency), 2)

        return {"period_minutes": minutes, "providers": providers}

    # ─── Private Aggregation Helpers ─────────────────────────────────────────

    async def _count_messages(self, db, org_id, since) -> int:
        result = await db.execute(
            select(func.count()).select_from(ChannelMessage)
            .where(ChannelMessage.organization_id == org_id, ChannelMessage.created_at >= since)
        )
        return result.scalar() or 0

    async def _count_by_direction(self, db, org_id, direction, since) -> int:
        result = await db.execute(
            select(func.count()).select_from(ChannelMessage)
            .where(ChannelMessage.organization_id == org_id,
                   ChannelMessage.direction == direction,
                   ChannelMessage.created_at >= since)
        )
        return result.scalar() or 0

    async def _count_by_status(self, db, org_id, status, since) -> int:
        result = await db.execute(
            select(func.count()).select_from(ChannelMessage)
            .where(ChannelMessage.organization_id == org_id,
                   ChannelMessage.delivery_status == status,
                   ChannelMessage.created_at >= since)
        )
        return result.scalar() or 0

    async def _count_ai_messages(self, db, org_id, since) -> int:
        result = await db.execute(
            select(func.count()).select_from(ChannelMessage)
            .where(ChannelMessage.organization_id == org_id,
                   ChannelMessage.sent_by_ai == True,
                   ChannelMessage.created_at >= since)
        )
        return result.scalar() or 0

    async def _avg_delivery_latency(self, db, org_id, since) -> Optional[float]:
        result = await db.execute(
            select(func.avg(DeliveryStatusRecord.latency_ms))
            .where(DeliveryStatusRecord.organization_id == org_id,
                   DeliveryStatusRecord.status == "sent",
                   DeliveryStatusRecord.created_at >= since,
                   DeliveryStatusRecord.latency_ms.isnot(None))
        )
        val = result.scalar()
        return round(float(val), 2) if val else None

    async def _count_active_conversations(self, db, org_id) -> int:
        result = await db.execute(
            select(func.count()).select_from(OmnichannelConversation)
            .where(OmnichannelConversation.organization_id == org_id,
                   OmnichannelConversation.status == "active")
        )
        return result.scalar() or 0

    async def _count_dead_letter(self, db, org_id) -> int:
        result = await db.execute(
            select(func.count()).select_from(OutboundQueue)
            .where(OutboundQueue.organization_id == org_id,
                   OutboundQueue.status == "dead_letter")
        )
        return result.scalar() or 0

    async def _count_retry_queue(self, db, org_id) -> int:
        result = await db.execute(
            select(func.count()).select_from(OutboundQueue)
            .where(OutboundQueue.organization_id == org_id,
                   OutboundQueue.status == "retry")
        )
        return result.scalar() or 0

    async def _channel_breakdown(self, db, org_id, since) -> Dict[str, int]:
        stmt = (
            select(ChannelMessage.channel, func.count().label("count"))
            .where(ChannelMessage.organization_id == org_id, ChannelMessage.created_at >= since)
            .group_by(ChannelMessage.channel)
        )
        result = await db.execute(stmt)
        return {row.channel: row.count for row in result.all()}
