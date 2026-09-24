# WEFYLABS ENTITLEMENT & SUBSCRIPTION UX SPECIFICATION
## Centralized Plan, Trial, and Feature Access Architecture

---

## 1. Executive Summary

Previous implementations handled trial expiration through ad-hoc logic:
- A fixed `bg-red-600` banner shifted the entire fixed navigation down by `mt-8`, breaking coordinates on every dashboard view.
- Multiple redundant indicators (`"Trial Expired"` pill + red banner + modal alerts) competed for visual attention.
- Feature gating was implemented via scattershot checks rather than a centralized entitlement service.

This specification unifies the entitlement experience into a predictable, non-destructive architecture.

---

## 2. Entitlement States

| State | User Experience | Navigation | Data Access | Mutations |
| :--- | :--- | :--- | :--- | :--- |
| **`ACTIVE` (Pro / Enterprise)** | Full platform access. Clean header badge: `"Pro Active"`. | Unrestricted | Full | Unrestricted |
| **`TRIAL_HEALTHY` (> 3 days)** | Full platform access. Subtle indicator: `"X Days Trial Left"`. | Unrestricted | Full | Unrestricted |
| **`TRIAL_WARNING` (1–3 days)** | Amber warning indicator with clean upgrade trigger. | Unrestricted | Full | Unrestricted |
| **`EXPIRED` (Trial Ended)** | Persistent inline alert banner in layout flow. Features transition to **READ-ONLY**. Mutation buttons show localized upgrade tooltip/modal. | Stable & reachable | Read-only browsing preserved | Blocked with clear explanation |
| **`SUSPENDED`** | Dedicated account suspension screen requiring administrative contact. | Blocked | Blocked | Blocked |

---

## 3. Frontend Entitlement Utility API

Located in `apps/web/src/lib/entitlements.ts`:

```typescript
export interface EntitlementState {
  status: 'active' | 'trial' | 'expired' | 'suspended';
  plan: 'free' | 'starter' | 'pro' | 'enterprise';
  trialDaysRemaining: number | null;
  features: Record<string, boolean>;
}

export function canAccess(feature: string, state: EntitlementState): boolean {
  if (state.status === 'suspended') return false;
  if (state.status === 'expired') {
    // Read-only inspection allowed, creation/automation blocked
    return READ_ONLY_PERMITTED_FEATURES.includes(feature);
  }
  return true;
}

export function isReadOnly(feature: string, state: EntitlementState): boolean {
  if (state.status === 'expired') return true;
  return false;
}

export function requiresUpgrade(feature: string, state: EntitlementState): boolean {
  if (state.status === 'expired') return true;
  return false;
}
```

---

## 4. UI Gating Rules

1. **No Layout-Breaking Offsets**:
   Never use `mt-8` on fixed headers. Any global entitlement message must sit inside the normal page flow or as an integrated part of the header bar.

2. **Localized Feature Gating**:
   When an expired user visits `/dashboard/marketing` or `/dashboard/deals`:
   - Existing campaigns and deals are fully visible in read-only mode.
   - Primary action buttons (`"New Campaign"`, `"Add Deal"`, `"Publish Listing"`) display a lock icon or trigger an `UpgradeModal` rather than throwing silent 403 errors or crashing.

3. **Backend Remains Authoritative**:
   Frontend entitlement checks improve user experience and eliminate surprise errors. However, the FastAPI backend remains the final authority on all mutations.
