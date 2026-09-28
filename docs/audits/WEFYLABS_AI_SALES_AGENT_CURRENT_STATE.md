# WEFYLABS — AI SALES AGENT & AUTONOMOUS EXECUTION AUDIT
## Master Build 06 — Phase 0: Current-State Architecture & Vulnerability Audit

**Audit Date:** 2026-09-26  
**Auditor:** Principal AI Engineer & Autonomous Systems Architect  
**Scope:** `apps/api/app/modules/ai_agent/**`, `apps/api/app/modules/sales_action/**`, `apps/api/app/modules/autonomous_loop/**`, `apps/api/app/infrastructure/ai_gateway/**`, `apps/api/app/modules/calendar/**`, `apps/api/app/modules/communication/**`  

---

## 1. CLASSIFICATION LEGEND

| Classification | Meaning | Action Required |
|---|---|---|
| ✅ `CANONICAL` | Production-ready, secure, enforces tenant isolation & validation. | Preserve & integrate into SalesAgent. |
| ⚠️ `FRAGMENTED` | Works well in isolation but duplicated or disconnected across modules. | Converge into unified architecture. |
| 🔴 `BYPASS` | Bypasses `AIGateway`, authorization, or tenant checks; potential safety issue. | Eliminate; route through policy & authorizer. |
| 🟡 `STUB` | Skeleton implementation or returns hardcoded text. | Implement real governed behavior. |
| 📦 `INFRA` | Foundational adapter / driver layer. | Reuse as provider boundary. |

---

## 2. SUBSYSTEM AUDIT

### 2.1 AI Agent Orchestration & Specialist Agents
* **Path:** `apps/api/app/modules/ai_agent/orchestrator/orchestrator.py`
* **Classification:** ⚠️ `FRAGMENTED` / 🔴 `BYPASS`
* **Findings:**
  - `QualificationAgent`, `PropertyAgent`, `FinancingAgent`, `SchedulingAgent`, `FollowUpAgent` exist as specialist agents under `BaseSpecialistAgent`.
  - `QualificationAgent.process()` calls `build_router_from_env().route()` directly, bypassing `AIGateway` (no `organization_id` enforcement, no `AIRequestRecord` audit log).
  - `PropertyAgent`, `FinancingAgent`, and `SchedulingAgent` return static placeholder text rather than invoking governed tools or querying verified inventory.
  - No unified `SalesAgent` facade exists to coordinate the end-to-end sales lifecycle.

### 2.2 Conversation Manager
* **Path:** `apps/api/app/modules/ai_agent/conversation_manager/manager.py`
* **Classification:** ⚠️ `FRAGMENTED` / 🔴 `BYPASS`
* **Findings:**
  - Robust 13-step turn pipeline restoring FSM state, enforcing human ownership, building context, selecting strategy, and persisting conversation states.
  - **Bypass:** Step 7 calls `self.llm_router.route()` directly instead of the canonical `AIGateway` established in Build 05.
  - **Authorization Gap:** Tool execution runs directly on model-suggested tool calls without requiring server-side action authorization for state-mutating side effects (e.g., booking viewings, sending external notifications).

### 2.3 Tool Registry & Executor
* **Path:** `apps/api/app/modules/ai_agent/tool_executor/registry.py`, `executor.py`
* **Classification:** ⚠️ `FRAGMENTED`
* **Findings:**
  - Declares 11 tools with JSON schemas: `search_properties`, `check_availability`, `get_payment_plan`, `book_viewing`, `update_qualification`, `update_lead_crm`, `search_knowledge`, `get_lead_context`, `trigger_workflow`, `send_notification`.
  - `ToolDefinition` includes policy metadata: `access` (read | write | external), `tenant_scoped`, `confirmation_required`.
  - `_validate_tool_call()` checks basic schema types and requires `context.get("confirmed_action")` for `book_viewing`.
  - **Gap:** Does not integrate with `AIActionAuthorizer.verify()` to cryptographically check server-side authorization tokens, parameter integrity hashes, or single-use consumption before executing side effects.

### 2.4 Server-Side AI Action Authorization
* **Path:** `apps/api/app/infrastructure/ai_gateway/action_auth.py`
* **Classification:** ✅ `CANONICAL`
* **Findings:**
  - Production-ready server-side authorizer enforcing `READ -> SUGGEST -> CONFIRM -> EXECUTE`.
  - Cryptographically verifies parameter SHA-256 hashes (`parameters_hash`), ensuring parameters cannot be tampered with between proposal and execution.
  - Enforces fail-closed multi-tenancy (`AIActionAuthorization.organization_id == org`).
  - Enforces TTL expiration (`record.expires_at < now`).
  - Consumes authorizations on single execution (`status = "consumed"`) to prevent replay attacks.
  - **Required Action:** Must be wired into the core `ActionExecutor` and canonical `SalesAgent` for all state-mutating side effects.

### 2.5 Sales Action Policy Engine & Next Best Action (NBA)
* **Path:** `apps/api/app/modules/sales_action/policy_engine.py`, `service.py`, `taxonomies.py`
* **Classification:** ✅ `CANONICAL`
* **Findings:**
  - Pure deterministic policy engine evaluating lead state, qualification snapshots, property matches, consent status, quiet hours, and contact fatigue.
  - Strict priority ordering:
    1. Human escalation / triggers (Priority 100)
    2. Consent revocation / fatigue blocking (Priority 90)
    3. Viewing confirmations / reminders (Priority 80)
    4. Missing qualification collection (Priority 70)
    5. Property recommendation dispatch (Priority 60)
    6. Re-engagement follow-up (Priority 50)
  - Controlled action taxonomy (`SalesActionType`, `SalesActionStatus`, `CommunicationChannel`).
  - **Required Action:** Elevate to canonical `NextBestActionEngine` called during each agent turn.

### 2.6 Autonomous Sales Loop & Guard Chain
* **Path:** `apps/api/app/modules/autonomous_loop/orchestrator.py`, `guard_chain.py`, `emergency_pause.py`
* **Classification:** ✅ `CANONICAL`
* **Findings:**
  - `AutonomousSalesLoopService` manages event-driven lifecycle processing.
  - `OrchestratorGuardChain` validates:
    1. Tenant isolation & active status
    2. Lead lifecycle state
    3. Emergency pause (global & tenant-specific kill switches)
    4. Contact fatigue & quiet hours
    5. Communication consent
    6. Autonomous execution permission policies
  - `EmergencyAutomationPauseService` allows instantaneous pausing of autonomous actions globally or per tenant.

### 2.7 Human Handoff & Overrides
* **Path:** `apps/api/app/modules/ai_agent/handoff/handoff_service.py`, `apps/api/app/modules/communication/canonical_service.py`
* **Classification:** ✅ `CANONICAL`
* **Findings:**
  - `HandoffService` creates `Escalation` records with rich briefings (buyer profile, properties discussed, objections raised, pending questions, last 20 conversation turns).
  - `CanonicalCommunicationService` manages `control_mode` transitions (`ai` <-> `human`), pauses autonomous outreach, and logs takeover audit records.
  - When human takes control (`control_mode = "human"`), autonomous AI sends are strictly blocked.

### 2.8 Calendar, Meetings & Appointments
* **Path:** `apps/api/app/modules/calendar/service.py`
* **Classification:** ✅ `CANONICAL`
* **Findings:**
  - `SchedulingOrchestratorService` handles availability search, booking locks, appointment creation, conflict checks, and viewings.
  - Booking is idempotent and checks for schedule conflicts, preventing double-booking.

---

## 3. SUMMARY OF DEFICIENCIES TO RESOLVE IN BUILD 06

1. **No Single Unified `SalesAgent`:** The system has fragments across `ConversationManager`, `AutonomousSalesLoopService`, `SalesActionDomainService`, `MultiAgentOrchestrator`, and `CopilotAgentEngine`. We must converge onto one canonical `SalesAgent` with the full lifecycle methods:
   `understand()`, `qualify()`, `search()`, `recommend()`, `answer()`, `handle_objection()`, `draft()`, `propose_action()`, `execute_authorized_action()`, `handoff()`, `summarize()`, `learn_from_outcome()`.
2. **Missing Action Authorization Enforcement in Agent Execution:** The AI agent can propose actions, but execution must strictly enforce `AIActionAuthorizer.verify()` before any external side effects (messages, calendar events, CRM mutations).
3. **No Centralized Objection Intelligence:** Objection handling is dispersed; we must implement a structured objection classification and response framework (`PRICE`, `LOCATION`, `TRUST`, `TIMELINE`, etc.) with zero false scarcity or fake discounts.
4. **Agent State Machine vs. Customer Journey State:** The conversation state (FSM) is mixed with business lead states. We must formally separate:
   - Agent Conversation States: `NEW`, `UNDERSTANDING`, `QUALIFYING`, `DISCOVERING`, `RECOMMENDING`, `ANSWERING`, `OBJECTION_HANDLING`, `FOLLOW_UP`, `WAITING`, `HANDOFF_REQUIRED`, `HUMAN_ACTIVE`, `RESOLVED`.
   - Customer Journey States: `NEW_LEAD`, `CONTACTED`, `QUALIFYING`, `QUALIFIED`, `PROPERTY_DISCOVERY`, `PROPERTY_SHORTLIST`, `ENGAGED`, `APPOINTMENT_PROPOSED`, `APPOINTMENT_CONFIRMED`, `SITE_VISIT_SCHEDULED`, `SITE_VISIT_COMPLETED`, `NEGOTIATION`, `BOOKING_READY`, `BOOKED`, `LOST`, `NURTURING`.
5. **AIGateway Centralization:** All agent reasoning must strictly route through `AIGateway.complete()` with `organization_id`, ensuring full observability, token caps, and tenant fail-closed invariants.
6. **Action Risk Tiers & Configurable Autonomy Policies:** Formalize `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` risk tiers, preventing autonomous execution of high/critical actions without explicit approval.

---

## 4. CONVERGENCE BLUEPRINT

```text
                    CUSTOMER MESSAGE
                           ↓
                    AIGateway (Observability + Tenant Boundary)
                           ↓
                Canonical SalesAgent
                           ↓
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
   Qualification      Property Graph      Knowledge / RAG
   (Build 05)         (Build 04)         (Build 05 Grounded)
          ↓                ↓                ↓
          └────────────────┼────────────────┘
                           ↓
                 Objection Intelligence
                           ↓
               Next-Best-Action Engine
                           ↓
                 Action Policy Engine
                           ↓
              AI Action Authorizer (HMAC / TTL)
                           ↓
                 Action Executor
            (Side Effect: Outbox / Calendar / CRM)
                           ↓
                    Post-Action Verify
                           ↓
                  Memory / Trace Update
```
