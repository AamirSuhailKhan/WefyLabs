# WEFYLABS PHASE 11 — OPERATIONAL MONITORING AND SHUTDOWN CHECKLIST
**Restricted Pilot Operations, Telemetry Guards, and Safe Teardown Procedures**  
**Execution Environment:** Isolated Test Container (`leadscore_test_acceptance`)  
**Operating Mode:** `PILOT_MODE = "RECOMMEND_ONLY"`  
**Auditor:** Principal Site Reliability Engineer (SRE) & SaaS Product Operations Lead  
**Audit Date:** 2026-10-28  
**Repository Branch:** `level-3` (HEAD: `0383020a865fe315adfda4549f536a594fb10454`)  

---

## 1. Operating Model & Pilot Safety Invariants

During internal pilot operations, the platform runs under strict non-autonomous governance:
1. **Operating Mode:** `PILOT_MODE = "RECOMMEND_ONLY"`. AI models and revenue intelligence recommend actions, drafts, and scores. Autonomous write operations, message sending, and pipeline auto-advancement are hard-disabled.
2. **Outbound Messaging Hard Block:**
   - `WHATSAPP_ENABLED = false`
   - `FOLLOWUP_HUB_DISPATCH_ENABLED = false`
   - `SMS_ENABLED = false`
   - Provider adapters fail safe and return `status="blocked"`, `error_code="CHANNEL_DISABLED"`.
3. **Database Target:** Staging/Acceptance database only (`leadscore_test_acceptance`). Live database (`leadscore`) is strictly read-only.

---

## 2. Pre-Flight Verification Checklist

Before onboarding pilot users or initializing test sessions, the operator must verify:

### A. Environment Configuration:
- [ ] `ENV` set to `staging` or `pilot`.
- [ ] `PILOT_MODE=RECOMMEND_ONLY` active.
- [ ] `WHATSAPP_ENABLED=false` active.
- [ ] `FOLLOWUP_HUB_DISPATCH_ENABLED=false` active.
- [ ] `AUTO_CREATE_SCHEMA_ON_STARTUP=false` enforced.
- [ ] `SECRET_KEY` validated with $\ge 32$ high-entropy characters.
- [ ] `DATABASE_URL` pointing strictly to `leadscore_test_acceptance`.

### B. Health & Infrastructure Verification:
- [ ] Liveness probe: `GET /health/live` returns HTTP 200 `{"status": "alive"}`.
- [ ] Readiness probe: `GET /health/ready` returns HTTP 200 `{"status": "ready", "database": "healthy", "redis": "healthy"}`.
- [ ] Prometheus metrics: `GET /metrics` returning HTTP 200 with standard counter and histogram families.
- [ ] Database schema: Migration revision confirmed at `0049_source_attribution_uuid_parity` on acceptance DB.

### C. Multi-Tenant Boundaries:
- [ ] Test tenant provisioned with dedicated `organization_id`.
- [ ] Test brokers linked via `OrganizationMember`.
- [ ] Cross-tenant IDOR verification: Foreign lead lookup returns HTTP 404.

---

## 3. Operational Monitoring & Alerting Matrix

Active monitoring thresholds during pilot operations:

| Monitored Metric | Target Threshold | Alert Trigger | Remediation Action |
| :--- | :---: | :---: | :--- |
| **HTTP 5xx Error Rate** | `0.0%` | $> 0.5\%$ over 5m | Inspect logs for unhandled exceptions or connection drops. |
| **API Response Latency (p95)**| $< 500\text{ ms}$ | $> 2,000\text{ ms}$ | Inspect PostgreSQL slow query log; check connection pool utilization. |
| **Outbound Dispatch Count** | **Strictly 0** | $> 0$ | **CRITICAL ALERT:** Immediately invoke Emergency Pause; check provider gates. |
| **Tenant Isolation Violations**| **Strictly 0** | Cross-tenant 200 | **CRITICAL SECURITY ALERT:** Isolate tenant session; investigate IDOR vector. |
| **PostgreSQL Connection Pool** | $< 70\%$ pool | $> 85\%$ pool | Increase `max_overflow` or recycle idle connections. |
| **Redis Memory Consumption** | $< 500\text{ MB}$ | $> 1.5\text{ GB}$ | Evict stale cache keys; inspect idempotency TTL settings. |

---

## 4. Emergency Incident Procedures

If anomalous behavior, unexpected mutations, or outbound leaks occur:

### Step 1: Engage Emergency Kill-Switch
Immediately update environment and reload containers:
```bash
# Set emergency pause in environment
export PILOT_MODE=DISABLED
# Signal application workers to halt processing
docker compose exec api kill -HUP 1
```

### Step 2: Verify Messaging Interception
Confirm that outbound messaging logs show blocked status:
```text
[WhatsAppCloudProvider] BLOCKED send: channel disabled by configuration
```

### Step 3: Capture Diagnostic Forensic Snapshot
Export container logs and database transaction state:
```bash
docker compose logs --tail=1000 api > incident_api_logs_$(date +%Y%m%d_%H%M%S).txt
docker compose logs --tail=1000 postgres > incident_db_logs_$(date +%Y%m%d_%H%M%S).txt
```

---

## 5. Controlled Post-Pilot Shutdown & Teardown

Upon conclusion of a pilot session:

1. **Stop Incoming Traffic:**
   Halt reverse proxy routing to the staging application port.
2. **Flush Background Queues:**
   Allow in-flight Celery tasks to reach terminal status; purge remaining test task queues.
3. **Execute Entity Purge:**
   Run `TestEntityTracker.safe_cleanup()` to delete synthetic pilot entities in reverse dependency order:
   - `source_attributions`
   - `leads`
   - `organization_members`
   - `brokers`
   - `organizations`
4. **Forensic Database Verification:**
   Query the live production database (`leadscore`) to verify absolute invariance:
   ```sql
   SELECT 'leads', count(*) FROM leads
   UNION ALL
   SELECT 'organizations', count(*) FROM organizations
   UNION ALL
   SELECT 'brokers', count(*) FROM brokers
   UNION ALL
   SELECT 'organization_members', count(*) FROM organization_members
   UNION ALL
   SELECT 'tasks', count(*) FROM tasks;
   ```
   *Expected counts:* Leads=4, Orgs=7, Brokers=8, Members=7, Tasks=4.
5. **Archive Session Evidence:**
   Ensure all execution logs, latency summaries, and verification reports are committed to `docs/audits/`.

