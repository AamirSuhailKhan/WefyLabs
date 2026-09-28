# WEFYLABS — LEAD INGESTION TEST REPORT

## 1. Test Suite Summary
This report summarizes the verification results for Universal Lead Ingestion and Real-Time Identity Resolution across all test suites.

**Date**: September 25, 2026  
**Environment**: Python 3.14.6, Windows, FastAPI + SQLAlchemy 2.0 Async + SQLite In-Memory / PostgreSQL  

---

## 2. Test Execution Breakdown

| Suite | File | Tests Run | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Master Build 02 Master Verification** | `test_master_build_02_ingestion_identity.py` | 18 | **PASSED** | 8.06s |
| **Tenant Matrix & Security Foundation** | `test_tenant_matrix_security.py` | 18 | **PASSED** | 96.45s |
| **Universal Lead Acquisition (Part 13)** | `test_part13_universal_lead_acquisition.py` | 21 | **PASSED** | 35.12s |
| **Lead Acquisition Engine (Part 21)** | `test_part21_lead_acquisition.py` | 71 | **PASSED** | 48.04s |
| **Lead Capture Hub (Part 26)** | `test_part26_lead_capture_hub.py` | 23 | **PASSED** | 1.19s |
| **Identity Resolution (Part 3)** | `test_part3_identity_resolution.py` | 13 | **PASSED** | 11.05s |
| **Lead Core Unit Tests** | `test_leads.py` | 2 | **PASSED** | 0.85s |
| **Frontend TypeScript Build** | `npm run typecheck` (`apps/web`) | Full App | **PASSED (0 Errors)** | 9.0s |

**Total Automated Proofs**: **166 Automated Tests Passing with 0 Failures**.

---

## 3. Key Invariant Test Verifications
- **Invariant 1: Idempotent Delivery**: Delivering the exact same webhook payload 10 times results in exactly 1 `Lead` record in the database (`test_repeated_delivery_idempotency`).
- **Invariant 2: Identity Graph Consolidation**: Enquiries for the same individual across Meta Ads, Google Ads, IndiaMART, 99acres, and WhatsApp converge into exactly 1 `Identity` node and 1 `Lead` record (`test_golden_path_multi_source_convergence`).
- **Invariant 3: First-Touch Attribution Immutability**: Subsequent touchpoints update `last_touch_at` without corrupting original `SourceAttribution.channel` (`test_golden_path_multi_source_convergence`).
- **Invariant 4: Atomic Outbox Emission**: Every lead creation writes an `OutboxEvent` in the same database transaction (`test_raw_payload_preservation_and_outbox_event`).
- **Invariant 5: Multi-Tenant Zero Leakage**: Identical phone numbers ingested for Tenant A and Tenant B create strictly isolated records scoped by `organization_id` (`test_tenant_lead_isolation`).
