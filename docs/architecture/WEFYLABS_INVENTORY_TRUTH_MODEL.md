# WEFYLABS AUTHORITATIVE INVENTORY TRUTH MODEL

**Build:** Master Build 04  
**Status:** Production Standard  
**Layer:** Core Inventory & State Machine Specification  

---

## 1. Domain Hierarchy

Authoritative inventory truth is anchored in the supply-side hierarchy:

```text
Organization (Tenant Boundary)
    │
    ▼
RealEstateDeveloper (Corporate Entity)
    │
    ▼
RealEstateProject (Master Development / RERA Scoped)
    │
    ▼
ProjectBuilding / Tower (Structural Block)
    │
    ▼
ProjectFloor (Vertical Level: Ground, Podium, 1..N, Penthouse)
    │
    ▼
ProjectUnit (Physical Unit with Stable Identity)
    │
    ├── ProjectUnitStatusLog (Append-Only Status Ledger)
    ├── PropertyPriceHistory (Material Price Changes)
    └── PropertyListing (Marketing Channel Syndication)
```

---

## 2. Canonical State Machine

Units transition strictly across controlled operational states:

```text
+-----------------------------------------------------------------------------------+
|                            INVENTORY STATE MACHINE                                |
+-----------------------------------------------------------------------------------+

     [INITIAL CREATION]
             │
             ▼
     ┌───────────────┐
     │   AVAILABLE   │ ◄──────────────────────────────┐
     └───────┬───────┘                                │
             │                                        │ (Release / Cancel)
    ┌────────┼─────────────────┬──────────────────┐   │
    │        │                 │                  │   │
    ▼        ▼                 ▼                  ▼   │
┌──────┐ ┌──────┐    ┌──────────────────┐   ┌─────────┴┐
│ HOLD │ │ BLOCKED │  │UNDER_NEGOTIATION │   │ALLOCATED │
└───┬──┘ └──────┘    └─────────┬────────┘   └──────────┘
    │                          │
    ▼                          │
┌──────────┐                   │
│ RESERVED │                   │
└─────┬────┘                   │
      │                        │
      ▼                        ▼
┌───────────┐         ┌─────────────────┐
│  BOOKED   │ ──────► │      SOLD       │ (Terminal)
└───────────┘         └─────────────────┘
```

### 2.1 Transition Enforcement Matrix
| Current State | Permitted Next States |
| :--- | :--- |
| **AVAILABLE** | `HOLD`, `RESERVED`, `BLOCKED`, `UNDER_OFFER`, `UNDER_NEGOTIATION`, `ALLOCATED` |
| **HOLD** | `AVAILABLE`, `RESERVED`, `EXPIRED`, `CANCELLED` |
| **RESERVED** | `BOOKED`, `AVAILABLE` (on expiry/release), `CANCELLED` |
| **UNDER_NEGOTIATION** | `RESERVED`, `HOLD`, `AVAILABLE` |
| **ALLOCATED** | `RESERVED`, `AVAILABLE` |
| **BOOKED** | `SOLD`, `AVAILABLE` (on cancellation/forfeit) |
| **BLOCKED** | `AVAILABLE` |
| **SOLD** | *(Terminal state; immutable without executive audit override)* |

---

## 3. Concurrency & Distributed Locking

To prevent race conditions where two sales agents or automated sync jobs attempt to hold or reserve the same unit simultaneously:

1. **Redis Distributed Lock:**
   - Resource key: `inventory:unit:{unit_id}:reservation`
   - TTL: 30 seconds
   - Spin-wait timeout: 500 ms
2. **Database Versioning & Row Locks:**
   - Atomic SQL `UPDATE ... WHERE id = :unit_id AND inventory_status = 'available'`
3. **Idempotency Key Guard:**
   - Repeated reservation requests carrying the identical `idempotency_key` return the existing reservation without re-locking or duplicate status log creation.

---

## 4. Price Truth & Price History

All monetary calculations use `Decimal` arithmetic; floats are prohibited in financial ledgers.

### 4.1 Price Classifications
- `LIST_PRICE`: Current officially published price from developer.
- `NEGOTIATED_PRICE`: Price agreed upon in an active deal pipeline.
- `DISCOUNTED_PRICE`: Price post-promotional scheme or incentive.
- `EFFECTIVE_PRICE`: Total customer outlay including floor rise, parking, and amenities.
- `ESTIMATE`: Indicative market valuation (never quoted by AI as firm list price).

### 4.2 Append-Only Historical Logging
Any material price mutation creates an immutable row in `property_price_history`:
- `unit_id` / `property_id`
- `old_price` vs `new_price`
- `currency` (INR, AED, USD)
- `price_type`
- `source` (e.g. `developer_api`, `csv_import`, `manual_audit`)
- `effective_from` & `effective_to`
- `observed_at` & `created_at`
