# WEFYLABS — LEAD DATA SECURITY & TENANT ISOLATION SPECIFICATION

## 1. Security Objectives
This document details the multi-tenant isolation, endpoint authentication, PII protection, and webhook security mechanisms of WefyLabs.

---

## 2. Multi-Tenant Fail-Closed Isolation

### 2.1 Server-Side Tenant Resolution
- Tenant context is **never accepted from untrusted request bodies**.
- For authenticated API endpoints: Derived exclusively from validated JWT claims (`Broker.organization_id`).
- For external webhooks: Derived exclusively from pre-configured, verified `LeadSource.webhook_token` or `LeadSource.configuration` records.
- Missing, ambiguous, or malformed tenant identifiers trigger immediate `401 Unauthorized` or `403 Forbidden` errors (Fail-Closed).

### 2.2 Database Row-Level Tenancy
- Every tenant-owned table (`leads`, `identities`, `identity_links`, `original_payloads`, `ingestion_logs`, `outbox_events`, `source_attributions`, `tasks`, `activities`) contains an indexed `organization_id` foreign key.
- Lookup queries (`_find_lead_by_phone`, `_find_lead_by_email`) enforce `Lead.organization_id == org_uuid`.
- Cross-tenant data retrieval, merging, or replay is structurally impossible.

---

## 3. Webhook Authentication & Integrity

### 3.1 Meta Webhook Verification
- Webhook signature is validated using HMAC-SHA256 (`X-Hub-Signature-256`) against the configured App Secret.
- Verification challenge requests (`GET hub.challenge`) validate `hub.verify_token` before acknowledging.

### 3.2 Google Ads & Portal Webhooks
- Google Ads payloads validate `google_key` using constant-time string comparison (`hmac.compare_digest`).
- IndiaMART push leads validate `glusr_crm_key`.
- 99acres webhooks validate `portal_key`.

---

## 4. PII Protection & Auditability
- Raw payloads containing contact information are stored in `original_payloads` with restricted access permissions.
- Ingestion events record client IP and User-Agent for rate-limiting and abuse tracking.
- Every state mutation triggers an entry in the centralized audit log (`audit_logs` table).
