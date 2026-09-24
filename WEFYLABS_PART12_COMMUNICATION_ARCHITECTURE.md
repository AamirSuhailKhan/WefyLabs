# WEFYLABS PART 12 — COMMUNICATION ARCHITECTURE

**Communication Hub + Unified Conversation Transport + Web Chat + Email + SMS Foundation + Message Orchestration + Delivery Tracking + Human Handoff + AI Workforce Integration**

Status date: 2026-09-22
Scope: reconciliation and hardening of the *existing* omnichannel communication engine into one canonical transport layer.

> **This part did not build a second communication system.** It extends the
> existing engine (`app/modules/communication/`, data model `communication_models.py`)
> with a canonical channel vocabulary, a truthful channel status service, an
> outbound send gate, a single transport facade (the *Communication Hub*), and a
> code-enforced WhatsApp kill-switch.

---

## 1. Architecture

```
                       WEB   EMAIL   SMS        (WHATSAPP: hard-disabled)
                         │     │      │
                         ▼     ▼      ▼
                   CHANNEL ADAPTERS  (provider_adapters/*)
                         │
                         ▼
                 COMMUNICATION HUB   (modules/communication/hub)
                ┌────────┴─────────┐
                │                  │
      OUTBOUND  ▼                  ▼  INBOUND
     ChannelGate            ConversationRouter
     DeliveryEngine         MessageNormalizer
     ChannelManager         ChannelMessage (timeline)
                │
                ▼
        PROVIDER (SMTP / Twilio / WebChat)
                │
                ▼
        DELIVERY TRACKING (DeliveryStatusRecord)
                │
                ▼
        CANONICAL EVENTS → AI WORKFORCE / REVENUE INTELLIGENCE
```

The Hub is deliberately thin. It does **not** re-implement transport; it enforces
policy and delegates to the existing engine so there is exactly one place where
channel authorization, idempotency and delivery recording happen.

---

## 2. Canonical Communication Domain (reused, not duplicated)

| Concept | Existing model | Notes |
|---|---|---|
| Conversation | `OmnichannelConversation` | one logical conversation per customer/org |
| Channel identity | `ConversationChannelLink` | email / phone / session → conversation |
| Control / handoff | `ConversationControl` | `ai` \| `human` \| `paused` |
| Message | `ChannelMessage` | channel-agnostic inbound + outbound |
| Attachment | `MessageAttachment` | storage reference, no duplicate media store |
| Delivery | `DeliveryStatusRecord` | immutable status log (queued→sent→delivered→read) |
| Outbound queue | `OutboundQueue` | DB-persisted, restart-safe |
| Inbound queue | `InboundQueue` | webhook dedupe + replay protection |
| Template | `MessageTemplate` | versioned, per channel |

No new tables were required for this part.

---

## 3. Canonical Channel Vocabulary

`app/modules/communication/channels/enums.py`

* `Channel`: `WEB, EMAIL, SMS, WHATSAPP, TELEGRAM, VOICE, INSTAGRAM, FACEBOOK, API, OTHER`
* `Channel.normalize()` maps legacy strings (`webchat`, `in_app`, `whatsapp_cloud`, `smtp`, `twilio`, …) to the canonical value.
* `ChannelEnablementState`: `ENABLED, DISABLED, CONFIGURED, NOT_CONFIGURED, STAGING, ERROR`
* `MessageActorType`: `CUSTOMER, HUMAN, AI_AGENT, AUTOMATION, SYSTEM`
* `MessageDeliveryState`: `RECEIVED, QUEUED, SENDING, SENT, DELIVERED, READ, FAILED, CANCELLED, UNKNOWN`

> Adding an enum value **never** activates a channel. Activation requires a
> configured provider *and* an enabled kill-switch.

---

## 4. Channel Status (truthful, never "adapter exists == live")

`app/modules/communication/channels/status.py`

`ChannelStatusService` derives state from two independent inputs:

1. the per-channel enablement flag in settings, and
2. the provider's own `verify_configuration()` readiness check.

| Channel | Provider | Default state | Notes |
|---|---|---|---|
| WEB | `webchat` | **ENABLED** | in-app/websocket; no external creds |
| EMAIL | `smtp_email` (Brevo) | ENABLED if SMTP configured, else **NOT_CONFIGURED** | reuses existing Brevo SMTP path |
| SMS | `sms_gateway` (Twilio/generic) | **DISABLED** (`SMS_ENABLED=false`) | truthful `CONFIGURATION_REQUIRED` if enabled without creds |
| WHATSAPP | `whatsapp_cloud` | **DISABLED** | hard-blocked; not exposed by the Hub |
| TELEGRAM | `telegram` | enabled flag, provider-gated | pre-existing channel, unchanged |
| VOICE / INSTAGRAM / FACEBOOK | — | **DISABLED** | not implemented (future) |

---

## 5. Outbound Send Gate

`app/modules/communication/channels/gate.py`

`ensure_channel_sendable(channel)` fails closed and raises `ChannelNotSendableError`
(carrying a machine-readable `state`) unless the channel is `ENABLED`. Every
outbound path must pass through this gate before persisting or dispatching.

The `POST /communication/v2/conversations/{id}/send` and `.../human-reply`
endpoints call `_authorize_outbound_channel()` and return **HTTP 409** for a
disabled/unavailable channel.

### 5a. Follow-Up Engine Channel Selection

`app/modules/follow_up/channel_selection/channel_selector.py`

The follow-up engine's `ChannelSelector.select_channel()` is **availability-aware**:
it orders the policy-permitted channels by priority and returns the first one whose
`ChannelStatusService` state is `ENABLED`. Disabled, not-configured and future
channels (including WhatsApp and SMS-by-default) are skipped. If no permitted
channel is deliverable it returns `None`, and the orchestrator suppresses the
follow-up with reason `NO_AVAILABLE_CHANNEL` rather than queueing an
undeliverable message.

### 5b. Follow-Up Dispatch via the Hub

`FollowUpOrchestratorService.dispatch_execution()` (exposed as
`POST /api/v1/v1/followups/{execution_id}/dispatch`) is the follow-up engine's
dispatch path. It routes the scheduled execution's message through
`CommunicationHub.send_message()` — **not** to a provider directly — so channel
gating, canonical vocabulary, idempotency and outbound queueing are centralized.
The execution transitions to `DISPATCHED`; a second call returns
`already_dispatched` and creates no duplicate message. A disabled channel is
rejected with `409`.

### 5c. Sales-Action Channel Selection Defaults

`SalesActionDomainService._resolve_default_channel()` resolves the outbound channel
from availability (policy-allowed channels first, then platform fallbacks such as the
web/in-app channel) and passes it to
`SalesActionPolicyEngine.evaluate_decision(default_channel=…)`. The historical
hardcoded `CommunicationChannel.WHATSAPP` default is gone, so the engine no longer
recommends a disabled channel. `RealDeliveryEngine` normalizes the canonical channel
to a registered provider key (e.g. `IN_APP`/`web` → `webchat`) before dispatch.

### 5d. Per-Channel Status on the Policy API

`GET /api/v1/v1/followups/policies` includes a `channel_status` object, and
`GET /api/v1/v1/followups/channels/status` returns the same truthful summary. The
static follow-up routes were moved ahead of `/{lead_id}` to fix a route-shadowing bug
that made `GET /policies` unreachable.

### 5e. Consent ↔ Channel Alignment (Sales Action)

`SalesActionDomainService._resolve_channel_and_consent()`

Consent used to be evaluated against a hardcoded WhatsApp proxy while the delivery
channel was resolved separately. Consent is now evaluated **against the exact
availability-resolved channel**:

1. the ordered list of `ENABLED` channels is computed (`_ordered_available_channels`),
2. each available channel is consent-checked, and the **first consented** channel wins,
3. if none is consented, the first available channel is returned together with its own
   (blocking) consent status, so the decision is blocked honestly rather than silently
   switching channel,
4. if no channel is enabled at all, the action is blocked with `UNKNOWN` consent.

`ConsentGuard` treats *first-party* surfaces (`IN_APP`, `WEB`, `WEBCHAT`) as not
requiring a marketing opt-in — the customer is already interacting in-product. The
exemption is deliberately narrow: the global opt-out / denied / revoked check runs
first and still blocks first-party contact, and `EMAIL`/`SMS`/`WHATSAPP` continue to
require an explicit opt-in record.

### 5f. Scheduled Dispatch Worker

`app/modules/follow_up/tasks.py` — `follow_up.dispatch_due_executions`
(routed to `lead_queue`, beat entry `dispatch-due-followup-executions`, every 5 min)

Scans due `FollowUpExecution` rows and dispatches each through the Communication Hub.
It is the scheduled counterpart of §5b and shares all of its guarantees:

* **opt-in** — inert unless `FOLLOWUP_HUB_DISPATCH_ENABLED=true`, so enabling the
  schedule can never mass-send pre-existing queued rows by surprise,
* **atomically claimed** — `SCHEDULED → DISPATCHING` compare-and-set before any send,
  with a 15-minute stale-claim reclaim for crashed workers,
* **idempotent** — always calls the Hub with `idempotency_key=f"followup:{id}"`,
* **tenant scoped** — dispatching under each row's own `organization_id`,
* **bounded** — `limit` per batch and a 300 s task time limit,
* **fail-safe** — a disabled/unconfigured channel *suppresses* the row with
  `NO_AVAILABLE_CHANNEL` instead of sending, and an undeliverable row is suppressed
  rather than retried forever.

### 5g. Operator Channel Status UI

The follow-up dashboard (`apps/web/src/app/dashboard/follow-ups/page.tsx`) renders a
**Delivery Channels** panel from `GET /followups/channels/status`. Every channel is
shown with its truthful state (`Live` / `Configured` / `Staging` / `Not configured` /
`Disabled` / `Error`) and the blocked channels are listed explicitly, so operators can
see which channels follow-ups will actually dispatch on — no channel is presented as
omnichannel-live just because an adapter exists.

---

## 6. Communication Hub

`app/modules/communication/hub/communication_hub.py`

```python
hub = CommunicationHub()

# OUTBOUND — the single supported send path
await hub.send_message(
    db=db, organization_id=org, lead_id=lead,
    channel=Channel.EMAIL, content="...", recipient_identifier="a@b.com",
    actor_type=MessageActorType.AI_AGENT, actor_id=agent_id,
)

# INBOUND — normalize + dedupe + persist
await hub.ingest_inbound(db=db, dto=inbound_dto,
                         organization_id=org, lead_id=lead)

# INTROSPECTION
await hub.get_channel_status(Channel.SMS)
await hub.get_channel_summary()
```

Outbound pipeline: **gate → resolve/create conversation → `DeliveryEngine.enqueue`
(ChannelMessage + OutboundQueue + queued status) → worker dispatch → delivery
tracking**.

Inbound pipeline: **channel normalize → (disabled-channel reject) → conversation
route (cross-channel continuity) → normalizer (idempotency) → ChannelMessage**.

---

## 7. WhatsApp Hard Block (intentional)

* Settings: `WHATSAPP_ENABLED: bool = False` (single source of truth).
* `ChannelManager` always passes the flag to `WhatsAppCloudProvider`.
* The adapter refuses to send when the flag is `False`, returning
  `DeliveryStatusEnum.BLOCKED` / `error_code="CHANNEL_DISABLED"` — never a fake wamid.
* `ChannelStatusService` reports WhatsApp as `DISABLED` **regardless** of credentials.
* `CommunicationHub` never exposes WhatsApp for send.

`enabled=None` (direct provider construction, e.g. tests) preserves the legacy
un-gated behaviour; only the runtime `ChannelManager` path is gated.

---

## 8. Identity, Deduplication, Continuity

* **Identity**: reuses the existing Customer Identity / `Identity` system. No new identity engine.
* **Deduplication**: `ChannelMessage.idempotency_key` (inbound: provider+message id hash; outbound: deterministic key) and `OutboundQueue.idempotency_key`. Duplicate webhooks return `{"status": "duplicate"}` and create no second message.
* **Caller-supplied idempotency**: `CommunicationHub.send_message(..., idempotency_key=...)` and `DeliveryEngine.enqueue(..., idempotency_key=...)` accept a deterministic key. A repeat call with the same key returns the already-persisted message (`SendResult.duplicate=True`) instead of enqueueing a second send, which is what makes the scheduled dispatcher (§5f) safe to retry. `ChannelMessage.idempotency_key` is `UNIQUE`, so the database is the final backstop.
* **Cross-channel continuity**: `ConversationRouter` resolves by channel identity first, then by existing lead conversation, so web → email joins one logical conversation.

---

## 9. Human Handoff

Reuses `ConversationControl` + `HumanTakeoverService` (`ai` / `human` / `paused`).
The control record is the authority the AI checks before replying; handoff
generates a briefing (no chain-of-thought). Resuming AI is an explicit action.

---

## 10. Events, Delivery Tracking, Retries

* `DeliveryStatusRecord` is the immutable delivery log; `ChannelMessage.delivery_status` is the denormalized current state.
* States: `queued → sent → delivered → read`, with `failed`/`retry`/`dead_letter`.
* Retries: exponential backoff, bounded by `max_retries`; terminal failures move to `dead_letter`. Non-retryable errors (invalid recipient, auth, config-required, channel-disabled) do not retry.

---

## 11. AI Workforce & Domain Integrations

* The Hub is transport only. Business logic (qualification, matching, appointment, revenue) stays in its domain service; channels never mutate domain state directly.
* The AI Workforce continues to reach the Hub rather than providers directly, so channel authorization and idempotency are centralized.
* `RealDeliveryEngine` (safety-guarded dispatch used by Sales Action / Revenue Autopilot) remains the policy-heavy executor for agent-approved outreach; the Hub is the canonical, lightweight transport facade for conversation messages.

---

## 12. Security

* Tenant scoping on every conversation/message lookup (`organization_id`).
* `CommunicationHub.send_message(conversation_id=...)` rejects conversations outside the caller's organization.
* Outbound endpoints authorize server-side; the frontend cannot choose `actor_type` or tenant.
* Webhooks verify provider signatures (e.g. Meta HMAC) before processing; tenant is never taken from the webhook body.
* WhatsApp cannot be activated by data — only by an explicit deployment flag, and never from a request.

---

## 13. Provider Reality Status (as of this part)

| Channel | Status |
|---|---|
| WEB | **LIVE / VERIFIED** (provider + status + hub tests) |
| EMAIL | **CONFIGURED when SMTP present; code path LIVE** — live send not exercised in this session |
| SMS | **DISABLED / NOT CONFIGURED** (foundation only; no fake success) |
| WHATSAPP | **DISABLED (intentional, code-enforced)** |
| TELEGRAM | pre-existing; **provider-configured only** |
| VOICE / INSTAGRAM / FACEBOOK | **FUTURE / NOT IMPLEMENTED** |

---

## 14. Known Limitations

* The follow-up dashboard now shows truthful channel status (§5g); the remaining communication console screens (inbox/detail) were **not** modified in this part.
* No `CommunicationHub` REST endpoint was added — the Hub is a service facade layered on the existing `/communication/v2` API. Wiring the existing routers fully through the Hub is incremental follow-up work.
* The scheduled dispatch worker (§5f) ships **disabled by default** (`FOLLOWUP_HUB_DISPATCH_ENABLED=false`). Turning it on is a deliberate operator action because it will drain every already-due `SCHEDULED` execution.
* The `web`-vs-`webchat` string: the Hub stores the canonical `web` channel on records it creates; the legacy v2 router still accepts/stores `webchat`. `Channel.normalize` handles both.
* SMS remains deliberately disabled; activating it requires credentials **and** `SMS_ENABLED=true`.
* Retention policy for messages is unchanged (no destructive auto-deletion).
