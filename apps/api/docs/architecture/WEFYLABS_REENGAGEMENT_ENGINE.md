# WEFYLABS ARCHITECTURE — RE-ENGAGEMENT ENGINE & ELIGIBILITY GATE (BUILD 07)

## 1. Executive Summary

The Re-Engagement Engine revives inactive leads without causing customer fatigue, brand damage, or regulatory non-compliance. In Build 07, `ReengagementEligibilityGate` wraps all draft generation and message scheduling behind strict multi-tiered governance.

---

## 2. Multi-Tiered Eligibility Verification

Before any re-engagement draft or task is generated, the lead must pass seven distinct gates:

```mermaid
flowchart TD
    LeadCandidate[Inactive Lead Candidate] --> Gate1{1. Multi-Tenant Check}
    Gate1 -->|Pass| Gate2{2. Lifecycle State Check}
    Gate1 -->|Fail| Rejected[REJECTED: Unauthorized Org]
    Gate2 -->|Not Terminal| Gate3{3. Human Takeover Check}
    Gate2 -->|Terminal: Lost/Converted| Rejected
    Gate3 -->|No Human Active| Gate4{4. Inactivity Threshold}
    Gate3 -->|Human Active| Rejected
    Gate4 -->|>= Policy Days (14d)| Gate5{5. Max Lifetime Attempts}
    Gate4 -->|Too Recent| Rejected
    Gate5 -->|< 3 Attempts| Gate6{6. Consent & Suppression Check}
    Gate5 -->|>= 3 Attempts| Rejected
    Gate6 -->|Active Consent & Passed Fatigue| Approved[APPROVED: Generate Grounded Draft]
    Gate6 -->|Opted Out / Fatigued| Rejected
```

---

## 3. Grounded AI Draft Generation & Prompt Injection Defense

### 3.1 Facts-Grounded Generation
- The draft prompt is populated **strictly** from verified CRM facts:
  - Lead Name, Property Type, Preferred Locations, Budget Range, Days Inactive, Assigned Advisor.
- LLMs are instructed to never hallucinate pricing, inventory availability, or prior unrecorded conversations.

### 3.2 Prompt Injection Neutralization
- User-supplied text fields (lead name, notes, custom tags) are sanitized by `_sanitize_untrusted_text()`.
- Strips system instruction tokens (`ignore previous instructions`, `system prompt`, `send secret`) and non-printable control characters.
- Injected prompts are replaced with safe filters (`[filtered]`), preventing jailbreaks or unauthorized data exfiltration.
