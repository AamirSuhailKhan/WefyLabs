# STAGE1_NATURAL_INGRESS_PROOF.md
# Phase 2C.6E — Genuine Production Event Chain & Natural Ingress Assessment

**Generated:** 2026-10-13  
**Status:** STAGE1_NATURAL_INGRESS_READY_WAITING_FOR_REAL_ACTIVITY  
**Assessed by:** Phase 2C.6E Evidence Verification Engine  

---

## 1. COMPLIANCE ASSESSMENT & CLASSIFICATION (GATE 4 & GATE 5 COMPLIANCE)

```
FINAL CLASSIFICATION:
STAGE1_NATURAL_INGRESS_READY_WAITING_FOR_REAL_ACTIVITY
```

The production Celery worker is verified, running with strict Redis TLS verification (`certifi.where()`), and actively consuming tasks from `sales-loop-orchestration`. The website enquiry form has been connected to Next.js route `/api/contact` and verified against the backend lead capture hub.

### Integration Safety Verification (Gate 4):
- **Test Suite Executed:** [`apps/api/tests/test_website_ingress_integration.py`](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/apps/api/tests/test_website_ingress_integration.py)
- **Results:** 7 / 7 test cases passed cleanly.
- **Classification:** **`TEST_EVIDENCE_ONLY`** (Explicitly marked as integration test evidence; NOT counted as longitudinal production evidence).
- **Verified Behaviors:**
  1. Missing contact info rejected with 422.
  2. Honeypot spam trap caught and neutralized.
  3. Prompt injection strings sanitized.
  4. Unauthorized source token access returns 404 / None.
  5. Sliding-window rate limit enforced.
  6. Idempotent repeated submissions deduplicated without record split.
  7. Production database isolation: **0 fake leads or observations were inserted into PostgreSQL during tests.**

### Natural Customer Traffic Audit (Gate 5):
- **Live Database Audit:**
  - Total leads in PostgreSQL: 7 (all historical).
  - Genuine customer enquiries received during this window: **0**.
  - Synthetic records injected: **0**.
  - Manufactured broker decisions: **0**.
- **Classification:** As mandated by Gate 5, because no genuine customer lead has arrived through the public website, the system is formally classified as **`READY_WAITING_FOR_REAL_ACTIVITY`**.

---

## 2. CANONICAL NATURAL INGRESS PATHWAY (VERIFIABLE 12-STEP CHAIN)

When a genuine customer submits an enquiry through the live website form, the event will traverse:

```
[1] Genuine Customer Enquiry Submitted
    (User fills name, phone, email on WefyLabs website)
                ↓
[2] Next.js Server Route
    POST /api/contact (injects server-side source token)
                ↓
[3] Production FastAPI Ingestion
    POST /api/v1/public/lead-capture/{token}
                ↓
[4] Tenant Resolution & Validation
    Token resolves to org a0317351; honeypot & rate limit passed
                ↓
[5] Database Persistence
    Persisted to `leads` table with generated UUID
                ↓
[6] Domain Event Emitted
    `StandardDomainEvents.LEAD_CREATED` published on `event_bus`
                ↓
[7] Async Loop Bridge Dispatch
    `lead_created_loop_subscriber` enqueues Celery task with correlation_id
                ↓
[8] Redis Queue Transport
    `sales-loop-orchestration` on Upstash Redis TLS broker (CERT_REQUIRED)
                ↓
[9] Deployed Celery Worker Consumes
    `autonomous_loop.process_sales_loop_event` executes in isolated loop
                ↓
[10] Policy Evaluation (Autonomy = 0)
    `Phase2CEventBridge` executes agent in `dry_run=True` (SHADOW mode)
                ↓
[11] Durable Observation Created
    Persisted to `pilot_observations` (`is_synthetic=False`, `SHADOW_PROJECTED`)
                ↓
[12] Authorized Broker Review & Chained Audit
    Broker reviews projection and submits decision; hash-chained in `pilot_audit_events`.
```

---

## 3. EVIDENCE INTEGRITY & LAYER RECONCILIATION

| Platform Entity | Direct Database | PilotRepository | Metrics API | Dashboard Display |
|---|---|---|---|---|
| **Pilot Observations** | 2 | 2 (0 pending) | 2 | 2 |
| **Human Decisions** | 2 | 2 | 2 | 2 |
| **Audit Events** | 4 | 4 | 4 | 4 |
| **Configured Lead Sources** | 1 | 1 | 1 | 1 |
| **Autonomy Level** | 0 | 0 | 0 | 0 |
| **Operational Stage** | STAGE_1_SHADOW | STAGE_1_SHADOW | STAGE_1_SHADOW | STAGE_1_SHADOW |

All platform layers remain in 100% mathematical harmony.

---

_End of Natural Ingress Proof Report_
