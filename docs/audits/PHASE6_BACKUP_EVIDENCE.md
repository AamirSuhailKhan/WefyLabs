# WEFYLABS AUTONOMOUS REVENUE OS — PHASE 6 BACKUP EVIDENCE
## Cryptographic and Forensic Validation of Pre-Phase 5 Database Backup

**Audit Date**: 2026-10-28T19:30:00+05:30  
**Repository**: WefyLabs / BeetleLabs AI Real Estate CRM  
**Base Commit**: `0383020a865fe315adfda4549f536a594fb10454`  
**Auditor Roles**: Database Reliability Engineer & PostgreSQL Forensic Analyst  
**Deliverable**: Master Prompt 6 — Phase B

---

## 1. Executive Summary

This report establishes the physical authenticity, cryptographic integrity, structural validity, and migration provenance of the baseline PostgreSQL database dump file (`leadscore_backup_20261028.dump`).

The backup represents the point-in-time state of the `leadscore` database immediately preceding the execution of the Phase 5 acceptance tests. The backup file was validated without modification or overwriting, and subsequently restored into a separately created, isolated verification database (`leadscore_verify_phase6`) to support record-level forensic reconciliation.

---

## 2. Backup File Attributes & Cryptographic Provenance

| Property | Attribute Value | Validation Method |
|---|---|---|
| **Host File Path** | `./backups/leadscore_backup_20261028.dump` | `Get-Item "backups\leadscore_backup_20261028.dump"` |
| **File Size** | `1,492,352 bytes` (~1.42 MB / 1.49 MB metric) | Exact file byte length confirmed |
| **File Format** | PostgreSQL Custom Binary (`pg_dump -Fc`, compressed) | Enumerable by `pg_restore` 16.15 |
| **SHA-256 Checksum** | `C28955F440B176285B96556009FD3E201A9B1B1F98CA26996673582FE4A1D9C6` | `Get-FileHash -Algorithm SHA256` |
| **Reported Phase 4 Hash** | `C28955F440B176285B96556009FD3E201A9B1B1F98CA26996673582FE4A1D9C6` | Verified 100% bitwise identical |
| **Creation Timestamp** | `2026-10-28 07:21:44 UTC` (`12:51:44 +05:30`) | Extracted directly from archive header |
| **PostgreSQL Version** | PostgreSQL 16.15 (`Debian 16.15-1.pgdg12+2`) | Native dump engine metadata |
| **TOC Entry Count** | `3,499` archive entries | `pg_restore -l` enumeration |

---

## 3. Git Staging & Ignore Validation

Per security and repository compliance policies, binary dumps must not be tracked in version control or accidentally committed.

### 3.1 Git Status & Rule Check
- **Command**: `git check-ignore -v backups/leadscore_backup_20261028.dump`
- **Output**:
  ```text
  .gitignore:40:backups/    backups/leadscore_backup_20261028.dump
  ```
- **Git Tracking Status**: Untracked and excluded from staging. `git status` verifies the dump file is classified as ignored.

---

## 4. Archive Enumeration & Migration Head Inspection

### 4.1 Header Inspection
```text
; Archive created at 2026-10-28 07:21:44 UTC
;     dbname: leadscore
;     TOC Entries: 3499
;     Compression: gzip
;     Dump Version: 1.15-0
;     Format: CUSTOM
;     Integer: 4 bytes
;     Offset: 8 bytes
;     Dumped from database version: 16.15 (Debian 16.15-1.pgdg12+2)
;     Dumped by pg_dump version: 16.15 (Debian 16.15-1.pgdg12+2)
```

### 4.2 Alembic Migration Revision Extraction
The Alembic version was extracted directly from the dump archive without restoring the whole database:
```bash
docker exec leadscore_postgres pg_restore -a -t alembic_version -f - /tmp/leadscore_backup_20261028.dump
```
- **Recorded Revision**: `0048_schema_reconciliation_parity`
- **Current Live Revision**: `0048_schema_reconciliation_parity`
- **Parity**: Identical schema revision baseline.

---

## 5. Isolated Verification Restoration

To perform rigorous record-level comparison without exposing the active `leadscore` database, an isolated verification database was provisioned.

### 5.1 Verification Database Isolation Steps
1. **Collision Check**: Evaluated `psql -c "\l"`. Databases present: `leadscore`, `postgres`, `template0`, `template1`. No conflicting verification database existed.
2. **Database Provisioning**:
   ```sql
   CREATE DATABASE leadscore_verify_phase6;
   ```
3. **Archive Restoration**:
   ```bash
   docker exec leadscore_postgres pg_restore -U postgres -d leadscore_verify_phase6 -v /tmp/leadscore_backup_20261028.dump
   ```
4. **Restore Status**: Exited with code `0`. 3,499 TOC entries restored cleanly (411 tables, indexes, B-tree/HNSW vector indexes, foreign key constraints, sequences, and extensions `vector` and `uuid-ossp`).

---

## 6. Scope and Limitations of the Backup

1. **Point-in-Time Scope**: The backup captures the exact database state at `2026-10-28 07:21:44 UTC`. Any changes occurring after this timestamp (such as automated Celery Beat background loops or Phase 5 dry-run actions) are naturally absent from this dump.
2. **Non-Transactional Redis State**: Redis keys (rate limit counters, ephemeral tokens) are stored outside PostgreSQL and are not captured in `pg_dump`.
3. **Storage Blobs**: Documents stored under `./storage/knowledge` are stored on the local filesystem and not inside the PostgreSQL dump.

---

## 7. Retention Policy

The baseline dump file `./backups/leadscore_backup_20261028.dump` is retained intact in the `backups/` directory as an authoritative immutable reference. The isolated verification database `leadscore_verify_phase6` is maintained as a read-only comparison database for this investigation.

