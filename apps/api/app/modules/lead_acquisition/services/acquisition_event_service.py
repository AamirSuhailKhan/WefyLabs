"""
Part 21.1 — Lead Acquisition Event Service
============================================
Records and manages LeadAcquisitionEvent entities.

Every incoming signal (website, WhatsApp, Meta, Google, webhook) creates
exactly ONE acquisition event. Idempotency is enforced via unique key.

Security: organization_id from authenticated context only.
"""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.acquisition_models import LeadAcquisitionEvent

logger = logging.getLogger(__name__)


class AcquisitionEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_event(
        self,
        organization_id: str,
        source_id: Optional[str],
        campaign_id: Optional[str],
        channel: Optional[str],
        external_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        raw_event_reference: Optional[str] = None,
        provider_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> tuple[LeadAcquisitionEvent, bool]:
        """
        Record an acquisition event.

        Returns:
            (event, is_new) — is_new=False means idempotent duplicate
        """
        # Generate idempotency key if not provided
        if not idempotency_key:
            components = f"{organization_id}:{source_id}:{external_id}:{occurred_at}"
            idempotency_key = hashlib.sha256(components.encode()).hexdigest()[:64]

        # Check for duplicate event
        existing = await self._find_by_idempotency_key(organization_id, idempotency_key)
        if existing:
            logger.info(f"[ACQ_EVENT] Idempotent duplicate for key={idempotency_key[:16]}... org={organization_id}")
            return existing, False

        # Hash IP and user_agent for privacy (truncate, not store raw)
        ip_fp = hashlib.sha256(ip_address.encode()).hexdigest()[:16] if ip_address else None
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16] if user_agent else None

        event = LeadAcquisitionEvent(
            organization_id=organization_id,
            source_id=source_id,
            campaign_id=campaign_id,
            external_id=external_id,
            provider_name=provider_name,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            raw_event_reference=raw_event_reference,
            idempotency_key=idempotency_key,
            channel=channel,
            ip_fingerprint=ip_fp,
            user_agent_hash=ua_hash,
            status="pending",
        )
        self.db.add(event)
        await self.db.flush()
        logger.info(f"[ACQ_EVENT] Recorded new event {event.id} channel={channel} org={organization_id}")
        return event, True

    async def mark_processed(self, event: LeadAcquisitionEvent) -> None:
        event.status = "processed"
        await self.db.flush()

    async def mark_rejected(self, event: LeadAcquisitionEvent, reason: str) -> None:
        event.status = "rejected"
        logger.warning(f"[ACQ_EVENT] Rejected event {event.id}: {reason}")
        await self.db.flush()

    async def _find_by_idempotency_key(
        self, organization_id: str, key: str
    ) -> Optional[LeadAcquisitionEvent]:
        stmt = select(LeadAcquisitionEvent).where(
            and_(
                LeadAcquisitionEvent.organization_id == organization_id,
                LeadAcquisitionEvent.idempotency_key == key,
            )
        )
        return (await self.db.execute(stmt)).scalars().first()
