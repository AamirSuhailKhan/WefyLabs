# WEFYLABS PROPERTY EVENT CONTRACTS & TRANSACTIONAL OUTBOX

**Build:** Master Build 04  
**Status:** Production Standard  
**Layer:** Event Sourcing & Messaging Contracts  

---

## 1. Overview & Transactional Guarantees

All state mutations in the property, inventory, and pricing domains write an immutable event record to the `outbox_events` table within the same database transaction as the domain entity update.

This guarantees:
- **Zero Dual-Write Hazards:** A transaction never commits without its corresponding event.
- **Asynchronous Search Projection:** Search indexes consume events reliably without holding database connection locks.
- **Idempotent Consumption:** Every event carries a deterministic `idempotency_key`.

---

## 2. Event Envelope Schema

```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "event_type": "string",
  "aggregate_type": "unit | project | price | conflict",
  "aggregate_id": "string",
  "payload": {},
  "idempotency_key": "string",
  "status": "pending | published | failed",
  "retry_count": 0,
  "created_at": "ISO-8601 UTC",
  "published_at": "ISO-8601 UTC | null"
}
```

---

## 3. Canonical Event Contracts

### 3.1 `inventory.unit.created`
Emitted upon creation of a physical unit record.
```json
{
  "event_type": "inventory.unit.created",
  "aggregate_type": "unit",
  "aggregate_id": "e7b0e1e2-1234-4567-89ab-cdef01234567",
  "payload": {
    "unit_id": "e7b0e1e2-1234-4567-89ab-cdef01234567",
    "unit_code": "UNIT-7A4B12",
    "project_id": "99b0e1e2-0000-4567-89ab-cdef01234567",
    "unit_number": "1002",
    "unit_type": "2BHK",
    "base_price": "5500000.00",
    "currency": "INR",
    "inventory_status": "available",
    "organization_id": "33b0e1e2-2222-4567-89ab-cdef01234567"
  },
  "idempotency_key": "inv_create_e7b0e1e2-1234-4567-89ab-cdef01234567"
}
```

### 3.2 `inventory.unit.reserved`
Emitted when a unit is atomically reserved.
```json
{
  "event_type": "inventory.unit.reserved",
  "aggregate_type": "unit",
  "aggregate_id": "e7b0e1e2-1234-4567-89ab-cdef01234567",
  "payload": {
    "unit_id": "e7b0e1e2-1234-4567-89ab-cdef01234567",
    "unit_code": "UNIT-7A4B12",
    "project_id": "99b0e1e2-0000-4567-89ab-cdef01234567",
    "from_status": "available",
    "to_status": "reserved",
    "deal_id": "55a0e1e2-9999-4567-89ab-cdef01234567",
    "reason": "Token deposit confirmed",
    "actor_id": "11a0e1e2-8888-4567-89ab-cdef01234567",
    "organization_id": "33b0e1e2-2222-4567-89ab-cdef01234567"
  },
  "idempotency_key": "inv_e7b0e1e2-1234-4567-89ab-cdef01234567_reserved_1774681200"
}
```

### 3.3 `inventory.price.changed`
Emitted when an authoritative price revision occurs.
```json
{
  "event_type": "inventory.price.changed",
  "aggregate_type": "price",
  "aggregate_id": "e7b0e1e2-1234-4567-89ab-cdef01234567",
  "payload": {
    "unit_id": "e7b0e1e2-1234-4567-89ab-cdef01234567",
    "old_price": "5500000.00",
    "new_price": "5800000.00",
    "currency": "INR",
    "source": "developer_api",
    "effective_from": "2026-09-26T10:00:00Z",
    "organization_id": "33b0e1e2-2222-4567-89ab-cdef01234567"
  },
  "idempotency_key": "price_e7b0e1e2-1234-4567-89ab-cdef01234567_5800000"
}
```

### 3.4 `inventory.conflict.detected`
Emitted when competing feeds report contradictory facts.
```json
{
  "event_type": "inventory.conflict.detected",
  "aggregate_type": "conflict",
  "aggregate_id": "ccb0e1e2-5555-4567-89ab-cdef01234567",
  "payload": {
    "conflict_id": "ccb0e1e2-5555-4567-89ab-cdef01234567",
    "field_name": "price",
    "current_value": "14000000.0",
    "competing_value": "14500000.0",
    "current_source": "internal_audit",
    "competing_source": "portal_webhook",
    "organization_id": "33b0e1e2-2222-4567-89ab-cdef01234567"
  },
  "idempotency_key": "conflict_price_e7b0e1e2_1774681200"
}
```

---

## 4. Consumer Responsibilities

1. **Search Indexer Worker:**
   - On `inventory.unit.created` or `status_changed`: updates PostgreSQL tsvector and Meilisearch document projections.
   - On index failure: marks outbox event for retry with exponential backoff.
2. **Notification & Deal Orchestrator:**
   - On `inventory.unit.reserved`: alerts dealing broker and dispatches booking agreement documents via WhatsApp Conversation Engine.
3. **Audit & Analytics Worker:**
   - Ingests status logs and price histories for inventory velocity analytics.
