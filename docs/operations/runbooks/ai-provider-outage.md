# RUNBOOK — AI PROVIDER (GOOGLE GEMINI) OUTAGE
## Code: RB-AI-006 | Severity: P1

---

## 1. Symptoms & Triggers
- Gemini API returns HTTP 429 (Rate Limit) or HTTP 503 (Unavailable).
- SLO `ai_response_p95_ms` breached (> 3,000ms).

## 2. Diagnostics
1. Check Google Cloud Service Health dashboard.
2. Verify token quota limits in Google AI Studio / GCP Console.

## 3. Mitigation & Recovery
- AI Circuit Breaker transitions to OPEN.
- System automatically deploys deterministic rule-based qualification and cached FAQs.
- Lead capture and human sales agent queues remain 100% operational.
- Once Gemini latency stabilizes under 1,500ms, circuit breaker returns to CLOSED.
