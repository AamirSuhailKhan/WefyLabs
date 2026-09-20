# WEFYLABS SECURITY GAP REGISTER

| Level | Risk | Evidence | Impact | Mitigation |
|---|---|---|---|---|
| HIGH (remediated in shared guard; rollout remains) | RBAC could authorize by default role | `require_permission(... current_role=Role.ADMIN)` previously; now resolves `OrganizationMember` from authenticated broker and denies missing/invalid membership | unauthorized sensitive operations | migrate remaining sensitive routes to this guard and add endpoint-level role tests |
| CRITICAL | Tenant isolation is not globally demonstrated | selected tests only; inconsistent property tenancy | cross-tenant data/action exposure | scoped repositories + integration matrix |
| HIGH | AI tool authorization not centrally demonstrated | direct LLM paths coexist with router | LLM-influenced unauthorized actions | policy before tool executor; confirmation/audit |
| HIGH | Mock storage/runtime delivery | runtime log and mock branches | loss/misrepresentation of customer communication | fail closed outside demo |
| HIGH | Production secrets/integrations unverified | `render.yaml` only declares vars | external service failure or unsafe defaults | owner-led staging smoke tests and secret review |
| MEDIUM | Frequent all-tenant scans | Celery config uses `tenant_id: '__all__'` | noisy or cross-tenant worker defects | bounded enumeration, audit, idempotency |
| MEDIUM | Prompt/retrieval boundary unverified | RAG response integration not proven | prompt injection/data disclosure | source isolation, citations, tests |

Probability is intentionally not quantified; production telemetry and configuration were unavailable.
