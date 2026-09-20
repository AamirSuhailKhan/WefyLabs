# WEFYLABS — CORE PRODUCT: PART 1 OF 8
# CUSTOMER IDENTITY + CONVERSATION + MEMORY FOUNDATION REPORT

**Project**: WefyLabs  
**Product**: Real Estate AI Revenue Operating System  
**Milestone**: Part 1 of 8 — Customer Identity + Conversation + Memory Foundation  
**Status**: `VERIFIED`  
**Execution Date**: September 18, 2026  

---

## Executive Summary

Part 1 establishes the canonical customer intelligence layer for WefyLabs. It fulfills all requirements without creating duplicate entities or parallel stacks:
- Established one canonical customer identity reusing `Lead` and `Identity`.
- Implemented a 3-tier deterministic identity resolution engine (`EXACT_MATCH`, `POSSIBLE_MATCH`, `NO_MATCH`).
- Created a structured customer requirement profile with negative preference retention and a strict 5-tier provenance hierarchy (`EXPLICIT`, `CRM`, `IMPORTED`, `SYSTEM`, `INFERRED`).
- Enforced the **Anti-Overwrite Rule**: AI inferences can never overwrite explicit customer statements.
- Unified the conversation and message domain around `OmnichannelConversation` and `ChannelMessage` with canonical sender types (`CUSTOMER`, `AI_AGENT`, `HUMAN_AGENT`, `SYSTEM`) and automated secret redaction.
- Built a 4-tier bounded memory architecture (`CURRENT_TURN`, `CURRENT_SESSION`, `CUSTOMER_MEMORY`, `CRM_MEMORY`) providing compact, token-budgeted AI context.
- Applied database migration `0027_customer_identity_canonical` adding native `email` to `leads` and `sender_type` to `channel_messages`.
- Verified 100% test pass rate across 39 backend tests and 0 TypeScript errors on the frontend.

---

## 1. Existing Entities Reused

Per the architectural mandate, zero duplicate entities were created:

| Domain | Entity Reused | Location | Role in Canonical Architecture | Status |
|---|---|---|---|---|
| **Customer Identity** | `Lead` | `apps/api/app/models/lead.py` | Authoritative operational customer identity in CRM | `VERIFIED` |
| **Identity Resolution** | `Identity`, `IdentityLink`, `IdentityAlias` | `apps/api/app/models/identity_models.py` | Permanent person node, alias indexing, cross-source link | `VERIFIED` |
| **Tenant Authority** | `Broker` / `Organization` | `apps/api/app/models/broker.py`, `organization.py` | Tenant ownership boundary (`broker_id` = `organization_id`) | `VERIFIED` |
| **Conversation** | `OmnichannelConversation` | `apps/api/app/models/communication_models.py` | Canonical multi-channel conversation envelope | `VERIFIED` |
| **Conversation Control** | `ConversationControl`, `ConversationChannelLink` | `apps/api/app/models/communication_models.py` | Real-time takeover state (`ai`, `human`, `paused`) & channel link | `VERIFIED` |
| **Message** | `ChannelMessage` | `apps/api/app/models/communication_models.py` | Canonical normalized message with sender type & direction | `VERIFIED` |
| **Customer Memory** | `MemoryRecord`, `MemoryVersion` | `apps/api/app/models/memory_models.py` | Long-term facts, negative preferences, version history | `VERIFIED` |
| **Objections & Feedback** | `MemoryObjection`, `MemoryPropertyFeedback` | `apps/api/app/models/memory_models.py` | Customer objection progression and structured rejection reasons | `VERIFIED` |
| **Event Bus** | `DomainEventBus`, `DomainEvent` | `apps/api/app/infrastructure/events/event_bus.py` | Central asynchronous enterprise event bus | `VERIFIED` |

---

## 2. New Entities & Extensions

No parallel `CustomerV2`, `LeadV2`, `ConversationV2`, or `MemoryV2` entities were created. Only necessary extensions and domain modules were implemented:

1. **Model Extensions**:
   - `Lead.email`: Added `String(255)` (nullable, indexed) to `leads` table and model.
   - `Lead.to_canonical_dict()`: Added helper producing canonical customer dictionary representation.
   - `ChannelMessage.sender_type`: Added `String(30)` (nullable, indexed) to `channel_messages` table and model.
   - `ChannelMessage.resolved_sender_type`: Dynamic property resolving `CUSTOMER`, `AI_AGENT`, `HUMAN_AGENT`, `SYSTEM`.
2. **New Module (`apps/api/app/modules/customer_intelligence/`)**:
   - `schemas.py`: Pydantic v2 schemas for Customer, Resolution, Requirements, Conversations, Messages, and Bounded Memory.
   - `service.py`: `CustomerIntelligenceService` encapsulating identity resolution, requirement provenance rules, conversation lifecycle, and bounded memory context.
   - `router.py`: REST API router mounted at `/api/v1/customers`.
3. **Database Migration**:
   - `apps/api/alembic/versions/0027_customer_identity_canonical.py`: Revision extending `leads` and `channel_messages`.

---

## 3. Canonical Customer Identity Architecture

The authoritative mappings for customer identity are:

- `CANONICAL_CUSTOMER_ENTITY`: `Lead` (`apps/api/app/models/lead.py`)
- `CANONICAL_CUSTOMER_ID`: `Lead.id` (`UUID`)
- `CANONICAL_TENANT_RELATION`: `Lead.broker_id` (`UUID`, foreign key to `brokers.id`, exposed as `organization_id`)
- `CANONICAL_LEAD_RELATION`: 1:1 direct identity (Lead is the customer entity in CRM, linked to `Identity` via `IdentityLink`)

### Attributes Supported:
- `name`: Full customer name
- `phone`: E.164 normalized phone number
- `email`: Normalized lowercase email
- `source`: Acquisition channel (`website_inquiry`, `whatsapp_forward`, `facebook`, `google`, `manual`)
- `status`: CRM lead status (`pending`, `active`, `qualified`, `converted`, `lost`)
- `pipeline_stage`: Configurable pipeline stage (`new`, `contacted`, `viewing`, `negotiating`, `closed_won`, `closed_lost`)
- `score`: Qualification score (`hot`, `warm`, `cold`, `unqualified`, `pending`)
- `score_confidence`: Confidence metric (0.0 to 1.0)
- `transaction_type`: `buy` | `rent` | `lease`
- `budget_min`, `budget_max`, `budget_currency`: Strict currency-budget pairing
- `preferred_locations`: Array/JSON list of localities
- `property_type`: Property classification
- `timeline`: `immediate` | `1_month` | `3_months` | `6_months`
- `loan_status`: `pre_approved` | `in_process` | `not_started`

---

## 4. Identity Resolution Architecture

Identity resolution is exposed via `POST /api/v1/customers/resolve`:

| Outcome | Trigger Criteria | Confidence | Action Taken |
|---|---|---|---|
| `EXACT_MATCH` | Phone, email, or `lead_id` matches an existing active customer within the tenant | `1.0` | Returns existing `customer_id`. Reuses record; prevents duplicate creation. |
| `POSSIBLE_MATCH` | Historical contact alias or candidate similarity found (0.85 – 0.94) within the tenant | `0.85 – 0.94` | Returns candidate details. **Never auto-merged**; flagged for human confirmation. |
| `NO_MATCH` | No matching phone, email, or identity node in tenant scope | `0.0` | Safe to create new customer. |

**Merge Safety Guard**: Cross-tenant candidates are strictly excluded. Accidental merges are prevented by requiring exact normalized matches for automated resolution.

---

## 5. Requirement Architecture & Update Semantics

Customer requirements are stored with granular provenance tracking:

### Attributes Normalized:
`transaction_type`, `budget_min`, `budget_max`, `currency`, `locations`, `property_types`, `bhk`, `area_min`, `area_max`, `amenities`, `furnishing`, `possession_preference`, `timeline`, `purpose`, `financing_required`, `urgency`, `positive_preferences`, `negative_preferences`.

### Provenance Hierarchy:
```
Rank 100: EXPLICIT / CUSTOMER_STATED  (Customer explicit statement, conf: 1.00)
Rank  90: AGENT_CONFIRMED             (Agent verified, conf: 0.90)
Rank  85: CRM / CRM_VERIFIED          (Verified CRM field, conf: 0.92)
Rank  80: IMPORTED                    (Portal/CSV import, conf: 0.85)
Rank  75: SYSTEM                      (Deterministic calculation, conf: 0.80)
Rank  60: BEHAVIORAL_SIGNAL           (Click/View behavior, conf: 0.80)
Rank  40: INFERRED / AI_INFERRED      (AI model extraction, conf: 0.60)
Rank  10: UNKNOWN                     (Unverified, conf: 0.30)
```

### Update Rules & Semantics:
1. **Anti-Overwrite Invariant**: An incoming update with lower rank than the existing active record is rejected. Inferred AI output can never overwrite explicit customer requirements.
2. **Supersession & Versioning**: If incoming rank $\ge$ existing rank, the active `MemoryRecord` is updated, and the prior state is archived into an immutable `MemoryVersion` record with reason code and timestamp.
3. **Single-Value Preferences**: When a customer explicitly changes a scalar configuration (e.g. from 3 BHK to 4 BHK), the previous value is superseded and archived.
4. **Negative Preferences (Disqualifiers)**: Negative constraints (e.g. "no ground floor", "not near highway", "not above ₹1.5 Cr") are stored as `NEGATIVE_PREFERENCE` in `MemoryRecord`. They are additive and durable, and cannot be negated by positive AI inferences.

---

## 6. Conversation & Message Domain Architecture

### Conversation Envelope (`OmnichannelConversation`):
- `id`: UUID (String)
- `organization_id`: Tenant context
- `lead_id`: Customer context
- `status`: Controlled statuses: `ACTIVE`, `WAITING`, `HANDED_OFF`, `CLOSED`, `ARCHIVED`
- `preferred_channel`: `whatsapp` | `telegram` | `email` | `webchat` | `sms`
- `control_mode`: `ai` | `human` | `bot` | `paused`
- `total_messages`, `unread_count`, `last_message_at`, `last_message_preview`

### Message Envelope (`ChannelMessage`):
- `conversation_id`: Associated conversation
- `organization_id`: Tenant context
- `lead_id`: Customer context
- `sender_type`: Controlled sender taxonomy:
  - `CUSTOMER` (direction: `inbound`)
  - `AI_AGENT` (direction: `outbound`, `sent_by_ai=True`)
  - `HUMAN_AGENT` (direction: `outbound`, `sent_by_agent_id` populated)
  - `SYSTEM` (direction: `outbound`)
- `content`: Sanitized message body
- `delivery_status`: `sent` | `delivered` | `read` | `failed`

### Credential & Secret Safety:
`_sanitize_content()` automatically scans message payloads and strips passwords, bearer tokens, and API keys (`[REDACTED_CREDENTIAL]`) before database persistence.

---

## 7. Bounded 4-Tier Memory Architecture

To prevent unbounded context window growth and unnecessary AI token consumption, the memory architecture provides four bounded tiers:

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: CURRENT_TURN                                        │
│ Latest customer message + agent response + tool execution   │
├─────────────────────────────────────────────────────────────┤
│ Tier 2: CURRENT_SESSION                                     │
│ Sliding dialogue window (last 6 messages) + active channel  │
├─────────────────────────────────────────────────────────────┤
│ Tier 3: CUSTOMER_MEMORY                                     │
│ Confirmed requirements + negative constraints + objections  │
├─────────────────────────────────────────────────────────────┤
│ Tier 4: CRM_MEMORY                                          │
│ Pipeline stage + score + assigned agent + scheduled visits  │
└─────────────────────────────────────────────────────────────┘
```

### Context String Generator:
`CustomerIntelligenceService.get_bounded_memory()` formats a deterministic, compact context string:
- Customer ID, Pipeline Stage, Lead Score
- Verified Requirements (budget, locations, property types, BHK, timeline)
- Negative Constraints (strict disqualifiers)
- Open Objections
- Recent Dialogue (last 6 messages)

No repeated Gemini API summarization calls are required for deterministic facts.

---

## 8. Tenant Security & Multi-Tenancy (P0 Safety Gate)

1. **Server-Derived Context**:
   - `organization_id` is derived strictly from the authenticated principal via `get_current_broker` (`current_broker.id`).
   - Client-provided tenant IDs are never used as authorization authority.
2. **Boundary Enforcement**:
   - Every database query for Customer, Conversation, Message, or Memory includes `WHERE broker_id = :org_id` or `WHERE organization_id = :org_id`.
   - Cross-tenant requests fail closed with `404 Not Found` or `403 Forbidden`.
3. **Automated Verification**:
   - Tests `test_cross_tenant_customer_isolation`, `test_cross_tenant_conversation_isolation`, and `test_cross_tenant_memory_isolation` pass with 100% rejection of cross-tenant attempts.

---

## 9. APIs & Endpoints

All endpoints are registered under `/api/v1/customers`:

| Method | Endpoint | Purpose | Status |
|---|---|---|---|
| `POST` | `/api/v1/customers/resolve` | Deterministic identity resolution | `VERIFIED` |
| `POST` | `/api/v1/customers` | Create or reuse canonical customer | `VERIFIED` |
| `GET` | `/api/v1/customers/{customer_id}` | Retrieve customer context & CRM state | `VERIFIED` |
| `GET` | `/api/v1/customers/{customer_id}/profile` | Retrieve requirement profile & provenance | `VERIFIED` |
| `PATCH` | `/api/v1/customers/{customer_id}/requirements` | Deterministic requirement update | `VERIFIED` |
| `POST` | `/api/v1/customers/{customer_id}/conversations` | Create conversation envelope | `VERIFIED` |
| `GET` | `/api/v1/customers/{customer_id}/conversations` | List customer conversations | `VERIFIED` |
| `POST` | `/api/v1/customers/{customer_id}/conversations/{c_id}/messages` | Send message with sender type | `VERIFIED` |
| `GET` | `/api/v1/customers/{customer_id}/conversations/{c_id}/messages` | List paginated conversation messages | `VERIFIED` |
| `GET` | `/api/v1/customers/{customer_id}/memory` | Retrieve 4-tier bounded memory | `VERIFIED` |

---

## 10. Domain Events

Integrated into `DomainEventBus` via `StandardDomainEvents`:

- `conversation.created`: Emitted when an `OmnichannelConversation` is initialized.
- `message.received`: Emitted when an inbound customer message is persisted.
- `message.created`: Emitted when an outbound agent/system message is created.
- `customer.requirement_updated`: Emitted when requirements are modified.
- `customer.preference_updated`: Emitted when positive or negative preferences are recorded.

---

## 11. Database Changes

### Migration: `0027_customer_identity_canonical.py`
- **Parent Revision**: `0026_revenue_autopilot`
- **New Head**: `0027_customer_identity_canonical`
- **Changes Applied**:
  - `leads`: Added column `email` (`VARCHAR(255)`, nullable), created index `ix_leads_email`.
  - `channel_messages`: Added column `sender_type` (`VARCHAR(30)`, nullable), created index `ix_channel_messages_sender_type`.
- **Status**: Applied cleanly to PostgreSQL and SQLite test environments.

---

## 12. Verification & Test Counts

### Test Execution Results:

| Test Suite | Total Tests | Passed | Failed | Execution Time | Pass Rate |
|---|---|---|---|---|---|
| `test_part1_customer_conversation_foundation.py` | 14 | 14 | 0 | 40.91s | **100%** |
| `test_ai_sales_agent_tools.py` | 8 | 8 | 0 | 12.30s | **100%** |
| `test_gemini_function_calling.py` | 5 | 5 | 0 | 8.20s | **100%** |
| `test_conversation_e2e.py` | 5 | 5 | 0 | 14.50s | **100%** |
| `test_tenant_isolation_ai.py` | 3 | 3 | 0 | 5.10s | **100%** |
| `test_property_truth.py` | 4 | 4 | 0 | 5.22s | **100%** |
| **Total Backend Test Suite** | **39** | **39** | **0** | **86.23s** | **100%** |

### Frontend Typecheck & Build:
- Command: `npx tsc --noEmit` (in `apps/web`)
- Result: **0 errors** across all TypeScript modules and components.
- Dev Servers: FastAPI (port 8000) and Next.js (port 3000) running with healthy startup logs.

---

## 13. Status Matrix & Part 2 Handoff

| Component | Status | Notes |
|---|---|---|
| Canonical Customer Identity | `VERIFIED` | `Lead` + `Identity` unified with tenant scoping |
| Identity Resolution | `VERIFIED` | 3 tiers implemented; zero cross-tenant merging |
| Requirement Profile & Precedence | `VERIFIED` | 5-tier provenance hierarchy; anti-overwrite rule enforced |
| Negative Preferences | `VERIFIED` | Durable disqualifier storage in `MemoryRecord` |
| Conversation Domain | `VERIFIED` | Unified envelope with 5 controlled statuses |
| Message Domain | `VERIFIED` | 4 canonical sender types + credential redaction |
| Bounded 4-Tier Memory | `VERIFIED` | Context builder formatted without unbounded history |
| Multi-Tenant Isolation | `VERIFIED` | Server-derived context; zero cross-tenant leakage |
| REST APIs | `VERIFIED` | 8 canonical endpoints live under `/api/v1/customers` |
| Domain Events | `VERIFIED` | 5 canonical events registered on `DomainEventBus` |
| Database Migration | `VERIFIED` | `0027_customer_identity_canonical` upgraded cleanly |
| Frontend Verification | `VERIFIED` | Client hooks added; 0 TypeScript errors |
| Property RAG | `DEFERRED` | Belongs to Part 2 |
| Property Matching Engine | `DEFERRED` | Belongs to Part 3 |
| AI Sales Agent Execution Loop | `DEFERRED` | Belongs to later parts |
| WhatsApp / Voice Channels | `DEFERRED` | Belongs to later parts |

---

## Conclusion

Part 1 (Customer Identity + Conversation + Memory Foundation) is **100% complete, verified, and locked**. All subsequent parts (Part 2: Property Authority & RAG; Part 3: Matching Engine) will build directly on this canonical intelligence foundation.
