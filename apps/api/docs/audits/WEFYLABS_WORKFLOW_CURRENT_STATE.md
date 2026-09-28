# WEFYLABS — WORKFLOW CURRENT STATE AUDIT
## Phase 0: Complete Workflow & Follow-Up System Inventory

> **Build:** 07 — Follow-Up, NBA, Workflow OS | **Audit Date:** 2026-09-26

---

## Executive Summary

The WefyLabs codebase contains **three independent NBA implementations**, **two task models**,
**one legacy follow-up model**, **one enterprise follow-up model**, **one workflow engine**,
**one autonomous sales loop**, and **one revenue autopilot engine** — all operating in parallel
with overlapping responsibilities and no shared convergence layer.

Build 07 must converge these into one canonical system without deleting production-ready infrastructure.

---

## 1. MODELS INVENTORY

### 1.1 Follow-Up Models

| Model | File | Classification | Assessment |
|---|---|---|---|
| `FollowUp` | `models/follow_up.py` | **LEGACY** | 3-step sequence (sequence_number IN [1,2,3]). No org_id. **DEPRECATE** after WorkItem canonical. |
| `FollowUpPolicy` | `models/follow_up_models.py` | **CANONICAL** | Full org governance: autonomy, quiet hours, channel limits, SLA minutes. **KEEP.** |
| `FollowUpSequence` / `FollowUpSequenceStep` | `models/follow_up_models.py` | **CANONICAL** | Multi-step nurture sequence definitions. **KEEP.** |
| `FollowUpEnrollment` | `models/follow_up_models.py` | **CANONICAL** | Per-lead sequence enrollment tracker. **KEEP.** |
| `FollowUpExecution` | `models/follow_up_models.py` | **CANONICAL** | Scheduled outbound follow-up execution. This IS the WorkItem for outbound follow-up. **KEEP.** |
| `FollowUpDecision` | `models/follow_up_models.py` | **CANONICAL** | Audit log per execution decision. **KEEP.** |
| `CommunicationConsent` | `models/follow_up_models.py` | **CANONICAL** | Per-channel, per-purpose consent. **KEEP.** |
| `ContactFatigue` | `models/follow_up_models.py` | **CANONICAL** | Real-time fatigue score tracker. **KEEP.** |
| `NextBestAction` | `models/follow_up_models.py` | **PARTIAL** | Cached NBA result. Free-text string, not enum. Missing: action_type enum, urgency, risk_level, evidence, policy_version. **EXTEND.** |
| `FollowUpAttribution` | `models/follow_up_models.py` | **CANONICAL** | Attribution linking to conversion milestones. **KEEP.** |
| `FollowUpRule` | `models/follow_up_models.py` | **CANONICAL** | Trigger-action rules. Workflow DSL seed. **KEEP.** |
| `FollowUpAutomationEvent` | `models/follow_up_models.py` | **CANONICAL** | Idempotency ledger. **KEEP.** |

### 1.2 Task / Work Item Models

| Model | File | Classification | Assessment |
|---|---|---|---|
| `Task` | `models/crm_models.py` | **PARTIAL** | CRM task: broker_id, lead_id, org_id, due_at, status (pending/in_progress/completed/cancelled), priority. Missing: `type`, `source`, `idempotency_key`, `conversation_id`, `reason`, provenance. **EXTEND — this becomes canonical WorkItem.** |
| `Meeting` | `models/crm_models.py` | **PARTIAL** | Status: scheduled/completed/cancelled/no_show. **ADAPTER target.** |

### 1.3 Workflow Models

| Model | File | Classification |
|---|---|---|
| `WorkflowDefinition` | `models/workflow_models.py` | **CANONICAL** |
| `WorkflowVersion` | `models/workflow_models.py` | **CANONICAL** |
| `WorkflowInstance` | `models/workflow_models.py` | **CANONICAL** |
| `WorkflowApproval` | `models/workflow_models.py` | **CANONICAL** |
| `WorkflowWaitState` | `models/workflow_models.py` | **CANONICAL** |
| `WorkflowTemplate` | `models/workflow_models.py` | **CANONICAL** |

### 1.4 Autonomous Loop / Revenue Autopilot Models

| Model | File | Classification |
|---|---|---|
| `LeadAutomationState` | `modules/autonomous_loop/models.py` | **CANONICAL** |
| `RevenueOpportunity` | `models/revenue_autopilot_models.py` | **CANONICAL** |
| `SlaInstance` | `models/crm_intelligence_models.py` | **CANONICAL** |
| `SlaBreach` | `models/crm_intelligence_models.py` | **CANONICAL** |

---

## 2. SERVICES INVENTORY

### 2.1 Follow-Up Services

| Service | Classification | Assessment |
|---|---|---|
| `FollowUpOrchestratorService` (service.py) | **CANONICAL** | 715-line orchestrator integrating consent, suppression, timing, channel, NBA, sequence, SLA. Dispatches via CommunicationHub. **KEEP.** |
| `SuppressionEngine` | **PRODUCTION-READY** | 5-layer: terminal state, human handoff, consent, fatigue, min interval. **KEEP.** |
| `ConsentManager` | **CANONICAL** | Per-channel consent verification. **KEEP.** |
| `FatigueDetector` | **CANONICAL** | Fatigue score. **KEEP.** |
| `TimingEngine` | **CANONICAL** | Quiet hours, timezone-aware scheduling. **KEEP.** |
| `ChannelSelector` | **CANONICAL** | Multi-channel selection. **KEEP.** |
| `GroundedMessageGenerator` | **CANONICAL** | Grounded generation. **KEEP.** |
| `NextBestActionEngine` (follow_up) | **STUB** | 100 lines. Free-text pipeline_stage only. No enum, no evidence. **REPLACE with adapter to Build 06 NBA.** |
| `SequenceEngine` | **CANONICAL** | Sequence enrollment and step progression. **KEEP.** |
| `SlaService` | **PRODUCTION-READY** | First-contact SLA, breach detection, idempotent task creation. **KEEP.** |
| `RuleEngine` | **CANONICAL** | Trigger-action rule evaluation. **KEEP.** |
| `EscalationService` | **CANONICAL** | Manager escalation. **KEEP.** |
| `ReengagementService` | **PARTIAL** | Generates drafts. No eligibility gate, no consent check. **EXTEND.** |
| `IdempotencyService` | **CANONICAL** | try_acquire / record_success. **KEEP.** |

### 2.2 Workflow Services

| Service | Classification | Assessment |
|---|---|---|
| `WorkflowService` | **CANONICAL** | Definitions, versioning, execution, simulation. **KEEP.** |
| `WorkflowExecutionEngine` | **CANONICAL** | DAG-based durable node execution. **KEEP.** |
| `WorkflowSimulator` | **CANONICAL** | Dry-run simulation. **KEEP.** |
| `ExpressionEvaluator` | **UNKNOWN** | Safety not yet verified (eval/exec risk). |
| `ActionRegistry` | **UNKNOWN** | Must confirm routes through Build 06 auth. |

### 2.3 Autonomous Loop

| Service | Classification | Assessment |
|---|---|---|
| `AutonomousSalesLoopService` | **CANONICAL** | 595-line event-driven orchestrator. Idempotency, tenant validation, state machine, guard chain, dead letter, metrics. **KEEP.** |
| `LeadStateMachine` | **CANONICAL** | Deterministic lifecycle transitions. **KEEP.** |
| `OrchestratorGuardChain` | **CANONICAL** | Consent, fatigue, human handoff, DNC guards. **KEEP.** |

### 2.4 Build 06 AI Agent

| Service | Classification | Assessment |
|---|---|---|
| `NextBestActionEngine` (ai_agent) | **CANONICAL** | 11-step priority ladder, structured `ProposedActionDTO`, evidence, risk tier. **PRIMARY NBA.** |
| `GovernedActionExecutor` | **CANONICAL** | Authorization-gated executor. **KEEP.** |
| `AIActionAuthorizer` | **CANONICAL** | Cryptographic single-use token. **KEEP.** |

---

## 3. CELERY / SCHEDULER STATE

> **Verdict: FULLY CONFIGURED, not yet deployed in this environment.**

`celery_app.py` is a complete enterprise Celery configuration:
- Redis broker + backend (`settings.REDIS_URL`)
- 30+ named queues (lead, notification, whatsapp, ai, retry, dlq, reminders, booking, sla-monitoring, workflow, follow-up)
- SSL support
- 7 task modules registered
- Beat schedule (not audited)

**Celery/Redis is production-configured. Tests mock at the service layer (no Celery worker needed for test suite).**

---

## 4. NBA ENGINE FRAGMENTATION (CRITICAL)

Three independent NBA implementations:

| # | Location | Type | Gap |
|---|---|---|---|
| 1 | `ai_agent/next_best_action.py` | **CANONICAL** | Structured DTO, 11-step priority, enum, evidence, risk tier |
| 2 | `follow_up/next_best_action/nba_calculator.py` | **STUB** | Free-text, pipeline_stage only |
| 3 | `autonomous_loop/` | **PARTIAL** | Policy enforcement, delegates externally |
| 4 | `revenue_autopilot/engine.py` | **SCORING ENGINE** | Opportunity scoring, not NBA decisions |

**Resolution:** Replace stub #2 with thin adapter calling canonical #1.

---

## 5. WORK ITEM FRAGMENTATION (CRITICAL)

No canonical `WorkItem` model exists.

| Concept | Current Model | Missing |
|---|---|---|
| CRM task | `crm_models.Task` | type, source, idempotency_key, conversation_id, reason |
| Follow-up execution | `FollowUpExecution` | type, priority, assigned_to |
| Legacy follow-up | `follow_up.FollowUp` | org_id, most fields |
| Commitment | **DOES NOT EXIST** | Entire model |

**Resolution:** Extend `crm_models.Task` → canonical WorkItem.

---

## 6. WHAT IS MISSING (NET NEW BUILD)

| Item | Priority |
|---|---|
| `Commitment` model + `CommitmentService` | HIGH |
| WorkItem extensions (type, source, provenance, idempotency_key) | HIGH |
| NBA convergence adapter (follow_up NBA → ai_agent NBA) | HIGH |
| Extended NBA output (enum, evidence, risk, timing, channel) | HIGH |
| `ActiveLeadHasNextAction` invariant monitor | HIGH |
| Stale lead + opportunity stall detector | HIGH |
| Reengagement eligibility gate | HIGH |
| Customer reply → cancel stale scheduled follow-up | HIGH |
| Post-visit follow-up workflow trigger | MEDIUM |
| Contact frequency per-day/week enforcer | MEDIUM |
| Test suite (35+ golden paths) | HIGH |

---

## 7. DEPRECATION MAP

| Component | Action |
|---|---|
| `models/follow_up.py::FollowUp` | DEPRECATE — migrate consumers to FollowUpExecution |
| `tasks/followup_tasks.py::async_send_follow_up` | ADAPTER — route to canonical dispatch |
| `follow_up/next_best_action/nba_calculator.py` | REPLACE — thin adapter to ai_agent NBA |

---

## 8. WHAT IS ALREADY PRODUCTION-READY

- `FollowUpPolicy` + governance fields
- `FollowUpExecution` + status machine
- `SuppressionEngine` (5-layer)
- `ConsentManager`, `FatigueDetector`, `TimingEngine`, `ChannelSelector`
- `SlaService` (first-contact SLA)
- `IdempotencyService`
- `WorkflowService` + `WorkflowExecutionEngine` + `WorkflowSimulator`
- `AutonomousSalesLoopService`
- `LeadStateMachine`
- `RevenueAutopilotEngine` (scoring v1)
- `celery_app.py` (enterprise Celery config)
- Build 06 `NextBestActionEngine` + `AIActionAuthorizer` + `GovernedActionExecutor`

