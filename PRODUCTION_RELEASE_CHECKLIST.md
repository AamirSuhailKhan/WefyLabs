# PRODUCTION RELEASE CHECKLIST
# BeetleLabs Enterprise Real Estate CRM/SaaS

**Version**: Post Part 32 Production Hardening  
**Last Updated**: 2026-09-12

Use this checklist before every production deployment. A senior engineer must sign off on each section.

---

## Section 1: Pre-Deployment Code Audit

- [ ] All Part 32 tests pass (pytest tests/test_part32_*.py -v)
- [ ] Full regression passes (pytest -v --tb=short)
- [ ] 
pm run build completes with 0 TypeScript errors
- [ ] 
pm audit --audit-level=critical returns 0 critical vulnerabilities
- [ ] pip-audit returns 0 known CVEs
- [ ] Bandit scan: 0 HIGH severity issues in pps/api/app/
- [ ] No print() statements in hot paths (grep -r "^    print(" apps/api/app/)
- [ ] Alembic single head confirmed (python -m alembic heads | grep "(head)")
- [ ] No .env committed to git (git log --all -- ".env" returns empty)

---

## Section 2: Environment Configuration

### Required Secrets (must be set before deployment)
- [ ] DATABASE_URL — Supabase connection pooler URL (postgresql+asyncpg://...)
- [ ] REDIS_URL — Upstash Redis URL (rediss://...)
- [ ] SECRET_KEY — Minimum 32 chars, cryptographically random
- [ ] SUPABASE_JWT_SECRET — Supabase project JWT secret
- [ ] GEMINI_API_KEY — Production Gemini API key (not placeholder)
- [ ] SMTP_PASSWORD — Brevo SMTP API key
- [ ] SMTP_USER — Brevo SMTP username
- [ ] CORS_ORIGINS — Comma-separated list of allowed frontend origins
- [ ] TRUSTED_PROXY_IPS — Render.com proxy IP ranges

### Razorpay (TEST MODE — Keep as-is until ready for live)
- [ ] RAZORPAY_ENVIRONMENT=test confirmed
- [ ] RAZORPAY_KEY_ID starts with zp_test_
- [ ] Do NOT change to live without explicit go-ahead

### DO NOT Configure (Disabled Features)
- [ ] WHATSAPP_ACCESS_TOKEN — leave as placeholder
- [ ] PHONE_NUMBER_ID — leave as placeholder
- [ ] WABA_ID — leave as placeholder

---

## Section 3: Database Migration

- [ ] python -m alembic heads shows exactly 1 head
- [ ] python -m alembic history --verbose | head -5 shows expected latest migration
- [ ] Alembic upgrade runs successfully in staging: python -m alembic upgrade head
- [ ] No pending schema changes exist outside of Alembic migrations
- [ ] Database backup created before migration (for production)

---

## Section 4: Deployment Services

Verify all 3 services are running on Render:

- [ ] eetlelabs-api (Web Service) — Status: Running
- [ ] eetlelabs-celery-worker (Worker) — Status: Running
- [ ] eetlelabs-celery-beat (Worker) — Status: Running ← **New in Part 32**

---

## Section 5: Health Check Verification

After deployment, verify health endpoints respond correctly:

- [ ] GET /health/liveness → {"status": "alive", "version": "..."}
- [ ] GET /health/readiness → {"status": "ready", "database": "ok", "cache": "ok"}
- [ ] GET /health → {"status": "healthy", ...} with all dependencies listed
- [ ] GET /metrics → Returns Prometheus-format metrics text

---

## Section 6: Smoke Tests

- [ ] POST /api/v1/auth/register — creates a new user
- [ ] POST /api/v1/auth/login — returns JWT token
- [ ] GET /api/v1/leads with valid token — returns empty list or leads
- [ ] GET /api/v1/notifications with valid token — responds OK
- [ ] POST /api/v1/onboarding/demo/create — creates demo org

---

## Section 7: Observability

- [ ] Structured JSON logs visible in Render log stream
- [ ] No unhandled exceptions in logs for 5 minutes post-deployment
- [ ] GET /metrics returns populated counters (not all zeros)
- [ ] Alert destinations configured: Slack webhook URL or PagerDuty routing key

---

## Section 8: Security Verification

- [ ] GET /api/v1/leads without token → 401
- [ ] GET /health/readiness does not expose DATABASE_URL in response body
- [ ] CORS rejects Origin: https://evil.com preflight
- [ ] WhatsApp webhook GET with wrong verify_token → 403

---

## Section 9: Rollback Plan Ready

- [ ] Previous Docker image SHA noted: ___________________
- [ ] Rollback command documented: ender deploy --service beetlelabs-api --image <previous-sha>
- [ ] Alembic downgrade command documented: python -m alembic downgrade -1
- [ ] Database backup restoration procedure tested

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Lead Engineer | | | |
| Security Review | | | |
| QA | | | |

**DEPLOYMENT APPROVED**: ☐ YES  ☐ NO
