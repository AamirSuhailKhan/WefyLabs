# WEFYLABS AUTONOMOUS REVENUE OS — PILOT DRY RUN OPERATING CHECKLIST

**Document Version**: 1.0.0  
**Effective Date**: 2026-10-28  
**Scope**: Operational Pilot Dry Run & Customer Onboarding Execution  
**Author**: Controlled Pilot Operations Lead  

---

## 1. Pre-Flight Checklist (Before the Dry Run)

The pilot operator must complete and check off each item before commencing any pilot workflow:

| Checkpoint | Requirement | Verification Command / Action | Operator Sign-Off |
|---|---|---|---|
| **1. Container Health** | All 5 containers up and healthy | `docker compose ps` shows `api`, `worker`, `beat`, `postgres`, `redis` Up | `[x] VERIFIED` |
| **2. API Probe** | `/health` returns status healthy | `curl.exe -s http://127.0.0.1:8000/health` -> `"status": "healthy"` | `[x] VERIFIED` |
| **3. Database Backup** | Binary backup verified on host | Check `./backups/leadscore_backup_20261028.dump` exists (1.49 MB) | `[x] VERIFIED` |
| **4. Outbound Safeguard** | Outbound dispatch strictly disabled | Inspect worker: `FOLLOWUP_HUB_DISPATCH_ENABLED = False` | `[x] VERIFIED` |
| **5. Synthetic Tenant** | Synthetic test organization prepared | Organization provisioned with isolated UUID | `[x] VERIFIED` |
| **6. Scoped Test Users** | Users bound to synthetic org | Brokers created with roles `owner` and `agent` | `[x] VERIFIED` |
| **7. Monitoring Ready** | Log streams actively observed | `docker compose logs -f --tail=20 celery_worker` active in terminal | `[x] VERIFIED` |

---

## 2. In-Flight Checklist (During the Dry Run)

While testing lead creation, status updates, notes, and task assignments:

| Checkpoint | Monitoring Action | Expected Observation | Anomaly Threshold |
|---|---|---|---|
| **1. API Error Rates** | Inspect HTTP response codes | 200 OK / 201 Created on valid payloads | Any unexpected 500 triggers immediate pause |
| **2. Worker Exception Logs** | Monitor Celery worker output | Task executions logged with zero tracebacks | Any `RuntimeError` triggers immediate pause |
| **3. Cross-Tenant Boundaries** | Attempt cross-org read | HTTP 404 Not Found (IDOR rejected) | Any data returned triggers immediate abort |
| **4. Outbound Communication** | Inspect dispatch logs | `FOLLOWUP_HUB_DISPATCH_ENABLED is false` | Any external HTTP call triggers immediate abort |
| **5. Task Deduplication** | Verify retry behavior | Re-evaluating tasks processes 0 items | Any duplicate message triggers immediate abort |

---

## 3. Post-Flight Checklist (After the Dry Run)

Following completion of the dry run:

| Checkpoint | Action | Verification | Status |
|---|---|---|---|
| **1. Workflow Verification** | Reconcile created entities | Leads, tasks, and notes created in target org | `[x] COMPLETED` |
| **2. Data Purification** | Safely delete synthetic records | Synthetic leads, tasks, and brokers purged | `[x] COMPLETED` |
| **3. Production Parity** | Check live database row counts | Database matches baseline (8 brokers, 4 leads) | `[x] COMPLETED` |
| **4. Error Log Audit** | Review all logs during test window | Zero unhandled exceptions or loop crashes | `[x] COMPLETED` |
| **5. Evidence Archival** | Save test evidence | Evidence recorded without secrets or customer PII | `[x] COMPLETED` |
| **6. Owner Approval** | Obtain written sign-off | Complete Mode B checklist before customer access | `[x] PENDING OWNER` |

---

## 4. Emergency Pause Command & Service Boundaries

If any safety anomaly occurs during pilot operations:

```powershell
docker compose stop celery_worker celery_beat
```

### Operational Scope & Limitations:
1. **Target Services**: Halts the `leadscore_celery_worker` and `leadscore_celery_beat` containers within **2 seconds**.
2. **What It Does**:
   - Immediately stops periodic scheduling crons.
   - Prevents worker threads from pulling new tasks from the Redis queue.
   - Preserves all database data and volume state without data loss.
3. **What It Does NOT Do**:
   - It **does not reverse** database mutations that were already committed.
   - It **does not undo** external network calls that were already dispatched prior to issuing the command.
   - It **does not flush** the Redis queue (pending tasks remain in queue until workers resume).
