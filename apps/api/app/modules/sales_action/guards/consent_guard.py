"""
Part 21.5 — Communication Consent Guard
=======================================
Enforces granular per-channel, per-purpose customer consent.
Never assumes consent. Fail-closed on revoked/denied/unknown consent.

Part 12 note: *first-party* surfaces (the in-product web / in-app chat the
customer is actively using) are not marketing channels, so they do not require a
separate marketing opt-in. This exemption is deliberately narrow: an explicit
opt-out / denial / revocation on any channel still blocks first-party contact too
(the global opt-out check runs first and is unaffected).
"""
import logging
from typing import Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.follow_up_models import CommunicationConsent
from app.modules.sales_action.taxonomies import CommunicationChannel, ConsentStatus

logger = logging.getLogger(__name__)

# CommunicationChannel values that represent a first-party surface the customer is
# already interacting with in-product. These are not marketing channels.
FIRST_PARTY_CHANNELS = {"IN_APP", "WEB", "WEBCHAT"}


class ConsentGuard:
    """
    Evaluates customer communication consent records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_consent(
        self,
        lead_id: str,
        organization_id: str,
        channel: CommunicationChannel,
        purpose: str = "MARKETING_AND_FOLLOWUP",
        is_direct_customer_inquiry: bool = False,
    ) -> Tuple[bool, ConsentStatus, Optional[str]]:
        """
        Evaluates consent for outbound communication.
        Returns (is_permitted, consent_status, reason_if_blocked).
        """
        ch_str = channel.value.upper()

        # Check global opt-out first
        stmt_optout = select(CommunicationConsent).where(
            CommunicationConsent.lead_id == lead_id,
            CommunicationConsent.status.in_(["OPTED_OUT", "DENIED", "REVOKED"])
        )
        res_opt = await self.db.execute(stmt_optout)
        opt_record = res_opt.scalars().first()
        if opt_record:
            status = ConsentStatus.REVOKED if opt_record.status == "REVOKED" else ConsentStatus.DENIED
            return False, status, f"Customer communication is blocked (status: {opt_record.status})."

        # Check channel-specific consent record
        stmt_ch = select(CommunicationConsent).where(
            CommunicationConsent.lead_id == lead_id,
            CommunicationConsent.channel == ch_str
        )
        res_ch = await self.db.execute(stmt_ch)
        consent = res_ch.scalars().first()

        if not consent:
            if ch_str in FIRST_PARTY_CHANNELS:
                # First-party in-product surface: no marketing opt-in required.
                return True, ConsentStatus.GRANTED, None
            if is_direct_customer_inquiry:
                # Direct customer initiated inquiry allows initial transactional response
                return True, ConsentStatus.GRANTED, None
            return False, ConsentStatus.UNKNOWN, f"No explicit opt-in consent recorded for channel '{ch_str}'."

        c_status = (consent.status or "").upper()
        if c_status in ("OPTED_OUT", "DENIED"):
            return False, ConsentStatus.DENIED, f"Customer explicitly denied consent for channel '{ch_str}'."
        elif c_status == "REVOKED":
            return False, ConsentStatus.REVOKED, f"Customer revoked consent for channel '{ch_str}'."
        elif c_status == "EXPIRED":
            return False, ConsentStatus.EXPIRED, f"Customer consent expired for channel '{ch_str}'."
        elif c_status in ("OPTED_IN", "GRANTED"):
            return True, ConsentStatus.GRANTED, None

        return False, ConsentStatus.UNKNOWN, f"Unverified consent state '{c_status}' for channel '{ch_str}'."
