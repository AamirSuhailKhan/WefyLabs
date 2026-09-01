# BEETLELABS — PART 21.7: AI CUSTOMER RESPONSE & CONVERSATION INTELLIGENCE ENGINE
## Master Implementation Plan

**Objective:** Build the canonical customer response intelligence loop that ingests real inbound communications, classifies multi-intent signals, extracts buying signals and objections, updates qualification facts with provenance, refreshes property recommendations, recalculates Next Best Action (Part 21.5), and prepares grounded responses or human handoffs with full auditability and tenant isolation.

---

### 1. Existing Reusable Baseline Components

| Module / Component | Location | Role in Part 21.7 |
| :--- | :--- | :--- |
| **Communication Models** | `app/models/communication_models.py` | `OmnichannelConversation`, `ChannelMessage`, `InboundQueue`, `MessageAttachment` |
| **Conversation Model** | `app/models/conversation.py` | `Conversation` (relational timeline persistence) |
| **Provider Webhooks** | `app/modules/communication/router.py` | Real Meta WhatsApp, SMTP, SMS webhook ingestion & signature verification |
| **Qualification Domain** | `app/modules/lead_qualification/` | `QualificationFactRepository`, `QualificationDomainService`, `QualificationFactExtractor` |
| **Sales Action & NBA** | `app/modules/sales_action/` | `SalesActionDomainService`, `SalesActionPolicyEngine`, `ConsentGuard`, `FatigueGuard` |
| **Property Recommendations** | `app/modules/property_recommendation/` | `PropertyRecommendationService`, `CandidateRetrievalService`, `HardConstraintEngine` |
| **Prospect Intelligence** | `app/modules/prospect_intelligence/` | `ProspectIntelligence` profile updates |
| **Prompt Guard & Security** | `app/infrastructure/security/prompt_guard.py` | Prompt injection detection & text sanitization |
| **LLM Router** | `app/modules/ai_agent/llm_router/` | Multi-provider LLM abstraction (Gemini / Anthropic / OpenAI / Mock) |

---

### 2. New Architecture & Module Structure

We will create `apps/api/app/modules/conversation_intelligence/` containing:

```
apps/api/app/modules/conversation_intelligence/
├── __init__.py
├── taxonomies.py               # CustomerIntent, BuyingSignalLevel, ObjectionCategory, etc.
├── dto.py                      # InboundCustomerMessage, ResponseAnalysisDTO, ObjectionDTO, HumanHandoffDTO
├── language_detector.py        # Real text language classification (EN, AR, HI, etc.)
├── intent_extractor.py         # Multi-intent classification & prompt injection defense
├── buying_signal_detector.py   # Grounded buying signal detection with evidence
├── objection_detector.py       # Objection extraction (Price, Location, Timeline, Trust, etc.)
├── negotiation_detector.py     # Price negotiation detection & discount request guard
├── appointment_detector.py     # Viewing intent & schedule preference extraction
├── response_generator.py       # Fact-grounded AI reply generation (truthful, no hallucinations)
├── handoff_service.py          # Structured HumanHandoffBrief generation & control transfer
├── service.py                  # ResponseIntelligenceService (Core domain orchestrator)
├── router.py                   # REST API endpoints for intelligence, signals, objections, handoff
├── metrics.py                  # PII-safe Prometheus metrics with masked org hash
└── workers/
    └── response_tasks.py       # Celery task for async response processing
```

---

### 3. Execution Pipeline & Data Flow

```
                     REAL INBOUND MESSAGE
                  (WhatsApp / Email / SMS / WebChat)
                                │
                                ▼
                  ┌───────────────────────────┐
                  │ Inbound Normalization     │
                  │ • Signature verify        │
                  │ • Tenant & Lead match     │
                  │ • SHA-256 Idempotency     │
                  │ • ChannelMessage persist  │
                  └─────────────┬─────────────┘
                                │
                                ▼
                  ┌───────────────────────────┐
                  │ ResponseIntelligenceService│
                  │ • Prompt injection check  │
                  │ • Language detection      │
                  │ • Multi-intent extraction │
                  │ • Buying signal detection │
                  │ • Objection extraction    │
                  │ • Negotiation detection   │
                  │ • Appointment detection   │
                  └─────────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
   │ Consent/Opt-Out │ │  Qualification  │ │ Property Matches│
   │ • Detect STOP   │ │  Fact Updates   │ │ • Update reqs   │
   │ • Revoke consent│ │ • Provenance    │ │ • Re-rank       │
   │ • Reset fatigue │ │ • Supersession  │ │ • Real inventory│
   │ • Halt outbound │ │ • Conflict check│ │   only          │
   └─────────────────┘ └────────┬────────┘ └────────┬────────┘
                                │                   │
                                └─────────┬─────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │ Recalculate NBA     │
                               │ (Part 21.5 Engine)  │
                               └──────────┬──────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
                        │                                   │
                        ▼                                   ▼
             ┌─────────────────────┐             ┌─────────────────────┐
             │ Grounded AI Draft   │             │ Human Handoff Brief │
             │ • Verified facts    │             │ • Escalations       │
             │ • Real properties   │             │ • Complaints        │
             │ • Truthful calendar │             │ • Negotiations      │
             └─────────────────────┘             └─────────────────────┘
```

---

### 4. Integration Points

1. **Lead Qualification Integration (Part 21.4)**:
   - Extracted budget, location, property type, bedrooms, timeline, financing are converted to `QualificationFactCreateDTO` with `source_type=CUSTOMER_MESSAGE`, `source_id=msg.id`.
   - `QualificationFactRepository.record_fact` enforces supersession vs conflict detection.
2. **Property Recommendation Integration (Part 21.3)**:
   - When requirement facts update, `PropertyRecommendationService.generate_recommendations` re-evaluates tenant listing candidates.
   - If no properties match, returns `NO_VERIFIED_MATCHES` without synthetic listings.
3. **Sales Action & Next Best Action Integration (Part 21.5)**:
   - `SalesActionDomainService.evaluate_next_sales_action` evaluates the new lead state and produces the next priority action.
4. **Communication Provider Integration (Part 21.6)**:
   - Inbound webhook in `apps/api/app/modules/communication/router.py` automatically links to `ResponseIntelligenceService`.

---

### 5. Verification Plan

1. **Dedicated Test Suite**: `tests/test_part21_7_conversation_intelligence.py` with 40+ unit and integration tests across categories A through Z.
2. **Critical Negative Tests**:
   - Prompt injection / data exfiltration attempt -> Neutralized, zero leak.
   - Unverified calendar availability -> No false booking claim.
   - Customer says "STOP" -> Immediate consent revocation & fatigue reset.
   - Conflicting budget -> Recorded with provenance, no silent wipe.
   - Zero matching properties -> Clean `NO_VERIFIED_MATCHES`.
   - Duplicate inbound webhook -> Processed exactly once.
   - Cross-tenant access attempt -> 403 / 404 forbidden.
   - AI provider unavailable -> Deterministic extraction fallback.
3. **Full Regression**: Parts 21.1 through 21.7 (350+ tests total).
4. **Frontend Production Build**: `npm run build` in `apps/web` with 0 errors.
5. **Alembic Migration Verification**: Verify head remains `merge_002_and_9999_heads`.
