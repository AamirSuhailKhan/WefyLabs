"""
Part 12 — Follow-Up Channel Gating Tests
========================================
The follow-up engine's channel selection must consult `ChannelStatusService`
and never return a disabled/unavailable channel (e.g. WhatsApp).
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.models.follow_up_models import FollowUpPolicy
from app.modules.follow_up.channel_selection.channel_selector import ChannelSelector
from app.modules.communication.channels.enums import Channel, ChannelEnablementState
from app.modules.communication.channels.status import ChannelStatus, ChannelStatusService


def _policy(allowed):
    return FollowUpPolicy(
        id=str(uuid.uuid4()),
        organization_id=str(uuid.uuid4()),
        allowed_channels=allowed,
    )


_LEAD = SimpleNamespace(id=str(uuid.uuid4()), phone="+919876543210")


# ─── Candidate ordering (pure) ────────────────────────────────────────────────

def test_document_requests_prefer_email():
    sel = ChannelSelector()
    ordered = sel.order_candidates(
        _policy(["WHATSAPP", "EMAIL"]), reason_type="DOCUMENT_REQUEST"
    )
    assert ordered[0] == ("EMAIL", 0.95)
    assert {t for t, _ in ordered} == {"EMAIL", "WHATSAPP"}


def test_preferred_step_channel_ranked_before_fallbacks():
    sel = ChannelSelector()
    ordered = sel.order_candidates(
        _policy(["WHATSAPP", "EMAIL"]),
        preferred_step_channel="EMAIL",
        reason_type="UNANSWERED_INQUIRY",
    )
    assert ordered[0] == ("EMAIL", 0.90)


def test_candidates_are_restricted_to_policy_allowed():
    sel = ChannelSelector()
    ordered = sel.order_candidates(
        _policy(["EMAIL"]), preferred_step_channel="WHATSAPP"
    )
    # WHATSAPP is not permitted by policy, so it must not appear.
    assert {t for t, _ in ordered} == {"EMAIL"}


# ─── Availability-aware selection ─────────────────────────────────────────────

async def test_whatsapp_only_policy_yields_no_channel():
    sel = ChannelSelector()
    channel, score = await sel.select_channel(_LEAD, _policy(["WHATSAPP"]))
    assert channel is None
    assert score == 0.0


async def test_disabled_channel_is_skipped_for_enabled_fallback():
    sel = ChannelSelector()
    # WhatsApp (disabled) is preferred, but WEB is enabled and must be chosen.
    channel, score = await sel.select_channel(
        _LEAD, _policy(["WHATSAPP", "WEB"]), preferred_step_channel="WHATSAPP"
    )
    assert channel == "WEB"
    assert score == 0.75


async def test_enabled_channel_is_returned():
    sel = ChannelSelector()
    channel, _score = await sel.select_channel(_LEAD, _policy(["WEB"]))
    assert channel == "WEB"


async def test_sms_disabled_by_default_is_not_selected():
    sel = ChannelSelector()
    channel, score = await sel.select_channel(_LEAD, _policy(["SMS"]))
    assert channel is None
    assert score == 0.0


async def test_env_independent_disabled_state_with_stub_service():
    class _StubStatusService(ChannelStatusService):
        async def get_status(self, channel: Channel) -> ChannelStatus:
            return ChannelStatus(
                channel=channel.value,
                state=ChannelEnablementState.DISABLED,
                enabled=False,
                configured=True,
                implemented=True,
                reason="stubbed disabled",
            )

    sel = ChannelSelector(status_service=_StubStatusService())
    channel, score = await sel.select_channel(_LEAD, _policy(["EMAIL", "WEB"]))
    assert channel is None
    assert score == 0.0
