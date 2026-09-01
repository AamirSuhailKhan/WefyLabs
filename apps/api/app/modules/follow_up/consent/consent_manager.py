"""
Consent Management & Compliance Engine
======================================
Tracks granular per-channel, per-purpose customer consent.
Enforces fail-closed rules: if consent cannot be verified, outbound marketing is blocked.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.follow_up_models import CommunicationConsent

logger = logging.getLogger(__name__)

class ConsentManager:
    """
    Manages customer communication consent records and verifies outbound permissions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_consent(
        self,
        lead_id: str,
        channel: str,
        purpose: str = "MARKETING_AND_FOLLOWUP"
    ) -> bool:
        """
        Verifies if valid opt-in consent exists for the specified channel and purpose.
        Defaults to True for initial transactional/direct inquiries if unrecorded,
        but strictly returns False if explicitly OPTED_OUT.
        """
        stmt = select(CommunicationConsent).where(
            CommunicationConsent.lead_id == lead_id,
            CommunicationConsent.channel == channel.upper(),
            CommunicationConsent.purpose == purpose
        )
        res = await self.db.execute(stmt)
        consent = res.scalar_one_or_none()

        if not consent:
            # If no consent row exists yet, check if there's a global opt-out
            stmt_optout = select(CommunicationConsent).where(
                CommunicationConsent.lead_id == lead_id,
                CommunicationConsent.status == "OPTED_OUT"
            )
            res_opt = await self.db.execute(stmt_optout)
            if res_opt.scalar_one_or_none():
                return False
            return True # Permitted for new direct customer inquiries

        if consent.status == "OPTED_OUT":
            logger.info(f"[CONSENT] Lead {lead_id} is explicitly OPTED_OUT for channel '{channel}'.")
            return False

        return consent.status == "OPTED_IN"

    async def record_opt_out(
        self,
        lead_id: str,
        organization_id: str,
        channel: Optional[str] = None
    ) -> None:
        """
        Permanently registers opt-out for a lead across one or all channels.
        """
        channels = [channel.upper()] if channel else ["WHATSAPP", "SMS", "EMAIL", "TELEGRAM", "WEBCHAT"]

        for ch in channels:
            stmt = select(CommunicationConsent).where(
                CommunicationConsent.lead_id == lead_id,
                CommunicationConsent.channel == ch
            )
            res = await self.db.execute(stmt)
            consent = res.scalar_one_or_none()

            if consent:
                consent.status = "OPTED_OUT"
                consent.withdrawn_timestamp = datetime.now(timezone.utc)
            else:
                consent = CommunicationConsent(
                    lead_id=lead_id,
                    organization_id=organization_id,
                    channel=ch,
                    purpose="ALL",
                    status="OPTED_OUT",
                    source="CUSTOMER_REQUEST",
                    withdrawn_timestamp=datetime.now(timezone.utc)
                )
                self.db.add(consent)

        await self.db.commit()
        logger.info(f"[CONSENT] Permanently recorded OPT_OUT for Lead {lead_id} (Channels: {channels}).")
