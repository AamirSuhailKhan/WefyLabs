# WEFYLABS PART 13: PROVIDER INTEGRATION RUNBOOK

## 1. Overview
This runbook provides step-by-step operational instructions for configuring, managing, verifying, and troubleshooting **Meta Lead Ads** and **Google Ads Lead Forms** integrations in WefyLabs.

---

## 2. Meta Lead Ads Setup & Operational Guide

### 2.1 Prerequisites
1. A verified Meta Business Manager account with Admin access.
2. A Meta App configured with the **leads_retrieval** and **pages_manage_ads** permissions.
3. Access to the target Facebook Page(s) hosting real estate lead generation campaigns.

### 2.2 Webhook Registration in Meta App Dashboard
1. Navigate to **Meta App Dashboard** > **Webhooks** > Select **Page** from the dropdown.
2. Click **Subscribe to this object**.
3. Set **Callback URL**:
   `https://<your-domain>/api/v1/lead-acquisition/webhooks/meta`
4. Set **Verify Token**:
   Enter the secret token configured in your tenant's Meta `LeadSource.webhook_secret`.
5. Meta will issue a `GET` challenge request. The endpoint will automatically verify `hub.mode == "subscribe"` and `hub.verify_token`, responding with the challenge value.
6. Under **Page Subscriptions**, subscribe to the `leadgen` field.

### 2.3 App Secret & Signature Verification
1. Copy the **App Secret** from **App Settings** > **Basic**.
2. Configure `META_APP_SECRET` in environment variables or within the tenant's `LeadSource.credentials["app_secret"]`.
3. Every inbound POST webhook will be verified against the `X-Hub-Signature-256` header.

### 2.4 Testing Meta Lead Delivery
1. Open the [Meta Lead Ads Testing Tool](https://developers.facebook.com/tools/lead-ads-testing).
2. Select your Facebook Page and Lead Form.
3. Click **Create Lead**.
4. Check the WefyLabs integration log or call `GET /api/v1/lead-acquisition/sources/{source_id}/health` to confirm successful ingestion.

---

## 3. Google Ads Lead Form Setup & Operational Guide

### 3.1 Webhook Delivery Setup
1. In the **Google Ads Dashboard**, navigate to **Ads & assets** > **Assets** > **Lead form**.
2. Create or edit a lead form asset.
3. Expand the **Lead delivery options** section.
4. Set **Webhook URL**:
   `https://<your-domain>/api/v1/lead-acquisition/webhooks/google`
5. Set **Key**:
   Enter a cryptographically secure key matching your tenant's `LeadSource.webhook_secret` or `credentials["google_key"]`.
6. Click **Send test data** to dispatch a test lead payload.
7. Confirm that Google Ads displays "Test data sent successfully".

### 3.2 Dual Schema Processing
The WefyLabs connector automatically detects whether the submission is received via:
- **Webhook POST**: JSON containing `user_column_data` array and `gclid`.
- **Google Ads API**: Structured `columnData` objects.
Both formats are parsed and routed through canonical normalization.

---

## 4. Bounded Reconciliation & Backfill Operations

### 4.1 Running a Reconciliation Scan
To check for missing leads between the external provider and WefyLabs over a bounded window:
```http
POST /api/v1/lead-acquisition/reconcile
Content-Type: application/json
Authorization: Bearer <ADMIN_OR_MANAGER_TOKEN>

{
  "source_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "start_time": "2026-09-20T00:00:00Z",
  "end_time": "2026-09-23T00:00:00Z",
  "dry_run": true
}
```
**Response Analysis**:
- `total_scanned`: Number of leads discovered at the provider.
- `missing_lead_ids`: Leads present at the provider but absent in WefyLabs.
- If `dry_run: false`, missing leads are automatically retrieved, normalized, and ingested into canonical state.

### 4.2 Executing a Bounded Backfill
To import historical leads within a capped range:
```http
POST /api/v1/lead-acquisition/backfill
Content-Type: application/json
Authorization: Bearer <ADMIN_TOKEN>

{
  "source_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "start_time": "2026-09-15T00:00:00Z",
  "end_time": "2026-09-22T00:00:00Z",
  "batch_limit": 200
}
```

---

## 5. Disconnect & Reconnect Lifecycle

### 5.1 Disconnecting a Provider
```http
POST /api/v1/lead-acquisition/disconnect/meta
Authorization: Bearer <ADMIN_TOKEN>

{
  "source_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```
**Safety Invariants**:
- Future incoming webhooks are rejected.
- All historical leads, customers, attribution data, conversations, and appointments are **strictly preserved**.
- Integration status transitions to `DISCONNECTED`.

### 5.2 Reconnecting a Provider
```http
POST /api/v1/lead-acquisition/connect/meta
Authorization: Bearer <ADMIN_TOKEN>

{
  "provider": "META",
  "name": "Primary Meta Ad Account",
  "credentials": {
    "access_token": "EAA...",
    "app_secret": "xyz..."
  },
  "webhook_secret": "tenant_verify_secret"
}
```
- Re-verifies access tokens and page permissions.
- Transitions status to `CONFIGURED` or `VERIFIED`.

---

## 6. Common Failures & Troubleshooting

| Symptom | Probable Cause | Corrective Action |
| :--- | :--- | :--- |
| `401 Unauthorized` on Meta Webhook | `X-Hub-Signature-256` mismatch or missing `app_secret` | Verify app secret in `LeadSource` matches Meta App Dashboard. |
| `400 Bad Request` on Meta Challenge | `hub.verify_token` mismatch | Ensure verify token entered in Meta matches `LeadSource.webhook_secret`. |
| `401 Unauthorized` on Google Webhook | `google_key` missing or incorrect | Check Google Ads lead form asset settings for key match. |
| Meta lead retrieved with empty name/phone | Missing `leads_retrieval` permission | Complete App Review or assign System User role in Meta Business Manager. |
| Duplicate lead events in logs | Retried provider delivery | Expected behavior: Ingestion engine detects existing `idempotency_key` and marks event `DUPLICATE` without creating new leads. |
| Leads not assigned to sales agents | No matching routing rule or capacity full | Inspect `routing_reason` in Lead details; adjust agent workload limits. |

---

## 7. Security Notes & Invariants

1. **Tenant Isolation**: Tenant identity is resolved solely from authenticated webhook signatures or keys. Never pass tenant/organization IDs in public URLs or request bodies.
2. **Access Control (RBAC)**: Only `OWNER` or `ADMIN` roles may connect/disconnect providers, configure secrets, or trigger backfills.
3. **No Direct WhatsApp Webhook**: Meta WhatsApp Cloud API webhooks must remain disabled as WhatsApp acquisition is out of scope for Part 13.
4. **Secret Sanitization**: Never output access tokens or webhook keys in application logs, database debug traces, or error notifications.
