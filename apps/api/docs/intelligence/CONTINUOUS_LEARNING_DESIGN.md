# WefyLabs — Continuous Learning System Design
## Master Build 14 · Phase 76

---

## 1. Principles

1. **Append-only** — Learning events are never mutated. Corrections are new events.
2. **Schema-versioned** — Every `LearningEvent.payload` carries a `schema_version` field to ensure replay compatibility as the system evolves.
3. **Provenance-first** — Every artifact that enters the learning pipeline carries a SHA-256 provenance hash derived from immutable identity fields.
4. **Human-gated policies** — No outcome of the learning loop may modify a `PolicyRule` with `auto_apply=True` without an explicit human approval step.
5. **Tenant-isolated** — Learning events are scoped strictly to a single tenant. Cross-tenant signals are never used to train tenant-specific models.

---

## 2. Learning Event Types

| Event Type | Trigger | Payload Fields |
|---|---|---|
| `outcome_confirmed` | Human verifies an OutcomeRecord | `outcome_id`, `verified_by`, `previous_is_verified` |
| `signal_corrected` | Signal score overridden by human | `signal_id`, `old_score`, `new_score`, `reason` |
| `policy_updated` | PolicyRule changed | `policy_id`, `change_delta`, `approved_by` |
| `objection_labeled` | ObjectionRecord receives a label | `objection_id`, `label`, `labeled_by` |
| `experiment_concluded` | Experiment reaches conclusion | `experiment_id`, `winner_variant`, `p_value` |
| `benchmark_published` | Cohort benchmark recomputed | `benchmark_id`, `cohort_size`, `percentiles` |

---

## 3. Schema Versioning Contract

All `LearningEvent.payload` JSON objects MUST include:

```json
{
  "schema_version": "1.0",
  "event_specific_fields": "..."
}
```

**Upgrade rules:**
- Minor changes (adding nullable fields): bump minor version (`1.0 → 1.1`)
- Breaking changes (removing or renaming fields): bump major version (`1.0 → 2.0`) AND provide a migration function in `app/modules/intelligence/service.py::_migrate_learning_payload`

---

## 4. Replay Architecture

Every learning event can be replayed from the `LearningEvent` table:

```python
# Replay all learning events for a tenant from a checkpoint
async def replay_learning_events(
    db: AsyncSession,
    tenant_id: UUID,
    from_created_at: datetime,
    dry_run: bool = True,
) -> ReplayResult:
    events = await db.execute(
        select(LearningEvent)
        .where(
            LearningEvent.tenant_id == tenant_id,
            LearningEvent.created_at >= from_created_at,
        )
        .order_by(LearningEvent.created_at)
    )
    ...
```

The `dry_run=True` flag makes replay non-destructive; it computes what WOULD change without writing.

---

## 5. Learning Poisoning Defences

The system defends against learning poisoning (deliberate injection of false outcomes to corrupt signals):

| Defence Layer | Mechanism |
|---|---|
| Outcome verification | `is_verified` flag; unverified outcomes excluded from signal computation |
| Provenance hashing | SHA-256 hash verified at read time |
| Velocity rate limit | Max outcomes per tenant per hour enforced in service layer |
| Outlier detection | Outcomes with `value_inr` > 3σ from tenant mean are flagged for review |
| Cross-validation | Signals computed from independent sub-samples of outcomes |

---

## 6. Data Minimisation

Feature vectors stored in `IntelligenceSignal.feature_vector` MUST NOT contain:
- Full names (use lead_id only)
- Phone numbers or emails
- Aadhaar / PAN / passport numbers
- Raw conversation transcripts (use embeddings or intent labels)

The `service.py::compute_signal` function enforces this via a PII scrubber
before writing to the database.

---

## 7. Operational Runbook

### Start learning loop for a tenant
```bash
POST /api/v1/intelligence/outcomes
{
  "outcome_type": "lead_converted",
  "source_module": "pipeline",
  "source_entity_id": "<deal_id>",
  "value_inr": 1500000
}
```

### Verify an outcome (human-in-the-loop)
```bash
POST /api/v1/intelligence/outcomes/{outcome_id}/verify
```
Requires `MANAGER` or `ADMIN` role. Records `verified_by` and `verified_at`.

### Replay learning events from a checkpoint
```bash
POST /api/v1/intelligence/replay
{
  "from_datetime": "2026-01-01T00:00:00Z",
  "dry_run": true
}
```

### Export benchmark comparison
```bash
GET /api/v1/intelligence/benchmarks/{definition_id}/compare
```
Returns your tenant's percentile position against the anonymised cohort (min 5 tenants).
