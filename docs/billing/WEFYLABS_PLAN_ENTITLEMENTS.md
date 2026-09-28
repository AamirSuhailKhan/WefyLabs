# WefyLabs Entitlements & Pre-Action Authorization Engine
**Master Build 13 — Canonical Entitlement Architecture**

## 1. Core Principles
1. **Server-Side Authority:** Frontend UI elements (buttons, forms, dashboards) never act as the security boundary.
2. **Deterministic Evaluation:** `EntitlementService.check_entitlement()` returns deterministic status objects detailing allowance, remaining quota, and enforcement reasons.
3. **Fail-Closed by Default:** In the absence of an active subscription or valid grace period, paid capabilities fail closed (`allowed=False`, `reason="No active subscription found for organization."`).
4. **LLM Decoupled:** Financial and quota authorization executes completely outside LLM logic and prompts.

---

## 2. Supported Entitlement Types & Dimensions
| Entitlement Type | Description | Example Dimension |
| :--- | :--- | :--- |
| `BOOLEAN` | Feature flag toggle (enabled/disabled). | `whatsapp_integration`, `advanced_analytics`, `copilot_agent` |
| `INTEGER_LIMIT` | Monthly hard/soft numeric cap per cycle. | `ai_messages_per_month`, `team_members`, `active_leads` |
| `UNLIMITED` | Unrestricted consumption capability. | `property_inventory`, `api_requests` (Enterprise) |
| `USAGE_LIMIT` | Meter-tracked quota with overage tiering. | `ai_tokens`, `document_processing` |

---

## 3. Enforcement Policies
- **`HARD_LIMIT`**: Immediately rejects requests when cumulative usage exceeds quota (`EntitlementExceededError`).
- **`SOFT_LIMIT`**: Permits request execution with non-blocking customer warning banner (issued at 80% and 90% consumption).
- **`OVERAGE`**: Permits execution beyond included allowance and calculates billable overage line items upon invoice generation.
- **`UNLIMITED`**: No consumption quota applied.

---

## 4. Pre-Action Reservation Pattern
For high-cost asynchronous jobs (e.g. bulk AI document extraction or campaign messaging):
```
[Client / Worker]
       |
       v
1. check_entitlement(org_id, "ai_messages_per_month")
       |--> If False: Raise EntitlementExceededError (Halt)
       v
2. reserve_entitlement(org_id, quantity)
       |--> Lock temporary quota reservation
       v
3. Execute Async Task (LLM Generation / WhatsApp Send)
       |--> Task Succeeded?
       |      |-- YES: commit_reservation() -> UsageEvent persisted
       |      |-- NO:  release_reservation() -> Quota restored
```
