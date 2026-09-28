# WefyLabs — Experiment & Policy Runbook
## Master Build 14 · Phase 78

---

## 1. Running an A/B Experiment

### Step 1: Define the experiment

```bash
POST /api/v1/intelligence/experiments
Authorization: Bearer <MANAGER_TOKEN>

{
  "name": "Faster follow-up vs standard cadence",
  "hypothesis": "Agents who follow up within 2h will achieve >15% higher conversion than 24h cadence",
  "experiment_type": "ab_test",
  "primary_metric": "conversion_rate",
  "min_sample_size": 200,
  "min_confidence": 0.95,
  "planned_end_date": "2026-11-01T00:00:00Z",
  "variants": [
    {"name": "control",   "description": "24h follow-up cadence", "allocation_pct": 50},
    {"name": "treatment", "description": "2h follow-up cadence",  "allocation_pct": 50}
  ]
}
```

### Step 2: Assign entities to variants

```bash
POST /api/v1/intelligence/experiments/{experiment_id}/assign
{
  "entity_type": "lead",
  "entity_id": "<lead_uuid>"
}

Response:
{
  "variant_id": "<variant_uuid>",
  "variant_name": "treatment"
}
```

Variant assignment is **deterministic** — the same `entity_id` will always map to the same variant (hash-based).

### Step 3: Record outcome against variant

```bash
POST /api/v1/intelligence/outcomes
{
  "outcome_type": "lead_converted",
  "source_module": "pipeline",
  "source_entity_id": "<lead_uuid>",
  "value_inr": 2500000,
  "signal_data": {
    "experiment_id": "<experiment_id>",
    "variant_id": "<variant_id>"
  }
}
```

### Step 4: Evaluate statistical significance

```bash
POST /api/v1/intelligence/experiments/{experiment_id}/evaluate
```

Returns Welch's t-test p-value and confidence intervals. If `p_value < min_confidence`, experiment is not yet conclusive.

### Step 5: Conclude (human approval required)

```bash
POST /api/v1/intelligence/experiments/{experiment_id}/conclude
Authorization: Bearer <MANAGER_TOKEN>

{
  "winner_variant_id": "<variant_uuid>",
  "notes": "Treatment achieved p=0.023, 19% conversion lift. Approved for full rollout."
}
```

**No experiment winner is promoted automatically.** A Manager or Admin must call this endpoint.

---

## 2. Managing Policy Rules

### Create a policy

```bash
POST /api/v1/intelligence/policies
Authorization: Bearer <ADMIN_TOKEN>

{
  "name": "High-value lead priority routing",
  "description": "Leads with predicted_value > 5000000 are routed to senior agents",
  "policy_type": "routing",
  "conditions": {
    "field": "predicted_value_inr",
    "operator": ">",
    "threshold": 5000000
  },
  "actions": {
    "route_to": "senior_agent_pool"
  },
  "auto_apply": false,
  "requires_human_approval": true
}
```

### Policy approval flow

```
draft ──[human approves]──► active
      ──[human rejects]──► draft (with rejection reason logged)

active ──[human pauses]──► paused
       ──[human deprecates]──► deprecated
```

All state transitions are recorded as `LearningEvent(event_type="policy_updated")`.

### Policy conditions format

```json
{
  "field": "lead_score",
  "operator": ">=",
  "threshold": 80
}
```

Supported operators: `>`, `>=`, `<`, `<=`, `=`, `!=`, `in`, `not_in`

---

## 3. Human-in-the-Loop (HiTL) Checklist

Before any policy goes `active`, the approving human must confirm:

- [ ] The hypothesis is explicitly stated in `description`
- [ ] The conditions produce no unintended exclusions (run `evaluate` first)
- [ ] The action does not create discriminatory routing
- [ ] The policy has an explicit `expires_at` or review schedule
- [ ] A rollback plan is documented in `notes`

---

## 4. Rollback Procedure

### Rollback an active policy

```bash
PATCH /api/v1/intelligence/policies/{policy_id}
Authorization: Bearer <ADMIN_TOKEN>

{
  "status": "paused",
  "notes": "Rollback: unexpected drop in conversion for new-agent pool. Reverting to manual routing."
}
```

A `LearningEvent` is written with the change delta and who approved the rollback.

### Replay learning events after rollback

```bash
POST /api/v1/intelligence/replay
{
  "from_datetime": "<ISO datetime before the bad policy was activated>",
  "dry_run": true
}
```

Inspect the `affected_count` before setting `dry_run: false`.

---

## 5. Operational Alerts

| Condition | Action |
|---|---|
| Experiment running > 30 days past `planned_end_date` | Alert to Manager; auto-pause |
| Policy active with no outcomes in 14 days | Alert to Admin for review |
| Benchmark cohort drops below 5 | Auto-archive benchmark; stop exposing stats |
| Learning event replay fails for schema mismatch | Page SRE; do NOT auto-migrate |
| Provenance hash mismatch on OutcomeRecord | Quarantine record; page Security |
