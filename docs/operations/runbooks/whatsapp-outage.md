# RUNBOOK — WHATSAPP CLOUD API PROVIDER OUTAGE
## Code: RB-WA-005 | Severity: P1 / P2

---

## 1. Symptoms & Triggers
- Outbound WhatsApp delivery fails with 5xx from Meta Graph API.
- Webhook signature failure or webhook ingestion latency > 1,000ms.

## 2. Diagnostics
1. Check Meta Business Status Page (metastatus.com).
2. Inspect WhatsApp Circuit Breaker state via `/health/dependencies`.

## 3. Mitigation & Recovery
- Circuit breaker trips to OPEN; outbound messages automatically buffer in Transactional Outbox.
- If customer inquiry requires immediate response, fallback to SMS/Email notification channel.
- When Meta recovers, Circuit Breaker probes in HALF_OPEN and flushes buffered outbox with rate-limited jitter.
