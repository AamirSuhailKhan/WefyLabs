# WEFYLABS PHASE 12 — WHATSAPP ACTIVATION CHECKLIST
**Meta WhatsApp Cloud API Commercial Activation & Safety Runbook**  
**Operating State:** **HARD DISABLED (`WHATSAPP_ENABLED = false`)**  
**Auditor:** Principal Integration Lead & Application Security Engineer  
**Audit Date:** 2026-10-29  

---

## 1. Safety Policy & Current Operating Invariant

In compliance with Master Prompt 12 Phase E:
- **Zero customer-facing messages may be sent during testing or unapproved pilot runs.**
- `WHATSAPP_ENABLED = false` and `FOLLOWUP_HUB_DISPATCH_ENABLED = false` are strictly enforced in configuration.
- The outbound adapter fails closed and returns:
  ```json
  {"status": "blocked", "error_code": "CHANNEL_DISABLED"}
  ```
- Before live messaging can be activated, every item in this checklist must be verified and signed off by the Operations Lead.

---

## 2. Meta Business & Application Configuration Checklist

### Stage 1: Meta Business Manager & Credentials
- [ ] **Meta Business Verification:** Complete business identity verification in Meta Business Manager (`business.facebook.com`).
- [ ] **WhatsApp Business Account (WABA):** Provision official WABA and bind credit line/payment method.
- [ ] **Phone Number Registration:** Register dedicated commercial sender phone number (e.g., `+91XXXXXXXXXX`) with two-step verification PIN.
- [ ] **System User Access Token:** Generate a permanent System User token with `whatsapp_business_messaging` and `whatsapp_business_management` permissions.
- [ ] **App Secret Provisioning:** Retrieve App Secret for webhook HMAC-SHA256 signature verification.

### Stage 2: Application Environment Injection
Configure the following environment variables in production `.env` (never commit to git):
```ini
WHATSAPP_ENABLED=true
WHATSAPP_API_VERSION=v20.0
WHATSAPP_PHONE_NUMBER_ID=100xxxxxxxxxxxx
WHATSAPP_BUSINESS_ACCOUNT_ID=200xxxxxxxxxxxx
WHATSAPP_ACCESS_TOKEN=<SYSTEM_USER_PERMANENT_TOKEN>
WHATSAPP_APP_SECRET=<META_APP_SECRET_FOR_HMAC>
WHATSAPP_VERIFY_TOKEN=<HIGH_ENTROPY_RANDOM_VERIFY_STRING>
```

---

## 3. Webhook Infrastructure & Cryptographic Verification

- [ ] **Endpoint Verification (`GET /api/v1/whatsapp/webhook`):**
  Meta sends `hub.mode=subscribe`, `hub.verify_token`, and `hub.challenge`. The endpoint must return the exact challenge string in plain text with HTTP 200.
- [ ] **HMAC SHA-256 Signature Verification (`POST /api/v1/whatsapp/webhook`):**
  - Evaluated in `verify_meta_signature()` against `X-Hub-Signature-256`.
  - Proved in `apps/api/tests/test_whatsapp_webhook.py` (13/13 passed): missing signature, forged signature, altered payload, or missing server secret immediately returns 401/503.
- [ ] **Webhook Idempotency & Deduplication:**
  All inbound messages and delivery receipts are logged to `raw_communication_events` with unique event IDs. Duplicate delivery receipts return `action: duplicate_suppressed`.

---

## 4. Delivery Status & Opt-Out Compliance

- [ ] **Delivery Lifecycle Transitions:**
  Verify that delivery receipts update message status in sequence:
  $$\text{PENDING} \longrightarrow \text{SENT} \longrightarrow \text{DELIVERED} \longrightarrow \text{READ} \quad (\text{or } \text{FAILED})$$
- [ ] **TCPA / GDPR Opt-Out Processing:**
  Inbound messages matching `STOP`, `UNSUBSCRIBE`, `CANCEL`, or `OPT OUT` automatically set `leads.is_opted_out = true` and block subsequent automated outreach.
- [ ] **Template Approval:**
  All outbound initial outreach messages must use Meta-approved WhatsApp Message Templates with verified parameter bindings. Free-form text is restricted to active 24-hour customer care windows.

---

## 5. Verified Emergency Kill-Switch Procedure

If unexpected message loops, spam complaints, or unintended customer messages are detected:

### Immediate Kill-Switch Trigger:
1. Set `WHATSAPP_ENABLED=false` in environment.
2. Signal the application to reload:
   ```bash
   docker compose exec api kill -HUP 1
   ```
3. Confirm in logs:
   ```text
   [WhatsAppCloudProvider] BLOCKED send: channel disabled by configuration.
   ```
4. Revoke the System User Access Token in Meta Business Manager if compromised.

