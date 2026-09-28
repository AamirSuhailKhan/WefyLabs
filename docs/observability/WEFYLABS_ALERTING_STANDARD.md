# WEFYLABS — ALERTING STANDARD
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/alerts/` and `apps/api/app/modules/observability/incident_manager.py`  

---

## 1. Alert Quality Invariants

Every production alert must answer:
1. **WHAT?** Name and description of the anomalous signal.
2. **WHY?** Underlying condition or metric threshold breached.
3. **WHEN?** Exact timestamp and duration of anomaly.
4. **SEVERITY?** Explicit P0, P1, P2, or P3 classification.
5. **IMPACT?** Customer and business functions impacted.
6. **OWNER?** Responsible engineering/SRE team.
7. **RUNBOOK?** Markdown link to the step-by-step resolution runbook in `docs/operations/runbooks/`.

---

## 2. Severity Classification Matrix

| Severity | Target TTD | Target TTR | Criteria & Examples | On-Call Notification |
| :---: | :---: | :---: | :--- | :--- |
| **P0** | < 1 min | < 15 min | Complete platform outage, database write failure, data isolation compromise. | Immediate phone page to Primary SRE |
| **P1** | < 5 min | < 30 min | Critical capability degraded (AI Gateway outage, WhatsApp ingest failure, SLO breached). | Page within 5 minutes |
| **P2** | < 15 min | < 2 hrs | Non-critical component degraded (e.g. pgvector search slow, email notifications delayed). | Alert in Slack/Ops channel |
| **P3** | < 1 hr | < 24 hrs | Minor anomalies, individual task retry spikes, non-blocking telemetry delay. | Ops ticket created |

---

## 3. Alert Deduplication & Noise Suppression

To prevent alert fatigue and cascading duplicate notifications during a single failure:
- **Deduplication Window:** Identical alerts within a 15-minute sliding window are merged into the existing incident.
- **Incident Grouping:** Alerts originating from downstream dependencies (e.g. DB query errors resulting from primary DB failover) correlate directly with the primary incident.
