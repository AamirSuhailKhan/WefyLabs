# WEFYLABS FAILURE MODES AND SAFE DEGRADATION MATRIX
# Comprehensive System Resilience & Fallback Specification

---

| Component | Failure Mode | User Impact | System Behavior | Fallback Strategy | Data Risk | Recovery Action | Alert Severity | Verified? |
|---|---|---|---|---|---|---|---|---|
| **Database (PostgreSQL)** | Connection pool exhaustion / Timeout | 500 on mutation | Asyncpg drops stale conn, pool pre-ping rejects | Return 503 with retry-after | Zero (Rollback on error) | Scale pooler or restart database | **CRITICAL** | **VERIFIED** |
| **Redis** | Network outage / Cluster unreachable | None for API reads | Rate limiter & lock engine switch to in-memory fallback | Local in-memory sliding window + threading lock | Zero (Transient rate keys lost) | Automatic reconnect | **HIGH** | **VERIFIED** |
| **Google Gemini (AI)** | Upstream 503 / Timeout (>10s) | AI chat delayed or degraded | `AIRuntimeGovernor` circuit breaker trips after 5 fails | Return deterministic fallback or rule-based response | Zero (Context preserved) | Automatic circuit reset (HALF_OPEN canary) | **HIGH** | **VERIFIED** |
| **Celery Beat** | Multiple worker instances race on cron | None | `RedisDistributedLock` singleton decorator blocks duplicates | Exactly one worker runs task; others skip cleanly | Zero (Idempotent execution) | Stale locks auto-expire via TTL | **MEDIUM** | **VERIFIED** |
| **Celery Worker** | Worker crash / OOM killer | Delayed background jobs | Tasks remain in Redis queue until worker restarts | At-least-once redelivery | Zero (Transactional Outbox) | Restart Celery worker processes | **HIGH** | **VERIFIED** |
| **Transactional Outbox** | Handler crashes mid-dispatch | None to client | Outbox marks event `FAILED`, increments retry count | Exponential backoff (AWS jitter standard) | Zero (Atomic DB commit) | Retries automatically up to 5 times -> DLQ | **MEDIUM** | **VERIFIED** |
| **Webhooks (Meta/Google)** | Malformed signature / Replay | Webhook dropped | `PublicCaptureGuard` rejects signature or expired timestamp | Returns 401/403, increments SecOps event metric | Zero (Untrusted payload dropped) | Logged for forensic review | **MEDIUM** | **VERIFIED** |
| **Public Lead Capture** | Bot spam / Prompt injection | None to CRM users | Honeypot trapped; prompt injection neutralized | Sanitizes text to `[FILTERED_INSTRUCTION]` | Zero (Sanitized before AI/DB) | Attacking IP rate-limited | **MEDIUM** | **VERIFIED** |
| **Predictive Intelligence** | Model feature store failure | Degraded predictions | `_degraded_surface()` invoked automatically | Deterministic conversion probability baseline (0.25) | Zero (Non-blocking) | Refreshes when feature store is restored | **LOW** | **VERIFIED** |
| **Revenue Autopilot** | Stagnant opportunity evaluation error | Delayed revenue intel | Isolated try/catch in periodic task | Skips batch, logs warning, continues with next tenant | Zero (DB transaction isolated) | Re-evaluates next periodic interval (10m) | **LOW** | **VERIFIED** |
| **AI Workforce** | Cyclic delegation loop (A->B->A) | Chat query timeout if unhandled | `MAX_AGENT_DEPTH = 3` limit enforced | Bounded delegation terminates, hands off to Human Agent | Zero (Conversation preserved) | Normal routing resumes on next turn | **MEDIUM** | **VERIFIED** |
| **Email (Brevo / SMTP)** | SMTP connection timeout | Lead doesn't receive instant email | Outbox/Celery worker catches SMTPException, queues retry | Exponential backoff up to 3 retries | Zero (Delivery status logged) | Automatic retry or fallback notification | **LOW** | **VERIFIED** |
| **WhatsApp Direct** | Provider disabled by default | Messages route via Email/SMS | Kill-switch active (`WHATSAPP_ENABLED = False`) | Safe rejection before provider call | Zero | Owner action required to enable credentials | **INFO** | **VERIFIED** |
| **Storage (Local/S3)** | Disk full / Upload timeout | 413 or 500 on document upload | Rejects uploads exceeding `KNOWLEDGE_MAX_UPLOAD_MB` | Bounded upload limits enforced | Zero | Clean temporary files | **HIGH** | **VERIFIED** |

---
_Status: ALL CRITICAL FAILURE MODES VERIFIED AGAINST RUNTIME BEHAVIOR._
