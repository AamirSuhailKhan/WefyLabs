# WefyLabs Canonical Outcome Model

## 1. Absolute Invariants of the Outcome Model
1. **Append-Only & Immutable**: No outcome event may ever be updated or deleted in production.
2. **Mandatory Tenant Gating**: `organization_id` is cryptographically enforced and indexed on every row.
3. **Cryptographic Provenance**: Every event contains a deterministic SHA-256 hash calculated over `(org_id, event_type, entity_type, entity_id, occurred_at, revenue_impact)`.
4. **Distinction Between Prediction and Fact**: Model predictions are stored as candidate signals; outcome events record actual business reality.

## 2. Canonical Outcome Event Types
| Event Type | Entity Type | Financial Impact | Trigger Source |
| :--- | :--- | :--- | :--- |
| `LEAD_QUALIFIED` | `LEAD` | None | CRM / Agent Qualification |
| `LEAD_DISQUALIFIED` | `LEAD` | None | Agent Review / Rule |
| `PROPERTY_MATCH_ACCEPTED` | `PROPERTY` | None | Lead / Agent Shortlist |
| `PROPERTY_MATCH_REJECTED` | `PROPERTY` | None | Explicit Client Pass |
| `MESSAGE_REPLIED` | `MESSAGE` | None | WhatsApp Webhook / Inbound |
| `FOLLOWUP_COMPLETED` | `FOLLOW_UP` | None | Agent Call / SMS Logged |
| `APPOINTMENT_BOOKED` | `APPOINTMENT` | None | Calendar Engine / Portal |
| `SITE_VISIT_COMPLETED` | `SITE_VISIT` | None | Location GPS / Agent Check-in |
| `SITE_VISIT_NO_SHOW` | `SITE_VISIT` | None | SLA Timeout Post-Appointment |
| `OPPORTUNITY_ADVANCED` | `OPPORTUNITY`| Pipeline | Deal Room Milestone Advance |
| `BOOKING_CREATED` | `BOOKING` | Gross Booking | Unit Reservation Agreement |
| `REVENUE_REALIZED` | `BOOKING` | Realized Rev | Payment Cleared / Escrow |
| `REFUND` | `BOOKING` | Negative Rev | Customer Cancellation Refund |

## 3. Database Schema Implementation
```python
class OutcomeEvent(Base):
    __tablename__ = "outcome_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(30), nullable=False)
    revenue_impact: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONBType, default=dict, nullable=False)
```

## 4. Tamper-Proof Provenance Verification
```python
def verify_event_integrity(event: OutcomeEvent) -> bool:
    payload = {
        "org_id": event.organization_id,
        "event_type": event.event_type,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "occurred_at": event.occurred_at.isoformat(),
        "revenue_impact": str(event.revenue_impact or 0),
    }
    expected_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return event.metadata_json.get("provenance_hash") == expected_hash
```
