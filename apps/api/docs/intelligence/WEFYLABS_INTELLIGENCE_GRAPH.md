# WefyLabs — Real Estate Revenue Intelligence Graph
## Architecture Reference · Master Build 14

---

## 1. Overview

The WefyLabs Intelligence Graph is an **append-only, tenant-isolated, provenance-tracked knowledge system** that
accumulates operational wisdom from every lead, conversation, property match, AI decision, and revenue outcome
across the platform.

It does NOT replace the operational database.  
It does NOT run inference at query time.  
It does NOT expose cross-tenant learning signals.

Its role is:

```
OBSERVE → UNDERSTAND → MEASURE → LEARN → RECOMMEND → EXECUTE SAFELY → MEASURE OUTCOME → IMPROVE
```

---

## 2. Core Entities

### 2.1 Outcome Record

```
OutcomeRecord
├── id                    UUID PK
├── tenant_id             FK → Tenant (strict isolation boundary)
├── outcome_type          ENUM(lead_converted, deal_closed, visit_scheduled,
│                               follow_up_responded, objection_resolved, …)
├── source_module         VARCHAR — which module produced this outcome
├── source_entity_id      UUID — FK to the originating record
├── occurred_at           TIMESTAMP WITH TZ (immutable)
├── value_inr             NUMERIC(15,2) — financial attribution
├── signal_data           JSONB — module-specific contextual fields
├── provenance_hash       SHA-256 of (tenant_id‖type‖entity_id‖occurred_at)
├── is_verified           BOOL — human-in-the-loop confirmation flag
├── verified_by           UUID FK → User (nullable)
└── verified_at           TIMESTAMP (nullable)
```

**Append-only invariant:** Outcomes are NEVER updated or deleted. Corrections are new records
with `corrects_outcome_id` pointing to the erroneous record.

### 2.2 Intelligence Signal

```
IntelligenceSignal
├── id                    UUID PK
├── tenant_id             FK → Tenant
├── signal_type           ENUM(velocity, objection_pattern, price_sensitivity,
│                               channel_preference, timing_pattern, …)
├── entity_type           VARCHAR — "lead" | "property" | "agent" | "campaign"
├── entity_id             UUID
├── computed_at           TIMESTAMP
├── score                 FLOAT — normalised [0.0 – 1.0]
├── confidence            FLOAT — calibrated Bayesian confidence
├── feature_vector        JSONB — raw features used
├── model_version         VARCHAR — which model produced this signal
└── expires_at            TIMESTAMP (nullable, for time-decaying signals)
```

### 2.3 Learning Event

```
LearningEvent
├── id                    UUID PK
├── tenant_id             FK → Tenant
├── event_type            ENUM(outcome_confirmed, signal_corrected, policy_updated,
│                               model_retrained, objection_labeled, …)
├── source_outcome_id     FK → OutcomeRecord (nullable)
├── payload               JSONB — change delta
├── schema_version        VARCHAR — for replay compatibility
├── created_at            TIMESTAMP (immutable)
└── provenance_hash       SHA-256
```

### 2.4 Intelligence Edge (Graph Relation)

```
IntelligenceEdge
├── id                    UUID PK
├── tenant_id             FK → Tenant (BOTH nodes must belong to same tenant)
├── from_entity_type      VARCHAR
├── from_entity_id        UUID
├── to_entity_type        VARCHAR
├── to_entity_id          UUID
├── edge_type             ENUM(influenced, converted_via, objection_resolved_by,
│                               matched_by, closed_by, …)
├── weight                FLOAT — relationship strength [0.0 – 1.0]
├── evidence_outcome_id   FK → OutcomeRecord
└── created_at            TIMESTAMP
```

---

## 3. Tenant Isolation Model

```
┌─────────────────────────────────────────────────────────────────┐
│                         Tenant A                                │
│  OutcomeRecord(tenant_id=A) ──► IntelligenceSignal(tenant_id=A)│
│  LearningEvent(tenant_id=A) ──► BenchmarkDefinition(tenant_id=A)│
└─────────────────────────────────────────────────────────────────┘
                         (NO cross-tenant reads)
┌─────────────────────────────────────────────────────────────────┐
│                         Tenant B                                │
│  OutcomeRecord(tenant_id=B) ──► IntelligenceSignal(tenant_id=B)│
└─────────────────────────────────────────────────────────────────┘
```

**Cross-tenant benchmark aggregation** uses privacy-preserving cohorts:
- Minimum cohort size: **5 tenants**  
- Only percentile distributions are exposed (no raw tenant data)  
- Aggregation is performed server-side; the calling tenant's own data is never re-identified

---

## 4. Provenance Chain

Every learning artifact carries a SHA-256 provenance hash computed from its immutable identity fields.

```
provenance_hash = SHA256(
    str(tenant_id) +
    str(outcome_type) +
    str(source_entity_id) +
    str(occurred_at.isoformat())
)
```

This enables:
- **Audit replay** — re-derive any learning event from its source
- **Tamper detection** — hash stored at write time; verified at read time
- **Legal hold** — outcomes can be frozen without modifying the data model

---

## 5. Learning Loop

```
┌──────────────────────────────────────────────────────────────────┐
│                    Continuous Learning Loop                       │
│                                                                  │
│  Operational Event (lead_scored, deal_closed, visit_completed)   │
│          │                                                        │
│          ▼                                                        │
│  OutcomeRecord written (append-only, provenance hashed)          │
│          │                                                        │
│          ▼                                                        │
│  LearningEvent emitted (schema-versioned, replayable)            │
│          │                                                        │
│          ├──► Signal recomputation triggered                      │
│          │                                                        │
│          ├──► Benchmark cohort updated (if cohort ≥ 5)           │
│          │                                                        │
│          └──► Policy evaluation queued                           │
│                       │                                          │
│                       ▼                                          │
│              Human-in-the-loop review                            │
│              (required for policy changes > threshold)           │
│                       │                                          │
│                       ▼                                          │
│              Next Recommended Action updated                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Experiment Framework

The intelligence system supports **A/B and multi-armed-bandit experiments**:

| Field              | Type    | Notes                                     |
|--------------------|---------|-------------------------------------------|
| `experiment_id`    | UUID    | Stable identifier                         |
| `variant_id`       | UUID    | Arm assignment (hashed on entity_id)      |
| `hypothesis`       | TEXT    | Mandatory — no untested deployments        |
| `primary_metric`   | VARCHAR | e.g. `conversion_rate`                    |
| `min_sample_size`  | INT     | Statistical power gate                    |
| `min_confidence`   | FLOAT   | Default 0.95                              |
| `status`           | ENUM    | `draft → running → paused → concluded`   |

Statistical evaluation uses **Welch's t-test** for continuous metrics and **Chi-square** for proportions.
Results are NEVER promoted automatically — a human must approve via `POST /intelligence/experiments/{id}/conclude`.

---

## 7. Anti-Patterns (What This System Must Never Do)

| Anti-Pattern | Reason |
|---|---|
| Train on cross-tenant data without consent | Privacy violation; corrupts signal |
| Auto-promote experiment results | Requires human sign-off |
| Report unverified outcomes as confirmed | Produces misleading benchmarks |
| Store PII in feature vectors | GDPR / data minimisation |
| Expose raw benchmark contributors | Re-identification risk |
| Allow AI to self-modify policies | Human-in-the-loop is mandatory |
| Delete or update OutcomeRecords | Breaks append-only guarantee |

---

## 8. Module Integration Map

```
Build 02  Lead Ingestion       ──► OutcomeRecord(lead_captured)
Build 03  Communication        ──► OutcomeRecord(conversation_completed)
Build 04  Property             ──► OutcomeRecord(match_accepted)
Build 06  AI Sales Agent       ──► OutcomeRecord(objection_resolved)
Build 07  Follow-Up            ──► OutcomeRecord(follow_up_responded)
Build 08  Pipeline             ──► OutcomeRecord(deal_closed)
Build 09  Revenue              ──► OutcomeRecord(revenue_attributed)
Build 12  Observability        ──► IntelligenceSignal(system_health)
Build 13  Billing              ──► OutcomeRecord(subscription_converted)
Build 14  Intelligence         ──► [All signals, edges, experiments, policies]
```
