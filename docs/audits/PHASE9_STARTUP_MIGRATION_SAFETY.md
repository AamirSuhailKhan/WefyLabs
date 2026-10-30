# PHASE 9 AUDIT REPORT: APPLICATION STARTUP DDL POLICY & MIGRATION SAFETY (ARCH-STARTUP-03)

**Document ID:** `PHASE9_STARTUP_MIGRATION_SAFETY`  
**Date:** 2026-10-28  
**Auditor:** Principal Database Reliability Engineer & Release Auditor  
**Repository Branch:** `level-3`  
**Status:** POLICY ENFORCED & PRODUCTION SECURED  

---

## 1. Issue Background & Risk Analysis (ARCH-STARTUP-03)

In `apps/api/app/main.py:130-136`, the application lifespan startup function previously executed:

```python
# PREVIOUS STARTUP LOGIC (RISK: UNVERSIONED DDL MUTATION)
is_prod = settings.ENV.lower() in ("production", "prod", "staging")
if not is_prod:
    async with engine.begin() as conn:
        from app.models import Base
        await conn.run_sync(Base.metadata.create_all)
    _startup_logger.info("[DB] Development schema sync complete via create_all")
```

### Architectural Dangers:
1. **Unversioned DDL Drift:** In development and CI environments running PostgreSQL, executing `create_all` at startup modifies the database schema outside of Alembic. Tables, columns, and indexes are created without migration version records in `alembic_version`.
2. **Masking of Missing Migrations:** Developers adding ORM models might observe their tables working locally via `create_all` while forgetting to author Alembic revisions, leading to catastrophic deployment failures in staging or production.
3. **Database Concurrency Lock Contention:** Multiple API worker processes starting concurrently in Docker or Kubernetes attempt to execute DDL statements against the shared PostgreSQL database simultaneously, risking table locks and startup crashes.

---

## 2. Enforced Startup DDL Policy

The enterprise policy requires that **Alembic is the sole authoritative schema management mechanism for PostgreSQL**. Unversioned `create_all()` execution is strictly prohibited by default.

### Remediated Implementation:

1. **Configuration Setting in `app/common/config/validated_settings.py`:**
   ```python
   # Database DDL Policy (ARCH-STARTUP-03)
   AUTO_CREATE_SCHEMA_ON_STARTUP: bool = False
   ```
2. **Lifespan Startup Logic in `app/main.py`:**
   ```python
   # ARCH-STARTUP-03: Prevent unversioned DDL drift.
   # Alembic is the authoritative schema migration tool.
   # create_all() is strictly bypassed for PostgreSQL to prevent drift,
   # and only permitted if explicitly enabled via AUTO_CREATE_SCHEMA_ON_STARTUP=True
   # or when running SQLite in-memory test suites.
   is_sqlite = engine.dialect.name == "sqlite"
   auto_create = getattr(settings, "AUTO_CREATE_SCHEMA_ON_STARTUP", False)
   if is_sqlite or auto_create:
       async with engine.begin() as conn:
           from app.models import Base
           await conn.run_sync(Base.metadata.create_all)
       _startup_logger.info(
           f"[DB] Schema initialized via create_all (dialect={engine.dialect.name}, auto_create={auto_create})"
       )
   else:
       _startup_logger.info(
           f"[DB] Schema managed by Alembic migrations — create_all bypassed (dialect={engine.dialect.name})"
       )
   ```

---

## 3. Operational Behavior Matrix

| Environment | Database Dialect | `AUTO_CREATE_SCHEMA_ON_STARTUP` | Startup Action |
| :--- | :--- | :--- | :--- |
| **Unit Testing** | SQLite In-Memory | Default (`False`) | `create_all()` executed (Required for fast in-memory test schemas) |
| **Local Development** | PostgreSQL | Default (`False`) | `create_all()` **bypassed**; developer runs `alembic upgrade head` |
| **CI / CD Pipeline** | PostgreSQL | Default (`False`) | `create_all()` **bypassed**; CI runner runs `alembic upgrade head` |
| **Staging / Pilot** | PostgreSQL | Default (`False`) | `create_all()` **bypassed**; controlled Alembic migration |
| **Production** | PostgreSQL | Default (`False`) | `create_all()` **bypassed**; zero startup DDL mutations |

---

## 4. Verification Evidence

Application startup and health diagnostics were verified in `apps/api/tests/test_part6_infrastructure.py` and `apps/api/tests/test_part22_production_integration.py`. The startup log confirms:
`[DB] Schema managed by Alembic migrations — create_all bypassed (dialect=postgresql)`
when connected to PostgreSQL without `AUTO_CREATE_SCHEMA_ON_STARTUP`.

