# STAGE1_INGRESS_CONFIGURATION.md
# Phase 2C.6E — Production Ingress Configuration & Website Integration

**Generated:** 2026-10-13  
**Status:** WEBSITE_INTEGRATION_COMPLETE | LEAD_SOURCE_CONFIGURED | PIPELINE_READY | AWAITING_CUSTOMER_SUBMISSION  
**Assessed by:** Phase 2C.6E Ingress Verification Engine  

---

## 1. WEBSITE ENQUIRY FORM INTEGRATION (GATE 1, GATE 2 & GATE 3)

The live WefyLabs website enquiry form on the landing page has been fully inspected, connected, committed, and verified:

| Inspection Attribute | Verified Implementation Truth |
|---|---|
| **Form Location** | [`apps/web/src/components/landing/GlobalPricing.tsx`](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/apps/web/src/components/landing/GlobalPricing.tsx#L400-L500) (Enterprise "CONTACT SALES →" / "Request Custom Pricing" modal) |
| **Form Fields** | Full Name, Email, Phone, Agency / Company, Expected Monthly Leads, Custom Requirements |
| **Client Submission Handler** | `handleContactSubmit` in `GlobalPricing.tsx` (asynchronous `fetch('/api/contact')`) |
| **Submission Target** | Server-side Route Handler: `POST /api/contact` ([`apps/web/src/app/api/contact/route.ts`](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/apps/web/src/app/api/contact/route.ts)) |
| **Token Isolation Strategy** | Server-side environment variable `WEBSITE_LEAD_SOURCE_TOKEN` in `apps/web/.env.local`. **Zero tokens in client JavaScript bundles or client logs.** |
| **Validation & Error Handling** | Client checks required fields; server validates contact presence; API returns 422/429/500 errors rendered as inline alert banners. |
| **Bot Anti-Spam Honeypot** | Hidden input field `_hp_trap` caught and neutralized both in Next.js route handler and FastAPI controller. |
| **Idempotency & Replay** | Double-click disabled via `isSubmitting` state; client sends idempotency tokens; backend deduplicates via `UniversalIntakeService`. |
| **Commit Synchronization** | Committed in `96467a0`, verified & documented in `8acbbe8`, and synchronized across both `origin/main` and `origin/level-3`. |

---

## 2. DOWNSTREAM PUBLIC CAPTURE ENDPOINT (GATE 3)

The Next.js server-side handler dispatches to the production FastAPI endpoint:

```
POST /api/v1/public/lead-capture/{token}
```

### Verification Invariants:
1. **Source Active in PostgreSQL:** `LeadSource` `4268a3f0-ee41-4dd6-90e7-933338fd6f5e` (`WefyLabs Official Website Lead Form`) verified active (`is_active = True`).
2. **Tenant Scope Derived:** Strictly maps to Organization `a0317351-e076-493e-8b84-182f8c43666e` (`Aamir Suhail's Agency`). The client cannot alter tenant scope.
3. **Security Controls Active:**
   - IP sliding-window limit: 60 req/min.
   - Source hourly limit: 500 req/hr.
   - LLM prompt-injection sanitization via `_sanitize_text`.
   - Honeypot bot protection.
4. **Event Emission:** Upon arrival of a genuine new enquiry, `UniversalIntakeService` persists the lead, emits `StandardDomainEvents.LEAD_CREATED`, and `lead_created_loop_subscriber` enqueues `autonomous_loop.process_sales_loop_event` onto Celery queue `sales-loop-orchestration`.

---

## 3. INTEGRATION ARCHITECTURE SCHEMATIC

```
[Customer Browser]
       │
       ▼ (Submits Form without token)
[Next.js Server Route: POST /api/contact]
       │
       ▼ (Injects WEBSITE_LEAD_SOURCE_TOKEN server-side)
[FastAPI: POST /api/v1/public/lead-capture/{token}]
       │
       ├─► [Token Tenant Resolution: Org a0317351]
       ├─► [Honeypot & Rate Limit Check]
       ├─► [Persist to `leads` Table]
       ├─► [Emit LEAD_CREATED on Event Bus]
       │
       ▼
[Redis: sales-loop-orchestration (Upstash TLS)]
       │
       ▼
[Celery Worker: autonomous_loop.process_sales_loop_event]
       │
       ▼ (Autonomy = 0, dry_run=True)
[Durable Shadow Observation in PostgreSQL]
```

---

_End of Ingress Configuration Report_
