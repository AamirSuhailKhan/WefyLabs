# WefyLabs UX & Product Architecture Audit — Current State
**Master Build 10 — Phase 0 Audit**  
**Date:** September 2026  
**Status:** COMPLETE & AUTHORITATIVE  
**Auditor Roles:** Chief Product Officer + CTO + Principal Frontend Architect + UX Systems Architect + Design Systems Engineer

---

## 1. Executive Summary

An exhaustive inspection of `apps/web/src/` was conducted across all 58 routes and 87 component modules. The platform possesses deep commercial and intelligence capabilities engineered in Builds 01 through 09, including:
- Omnichannel Communication Engine v2 (Build 03)
- Property Intelligence & Grounded Matching (Build 04)
- AI Sales Agent & Safe Tool Execution (Build 05/06)
- Follow-Up Workflows & Next-Best-Action (NBA) Engine (Build 07)
- Commercial Deals Lifecycle & Stage Guardrails (Build 08)
- Measurable Revenue Intelligence, Attribution & Funnel Analytics (Build 09)

However, the user experience currently exhibits **surface fragmentation**:
1. **Parallel Workspaces:** Two competing lead listings (`/dashboard/leads` vs `/dashboard/crm/leads`), two pipeline views (`/dashboard/pipeline` vs `/dashboard/crm/pipeline`), and split inventory views (`/dashboard/properties` vs `/dashboard/inventory`).
2. **Disconnected Navigation:** High-frequency daily operational surfaces—specifically the **Omnichannel Inbox** (`/dashboard/inbox`) and **Tasks Center** (`/dashboard/tasks`)—are either absent from the top navigation bar or buried in sub-menus.
3. **Command Center Mode Toggling:** The main `/dashboard` page relies on an artificial view mode switcher (`Revenue Autopilot` vs `Command Center` vs `Pipeline` vs `Table`) rather than presenting a unified, prioritized operational hierarchy.
4. **Theme Inconsistency:** `/dashboard` adheres to a warm editorial design palette (`#F0EDE8` background, `#1A1A1A` high-contrast typography, `#D4D0C8` subtle borders), whereas `/leads/[id]` uses dark slate styling (`bg-slate-900`, `glass-panel`, `border-dark-border`).
5. **Partial API Wiring in Inbox:** The Omnichannel Inbox was displaying AI escalations but lacked direct wiring to the canonical `/communication/v2/inbox` endpoint implemented in Build 03.
6. **Global Search Isolation:** The `CommandMenu` was limited to hardcoded client routes, while the backend exposes canonical cross-entity search (`/v1/search` and `/crm/search`).

---

## 2. Route Inventory & Classification

Every route in `apps/web/src/app` was mapped, analyzed, and classified into the required architectural categories:

| Route Path | Lines | Classification | Functional Reality & Findings |
|---|---|---|---|
| `/` (`app/page.tsx`) | 780 | `CANONICAL` / `PRODUCTION-READY` | Public landing page, ROI calculator, region context switcher. |
| `/login` (`app/login/page.tsx`) | 258 | `CANONICAL` / `PRODUCTION-READY` | Secure broker authentication with Google OAuth & password fallback. |
| `/register` (`app/register/page.tsx`) | 343 | `CANONICAL` / `PRODUCTION-READY` | Broker onboarding registration with agency and city profiling. |
| `/auth/callback` (`app/auth/callback/page.tsx`) | 133 | `CANONICAL` / `PRODUCTION-READY` | OAuth exchange handler with deterministic token storage. |
| `/onboarding` (`app/onboarding/page.tsx`) | 855 | `CANONICAL` / `PRODUCTION-READY` | 6-step tenant setup checklist, CSV import, demo mode toggle. |
| `/dashboard` (`app/dashboard/page.tsx`) | 235 | `FRAGMENTED` | Shell hosting 4 separate view modes via client state; lacks unified convergence. |
| `/dashboard/inbox` (`app/dashboard/inbox/page.tsx`) | 451 | `INCOMPLETE` / `CANONICAL` | Surfaces real AI escalations & takeover, but was missing connection to `/communication/v2/inbox`. Not in top navigation! |
| `/dashboard/leads` (`app/dashboard/leads/page.tsx`) | 428 | `CANONICAL` / `PRODUCTION-READY` | Filterable lead table with scores, export, and modal creation. |
| `/dashboard/crm/leads` (`app/dashboard/crm/leads/page.tsx`) | 373 | `DUPLICATE` | Second lead table inside CRM subfolder with redundant filter set. |
| `/leads/[id]` (`app/leads/[id]/page.tsx`) | 201 | `CANONICAL` / `FRAGMENTED` | Comprehensive lead detail, but suffers from dark-theme styling mismatch and redundant data cards. |
| `/dashboard/crm/customers/[id]` | 597 | `DUPLICATE` / `FRAGMENTED` | Secondary customer 360 page duplicating `/leads/[id]`. |
| `/dashboard/pipeline` (`app/dashboard/pipeline/page.tsx`) | 218 | `CANONICAL` | Visual pipeline kanban based on lead lifecycle stages. |
| `/dashboard/crm/pipeline` | 198 | `DUPLICATE` | Second pipeline kanban backed by `api.crm.getPipeline()`. |
| `/dashboard/deals` (`app/dashboard/deals/page.tsx`) | 1,621 | `CANONICAL` / `PRODUCTION-READY` | Comprehensive 9-stage commercial deal workspace with guardrails and confirmation modals. |
| `/dashboard/properties` (`app/dashboard/properties/page.tsx`) | 1,450 | `CANONICAL` / `PRODUCTION-READY` | Natural language search, property valuations, debrief modals, and buyer matching. |
| `/dashboard/inventory` (`app/dashboard/inventory/page.tsx`) | 916 | `CANONICAL` / `PRODUCTION-READY` | Unit-level supply inventory with multi-state transitions (`available` → `reserved` → `booked`). |
| `/dashboard/matching` (`app/dashboard/matching/page.tsx`) | 695 | `CANONICAL` / `PRODUCTION-READY` | Explainable AI buyer-to-unit matching workspace with confidence scoring. |
| `/dashboard/tasks` (`app/dashboard/tasks/page.tsx`) | 962 | `CANONICAL` / `PRODUCTION-READY` | Operational task manager with overdue/due-today grouping, SLAs, and tags. Hidden in profile dropdown. |
| `/dashboard/crm/tasks` | 272 | `DUPLICATE` | Redundant task view under `/dashboard/crm`. |
| `/dashboard/revenue-intelligence` | 984 | `CANONICAL` / `PRODUCTION-READY` | Full Build 09 revenue command center (Overview, Funnel, Leakage, Attribution, Outcomes, Team). |
| `/dashboard/analytics` | 205 | `FRAGMENTED` | Secondary analytics dashboard duplicating revenue-intelligence metrics. |
| `/dashboard/analytics/predictions` | 315 | `CANONICAL` | Propensity scoring and conversion likelihood models. |
| `/dashboard/settings` (`app/dashboard/settings/page.tsx`) | 451 | `CANONICAL` / `PRODUCTION-READY` | Broker preferences, agency profile, WhatsApp webhook config, and team settings. |
| `/dashboard/partners` (`app/dashboard/partners/page.tsx`) | 950 | `CANONICAL` / `PRODUCTION-READY` | Channel partner commission tiers, payout schedules, and co-broker visibility. |
| `/dashboard/marketing` (`app/dashboard/marketing/page.tsx`) | 459 | `CANONICAL` / `PRODUCTION-READY` | Campaign management, project launch studio, and landing pages. |
| `/knowledge` (`app/knowledge/page.tsx`) | 1,098 | `CANONICAL` / `PRODUCTION-READY` | RAG documentation grounding, project brochures, and policy search. |
| `/mobile` (`app/mobile/page.tsx`) | 96 | `CANONICAL` / `PRODUCTION-READY` | Mobile view router redirecting to optimized broker workflows. |
| `/portal` (`app/portal/page.tsx`) | 1,604 | `CANONICAL` / `PRODUCTION-READY` | Customer-facing digital deal room and self-service buyer portal. |
| `/admin` (`app/admin/page.tsx`) | 30 | `CANONICAL` | Super admin system monitoring router. |
| `/simulator` (`app/simulator/page.tsx`) | 23 | `CANONICAL` | Real-time WhatsApp inbound/outbound event simulator for testing. |

---

## 3. Component Architecture & Reusability Audit

An audit of `apps/web/src/components` identified the following canonical vs duplicate primitives:

### Design System Primitives (`components/ui/`)
- `Button.tsx`: Canonical styled button with variant tokens (`primary`, `secondary`, `destructive`, `outline`, `ghost`), loading spinners, and size tokens.
- `Card.tsx`: Standard container with border, radius, and header/content sub-components.
- `ConfirmDialog.tsx`: Focus-trapped modal dialog for destructive or irreversible actions (used in Deals).
- `EmptyState.tsx`: Accessible empty state component with icon, title, description, and call-to-action button.
- `ErrorState.tsx` & `ErrorBoundary.tsx`: Categorized error presentation with retry handlers.
- `KpiCard.tsx`: Standardized KPI presentation with trend indicators.
- `StatusBadge.tsx`: Semantic colored status pills with accessible contrast.
- `Skeleton.tsx`: Layout-preserving shimmer skeletons.
- `CommandMenu.tsx`: Keyboard-driven shortcut menu (`Cmd+K`).

### Communication & Copilot Primitives
- `UnifiedTimeline.tsx` (`components/communication/`): Channel-badged timeline for Web, WhatsApp, Email, SMS, and Call logs.
- `AICopilotBar.tsx` (`components/communication/`): Contextual smart-reply generator and draft approver.
- `GlobalAICopilot.tsx` (`components/copilot/`): Enterprise drawer with action previews, confirmation tokens, citations, and conversation history.

### Lead & Customer Primitives (`components/leads/`)
- `LeadDrawer.tsx`: Flyout drawer for fast customer inspection without losing page context.
- `ConversationTimeline.tsx`: Compact message history feed.
- `AIConversationTab.tsx`: Interactive AI Sales Agent session operator.
- `AutonomousSalesTimeline.tsx`: Autopilot event log with human override controls.
- `SalesActionCard.tsx`: Next-Best-Action (NBA) card with reason, evidence, and execution actions.
- `ExtractedDataCard.tsx`: Structured qualification attributes (budget, location, timeline, loan).
- `LeadPropertyMatchesPanel.tsx`: Matched property cards with match score explanations.
- `SourceAttributionCard.tsx`: First-touch and last-touch marketing source attribution.
- `LeadSchedulingTab.tsx`: Integrated appointment and site visit calendar slot selector.

### Dashboard Core Views (`components/dashboard/`)
- `CommandCenterView.tsx`: Operational priorities queue with SLA countdowns, priority filtering, and Start My Day workflow.
- `RevenueAutopilotView.tsx`: Action queue for autonomous commercial operations and demand intelligence.
- `KanbanBoard.tsx`: Drag-and-drop pipeline board with stage totals.
- `LeadTable.tsx`: Full-featured data table with bulk selection, sorting, and inline stage updates.

---

## 4. UI/UX Inconsistencies & Deficiencies

1. **Top Navigation Fragmentation:**
   - The current `PRIMARY_WORKSPACES` list in `DashboardNav.tsx` omits `Inbox`, `Tasks`, `Calendar`, and `Revenue`, while nesting them under `/dashboard/crm` or user profile dropdowns.
   - Requirement 5 mandates top-level navigation converged around:
     `Home`, `Inbox`, `Leads`, `Properties`, `Pipeline`, `Tasks`, `Calendar`, `Revenue`, `AI`, `Settings`.
2. **Visual Palette Disconnect:**
   - The application has two distinct visual personalities:
     - Dashboard & Lists: Warm editorial sand palette (`#F0EDE8`, `#FAF7F2`, `#1A1A1A`, `#D4D0C8`).
     - Lead Detail Page (`/leads/[id]`): Dark futuristic slate palette (`bg-slate-900`, `glass-panel`, `text-slate-400`).
   - Must be unified under the canonical WefyLabs warm editorial design system with dark mode tokens cleanly managed.
3. **Omnichannel Inbox Real Data Wiring:**
   - `InboxPage.tsx` was only fetching AI escalations. It had no active fetch for `/communication/v2/inbox`, leaving the main conversation list empty.
   - We must wire `api.inbox.getInbox()` directly to `/communication/v2/inbox`.
4. **Global Search Scope:**
   - The `CommandMenu` only performed string matching on 6 static links.
   - It must execute real cross-entity search across Leads, Properties, Deals, Tasks, and Conversations via the backend API.
5. **No Universal Calendar Surface:**
   - Calendar appointments and site visits are tracked in `LeadSchedulingTab.tsx` and `CommandCenterView.tsx`, but there was no standalone `/dashboard/calendar` route accessible from the main navigation.

---

## 5. Convergence Blueprint

To satisfy Master Build 10 without breaking backend contracts or duplicating code:

1. **Converge `DashboardNav.tsx`:**
   - Expose the canonical navigation items:
     - **Home** (`/dashboard`)
     - **Inbox** (`/dashboard/inbox`)
     - **Leads** (`/dashboard/leads`)
     - **Properties** (`/dashboard/properties`)
     - **Pipeline** (`/dashboard/deals` & `/dashboard/pipeline`)
     - **Tasks** (`/dashboard/tasks`)
     - **Calendar** (`/dashboard/calendar`)
     - **Revenue** (`/dashboard/revenue-intelligence`)
     - **AI Copilot** (Contextual trigger & `/knowledge`)
     - **Settings** (`/dashboard/settings`)
   - Add global search button (`Cmd+K` indicator) directly in the navigation header.
2. **Harmonize Command Center (`/dashboard/page.tsx`):**
   - Eliminate confusing mode switching.
   - Create a single, calm, authoritative Command Center presenting:
     - **Today's Urgent Layer:** SLA breaches, customer waiting, appointments, pending AI handoffs.
     - **Priorities & WorkItems:** Categorized operational work queue with reason, evidence, and single-click actions.
     - **Active Deals & Pipeline Snapshot:** Velocity and stalled deals.
     - **Revenue at Risk:** Direct link to leakage remediation.
     - **Quick Actions:** Add Lead, Schedule Visit, Search Inventory.
3. **Wire Omnichannel Inbox (`/dashboard/inbox/page.tsx`):**
   - Connect directly to `/communication/v2/inbox`.
   - Implement filters: `All`, `Unread`, `Waiting`, `AI Active`, `Human Takeover`, `Failed`.
   - Real-time channel badges for Web, WhatsApp, Email, SMS, Call.
   - Human takeover controls with clear state indication (`AI ACTIVE`, `AI PAUSED`, `HUMAN ACTIVE`).
4. **Unify Lead Workspace (`/leads/[id]/page.tsx`):**
   - Restyle to the canonical warm design system.
   - Add `DashboardNav` at the top with breadcrumb navigation.
   - Implement the canonical **Lead Header** (Name, Stage, Score, Owner, Source, Intent, Budget, Location, Next Best Action).
   - Implement the **Customer Context Rail** (Intent, Budget, Preferences, Objections, Matched Properties, Tasks, Appointments).
5. **Universal Global Search (`CommandMenu.tsx`):**
   - Wire to `api.crm.search(q)` and `api.search.global(q)`.
   - Group results into Leads, Properties, Opportunities, Tasks, and Navigation Shortcuts.
   - Fully keyboard-navigable (`↑`/`↓`/`Enter`/`Esc`).
6. **Dedicated Calendar Experience (`/dashboard/calendar/page.tsx`):**
   - Converge appointments, site visits, and scheduled follow-ups into a unified calendar view.
7. **Comprehensive Documentation & Test Suite:**
   - Generate all 9 required architecture documents in `docs/`.
   - Build complete E2E test suite in `apps/web/tests/master-build-10/`.
   - Verify zero regressions against backend test suites (Builds 02-09).
