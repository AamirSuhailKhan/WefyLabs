# WEFYLABS AUTONOMOUS REVENUE OS — CONTROLLED PILOT OPERATIONS RUNBOOK

**Document Version**: 1.0.0  
**Effective Date**: 2026-10-28  
**Target Environment**: Local Docker Compose / Staging Infrastructure  
**Author**: Controlled Pilot Operations Lead & Senior Systems Architect  
**Classification**: Internal Operational Runbook  

---

## 1. Controlled Pilot Scope Boundaries

To guarantee customer safety, prevent data leakage, and eliminate unintentional external messaging, the pilot operates strictly within the following boundaries:

### 1.1 In-Scope Features
- Broker and team authentication via Supabase JWT Bearer tokens.
- Organization workspace scoping and role-based permissions (`admin`, `agent`, `read_only`).
- Inbound lead ingestion via authenticated APIs and mock webhook endpoints.
- Lead lifecycle status transitions (`new` -> `contacted` -> `qualified` -> `negotiation` -> `won`/`lost`).
- Agent assignment, task scheduling, and reminder generation.
- Internal AI sales brief generation and Next-Best-Action (NBA) structured recommendations.
- Property catalog browsing and deterministic requirement matching.
- CRM dashboard analytics and activity timeline visualization.

### 1.2 Excluded Features
- Live automated WhatsApp messaging to external customer phone numbers.
- Automated customer email delivery via live SMTP relays.
- Real credit card/payment charging via live Razorpay settlement APIs.
- Fully autonomous AI actions without prior broker review and confirmation.
- Direct public internet exposure without an authenticated reverse proxy.

### 1.3 Actions Requiring Explicit Human Approval
- Transition of any follow-up execution from `pending_approval` to `approved`.
- Any modification to outbound communication feature flags (`FOLLOWUP_HUB_DISPATCH_ENABLED`).
- Bulk reassignment or deletion of lead records.
- Any manual database schema modification or migration.

### 1.4 Operating Roles & Ownership
- **Pilot Operator**: Designated Senior Release Engineer (responsible for execution, monitoring, and runbook compliance).
- **Responsible Technical Owner**: Lead Architect / CTO (holds sole authority to approve outbound dispatch activation or pilot scope changes).

---

## 2. Operational Health & Telemetry Monitoring

The pilot operator must monitor the running system using the following non-invasive inspection commands:

### 2.1 API Service & Infrastructure Health
```powershell
# Expected: {"status": "healthy", "database": {"connected": true}, "redis": {"connected": true}}
curl -s http://127.0.0.1:8000/health
```

### 2.2 Database & Connection Pool Monitoring
```powershell
# Check active connections and database size:
docker compose exec postgres psql -U postgres -d leadscore -c "SELECT count(*) AS active_conns FROM pg_stat_activity WHERE datname = 'leadscore'; SELECT pg_size_pretty(pg_database_size('leadscore')) AS db_size;"
```
- **Normal Observation**: Active connections between 3 and 10; database size under 50 MB for pilot volumes.

### 2.3 Redis Queue Backlog Inspection
```powershell
# Inspect Celery queue length:
docker compose exec redis redis-cli LLEN celery
```
- **Normal Observation**: Queue length between 0 and 5. A persistent backlog (> 50 items) indicates worker blockage.

### 2.4 Celery Worker & Beat Process Health
```powershell
# Check for unhandled exceptions or event loop errors:
docker compose logs --since=15m --tail=100 celery_worker | Select-String -Pattern "ERROR", "Traceback", "closed"
```
- **Normal Observation**: Clean log stream of task receipts and acknowledgments. Zero `RuntimeError: Event loop is closed`.

### 2.5 Outbound Safeguard Circuit-Breaker Verification
```powershell
# Verify that outbound dispatch remains actively suppressed:
docker compose exec celery_worker python -c "from app.config import settings; print('FOLLOWUP_HUB_DISPATCH_ENABLED =', getattr(settings, 'FOLLOWUP_HUB_DISPATCH_ENABLED', False))"
```
- **Mandatory Observation**: Must print `FOLLOWUP_HUB_DISPATCH_ENABLED = False`.

---

## 3. Objective Abort & Pause Criteria

The pilot operator MUST immediately halt autonomous operations if ANY of the following conditions occur:

1. **Cross-Tenant Access Detection**: Any logged error or audit entry indicating a request attempted or succeeded in querying an organization outside its authenticated context.
2. **Unexpected Outbound Communication**: Any log message indicating a message was dispatched to an external WhatsApp or SMTP endpoint while `FOLLOWUP_HUB_DISPATCH_ENABLED` was assumed false.
3. **Database Integrity Anomaly**: Any foreign-key violation, unique constraint corruption, or unexpected drop in table row counts.
4. **Repeated Celery Task Loop Failure**: Occurrence of `RuntimeError: Event loop is closed` or unhandled worker process restarts.
5. **Persistent API Unavailability**: The `/health` endpoint fails or reports database disconnection for more than 3 consecutive checks.
6. **Unexplained Google Gemini API Spikes**: Any anomaly in API latency (> 10s) or unexplained quota consumption reported in Google Cloud Console.

---

## 4. Emergency Stop & Rollback Procedures

### 4.1 Emergency Stop Command
If any abort criterion is triggered, the operator must immediately execute:
```powershell
docker compose stop celery_worker celery_beat
```
- **Execution Time**: Halts all asynchronous workers within **2 seconds**.
- **Data Safety**: Does NOT stop PostgreSQL or Redis; does NOT delete volumes; preserves all in-flight database transactions without data loss.

### 4.2 Limitations of the Emergency Stop
- Stopping the worker processes prevents future task evaluations and pending queue dispatches.
- It **does not reverse** database mutations that have already been committed.
- It **does not retract** external network calls that were already dispatched prior to issuing the command.

### 4.3 Clean Restart Procedure
Once the root cause is resolved and documented:
```powershell
docker compose up -d celery_worker celery_beat
docker compose logs --tail=50 celery_worker
```

---

## 5. Owner Approval Checklist

Before any real customer brokerage data is ingested or test users are granted access, the **Responsible Technical Owner** must review and sign off on this checklist:

| Checkpoint | Verification Requirement | Owner Sign-Off |
|---|---|---|
| **1. Residual Risk Acceptance** | The unrotated Google Gemini API key is accepted as an unresolved risk bounded by private repository access and spending caps. | `[ ] APPROVED` |
| **2. Outbound Circuit Breaker** | Verified that `FOLLOWUP_HUB_DISPATCH_ENABLED = False` is active across API and worker runtimes. | `[ ] APPROVED` |
| **3. Disaster Recovery Verified** | Verified that a binary database backup exists (`./backups/`) and restored cleanly in 21.29 seconds. | `[ ] APPROVED` |
| **4. Multi-Tenant Isolation** | Confirmed that tenant boundaries reject IDOR requests and enforce organization headers. | `[ ] APPROVED` |
| **5. Network Exposure Boundary** | Confirmed that containers bind to `127.0.0.1` and will only be exposed via an authenticated TLS reverse proxy. | `[ ] APPROVED` |
| **6. Monitoring Ownership** | Designated operator is actively monitoring `/health`, Celery logs, and Redis queues during pilot hours. | `[ ] APPROVED` |
| **7. Emergency Abort SOP** | Operator has verified the emergency abort command (`docker compose stop celery_worker celery_beat`). | `[ ] APPROVED` |
