"""
Part 12 — Sales-Action Consent ↔ Channel Alignment Tests
=======================================================
The sales-action consent guard used to evaluate a hardcoded WhatsApp proxy while
the delivery channel was resolved separately. Consent is now evaluated against
the *availability-resolved* channel.

Covers:
  * first-party in-product surfaces need no marketing opt-in,
  * an explicit opt-out still blocks first-party contact,
  * marketing channels (email/SMS/WhatsApp) still require explicit opt-in,
  * the resolver never returns a disabled channel and prefers a consented one,
  * the decision pipeline blocks honestly when no available channel is consented.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.models.broker import Broker
from app.models.follow_up_models import CommunicationConsent
from app.models.lead import Lead
from app.modules.communication.channels import Channel, ChannelEnablementState
from app.modules.communication.channels.status import ChannelStatusService
from app.modules.sales_action.guards.consent_guard import FIRST_PARTY_CHANNELS, ConsentGuard
from app.modules.sales_action.service import SalesActionDomainService
from app.modules.sales_action.taxonomies import (
    CommunicationChannel,
    ConsentStatus,
    SalesActionStatus,
)


@pytest.fixture
def availability(monkeypatch):
    """Deterministic availability: EMAIL + WEB enabled, everything else not."""
    enabled = {Channel.EMAIL, Channel.WEB}

    async def fake_get_status(self, channel):
        state = (
            ChannelEnablementState.ENABLED
            if channel in enabled
            else ChannelEnablementState.DISABLED
        )
        return SimpleNamespace(channel=channel.value, state=state, enabled=state == ChannelEnablementState.ENABLED)

    monkeypatch.setattr(ChannelStatusService, "get_status", fake_get_status)
    return enabled


async def _make_lead(db_session, broker, **overrides) -> Lead:
    values = {
        "id": uuid.uuid4(),
        "broker_id": broker.id,
        "name": "Consent Alignment Lead",
        "phone": f"+9715{uuid.uuid4().int % 10**8:08d}",
        "status": "active",
        "pipeline_stage": "QUALIFIED",
    }
    values.update(overrides)
    lead = Lead(**values)
    db_session.add(lead)
    await db_session.commit()
    return lead


async def _add_consent(db_session, lead, org_id, channel: str, status: str) -> None:
    db_session.add(
        CommunicationConsent(
            lead_id=str(lead.id),
            organization_id=org_id,
            channel=channel,
            status=status,
        )
    )
    await db_session.commit()


# ─── 1. Consent guard semantics ───────────────────────────────────────────────

def test_first_party_channel_set_is_narrow():
    assert FIRST_PARTY_CHANNELS == {"IN_APP", "WEB", "WEBCHAT"}


async def test_first_party_channel_needs_no_marketing_opt_in(db_session, test_broker):
    permitted, status, reason = await ConsentGuard(db_session).evaluate_consent(
        lead_id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        channel=CommunicationChannel.IN_APP,
    )
    assert permitted is True
    assert status == ConsentStatus.GRANTED
    assert reason is None


async def test_first_party_channel_still_blocked_by_explicit_opt_out(db_session, test_broker):
    lead = await _make_lead(db_session, test_broker)
    await _add_consent(db_session, lead, str(test_broker.id), "WHATSAPP", "OPTED_OUT")

    permitted, status, _ = await ConsentGuard(db_session).evaluate_consent(
        lead_id=str(lead.id),
        organization_id=str(test_broker.id),
        channel=CommunicationChannel.IN_APP,
    )
    assert permitted is False
    assert status == ConsentStatus.DENIED


async def test_email_still_requires_explicit_opt_in(db_session, test_broker):
    permitted, status, reason = await ConsentGuard(db_session).evaluate_consent(
        lead_id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        channel=CommunicationChannel.EMAIL,
    )
    assert permitted is False
    assert status == ConsentStatus.UNKNOWN
    assert reason is not None


# ─── 2. Channel + consent resolution ──────────────────────────────────────────

async def test_resolver_never_returns_a_disabled_channel(db_session, test_broker, availability):
    service = SalesActionDomainService(db_session)
    policy = await service.get_or_create_policy(str(test_broker.id))

    channel, consent_status, _ = await service._resolve_channel_and_consent(
        policy=policy,
        lead_id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        is_direct_customer_inquiry=False,
    )

    # WhatsApp is the policy default but is disabled → first-party in-app is used.
    assert channel != CommunicationChannel.WHATSAPP
    assert channel == CommunicationChannel.IN_APP
    assert consent_status == ConsentStatus.GRANTED


async def test_resolver_prefers_the_consented_channel(db_session, test_broker, availability):
    lead = await _make_lead(db_session, test_broker)
    await _add_consent(db_session, lead, str(test_broker.id), "EMAIL", "OPTED_IN")

    service = SalesActionDomainService(db_session)
    policy = await service.get_or_create_policy(str(test_broker.id))
    channel, consent_status, _ = await service._resolve_channel_and_consent(
        policy=policy,
        lead_id=str(lead.id),
        organization_id=str(test_broker.id),
        is_direct_customer_inquiry=False,
    )

    assert channel == CommunicationChannel.EMAIL
    assert consent_status == ConsentStatus.GRANTED


async def test_resolver_reports_denied_when_every_available_channel_is_blocked(
    db_session, test_broker, availability
):
    lead = await _make_lead(db_session, test_broker)
    await _add_consent(db_session, lead, str(test_broker.id), "WHATSAPP", "OPTED_OUT")

    service = SalesActionDomainService(db_session)
    policy = await service.get_or_create_policy(str(test_broker.id))
    channel, consent_status, reason = await service._resolve_channel_and_consent(
        policy=policy,
        lead_id=str(lead.id),
        organization_id=str(test_broker.id),
        is_direct_customer_inquiry=False,
    )

    assert channel != CommunicationChannel.WHATSAPP
    assert consent_status in (ConsentStatus.DENIED, ConsentStatus.REVOKED)
    assert reason


async def test_resolver_reports_no_available_channel(monkeypatch, db_session, test_broker):
    async def everything_disabled(self, channel):
        return SimpleNamespace(
            channel=channel.value,
            state=ChannelEnablementState.DISABLED,
            enabled=False,
        )

    monkeypatch.setattr(ChannelStatusService, "get_status", everything_disabled)

    service = SalesActionDomainService(db_session)
    policy = await service.get_or_create_policy(str(test_broker.id))
    channel, consent_status, reason = await service._resolve_channel_and_consent(
        policy=policy,
        lead_id=str(uuid.uuid4()),
        organization_id=str(test_broker.id),
        is_direct_customer_inquiry=False,
    )

    assert channel == CommunicationChannel.WHATSAPP
    assert consent_status == ConsentStatus.UNKNOWN
    assert "available" in reason.lower()


# ─── 3. Decision pipeline wiring ──────────────────────────────────────────────

async def test_decision_uses_available_channel_and_is_not_blocked(db_session, availability):
    broker = Broker(id=uuid.uuid4(), name="Agent Aligned", email=f"aligned_{uuid.uuid4()}@example.com")
    org_id = str(broker.id)
    lead = await _make_lead(db_session, broker, pipeline_stage="QUALIFIED", budget_max=3000000)
    await _add_consent(db_session, lead, org_id, "WHATSAPP", "OPTED_IN")

    decision = await SalesActionDomainService(db_session).evaluate_next_sales_action(
        str(lead.id), org_id, broker=broker
    )

    assert decision.recommended_channel != CommunicationChannel.WHATSAPP
    assert decision.recommended_channel == CommunicationChannel.IN_APP
    assert decision.status in (
        SalesActionStatus.APPROVED,
        SalesActionStatus.QUEUED,
        SalesActionStatus.HUMAN_REVIEW,
    )


async def test_decision_is_blocked_for_globally_opted_out_lead(db_session, availability):
    broker = Broker(id=uuid.uuid4(), name="Agent Blocked", email=f"blocked_{uuid.uuid4()}@example.com")
    org_id = str(broker.id)
    lead = await _make_lead(db_session, broker, pipeline_stage="QUALIFIED", budget_max=3000000)
    await _add_consent(db_session, lead, org_id, "WHATSAPP", "OPTED_OUT")

    decision = await SalesActionDomainService(db_session).evaluate_next_sales_action(
        str(lead.id), org_id, broker=broker
    )

    assert decision.status == SalesActionStatus.BLOCKED
    assert decision.recommended_channel != CommunicationChannel.WHATSAPP
