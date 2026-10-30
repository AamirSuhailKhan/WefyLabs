# WEFYLABS PHASE 8 — DATABASE INTEGRITY & SAFETY REPORT

**Project:** WefyLabs Autonomous Revenue OS / AI Real Estate CRM  
**Target Branch:** `level-3`  
**Primary Database Engine:** PostgreSQL 16 with pgvector  
**Active Database:** `leadscore`  
**Isolated Test Database:** `leadscore_test_acceptance`  
**Reference Baseline Database:** `leadscore_verify_phase6`  
**Authoritative Migration Head:** `0048_schema_reconciliation_parity`  
**Report Date:** 2026-10-28  

---

## 1. Executive Summary

This report establishes the baseline database integrity, schema parity, foreign-key constraint analysis, and runtime protection architecture for WefyLabs across live and testing environments.

Following the authorized cleanup of the two Phase 5 residual orphan records in `source_attributions`, the active `leadscore` database achieves **100% row-level and checksum parity** with the reference baseline. All 411 tables are synchronized with the authoritative migration head `0048_schema_reconciliation_parity`.

---

## 2. PostgreSQL Instance & Extension State

All three databases reside in the container `leadscore_postgres` (`pgvector/pgvector:pg16`):

| Database Name | Role | Total Tables | Migration Head | Vector Extension Status |
| :--- | :--- | :---: | :---: | :---: |
| `leadscore` | Active Production DB | 411 | `0048_schema_reconciliation_parity` | Active (0.7.0) |
| `leadscore_verify_phase6` | Forensic Baseline | 411 | `0048_schema_reconciliation_parity` | Active (0.7.0) |
| `leadscore_test_acceptance`| Isolated Test DB | 411 | `0048_schema_reconciliation_parity` | Active (0.7.0) |

Installed Extensions:
- `uuid-ossp`: Native UUID generation.
- `pgcrypto`: Cryptographic hashing and token verification.
- `vector`: pgvector vector embeddings support with native HNSW indexing (`ix_ke_vector_hnsw` on `knowledge_embeddings`).

---

## 3. Core Business Table Invariance & Parity

Verification of record counts across core business models:

| Table Name | `leadscore` (Live) | `leadscore_verify_phase6` (Backup) | Status |
| :--- | :---: | :---: | :---: |
| `leads` | 4 | 4 | Invariant |
| `organizations` | 7 | 7 | Invariant |
| `brokers` | 8 | 8 | Invariant |
| `organization_members` | 7 | 7 | Invariant |
| `source_attributions` | 3 | 3 | Invariant (Reconciled) |
| `tasks` | 0 | 0 | Invariant |
| `lead_notes` | 0 | 0 | Invariant |

---

## 4. Referential Integrity & Data Type Variance Analysis

An architectural analysis of primary keys and foreign keys across core CRM models revealed variance between native PostgreSQL `UUID` and `VARCHAR(36)` fields:

| Model / Table | Primary Key Type | Foreign Keys & Cascade Behavior | Orphan Risk |
| :--- | :--- | :--- | :--- |
| `organizations` | `UUID` | None (Top-level tenant) | Low |
| `brokers` | `UUID` | None (Actor entity) | Low |
| `organization_members` | `UUID` | FK to `organizations.id` (CASCADE)<br>FK to `brokers.id` (CASCADE) | None |
| `leads` | `UUID` | FK to `organizations.id` (CASCADE)<br>FK to `brokers.id` (CASCADE) | None |
| `tasks` | `VARCHAR(36)` | FK to `leads.id` (CASCADE) | None |
| `lead_notes` | `VARCHAR(36)` | FK to `leads.id` (CASCADE) | None |
| `source_attributions` | `VARCHAR(36)` | **No FK to `leads.id`** (`VARCHAR(36)` vs `UUID`)<br>**No FK to `organizations.id`** (`VARCHAR(36)` vs `UUID`)<br>FK to `campaigns` (SET NULL)<br>FK to `sources` (SET NULL) | **High (Mitigated)** |

### Mitigation of the `source_attributions` Schema Gap:
Because `source_attributions.lead_id` cannot have a direct PostgreSQL foreign key to `leads.id` without migrating column types across the database, two mitigations are enforced:
1. **Application-Level Tracker:** [`TestEntityTracker`](file:///c:/Users/aamir/OneDrive/Desktop/crm real state/apps/api/app/core/database_safety.py) explicitly captures all `source_attributions` rows linked to synthetic leads and purges them before lead deletion.
2. **Dual-Tenant Filters:** Revenue intelligence services query using dual-read filters `or_(Lead.organization_id == org_id, Lead.broker_id == org_id)` rather than relying on un-cascaded secondary attribution tables for core pipeline metrics.

---

## 5. Runtime Database Protection Architecture

Future testing and development workflows are bounded by multi-tier runtime controls:

1. **Positive Allowlist Intercept:**
   `validate_test_database_target(db_url)` strictly permits only `:memory:`, `leadscore_test_acceptance`, `leadscore_verify_phase6`, `leadscore_test`, `leadscore_ci_test`, and dynamic test databases matching `^(leadscore_test|test_db)_[a-f0-9]{4,32}$`.
2. **Session Target Binding Verification:**
   `verify_session_target(session)` inspects `session.bind.url` directly, preventing environment variable desynchronization after engine initialization.
3. **Host Isolation:**
   Restricts database operations to `APPROVED_TEST_HOSTS = {"", "localhost", "127.0.0.1", "postgres", "db"}`.
4. **Pre-Existing Record Immunity:**
   `TestEntityTracker.safe_cleanup()` validates registered IDs against pre-existing database records before issuing deletions.

