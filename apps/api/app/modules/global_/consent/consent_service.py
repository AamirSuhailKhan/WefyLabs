"""
ConsentService — Per-Lead, Per-Channel Consent Management
==========================================================
Consent must NEVER be assumed from lead existence.
Communication services MUST check ConsentService before dispatch.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.global_models import ConsentRecord

logger = logging.getLogger(__name__)


class ConsentService:
    """
    Manages per-lead, per-channel consent records.
    Consent is checked by:
      - CommunicationService (before WhatsApp/SMS/Email dispatch)
      - WorkflowEngine (before automated outreach steps)
      - PolicyService (as part of CONSENT policy evaluation)
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def has_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,          # WHATSAPP | SMS | EMAIL | VOICE | PUSH
        purpose: str = "marketing",
    ) -> bool:
        """
        Returns True if an active, non-expired consent record exists.
        Returns False if no consent, withdrawn, or expired.
        """
        record = await self._get_active_consent(lead_id, organization_id, channel, purpose)
        return record is not None

    async def get_consent_status(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,
        purpose: str = "marketing",
    ) -> str:
        """
        Returns consent status: GRANTED | DENIED | WITHDRAWN | EXPIRED | UNKNOWN
        """
        # Check for any record (active or not)
        stmt = (
            select(ConsentRecord)
            .where(and_(
                ConsentRecord.lead_id == lead_id,
                ConsentRecord.organization_id == organization_id,
                ConsentRecord.channel == channel,
                ConsentRecord.purpose == purpose,
            ))
            .order_by(ConsentRecord.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            return "UNKNOWN"

        if record.status == "GRANTED":
            now = datetime.now(timezone.utc)
            if record.expires_at and record.expires_at < now:
                return "EXPIRED"
            return "GRANTED"

        return record.status

    async def grant_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,
        purpose: str,
        source: str,           # FORM | IMPORT | EXPLICIT | API | INFERRED
        expires_at: Optional[datetime] = None,
    ) -> ConsentRecord:
        """Grant or update consent for a lead+channel+purpose."""
        now = datetime.now(timezone.utc)

        # Check for existing record to update
        existing = await self._get_latest_consent(lead_id, organization_id, channel, purpose)
        if existing:
            existing.status = "GRANTED"
            existing.source = source
            existing.granted_at = now
            existing.withdrawn_at = None
            existing.expires_at = expires_at
            await self._db.flush()
            logger.info(f"[Consent] Updated GRANTED: lead={lead_id} channel={channel} purpose={purpose}")
            return existing

        record = ConsentRecord(
            lead_id=lead_id,
            organization_id=organization_id,
            channel=channel,
            status="GRANTED",
            purpose=purpose,
            source=source,
            granted_at=now,
            expires_at=expires_at,
        )
        self._db.add(record)
        await self._db.flush()
        logger.info(f"[Consent] GRANTED: lead={lead_id} channel={channel} purpose={purpose}")
        return record

    async def withdraw_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,
        purpose: str = "marketing",
    ) -> bool:
        """Mark consent as withdrawn. Communication must stop immediately."""
        now = datetime.now(timezone.utc)
        existing = await self._get_latest_consent(lead_id, organization_id, channel, purpose)

        if existing:
            existing.status = "WITHDRAWN"
            existing.withdrawn_at = now
            await self._db.flush()
            logger.info(f"[Consent] WITHDRAWN: lead={lead_id} channel={channel} purpose={purpose}")
            return True

        # Create a WITHDRAWN record to prevent re-inference
        record = ConsentRecord(
            lead_id=lead_id,
            organization_id=organization_id,
            channel=channel,
            status="WITHDRAWN",
            purpose=purpose,
            source="EXPLICIT",
            withdrawn_at=now,
        )
        self._db.add(record)
        await self._db.flush()
        return True

    async def deny_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,
        purpose: str = "marketing",
    ) -> ConsentRecord:
        """Mark consent as explicitly denied."""
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            lead_id=lead_id,
            organization_id=organization_id,
            channel=channel,
            status="DENIED",
            purpose=purpose,
            source="EXPLICIT",
        )
        self._db.add(record)
        await self._db.flush()
        logger.info(f"[Consent] DENIED: lead={lead_id} channel={channel} purpose={purpose}")
        return record

    async def _get_active_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,
        purpose: str,
    ) -> Optional[ConsentRecord]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(ConsentRecord)
            .where(and_(
                ConsentRecord.lead_id == lead_id,
                ConsentRecord.organization_id == organization_id,
                ConsentRecord.channel == channel,
                ConsentRecord.purpose == purpose,
                ConsentRecord.status == "GRANTED",
                ConsentRecord.withdrawn_at.is_(None),
            ))
            .order_by(ConsentRecord.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        record = result.scalar_one_or_none()

        if record and record.expires_at and record.expires_at < now:
            return None
        return record

    async def _get_latest_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: str,
        purpose: str,
    ) -> Optional[ConsentRecord]:
        stmt = (
            select(ConsentRecord)
            .where(and_(
                ConsentRecord.lead_id == lead_id,
                ConsentRecord.organization_id == organization_id,
                ConsentRecord.channel == channel,
                ConsentRecord.purpose == purpose,
            ))
            .order_by(ConsentRecord.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
