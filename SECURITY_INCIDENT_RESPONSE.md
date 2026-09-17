# SECURITY INCIDENT RESPONSE PLAYBOOK
# BeetleLabs Enterprise Real Estate CRM/SaaS

**Version**: 1.0 (Part 32)  
**Last Updated**: 2026-09-12  
**Classification**: Internal — Engineering & Security Team

---

## Incident Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P0 CRITICAL | Data breach, credential leak, active exploit | < 15 minutes |
| P1 HIGH | Auth bypass, unauthorized data access | < 1 hour |
| P2 MEDIUM | Privilege escalation attempt, suspicious auth pattern | < 4 hours |
| P3 LOW | Failed attack, minor misconfiguration | < 24 hours |

---

## Incident Response Process

### Step 1: Detect & Triage (0-15 minutes)

**Detection Sources**:
- Render log stream: unusual error rates, auth failures
- Structured logging alerts (ALERT_SLACK_WEBHOOK_URL)
- PagerDuty alert (ALERT_PAGERDUTY_ROUTING_KEY)
- External report (customer, bug bounty)

**Triage Questions**:
1. Is customer data at risk?
2. Is the system actively compromised?
3. What is the blast radius (single tenant or all tenants)?

### Step 2: Contain (15-60 minutes)

**Immediate Containment Actions by Incident Type**:

#### Credential Leak (SECRET_KEY, SUPABASE_JWT_SECRET, API keys)
```
1. IMMEDIATELY rotate the compromised secret in Render environment variables
2. Restart beetlelabs-api to invalidate all existing JWT tokens
3. Rotate SUPABASE_JWT_SECRET in Supabase project settings
4. Force-logout all active sessions (JWT invalidation via rotation)
5. Audit access logs for use of the compromised credential
```

#### Unauthorized Data Access (IDOR, broken access control)
```
1. Identify the affected organization_id(s)
2. Temporarily disable the vulnerable endpoint via feature flag if possible
3. Review audit logs for extent of access: GET /api/v1/audit/logs
4. Preserve all access logs before any rotation
```

#### Active DDoS / Rate Limit Bypass
```
1. Check Render metrics for request spike
2. Review rate limiter Redis keys for bypass patterns
3. Add IP blocks at Render network layer if needed
4. Set PAYMENTS_EMERGENCY_PAUSE=true if payment endpoints targeted
```

#### Database Connection Attack
```
1. Check pg_stat_activity for suspicious long-running queries
2. Terminate suspicious connections: pg_terminate_backend(pid)
3. Review Supabase auth logs for connection source
```

### Step 3: Eradicate (1-4 hours)

1. Remove the root cause (patch code, rotate credentials, fix config)
2. Deploy the fix through standard CI/CD
3. Verify fix with Part 32 security tests
4. Run full regression test suite

### Step 4: Recover

1. Restore affected services to normal operation
2. Monitor health endpoints for stability
3. Verify `GET /health/readiness` returns 200 for 10+ consecutive minutes
4. Notify affected tenants if data was accessed (GDPR notification required within 72 hours for EU users)

### Step 5: Post-Mortem (within 48 hours)

Document in a post-mortem report:
- Timeline of events
- Root cause
- Impact assessment
- Actions taken
- Prevention measures
- Process improvements

---

## Specific Incident Procedures

### Credential Rotation Procedure

**SECRET_KEY Rotation** (invalidates ALL JWT tokens — all users logged out):
1. Generate new key: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. Update `SECRET_KEY` in Render dashboard for `beetlelabs-api`
3. Update `SECRET_KEY` reference in `beetlelabs-celery-worker` (fromService will auto-sync)
4. Restart both services
5. Notify users that they need to log in again

**SUPABASE_JWT_SECRET Rotation**:
1. Generate new secret in Supabase project settings → API → JWT Secret → Rotate
2. Update `SUPABASE_JWT_SECRET` in Render environment variables
3. Restart `beetlelabs-api`

**GEMINI_API_KEY Rotation**:
1. Revoke old key in Google AI Studio
2. Generate new key
3. Update in Render `GEMINI_API_KEY` env var
4. Restart services

**SMTP_PASSWORD Rotation**:
1. Regenerate API key in Brevo dashboard
2. Update `SMTP_PASSWORD` in Render
3. Verify with test email

---

## Security Monitoring Checklist

Run daily in production:

- [ ] Check `GET /health/readiness` response time < 500ms
- [ ] Check Render log stream for `CRITICAL` or `ERROR` patterns
- [ ] Check auth failure rate in structured logs
- [ ] Check Celery beat is firing scheduled tasks (look for task success logs)
- [ ] Check `/metrics` for anomalous request rates

---

## Emergency Contacts

| Service | Emergency Contact |
|---------|------------------|
| Render.com | https://render.com/support |
| Supabase | https://supabase.com/support |
| Upstash | https://upstash.com/support |
| Google (Gemini) | https://cloud.google.com/support |
| Brevo | https://help.brevo.com |
