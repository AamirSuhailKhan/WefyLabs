# WEFYLABS PHASE 10 — CONTROLLED PILOT OPERATING CHECKLIST
**Autonomous Revenue OS & AI Real Estate CRM**  
**Operating Mode:** `PILOT_MODE = "RECOMMEND_ONLY"`  
**Target:** Restricted Internal Alpha Pilot  
**Date:** 2026-10-28  

---

## 1. Operating Model & Invariants

During the restricted internal pilot, the system operates strictly in **RECOMMEND_ONLY** mode:
1. **Autonomous Action Disabled:** The AI agent and Revenue Intelligence engine generate suggestions, draft responses, lead scores, and recommended actions, but **NEVER** autonomously execute or dispatch them without human confirmation.
2. **Zero Outbound Messages:**
   - `WHATSAPP_ENABLED = false`
   - `FOLLOWUP_HUB_DISPATCH_ENABLED = false`
   - `SMS_ENABLED = false`
   - All outbound communication adapters return `CHANNEL_DISABLED` or `CONFIGURATION_REQUIRED`.
3. **Database Invariance:** Live database schema changes can only be performed via authoritative Alembic migrations following `PHASE10_MIGRATION_0049_RUNBOOK.md`.

---

## 2. Pre-Flight Pilot Checklist

Before inviting pilot brokers or loading demo tenant data, verify every item below:

### Configuration Verification:
- [ ] Confirm `ENV` is set to `production` or `staging`.
- [ ] Confirm `PILOT_MODE=RECOMMEND_ONLY`.
- [ ] Confirm `WHATSAPP_ENABLED=false`.
- [ ] Confirm `FOLLOWUP_HUB_DISPATCH_ENABLED=false`.
- [ ] Confirm `AUTO_CREATE_SCHEMA_ON_STARTUP=false`.
- [ ] Verify `SECRET_KEY` has at least 32 characters of high entropy.
- [ ] Verify `SUPER_ADMIN_EMAILS` lists designated operations personnel.

### Infrastructure Health Checks:
- [ ] Database Liveness: `GET /health/live` returns HTTP 200.
- [ ] Database Readiness: `GET /health/ready` returns HTTP 200 with DB & Redis status `healthy`.
- [ ] Prometheus Telemetry: `GET /metrics` returns Prometheus counter and histogram metrics.
- [ ] Alembic Revision: Confirm live database is at `0048_schema_reconciliation_parity` (or `0049` post-rollout).

### Tenant Boundary Checks:
- [ ] Pilot tenant provisioned with dedicated `organization_id`.
- [ ] Pilot brokers assigned via `OrganizationMember` records.
- [ ] Pilot brokers cannot view competitor leads (`GET /api/v1/leads/{competitor_lead_id}` returns 404).

---

## 3. Operational Monitoring & Telemetry

Monitor the following key metrics during pilot operations:

| Metric | Target / Threshold | Alert Condition | Action |
| :--- | :--- | :--- | :--- |
| **HTTP 5xx Error Rate** | < 0.1% | > 1% over 5m window | Inspect logs via `service=wefylabs-api level=ERROR` |
| **API Latency (p95)** | < 150 ms | > 500 ms over 5m | Check PostgreSQL slow queries & connection pool |
| **Outbound Dispatch Counter** | Exactly 0 | Any increment > 0 | Immediate emergency shutdown: check kill-switches |
| **Tenant Isolation Violations**| Exactly 0 | Any 403/404 cross-tenant spike | Audit user session and organization tokens |
| **Database Disk Usage** | < 75% | > 85% | Check pgvector index disk allocations & logs |

---

## 4. Emergency Incident Procedures

If an anomalous event or unexpected behavior is detected:

### Step 1: Engage Emergency Pause
Set `PILOT_MODE=DISABLED` in environment and reload service containers:
```bash
docker compose exec api kill -HUP 1
```

### Step 2: Verify Outbound Block
Confirm logs report `[WhatsAppProvider] BLOCKED send: channel disabled`.

### Step 3: Diagnostic Snapshot
Collect logs and metrics:
```bash
docker compose logs --tail=500 api > incident_api_logs.txt
docker compose logs --tail=500 postgres > incident_db_logs.txt
```

