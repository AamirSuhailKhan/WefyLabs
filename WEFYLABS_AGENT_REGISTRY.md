# WEFYLABS AI WORKFORCE — AGENT REGISTRY

## Canonical Agent Registry (Part 10)

All specialist agents operate over a single unified application state, adhering to strict multi-tenant scoping and bounded token/delegation policies.

| AGENT | PURPOSE | INPUT | OUTPUT | TOOLS | DELEGATES TO | CAN WRITE | CONFIRMATION | TENANT | MODEL | STATUS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SALES_AGENT** | Primary conversational orchestrator, buyer discovery, sales qualification, and unified customer persona. | Customer message, conversation state, lead requirements | Natural language response, suggested requirement updates, shortlist actions | `search_properties`, `check_availability`, `get_payment_plan`, `book_viewing`, `request_human_handoff` | `PROPERTY_ADVISOR`, `QUALIFICATION_AGENT`, `APPOINTMENT_ASSISTANT`, `HANDOFF_ASSISTANT` | Yes (Lead requirements, shortlist) | Yes (`book_viewing`) | Enforced (Strict) | `gemini-1.5-pro` | ACTIVE |
| **QUALIFICATION_AGENT** | Analyzes customer responses, extracts explicit/implicit preferences, scores missing requirements. | Customer message, current qualification state | Qualification delta, missing criteria questions, buyer readiness summary | `get_lead_details`, `update_lead_status` | None (Leaf reasoning role) | No direct CRM mutations without domain validation | No | Enforced (Strict) | `gemini-1.5-flash` | ACTIVE |
| **PROPERTY_ADVISOR** | Deep property comparisons, amenity analysis, verified fact packs, and match explanations. | Property IDs, buyer preferences, comparison requests | Comparative matrix, verified truth answers, amenity citations | `search_properties`, `check_availability`, `compare_properties` | None (Leaf reasoning role) | No (Read-only property truth consumer) | No | Enforced (Strict) | `gemini-1.5-pro` | ACTIVE |
| **FOLLOW_UP_AGENT** | Drafts post-interaction messages, post-visit briefings, and re-engagement templates. | Customer context, visit history, objection log | Structured message drafts, follow-up timing, channel recommendations | `get_lead_details`, `get_recent_interactions`, `draft_followup` | None (Leaf reasoning role) | No (Follow-Up Automation engine owns send/schedule) | No | Enforced (Strict) | `gemini-1.5-flash` | ACTIVE |
| **APPOINTMENT_ASSISTANT** | Interprets viewing requests, queries real-time calendar slots, prepares bookings. | Preferred date/time, property ID, lead ID | Verified slot options, confirmation prompts, booking receipts | `get_available_slots`, `check_availability`, `book_viewing` | `HANDOFF_ASSISTANT` | Yes (Viewing bookings via verified domain service) | Yes (`CONFIRMATION_REQUIRED` before booking execution) | Enforced (Strict) | `gemini-1.5-flash` | ACTIVE |
| **HANDOFF_ASSISTANT** | Synthesizes conversation context, requirements, and objections into concise human handoff packets. | Full turn context, customer objections, urgency signals | Executive summary, requirements brief, escalation rationale | `request_human_handoff`, `get_lead_details` | None (Leaf reasoning role) | Yes (Updates handoff queue and status) | No | Enforced (Strict) | `gemini-1.5-flash` | ACTIVE |
| **REVENUE_COPILOT** | Explains Revenue Autopilot signals, priority scores, deal velocity, and stall reasons. | Opportunity ID, lead ID, revenue signals | Urgency breakdown, next recommended revenue action | `get_opportunity_details`, `get_pipeline_metrics` | None (Internal advisory role) | No (Revenue Autopilot engine owns opportunity scoring) | No | Enforced (Strict) | `gemini-1.5-pro` | ACTIVE |
| **MANAGER_COMMAND_AGENT** | Enterprise command assistant answering team workload, SLA breaches, stalled deals, and hot inventory. | Manager query, filter criteria, operational scope | Structured operational diagnostic, prioritized lead list, actionable recommendations | `get_pipeline_metrics`, `get_sla_breaches`, `get_team_workload`, `get_stalled_opportunities` | `REVENUE_COPILOT` | No (High-impact CRM modifications require human authorization) | No | Enforced (Strict) | `gemini-1.5-pro` | ACTIVE |

---

## Agent Configuration Specifications

- **Token Budgets**:
  - `SALES_AGENT`: 2048 max output tokens (complex conversational synthesis)
  - `QUALIFICATION_AGENT`: 1024 max output tokens (structured requirement extraction)
  - `PROPERTY_ADVISOR`: 1536 max output tokens (comparative matrices & truth packs)
  - `FOLLOW_UP_AGENT`: 1024 max output tokens (concise contextual drafts)
  - `APPOINTMENT_ASSISTANT`: 512 max output tokens (slot interpretation & confirmation receipts)
  - `HANDOFF_ASSISTANT`: 1024 max output tokens (concise structured operator summaries)
  - `REVENUE_COPILOT`: 1024 max output tokens (opportunity signal explanations)
  - `MANAGER_COMMAND_AGENT`: 2048 max output tokens (executive operational diagnostics)
- **Timeouts**: 10,000ms – 15,000ms with fail-safe parent fallback.
- **Max Recursion Depth**: `MAX_AGENT_DEPTH = 3`.
- **Concurrency & State**: Zero separate agent databases. Single shared PostgreSQL state with transactional isolation.
