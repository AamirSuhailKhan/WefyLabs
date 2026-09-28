# WefyLabs Data Usage, Privacy & Tenant Isolation Governance

## 1. Absolute Data Governance Principles
1. **Tenant Isolation**: Customer operational data is strictly segregated by `organization_id`. Tenant data never leaks into another organization's analytics or recommendations.
2. **Explicit Consent**: Customer data must never be used for cross-customer machine learning training without explicit, contractual authorization.
3. **No Unsanctioned Aggregation**: Aggregation alone does not make data safe; k-anonymity ($k \ge 5$) is mandatory to prevent reconstruction attacks.
4. **Data Classification**:
   - `PUBLIC`: Developer floorplans, project brochure marketing assets.
   - `INTERNAL`: Operational task assignments, system configuration.
   - `CONFIDENTIAL`: Lead names, conversation transcripts, offer negotiation terms.
   - `RESTRICTED`: Payment gateway credentials, passport copies, banking records.

## 2. Red Team Security Invariants
- **Prompt Injection Defense**: All untrusted external inputs (inbound WhatsApp text, web forms) are filtered and tokenized before inclusion in prompt context. Malicious override commands (`IGNORE PREVIOUS INSTRUCTIONS`) are stripped.
- **IDOR Protection**: All resource lookup endpoints (`/intelligence/outcomes`, `/intelligence/learning/signals`, `/intelligence/graph/leads/{id}/journey`) authenticate tenant membership and enforce tenant filtering at the SQL layer.
- **Poisoning Resistance**: Events originating from untrusted webhooks or external brokers must pass cryptographic hash validation before entering learning queues.

## 3. Replay & Backfill Determinism
- **Deterministic Replay**: Re-running the outcome event stream across any historical time window yields bit-for-bit identical aggregate intelligence snapshots.
- **Idempotent Backfill**: Scanning operational tables uses unique source keys (`leads:lead_id`) to ensure no duplicate outcome events are generated.
