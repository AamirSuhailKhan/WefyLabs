# WefyLabs Customer Portal Architecture OS — Part 21

## 1. Executive Summary

WefyLabs Part 21 delivers the **Customer Experience & Digital Deal Room OS**, an enterprise-grade customer-facing operational layer for high-value real estate transactions. Unlike generic portals that expose raw CRM tables, WefyLabs implements a **Zero-Trust Customer Projection Layer** that strictly protects internal revenue operations, margins, internal notes, risk scores, and multi-tenant boundaries while offering purchasers a transparent, frictionless, and secure transaction collaboration workspace.

---

## 2. Core Architecture Topology

```
                  ┌──────────────────────────────────────────────┐
                  │          Customer Frontend Workspace         │
                  │   (/portal - Next.js 15 App Router + Vanilla)│
                  └──────────────────────┬───────────────────────┘
                                         │ Bearer Customer JWT
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │    Customer Security Gateway & Auth Barrier  │
                  │        (app.modules.portal.dependencies)     │
                  │  - Validates role == 'portal_customer'       │
                  │  - Resolves lead_id & organization_id from   │
                  │    signed JWT claims (never from client args)│
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │      Customer-Safe Projection Layer (DTOs)   │
                  │    - Strips commission, margins, notes       │
                  │    - Filters internal CRM channels           │
                  │    - Maps internal state to customer state   │
                  └──────┬───────────────┬───────────────┬───────┘
                         │               │               │
        ┌────────────────▼───┐   ┌───────▼────────┐   ┌──▼───────────────────┐
        │  Digital Deal Room │   │ Document Engine│   │ Payment & Accounting │
        │  (Deal, Booking,   │   │ (DealDocument, │   │ (PaymentMilestones,  │
        │   Milestones)      │   │  MIME audit)   │   │  PaymentProof)       │
        └────────────────────┘   └────────────────┘   └──────────────────────┘
                         │               │               │
                         ▼               ▼               ▼
                  ┌──────────────────────────────────────────────┐
                  │         WefyLabs Core Authoritative DB       │
                  │     PostgreSQL + Alembic (0034_customer_... ) │
                  └──────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Authentication & Session Architecture
1. **Invite Token Generation (`POST /api/v1/portal/invites`)**:
   - Internal brokers generate time-bound, cryptographically random 64-character hex tokens (`secrets.token_urlsafe(32)`).
   - Only the SHA-256 hash is persisted in `customer_portal_invites` table.
   - Tokens default to 7 days lifespan and support automatic invalidation upon status revocation.
2. **Token Exchange (`POST /api/v1/portal/auth/token`)**:
   - Customer presents raw invite token.
   - Server computes SHA-256 hash and checks against database.
   - Upon valid verification, generates a short-lived signed RS256/HS256 JWT containing:
     ```json
     {
       "sub": "<lead_id>",
       "organization_id": "<organization_id>",
       "role": "portal_customer",
       "deal_id": "<optional_deal_id>",
       "exp": 1727720000
     }
     ```
   - Increments invite `access_count` and updates `last_accessed_at`.

### 3.2 Authorization Boundary (`get_current_portal_customer`)
- Dependency strictly extracts `sub` as the authoritative `lead_id` and `organization_id` from the decoded JWT.
- Verifies `role == "portal_customer"`.
- Validates the `Lead` exists, is active, and is not soft-deleted.
- Client-supplied `customer_id` or `tenant_id` query parameters and headers are **completely ignored** as authority.

---

## 4. API Endpoints Catalog

| Route | Method | Access | Purpose |
|---|---|---|---|
| `/api/v1/portal/invites` | `POST` | Broker/Admin | Generate secure customer portal invite link |
| `/api/v1/portal/auth/token` | `POST` | Public / Customer | Exchange raw invite token for Customer JWT |
| `/api/v1/portal/overview` | `GET` | Customer | High-level summary of active deal, next action, documents, advisor |
| `/api/v1/portal/deal` | `GET` | Customer | Authoritative Deal Room details, accepted terms, 9-stage stepper |
| `/api/v1/portal/documents` | `GET` | Customer | List requested documents with customer-safe status |
| `/api/v1/portal/documents/{id}/upload` | `POST` | Customer | Upload file URL for required document (marks `IN_REVIEW`) |
| `/api/v1/portal/documents/{id}/review` | `POST` | Broker/Admin | Internal compliance approval or rejection |
| `/api/v1/portal/payments/schedule` | `GET` | Customer | Milestone schedule, due dates, verified amounts |
| `/api/v1/portal/payments/proof` | `POST` | Customer | Submit bank transfer remittance slip (marks `REPORTED`) |
| `/api/v1/portal/payments/proof/{id}/review` | `POST` | Broker/Admin | Finance audit verification or rejection |
| `/api/v1/portal/appointments` | `GET` | Customer | Scheduled property viewings & DLD notarizations |
| `/api/v1/portal/appointments/{id}/confirm` | `POST` | Customer | Customer confirmation of attendance |
| `/api/v1/portal/messages` | `GET` | Customer | Customer-visible messages (internal notes strictly omitted) |
| `/api/v1/portal/messages` | `POST` | Customer | Post customer message to assigned advisor |
| `/api/v1/portal/support` | `GET` | Customer | List customer support requests |
| `/api/v1/portal/support` | `POST` | Customer | Submit support ticket (spawns CRM Task for broker) |
| `/api/v1/portal/post-sale/feedback` | `POST` | Customer | Submit CSAT (1-5) and NPS (0-10) post-sale feedback |
| `/api/v1/portal/acknowledgement` | `POST` | Customer | Formal customer acceptance of booking/milestone terms |
| `/api/v1/portal/ai/query` | `POST` | Customer | Governed AI Assistant grounded strictly in active customer records |
