# WEFYLABS PART 14 — NATIVE REAL-ESTATE CRM ARCHITECTURE
============================================================
**Authoritative Architectural Specification — Native Real-Estate CRM & Customer 360**
*WefyLabs Revenue Operating System*

---

## 1. Executive Summary & Fundamental Business Philosophy

WefyLabs is built as a complete, sovereign, and self-contained **Native Real-Estate CRM**. 

Historically, AI applications in real estate functioned merely as ephemeral "connectors" or chat widgets attached to external legacy systems like HubSpot, Salesforce, Zoho, or Pipedrive. **WefyLabs breaks this dependency entirely**:
- **WefyLabs is the canonical System of Record** for all customers, leads, properties, pipeline deals, tasks, activities, notes, appointments, site visits, and revenue attribution.
- **Zero External CRM Dependency**: A real-estate brokerage or property developer can subscribe, onboard, acquire leads via Meta/Google, run AI qualification, match inventory, schedule viewings, negotiate transactions, track commission revenue, and manage their sales workforce without ever purchasing or configuring an external CRM.
- **Future Integration Boundary**: Legacy external CRMs (HubSpot, Salesforce, Zoho, Pipedrive) are strictly optional outbound export or sync adapters. The native CRM never imports external CRM schemas or depends on external provider keys.

```
                     WEFYLABS NATIVE PLATFORM
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
    LEAD OS               PROPERTY OS               SALES OS
(Acquisition, Form)     (Inventory Truth)     (Deals, Milestones)
       │                       │                       │
       └───────────────────────┼───────────────────────┘
                               │
                       NATIVE CRM CORE
      ┌────────────────────────┼────────────────────────┐
      │                        │                        │
 CUSTOMER 360            SALES PIPELINE               TASKS
(Full Context)          (11-Stage Kanban)        (Work Items & SLA)
      │                        │                        │
 ACTIVITIES                 NOTES                   TIMELINE
(Event Audits)          (Rich Briefs)           (Unified Stream)
      │                        │                        │
      └────────────────────────┼────────────────────────┘
                               │
                          AI WORKFORCE
                 (Gateway, Router, Tool Agents)
                               │
                       REVENUE AUTOPILOT
                   (Opportunities & Actions)
                               │
                     REVENUE INTELLIGENCE
                 (Funnel, Leakage, Attribution)
                               │
                     CANONICAL DOMAIN BUS
```

---

## 2. Core Domain Boundaries & System of Record

WefyLabs enforces strict separation of concerns across its domain entities. The CRM layer orchestrates, manages, and presents business state without corrupting underlying domain truth.

| Domain Entity | Authoritative System | CRM Layer Role | External CRM Dependency |
|---|---|---|---|
| **Customer Identity** | `CustomerIdentity` / `Lead` | Consolidated identity card & contact preferences | **NONE** |
| **Lead Lifecycle** | `Lead` + Regional Pipeline | Operator triage table, filters, transitions, routing | **NONE** |
| **Property Inventory** | Property OS (`PropertyListing`) | Read-only truth, unit pricing, specifications, match display | **NONE** |
| **Conversations** | Communication Hub (`OmnichannelConversation`) | Embedded channel viewer, delivery audits, message dispatches | **NONE** |
| **Sales Deals** | `DealTransaction` | Deal workspace, agreed price, stage progression, commission | **NONE** |
| **Tasks & Work** | `Task` | Daily operator priorities, due dates, overdue badges, completions | **NONE** |
| **Customer Activities** | `Activity` | Historical interaction tracking with actor provenance | **NONE** |
| **Notes** | `LeadNote` | Operator and AI briefing records with visibility tags | **NONE** |
| **Appointments & Visits**| Calendar & Site Visit Engines | Viewing confirmations, attendees, calendar sync, debriefs | **NONE** |
| **Revenue Intelligence**| Revenue Engine (`RevenueFunnelSnapshot`) | Funnel velocity, conversion metrics, leakage risk alerts | **NONE** |
| **Revenue Autopilot** | Autopilot (`RevenueOpportunity`) | Commercial interventions (READ, SUGGEST, CONFIRM, EXECUTE) | **NONE** |

---

## 3. Customer 360 Architecture

The Customer 360 workspace provides a consolidated single-pane-of-glass interface for sales agents and managers.

### 3.1 Visual & Logical Hierarchy
1. **Header**: Customer identity, phone, email, current sales stage, temperature badge (`hot`, `warm`, `cold`), lead owner, priority, SLA state, and next best action.
2. **Overview & Structured Preferences**: Budget (AED/INR), preferred property type (Villa, Penthouse, Apartment), target locations, furnishing, transaction intent (`buy`, `rent`), and timeline.
3. **Property Matches & Shortlist**: Ranked inventory matches generated by the property matching engine with suitability rationale and status (`recommended`, `viewed`, `visited`, `rejected`).
4. **Active Opportunities & Deals**: Commercial deal transactions, agreed valuation, expected commission, closing probability, and missing documentation.
5. **Operational Tasks**: Pending, high-priority, and overdue action items linked to the customer.
6. **Unified Customer Timeline**: High-performance reverse-chronological event stream consolidating:
   - Lead acquisition events (Meta Lead Ads, Google Ads, manual entry).
   - Inbound and outbound communications across Web Chat, Email, SMS.
   - Stage transitions with user and system provenance.
   - Appointments and site visit completions with feedback debriefs.
   - Tasks created, assigned, and completed.
   - Deal milestones and payment schedules.
   - AI Workforce recommendations and Revenue Autopilot actions.

---

## 4. Sales Pipeline & Kanban Architecture

The native CRM provides a visual 11-stage sales pipeline mapped to the property lifecycle:
`NEW` → `CONTACTED` → `ENGAGED` → `QUALIFIED` → `MATCHED` → `APPOINTMENT` → `SITE_VISIT` → `OPPORTUNITY` → `NEGOTIATION` → `BOOKING` → `WON / LOST`

### 4.1 Authoritative Valuation & Stagnation
- **Pipeline Total Value**: Sum of authoritative deal transaction agreed prices (or qualified lead maximum budgets) across all active, non-terminal stages.
- **Recorded Revenue**: Sum of actual agreed transaction values for deals successfully marked as `WON`.
- **Card Stagnation Alerts**: Real-time evaluation calculating the elapsed days since the lead's last stage progression or activity. Integrates with Revenue Autopilot to flag stalled opportunities.
- **Stage Transitions**: Governed by server-side state machine with audit log emission and domain event dispatch (`lead.stage_changed`).

---

## 5. Universal CRM Search & Filter Engine

Native CRM search enables instant retrieval across customers, leads, opportunities, tasks, and notes without third-party search dependencies:
- **Tenant Scoping**: All search queries are strictly bounded by `broker_id` and `organization_id`.
- **Deterministic Normalization**: Strips international dialing characters (`+`, `-`, spaces), normalizes email casing, and executes indexed wildcard queries.
- **Performance**: Paged via cursor and limit parameters; queries optimized to run under 20ms on indexed PostgreSQL and SQLite instances.

---

## 6. Security, RBAC & Multi-Tenant Isolation

1. **Authentication & Identity**: Every request requires verified JWT bearer tokens resolving authenticated `Broker` instances.
2. **Tenant Boundary**:
   - Every database query explicitly filters by `broker_id` or `organization_id`.
   - Cross-tenant lookups on customers, leads, deals, tasks, or search return strict `404 Not Found` or `403 Forbidden`.
3. **Bulk Safety**:
   - Maximum batch limit enforced (100 records).
   - Server independently verifies tenant ownership of every ID in the batch before mutating state.
   - Audit logs capture total targeted, successful, and failed counts with correlation IDs.
4. **AI Spoofing Defense**: Actor identity for AI actions is derived strictly from server-side AI execution tokens, preventing client-side actor tampering.

---

## 7. Zero External CRM Dependency Verification

A fresh WefyLabs tenant can execute the entire real estate revenue journey from lead acquisition to commission recording without connecting or configuring any external CRM. All CRM features are native to WefyLabs.
