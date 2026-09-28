# WEFYLABS — LEAD EVENT CONTRACTS & OUTBOX SPECIFICATION

## 1. Domain Event & Outbox Taxonomy
All significant business events produced by the lead acquisition and identity layer are formalized as versioned event schemas.

---

## 2. Event Schemas

### 2.1 `lead.ingested`
Emitted when a new lead is successfully ingested and persisted.
- **Aggregate**: `Lead`
- **Aggregate ID**: `lead.id` (UUID string)
- **Tenant ID**: `organization_id`
- **Payload Schema**:
  ```json
  {
    "lead_id": "00000000-0000-0000-0000-000000000001",
    "organization_id": "11111111-1111-1111-1111-111111111111",
    "source": "META",
    "external_source": "meta_lead_ads",
    "external_lead_id": "meta_lead_12345",
    "is_duplicate": false,
    "phone_e164": "+919876543210",
    "email": "customer@example.com",
    "name": "Arjun Kapoor",
    "event_id": "event_uuid_123"
  }
  ```

### 2.2 `lead.reengaged`
Emitted when an existing customer submits an enquiry via another channel.
- **Aggregate**: `Lead`
- **Aggregate ID**: Existing `lead.id`
- **Payload Schema**: Same as `lead.ingested` with `"is_duplicate": true`.

---

## 3. Transactional Outbox Schema (`outbox_events`)
- `id`: UUID primary key
- `event_id`: Unique event UUID string
- `tenant_id`: String UUID of the organization
- `event_type`: Domain event name (e.g. `lead.ingested`)
- `aggregate_type`: `Lead`
- `aggregate_id`: Entity UUID string
- `payload`: JSON data payload
- `status`: `PENDING` | `PROCESSING` | `PROCESSED` | `FAILED` | `DEAD_LETTER`
- `retry_count`: Integer counter (max retries: 5)
- `idempotency_key`: Unique string key (`outbox:<event_id>`)
- `created_at`: Timestamp
