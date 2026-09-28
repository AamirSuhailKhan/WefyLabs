# WefyLabs Subscription Lifecycle & State Machine
**Master Build 13 — Canonical Lifecycle Architecture**

## 1. Lifecycle Finite State Machine (FSM)
A subscription progresses through strictly validated lifecycle states:

```
[New Tenant]
     |
     v
+-----------+       Trial Expires / Payment Success
|  TRIALING +----------------------------------------+
+-----+-----+                                        |
      |                                              v
      | Non-converted                           +----------+
      v                                         |  ACTIVE  |<----+
+-----------+                                   +----+-----+     |
|  EXPIRED  |                                        |           |
+-----------+                     Renewal Payment    |           | Payment
                                  Fails              v           | Recovers
                                                +----------+     |
                                                | PAST_DUE +-----+
                                                +----+-----+
                                                     |
                                  Grace Period       |
                                  Expires            v
                                                +-----------+
                                                | SUSPENDED |
                                                +-----------+
```

---

## 2. Transition Rules Matrix
| Current State | Target State | Trigger | Permitted? | Side Effects |
| :--- | :--- | :--- | :--- | :--- |
| `TRIALING` | `ACTIVE` | Initial checkout / Payment verified | **YES** | Creates BillingPeriod, resets grace, activates full quota |
| `TRIALING` | `EXPIRED` | Trial duration reaches 0 without payment | **YES** | Cuts off paid entitlements, sends conversion reminder |
| `ACTIVE` | `PAST_DUE` | Renewal charge fails on provider | **YES** | Starts 7-day grace period, flags non-blocking UI warning |
| `PAST_DUE` | `ACTIVE` | Overdue invoice paid | **YES** | Extends period end, clears `grace_ends_at` |
| `PAST_DUE` | `SUSPENDED`| `grace_ends_at < now` | **YES** | Blocks paid actions, restricts to read-only customer portal |
| `ACTIVE` | `CANCEL_AT_PERIOD_END`| Customer requests non-renewal | **YES** | Leaves entitlements intact until `current_period_end` |
| `ACTIVE` | `CANCELLED` | Immediate administrative cancellation | **YES** | Revokes entitlements immediately, recalculates proration credit |
| `SUSPENDED`| `CANCELLED` | Final write-off / tenant departure | **YES** | Terminates billing period |

---

## 3. Plan Upgrades & Proration
1. **Immediate Upgrades:** When upgrading from Starter to Pro, new limits take effect instantly.
2. **Proration Credit Calculation:** The system calculates unused time on the previous tier down to the second, generating an automated credit adjustment against the upgrade invoice.
3. **Period Alignment:** Upgrades close the previous open `BillingPeriod` and initialize a fresh period under the new plan version.
