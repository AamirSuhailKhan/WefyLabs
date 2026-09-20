# WEFYLABS TECHNICAL DEBT REGISTER

| Severity | Debt | Evidence | Mitigation |
|---|---|---|---|
| Critical | RBAC default-admin dependency | `infrastructure/security/rbac.py` | bind to authenticated principal; negative-route tests |
| High | Schema authority split | Alembic head plus many models; dev `create_all` | PostgreSQL drift gate; remove production ambiguity |
| High | Calendar duplicate registration | `main.py`; runtime duplicate operation-ID warnings | register once, add OpenAPI uniqueness test |
| High | Parallel domain models/engines | scoring/conversation/follow-up/matching modules | name canonical path, adapters, deprecate slowly |
| High | Mock storage in runtime | `media_service.py` runtime log | production storage provider and fail-closed config |
| Medium | Direct LLM calls bypass router | `ai_service.py`, extractor, reengagement, Copilot | facade/gateway migration |
| Medium | Deprecated Gemini SDK | test runtime warning | migrate to supported SDK with contract tests |
| Medium | Pydantic/FastAPI deprecations | targeted test warnings | replace class config/regex patterns |
| Medium | Broad worker schedules | `celery_app.py` | inventory tasks, idempotency/load tests |
| Low | Product naming residue | package/project names retain LeadScore/BeetleLabs | staged brand cleanup after deploy-impact review |
