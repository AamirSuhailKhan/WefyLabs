# WEFYLABS — DATA RETENTION, DELETION & LEGAL HOLD POLICY

**Document Reference:** SEC-POL-004  
**Classification:** INTERNAL  
**Authority:** Compliance Architect + Legal Counsel  
**Last Updated:** 2026-09-27 (Master Build 11)  
**Status:** ACTIVE — PRODUCTION TRUTH  

---

## 1. STATUTORY RETENTION SCHEDULES

WefyLabs enforces automated statutory data retention limits across all CRM and observability domains:

| Domain | Statutory Retention | Rationale / Regulation |
| :--- | :---: | :--- |
| **Audit Logs** | **2,555 Days (7 Years)** | SOC 2 Type II, ISO/IEC 27001, Sarbanes-Oxley auditability |
| **Financial Records** | **2,555 Days (7 Years)** | Tax accounting, payment receipts, commission ledgers |
| **CRM Leads & Contacts**| **730 Days (2 Years)** | Standard real estate customer lifecycle |
| **Conversations / WhatsApp**| **365 Days (1 Year)** | Communication record history |
| **AI Prompt Traces** | **90 Days** | Operational debugging & latency telemetry |
| **Governed Data Exports**| **7 Days** | Ephemeral download URL expiry |

---

## 2. CONTROLLED DELETION STRATEGIES

When data deletion is requested (e.g. GDPR Article 17 Right-to-be-Forgotten or retention expiry), WefyLabs supports three formal strategies:

1. **SOFT_DELETE:** Flags the record `is_deleted = True`. Data is omitted from all standard business queries while preserving referential integrity.
2. **ANONYMIZE:** Strips all identifying PII (name set to `"Anonymized GDPR Subject"`, phone to `"+0000000000"`, email erased) while retaining transaction amounts, closing dates, and property IDs for aggregate financial reporting.
3. **HARD_DELETE:** Permanently drops the row from storage. Only permitted when statutory retention has elapsed and no legal hold is active.

---

## 3. THE LEGAL HOLD MECHANISM

- **Preemption:** An active **Legal Hold** strictly overrides and preempts any automated retention purge or GDPR Right-to-be-Forgotten deletion request.
- **Fail-Closed Locking:** Any API request or background worker attempting to delete or anonymize a record under an active Legal Hold immediately fails with `HTTP 423 Locked` (`LegalHoldActiveError`).
- **Scope:** Legal holds can be placed on specific target records (e.g. a specific `Lead` or `Deal`) or organization-wide (locking all tenant records during regulatory discovery).
- **Audit Requirement:** Placing and releasing legal holds requires administrative authentication (`OWNER` or `ADMIN`) and records an immutable high-severity entry in `AuditLog`.
