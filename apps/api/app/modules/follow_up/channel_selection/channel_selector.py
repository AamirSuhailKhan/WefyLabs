"""
Channel Selection & Scoring Engine
==================================
Selects the most appropriate *available* communication channel based on customer
preferences, organization policy, message urgency — and whether the channel can
actually deliver.

Part 12 invariant: the selector MUST NOT return a channel that is disabled or
unavailable. It consults the canonical ``ChannelStatusService`` (config flag +
provider readiness) and only returns a channel whose state is ``ENABLED``. If no
permitted channel is available it returns ``None`` so the caller can skip the
follow-up instead of queueing an undeliverable message.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy
from app.modules.communication.channels.enums import (
    Channel,
    ChannelEnablementState,
)
from app.modules.communication.channels.status import ChannelStatusService

logger = logging.getLogger(__name__)

_DEFAULT_ALLOWED = ["WHATSAPP", "EMAIL"]
_DOCUMENT_REASONS = ("DOCUMENT_REQUEST", "PAYMENT_PLAN_UPDATE")


class ChannelSelector:
    """
    Evaluates channel suitability and returns the best **available** channel.

    Returns ``(channel_token, score)`` where ``channel_token`` is ``None`` when no
    permitted channel is currently enabled/available.
    """

    def __init__(self, status_service: Optional[ChannelStatusService] = None):
        self._status_service = status_service or ChannelStatusService()

    # ─── Candidate ordering (pure, unit-testable) ─────────────────────────────

    def order_candidates(
        self,
        policy: FollowUpPolicy,
        preferred_step_channel: str = "WHATSAPP",
        reason_type: str = "UNANSWERED_INQUIRY",
    ) -> List[Tuple[str, float]]:
        """Return ``[(channel_token, score), ...]`` in priority order.

        Only channels permitted by the policy are considered. The first entry is
        the preferred choice; later entries are fallbacks.
        """
        allowed = [
            str(c).strip().upper()
            for c in (policy.allowed_channels or _DEFAULT_ALLOWED)
            if str(c).strip()
        ]
        if not allowed:
            allowed = list(_DEFAULT_ALLOWED)

        ordered: List[Tuple[str, float]] = []
        seen = set()

        def _add(token: Optional[str], score: float) -> None:
            tok = (token or "").strip().upper()
            if tok and tok in allowed and tok not in seen:
                seen.add(tok)
                ordered.append((tok, score))

        # 1. Document / payment reasons prefer Email when permitted.
        if reason_type in _DOCUMENT_REASONS:
            _add("EMAIL", 0.95)

        # 2. Preferred step channel when permitted.
        _add(preferred_step_channel, 0.90)

        # 3. Remaining permitted channels as fallbacks, in policy order.
        for ch in allowed:
            _add(ch, 0.75)

        return ordered

    # ─── Availability-aware selection (async) ─────────────────────────────────

    async def select_channel(
        self,
        lead: Lead,
        policy: FollowUpPolicy,
        preferred_step_channel: str = "WHATSAPP",
        reason_type: str = "UNANSWERED_INQUIRY",
        organization_id: Optional[str] = None,
    ) -> Tuple[Optional[str], float]:
        """Return the best enabled channel, or ``(None, 0.0)`` if none available.

        A channel is available only when ``ChannelStatusService`` reports its
        state as ``ENABLED``. Disabled / not-configured / future channels are
        skipped, so this never selects WhatsApp (disabled), SMS (not configured)
        or any other unavailable channel.
        """
        candidates = self.order_candidates(policy, preferred_step_channel, reason_type)

        for token, score in candidates:
            canonical = Channel.normalize(token)
            try:
                status = await self._status_service.get_status(canonical)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "[ChannelSelector] Status lookup failed for %s: %s — skipping", token, exc
                )
                continue

            if status.state == ChannelEnablementState.ENABLED:
                return token, score

            logger.info(
                "[ChannelSelector] Skipping channel=%s state=%s reason=%s (org=%s)",
                token, status.state.value, status.reason, organization_id,
            )

        logger.warning(
            "[ChannelSelector] No available channel for policy=%s allowed=%s (org=%s)",
            getattr(policy, "organization_id", None), policy.allowed_channels, organization_id,
        )
        return None, 0.0
