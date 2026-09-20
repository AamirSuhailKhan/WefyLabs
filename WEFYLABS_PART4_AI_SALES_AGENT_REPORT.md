# WefyLabs Part 4 — AI Sales Agent Engine

## Architecture

`ConversationManager` builds a bounded `AgentContext`, selects deterministic strategy/state, builds the prompt, calls the centralized `LLMRouter`, validates model-originated calls in `ToolExecutor`, invokes tenant-scoped canonical services, validates the response, and persists turns, decisions, tool audits, and model usage.

The model has no database handle, does not determine authorization, and does not calculate property truth, matching, qualification completion, or state transitions. Property-specific output comes from verified service results. Appointment booking is confirmation-gated; full conversion execution remains deferred to Part 6.

## Controls added in this milestone

- Machine-readable tool access, tenant, permission, confirmation, audit, and idempotency metadata.
- Central tool input validation before dispatch, including required fields, primitive types, bounded comparisons, slot range, and scoped lead access.
- Runtime tenant/resource context supplied by `ConversationManager` to every model-requested tool call.
- Explicit tool result statuses, rather than ambiguous null outcomes.
- A booking request cannot execute unless trusted application context records explicit customer confirmation.

## Test evidence

Targeted Part 1–3 foundation, AI tool registry, tenant-isolation, and property-truth tests were run with Python's pytest module. Provider-backed runtime verification was not performed because it would require configured live credentials and a controlled tenant.

## Deferred / remaining risks

- Replace the legacy direct Gemini calls in older `app/services/ai_service.py` with the centralized router before declaring repository-wide gateway consolidation complete.
- Capture real `LLMUsage` samples before reporting observed model cost.
- Apply authenticated principal/RBAC checks at the external router endpoints; the agent's internal tool scope is enforced from the trusted conversation context.
