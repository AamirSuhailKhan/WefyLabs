# WEFYLABS INVENTORY STATE MACHINE & CONCURRENCY PROTOCOL
## Formal State Machine & Concurrency Control Specification

---

## 1. Mathematical State Machine Formulation

Let $S$ be the finite set of authoritative unit inventory states:
$$S = \{\text{AVAILABLE}, \text{RESERVED}, \text{UNDER\_OFFER}, \text{BOOKED}, \text{SOLD}, \text{BLOCKED}, \text{RETURNED}\}$$

Let $T: S \to \mathcal{P}(S)$ be the deterministic allowable transition function:

$$T(\text{AVAILABLE}) = \{\text{RESERVED}, \text{BLOCKED}, \text{UNDER\_OFFER}\}$$
$$T(\text{RESERVED}) = \{\text{AVAILABLE}, \text{BOOKED}, \text{BLOCKED}\}$$
$$T(\text{UNDER\_OFFER}) = \{\text{RESERVED}, \text{AVAILABLE}, \text{BOOKED}\}$$
$$T(\text{BOOKED}) = \{\text{SOLD}, \text{RETURNED}\}$$
$$T(\text{RETURNED}) = \{\text{AVAILABLE}\}$$
$$T(\text{BLOCKED}) = \{\text{AVAILABLE}\}$$
$$T(\text{SOLD}) = \emptyset \quad \text{(Irreversible terminal state)}$$

Any transition $(s_1, s_2)$ where $s_2 \notin T(s_1)$ is strictly prohibited by `UnitInventoryStatus.can_transition()` and rejected with HTTP `409 Conflict`.

---

## 2. Distributed Locking & Race Condition Prevention

1. **Lock Key**: `lock:inventory:unit:{unit_id}:reservation`
2. **Lock Manager**: `RedisDistributedLock` with atomic `SET NX EX 30` and in-process fallback for test environments.
3. **Idempotency Guard**:
   - Replays with matching `last_reservation_idempotency_key` return the existing held unit without raising transition error or writing duplicate log entries.
4. **Expiry Auto-Release**:
   - Holds are bound to `reservation_expires_at` (default 48 hours).
   - Once released, the unit transitions back to `AVAILABLE` and becomes bookable by other buyers.
