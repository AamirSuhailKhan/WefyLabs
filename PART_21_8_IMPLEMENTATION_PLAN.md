# BEETLELABS — PART 21.8: AI AUTONOMOUS SALES LOOP & EVENT-DRIVEN ORCHESTRATION ENGINE
# MASTER IMPLEMENTATION PLAN

---

## 1. Deep Repository Audit & Baseline Verification

### Current System Baseline (Parts 21.1 – 21.7)
The repository contains an established, production-grade real estate CRM architecture:
- **Part 21.1 (Lead Acquisition)**: Multi-channel intake (WhatsApp, webhooks, portal connectors, manual CSV import) normalizing raw payloads into CRM `Lead` records.
- **Part 21.2 & 21.2A (AI Discovery & Prospect Intelligence)**: Intent classification, timeline categorization, financing readiness, and buying signal extraction.
- **Part 21.3 (AI Property Matching & Recommendation)**: Multi-factor property ranking engine filtering strictly against verified, active tenant inventory with zero property hallucination.
- **Part 21.4.1 – 21.4.4 (AI Lead Qualification Domain)**: Deterministic policy engine (`DeterministicQualificationPolicyEngine`), immutable fact repository (`QualificationFactRepository`), snapshot generation, and conversational clarification.
- **Part 21.5 (AI Sales Action / Next Best Action)**: Policy-governed NBA determination (`SalesActionDomainService`), safety guardrails (`ConsentGuard`, `QuietHoursGuard`, `FatigueGuard`, `HumanApprovalGuard`), and prompt phrasing.
- **Part 21.6 (Real Communication Delivery Engine)**: Idempotent provider dispatch (`WhatsAppProvider`, `EmailSMTPProvider`, `SMSProvider`, `TelegramProvider`, `WebChatProvider`) with delivery status reconciliation and truthful error reporting.
- **Part 21.7 (Conversation Intelligence)**: Inbound response ingestion (`ResponseIntelligenceService`), sentiment/objection/negotiation analysis, buying signal tracking, and immediate consent revocation on opt-out.

---

## 2. Part 21.8 Architectural Mission

Part 21.8 establishes the **centralized event-driven orchestration layer** that binds Parts 21.1 through 21.7 into a cohesive, safe, autonomous sales loop:
```
Real Event Ingestion
       ↓
Tenant & Lead Isolation Validation
       ↓
Durable Idempotency Check (sales_loop_events)
       ↓
Lead State Machine Evaluation (lead_automation_states)
       ↓
Targeted Intelligence Ingestion (21.4 Qualification / 21.3 Properties / 21.7 Conversation)
       ↓
Next Best Action Determination (21.5 NBA)
       ↓
Autonomy Policy Evaluation (Deterministic Permissions)
       ↓
Safety Guard Chain (21.5 Consent, Quiet Hours, Fatigue, Human Approval + Loop Protection)
       ↓
Truthful Execution Dispatch (21.6 Real Delivery Engine)
       ↓
Immutable Explainability Audit Entry (sales_loop_audit_entries)
       ↓
Follow-up Event Scheduling (Celery Queue Workers)
```

---

## 3. Core Principles & Safety Invariants

1. **Zero-Fabrication Policy**:
   - Zero hallucination of leads, properties, prices, dates, or consent.
   - Any missing data yields `UNKNOWN` or `NO_ACTION` / `HUMAN_REVIEW`.
2. **Deterministic Autonomy Policy**:
   - AI phrases text; deterministic Python code decides authorization.
   - Action permissions: `AUTOMATIC`, `HUMAN_APPROVAL`, `FORBIDDEN`, `SCHEDULED`, `NO_ACTION`.
3. **Fail-Closed Guard Chain**:
   - Any failing guard halts outbound communication immediately and records the blocking reason.
4. **Durable Idempotency**:
   - Unique constraints on `idempotency_key` prevent duplicate dispatch even if events are replayed 10x.
5. **Correlation & Causation Tracing**:
   - Every action and event carries `correlation_id` and `causation_id` to answer *"Why did BeetleLabs do this?"*.
6. **Broker Empowerment**:
   - Brokers can pause, resume, take over, approve, or reject automations per lead at any moment.

---

## 4. Planned & Implemented Components

### Database Tables (Alembic 0015)
- `sales_loop_events`: Durable event store with idempotency and processing state tracking.
- `sales_loop_audit_entries`: Explainability audit records capturing full intelligence and guard decisions.
- `sales_loop_dead_letters`: Durable repository for permanently failed events requiring administrative action.
- `lead_automation_states`: Per-lead automation controls, lifecycle tracking, and loop protection counters.

### Backend Services (`app/modules/autonomous_loop/`)
- `taxonomies.py`: 37 controlled event types, lifecycle states, and failure classes.
- `models.py`: SQLAlchemy database models.
- `dto.py`: Typed Pydantic schemas.
- `event_store.py`: Idempotent ingestion and state transition tracking.
- `state_machine.py`: Deterministic lead state machine with allowed transition tables.
- `automation_policy.py`: AI-proof permission lookup engine.
- `guard_chain.py`: Comprehensive guard chain wrapping Part 21.5 guards.
- `loop_protection.py`: Daily action budget and recursion depth guards.
- `audit_service.py`: Explainability record retrieval.
- `dead_letter_service.py`: Dead-letter admission and resolution manager.
- `orchestrator.py`: `AutonomousSalesLoopService` orchestrator.
- `metrics.py`: Tenant-masked Prometheus metrics.
- `workers/loop_tasks.py`: Celery workers for async event processing and retries.
- `router.py`: REST API endpoints under `/api/v1/autonomous-loop`.

### Frontend Component (`apps/web/`)
- `AutonomousSalesTimeline.tsx`: Real-time interactive timeline displaying event progression, guard evaluations, explainability details, and broker controls.
- Integrated into `apps/web/src/app/leads/[id]/page.tsx`.

---

## 5. Verification Plan

1. **Dedicated Unit & Integration Tests**: 57 test cases in `test_part21_8_autonomous_sales_loop.py`.
2. **Full Part 21 Regression Suite**: Execute all 12 test suites (411 tests).
3. **Frontend Production Build**: `npm run build` with zero TypeScript or route errors.
4. **Database Migration Verification**: `python -m alembic heads` showing single head.
5. **Static Code & Security Audit**: Audit for fake mocks, PII leaks, prompt injection vulnerabilities, and tenant leaks.
6. **Controlled Smoke Test**: Validate event-to-execution pipeline using database fixtures.
