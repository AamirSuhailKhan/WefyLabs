# WEFYLABS PROPERTY SYNC & INVENTORY OPERATIONS RUNBOOK

**Build:** Master Build 04  
**Status:** Production Standard  
**Layer:** Operations & Integration Runbook  

---

## 1. Canonical Sync Architecture

Synchronizing inventory from external providers (developer feeds, portal webhooks, broker syndications, batch CSV imports) follows a strict pipeline:

```text
External Source Feed / Webhook / CSV
                  │
                  ▼
         1. Raw Event Ingestion
                  │
                  ▼
         2. Deterministic Idempotency Guard
                  │
                  ▼
         3. Field Normalization (Taxonomy, Currency, Area)
                  │
                  ▼
         4. Stable Identity Resolution (Project/Building/Unit)
                  │
                  ▼
         5. Domain Validation (Schema, Numeric bounds)
                  │
                  ▼
         6. Conflict Detection (Source Precedence Check)
                 / \
   [Conflict]   /   \   [No Conflict]
               ▼     ▼
    Record to         Canonical Upsert (DB Transaction)
    Conflict                 │
    Workbench                ▼
                       7. History Logging (Price/Status)
                             │
                             ▼
                       8. Transactional Outbox Event
                             │
                             ▼
                       9. Async Search Projection & Cache Invalidation
```

---

## 2. Source Trust Precedence

When updates are received from multiple sources for the same property or unit, the engine enforces deterministic source precedence:

```text
Tier 1: Developer Direct API (Highest Trust)
   ↓
Tier 2: Verified Internal Physical Audit
   ↓
Tier 3: Authorized Broker Feed
   ↓
Tier 4: Portal Feed (99acres, Housing)
   ↓
Tier 5: CSV Batch Import
   ↓
Tier 6: Manual Operator Entry (Lowest Trust)
```

**Rule:** A lower-tier source may never overwrite a higher-tier source's active data. Competing data generates a `PropertyDataConflict` record for manual resolution in the Conflict Workbench.

---

## 3. CSV Import Operations

### 3.1 Standard Pipeline Execution
1. **Upload & Format Validation:** Check CSV headers against canonical column definitions (`title`, `price`, `bedrooms`, `city`, `locality`, `built_up_area_sqft`, `amenities`).
2. **Dry-Run Mode (`dry_run=True`):**
   - Parses all rows without committing to database.
   - Categorizes each row:
     - `CREATED`: Valid new property.
     - `UPDATED`: Existing property with updated fields.
     - `UNCHANGED`: Existing property with identical values.
     - `DUPLICATE`: Multiple rows with matching identity in same file.
     - `INVALID`: Missing required columns or failed validation.
3. **Commit Mode (`dry_run=False`):**
   - Applies validated records in a single database transaction.
   - Writes initial status logs and emits outbox events.

---

## 4. Inventory Deprecation & Deletion Policy

**CRITICAL RULE:** Never execute a database `DELETE` simply because an external feed omits a unit or reports zero availability.

1. **Missing from Source Feed:**
   - Mark unit as `SOURCE_REMOVED` or `UNAVAILABLE`.
   - Update `last_verified_at` timestamp.
   - Preserve all historical price and deal records for revenue intelligence.
2. **Prolonged Absence (>30 Days):**
   - Transition unit to `ARCHIVED`.
   - Evict from customer search projections while retaining relational integrity.

---

## 5. Operational Incident Runbooks

### Runbook A: Stale Inventory Alert Triggered
- **Symptom:** More than 5% of units have `availability_observed_at` > 2 hours.
- **Action:**
  1. Check Celery inventory sync worker logs (`celery.sync_inventory`).
  2. Inspect external provider API rate-limit statuses.
  3. If provider is down, verify search queries fallback to marking inventory `requires_confirmation: True`.

### Runbook B: Resolving Data Conflicts via Workbench
- **Endpoint:** `POST /api/v1/property-intelligence/conflicts/{conflict_id}/resolve`
- **Payload:**
  ```json
  {
    "resolution": "ACCEPT_COMPETING | KEEP_CURRENT | MANUAL_OVERRIDE",
    "reason": "Developer emailed signed revision sheet",
    "override_value": "14200000.0"
  }
  ```
- **Action:** Resolving a conflict immediately updates the canonical property record and invalidates the cached search projection.
