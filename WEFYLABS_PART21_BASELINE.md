# WefyLabs Part 21 — Customer Experience & Digital Deal Room OS Baseline Audit

## Reality Audit Summary

**Date**: September 24, 2026  
**Auditor**: Principal Product Architect, Real Estate SaaS Architect, Security Architect  
**Objective**: Reality audit of existing customer-facing capabilities, models, authentication, and transaction touchpoints across Parts 1–20 before building Part 21.

---

## 1. System Inventory & Classification Matrix

| Capability Area | Status | Existing Location / Model | Audit Finding & Action Required |
|---|---|---|---|
| **Customer Portal Home** | `PARTIAL` | `apps/web/src/app/portal/page.tsx` | Prototype exists; lacks authenticated session binding, deal room tab, document review, and payment schedule. |
| **Customer Authentication** | `MISSING` | `apps/api/app/modules/auth/` | Broker/Agent authentication is robust (`/auth/login`, `/auth/register`, Google OAuth). Customer-specific magic link and customer JWT authorization boundary were missing. |
| **Customer Access Tokens** | `MISSING` | N/A | Need single-use SHA-256 hashed portal invite tokens and short-lived customer JWTs (`sub: lead_id, org: organization_id, role: portal_customer`). |
| **Digital Deal Room** | `BACKEND ONLY` | `apps/api/app/models/deal_models.py` (`Deal`) | Complete backend deal lifecycle exists (Opportunity → Closing). Customer-safe Deal Room projection was missing. |
| **Document Request Engine** | `PARTIAL` | `deal_documents` table in Part 18 | `DealDocument` stores `document_type`, `required_at_stage`, `file_url`, `status`. Needs customer-safe request/upload/review workflow. |
| **Customer Document Upload** | `MISSING` | `MediaHandler` in Part 12 / Part 18 | Document upload endpoint existed only for brokers. Customer-authenticated upload with MIME/size validation required. |
| **Document Review Workflow** | `BACKEND ONLY` | `deal_service.py` | Statuses (`REQUIRED`, `UPLOADED`, `VERIFIED`, `REJECTED`). Customer must see only customer-safe statuses (`IN_REVIEW`, `APPROVED`, `ACTION_REQUIRED`). |
| **Payment Schedule Visibility** | `BACKEND ONLY` | `DealBooking.payment_schedule` (Part 18) | Booking payment milestones stored as JSONB. Needs customer-safe projection (amounts, due dates, statuses: `UPCOMING`, `DUE`, `REPORTED`, `VERIFIED`). |
| **Payment Proof Upload** | `MISSING` | N/A | Customer can upload payment receipt proof (`REPORTED` status). System must NEVER mark payment as `VERIFIED` on upload. |
| **Transaction Milestones** | `BACKEND ONLY` | `DealStage` (Part 18) | 9 canonical deal stages. Customer view must project filtered customer-visible milestones without exposing internal margins or risk scores. |
| **Appointments & Site Visits** | `BACKEND ONLY` | `SchedulingMeeting` (`calendar_models.py`, Part 6) | Full Google Calendar integration exists. Needs customer-filtered projection (upcoming site visits, meeting links, status). |
| **Customer Messaging** | `PARTIAL` | `UnifiedMessage` (`communication_models.py`, Part 12) | Omnichannel communication exists. Must strictly enforce `INTERNAL` vs `CUSTOMER_VISIBLE` boundary (never leak `internal_note`). |
| **Customer Timeline** | `HARDCODED` | `CustomerTimelineTracker.tsx` (Frontend) | Existed as static dummy steps. Must be bound to authoritative transaction and document events. |
| **Closing & Handover** | `BACKEND ONLY` | `DealClosing` (`deal_models.py`, Part 18) | Title deed, registration number, handover date exist. Needs customer-safe projection without private legal notes. |
| **Post-Sale & NPS/CSAT** | `BACKEND ONLY` | `DealPostSale` (`deal_models.py`, Part 18) | NPS (1-10), CSAT (1-5), and feedback fields exist. Needs customer submission endpoint with duplicate submission prevention. |
| **Customer Support Requests** | `MISSING` | N/A | Need structured customer support ticket creation (`DOCUMENT_HELP`, `PAYMENT_QUERY`, etc.) feeding into CRM tasks. |
| **Customer AI Assistant** | `PARTIAL` | `AISalesChat.tsx`, Part 5 AI Agent | AI agent exists, but lacked authoritative deal room data grounding and strict data leakage boundary. |
| **Financial Safety** | `VERIFIED` | Architecture Policy | Razorpay remains TEST/MOCK only. No autonomous financial deductions. Server is sole authority for all pricing. |

---

## 2. Non-Negotiable Data Separation Rules

1. **Internal CRM Notes**: Filter `UnifiedMessage.channel != 'internal_note'` and exclude `LeadNote` completely.
2. **Internal AI Reasoning**: Exclude `ai_urgency_score`, `ai_detected_objections`, `ai_sentiment`, `closing_probability_pct`, `risk_level`, `risk_factors`.
3. **Internal Commercials**: Exclude `commission_percentage`, `commission_amount`, `gross_commission`, `net_commission`, `commission_split_details`.
4. **Tenant & Customer Isolation**: Customer identity is resolved strictly from verified JWT `lead_id` and `organization_id`. URL parameters or body fields containing `customer_id` or `tenant_id` are ignored and forbidden.
