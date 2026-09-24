# WefyLabs Part 18 — Reality Audit & Architecture Baseline
**Date:** 2026-09-24  
**Author:** Principal Engineer & Real Estate SaaS Architect  
**Subject:** Reality Audit of Existing Commercial Pipeline, Deal Management, and Transaction Artifacts

---

## Executive Summary
This document establishes the verified baseline of WefyLabs before implementing **Part 18: Real Estate Deal, Booking & Transaction Operating System (OS)**.
Every finding has been independently verified against the actual repository codebase, database models, Alembic migrations, and test suites.

---

## 1. Verified Inventory of Existing Commercial Concepts

| Domain Area | Concept / Entity | Actual File Location | Classification | Findings & Boundary with Part 18 |
|---|---|---|---|---|
| **Pipeline & Deals** | `DealTransaction` | `apps/api/app/models/transaction_models.py` | **VERIFIED (PARTIAL)** | 13-stage legacy pipeline (`lead` to `after_sales`). Handled primarily in `/transactions`. Part 18 introduces canonical `Deal` with backward compatibility reference (`legacy_deal_transaction_id`). |
| **Milestones** | `DealMilestone`, `DealPaymentSchedule` | `apps/api/app/models/transaction_models.py` | **VERIFIED** | Tracks milestone completion and scheduled payments for deals. |
| **AI Risk Service** | `DealAIRiskService` | `apps/api/app/services/deal_ai_risk_service.py` | **VERIFIED** | Computes closing probability (0-100%), risk level (`low`, `medium`, `high_risk`, `critical_stalled`), missing documents. |
| **Workflow Engine** | `DealWorkflowEngine` | `apps/api/app/services/deal_workflow_engine.py` | **VERIFIED** | Deterministic state machine validating stage progression and required stage documents. |
| **CRM Opportunities** | `OpportunitySummaryDTO`, `OpportunityCreateRequest` | `apps/api/app/modules/crm/dto/crm_schemas.py` | **VERIFIED** | DTOs in CRM core (Part 14) representing commercial pursuits. Directly inter-operable with deals. |
| **Autopilot Revenue** | `RevenueOpportunity` | `apps/api/app/models/revenue_autopilot_models.py` | **VERIFIED** | High-value commercial discovery linking Lead + Property Recommendation. Converts into Deals. |
| **Revenue Intelligence** | `RevenueFunnelSnapshot`, `RevenueLeakageEvent` | `apps/api/app/models/revenue_intelligence_models.py` | **VERIFIED** | Periodic funnel health snapshots and lost deal leakage analysis (Part 11). |
| **Property Inventory** | `PropertyListing`, `LeadPropertyInterest` | `apps/api/app/models/property_models.py` | **VERIFIED** | Real estate listings. `LeadPropertyInterest` tracks status: `INTERESTED`, `SHORTLISTED`, `VIEWED`, `RESERVED`, `PURCHASED`. |
| **Transactional Outbox** | `OutboxEvent` | `apps/api/app/models/outbox_models.py` | **VERIFIED** | Outbox engine guaranteeing reliable, idempotent delivery of domain events for all irreversible commercial operations. |
| **Audit Log** | `AuditLog` | `apps/api/app/models/audit_log.py` | **VERIFIED** | SOC2-compliant immutable audit log recording all administrative and business mutations. |
| **Distributed Locks** | `RedisDistributedLock` | `apps/api/app/infrastructure/redis/redis_lock.py` | **VERIFIED** | Atomic Redis lock (`SET NX EX` + Lua token verification) preventing race conditions in unit reservations. |
| **Payments Layer** | `PaymentOrder`, `PaymentTransaction` | `apps/api/app/models/payment_models.py` | **VERIFIED (MOCKED/ENV-GATED)** | Razorpay models present, explicitly mocked/test-mode only. No live financial processing. |
| **Offers & Negotiations**| Formal Offer Model | *Non-existent prior to Part 18* | **MISSING** | Part 18 introduces `DealOffer` with versioned history and counter-offer mechanisms. |
| **Reservations** | Unit Hold Model | *Non-existent prior to Part 18* | **MISSING** | Part 18 introduces `DealReservation` with distributed lock protection and auto-expiry. |
| **Bookings** | Booking Confirmation Model | *Non-existent prior to Part 18* | **MISSING** | Part 18 introduces `DealBooking` with token payment logging and signed form tracking. |
| **Commission Ledger** | Splits & Invoicing | *Non-existent prior to Part 18* | **MISSING** | Part 18 introduces `DealCommission` with multi-agent split calculations and dispute resolution. |
| **Closing & Handover** | Legal & Title Transfer | *Non-existent prior to Part 18* | **MISSING** | Part 18 introduces `DealClosing` with registration and key handover workflows. |
| **Post-Sale Intelligence**| Post-Sale & Revenue Learning | *Non-existent prior to Part 18* | **MISSING** | Part 18 introduces `DealPostSale` capturing NPS, satisfaction, and revenue feedback signals. |

---

## 2. Alembic Migration Head
- **Current Head:** `0030_enterprise_runtime`
- **Part 18 Migration:** `0031_deal_booking_transaction_os` (down-revision: `0030_enterprise_runtime`)

---

## 3. Architectural Boundary: Opportunity vs Deal vs Transaction
1. **Opportunity:** Early-stage commercial intent detected by AI Autopilot (`RevenueOpportunity`) or captured by broker in CRM (`OpportunityCreateRequest`).
2. **Deal (`Deal`):** Accepted commercial pursuit where buyer and broker actively negotiate terms, make formal offers, and hold property reservations.
3. **Transaction (`DealBooking` / `DealClosing`):** Irreversible commercial execution after booking token confirmation, leading to contract signing, commission split, registration, and handover.

---

## 4. Non-Negotiable Safety Invariants Verified
1. **No External CRM Dependencies:** Native WefyLabs database is the sole authoritative system of record.
2. **Payment Engine Gating:** No live Razorpay keys are active. Financial state management operates purely as ledger bookkeeping.
3. **Double-Reservation Prevention:** All unit reservation requests must acquire a Redis distributed lock on `lock:property:{property_id}:reservation` with strict TTL.
4. **Transactional Outbox Guarantee:** Every stage transition, offer acceptance, booking confirmation, and closing event atomically registers an `OutboxEvent` within the same DB transaction.
