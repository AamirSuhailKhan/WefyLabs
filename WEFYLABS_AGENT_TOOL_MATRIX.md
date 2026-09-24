# WEFYLABS AI WORKFORCE — AGENT × TOOL PERMISSION MATRIX

## Canonical Agent Tool Permission Matrix (Part 10)

Every agent execution passes through the centralized `WorkforcePolicyEngine`. Agent identity is strictly non-authoritative: tenant boundaries, capability permissions, and confirmation gates are validated prior to any tool execution.

| AGENT | TOOL | READ | WRITE | SIDE EFFECT | CONFIRMATION | TENANT | ROLE | STATUS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SALES_AGENT** | `search_properties` | Yes | No | No | No | Enforced | Customer-Facing | AUTHORIZED |
| **SALES_AGENT** | `check_availability` | Yes | No | No | No | Enforced | Customer-Facing | AUTHORIZED |
| **SALES_AGENT** | `get_payment_plan` | Yes | No | No | No | Enforced | Customer-Facing | AUTHORIZED |
| **SALES_AGENT** | `book_viewing` | No | Yes | Yes | **Required** | Enforced | Customer-Facing | AUTHORIZED |
| **SALES_AGENT** | `request_human_handoff` | No | Yes | Yes | No | Enforced | Customer-Facing | AUTHORIZED |
| **QUALIFICATION_AGENT** | `get_lead_details` | Yes | No | No | No | Enforced | Analytical | AUTHORIZED |
| **QUALIFICATION_AGENT** | `update_lead_status` | No | Yes | Yes | No | Enforced | Analytical | AUTHORIZED |
| **PROPERTY_ADVISOR** | `search_properties` | Yes | No | No | No | Enforced | Specialist | AUTHORIZED |
| **PROPERTY_ADVISOR** | `check_availability` | Yes | No | No | No | Enforced | Specialist | AUTHORIZED |
| **PROPERTY_ADVISOR** | `compare_properties` | Yes | No | No | No | Enforced | Specialist | AUTHORIZED |
| **FOLLOW_UP_AGENT** | `get_lead_details` | Yes | No | No | No | Enforced | Analytical | AUTHORIZED |
| **FOLLOW_UP_AGENT** | `get_recent_interactions`| Yes | No | No | No | Enforced | Analytical | AUTHORIZED |
| **FOLLOW_UP_AGENT** | `draft_followup` | Yes | No | No | No | Enforced | Analytical | AUTHORIZED |
| **APPOINTMENT_ASSISTANT** | `get_available_slots` | Yes | No | No | No | Enforced | Action Specialist| AUTHORIZED |
| **APPOINTMENT_ASSISTANT** | `check_availability` | Yes | No | No | No | Enforced | Action Specialist| AUTHORIZED |
| **APPOINTMENT_ASSISTANT** | `book_viewing` | No | Yes | Yes | **Required** | Enforced | Action Specialist| AUTHORIZED |
| **HANDOFF_ASSISTANT** | `request_human_handoff` | No | Yes | Yes | No | Enforced | Escalation | AUTHORIZED |
| **HANDOFF_ASSISTANT** | `get_lead_details` | Yes | No | No | No | Enforced | Escalation | AUTHORIZED |
| **REVENUE_COPILOT** | `get_opportunity_details`| Yes | No | No | No | Enforced | Internal Advisor | AUTHORIZED |
| **REVENUE_COPILOT** | `get_pipeline_metrics` | Yes | No | No | No | Enforced | Internal Advisor | AUTHORIZED |
| **MANAGER_COMMAND_AGENT**| `get_pipeline_metrics` | Yes | No | No | No | Enforced | Internal Command | AUTHORIZED |
| **MANAGER_COMMAND_AGENT**| `get_sla_breaches` | Yes | No | No | No | Enforced | Internal Command | AUTHORIZED |
| **MANAGER_COMMAND_AGENT**| `get_team_workload` | Yes | No | No | No | Enforced | Internal Command | AUTHORIZED |
| **MANAGER_COMMAND_AGENT**| `get_stalled_opportunities`| Yes | No | No | No | Enforced | Internal Command | AUTHORIZED |

---

## Negative Authorization Enforcements (Explicitly Blocked)

1. **`PROPERTY_ADVISOR` cannot execute CRM mutations or bookings**:
   - `book_viewing` -> **FORBIDDEN** (Raises `WorkforceSecurityViolation`)
   - `update_lead_status` -> **FORBIDDEN**
2. **`REVENUE_COPILOT` cannot modify sales records or trigger communications**:
   - Direct opportunity scoring alteration -> **FORBIDDEN** (Domain engine is authoritative)
   - `book_viewing` -> **FORBIDDEN**
3. **`SALES_AGENT` cannot view internal SLA breaches or team workload metrics**:
   - `get_sla_breaches` -> **FORBIDDEN**
   - `get_team_workload` -> **FORBIDDEN**
4. **Cross-Tenant Tool Calls**:
   - Supplying an `organization_id` different from the verified session context -> **FORBIDDEN** (Tenant mismatch blocked unconditionally).
