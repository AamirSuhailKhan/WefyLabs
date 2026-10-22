# Phase 2C.6C Route Data Map & API Contract Inventory

## 1. Executive Summary
This document provides the authoritative mapping of every authenticated product route in the WefyLabs frontend application (`apps/web`) to its underlying backend API endpoints (`apps/api`), database source tables, authorization models, tenant isolation controls, and UX lifecycle states.

Every screen has been verified to ensure:
1. It is wrapped by the canonical authenticated AppShell (`DashboardLayoutClient.tsx`).
2. Its API requests convey authenticated session JWT tokens and server-validated tenant headers.
3. Every displayed metric and collection binds directly to durable PostgreSQL records without synthetic fallbacks.

---

## 2. Comprehensive Authenticated Route Data Matrix

| Route Path | Page Component | Layout Shell | Primary API Endpoints | HTTP Method | DB Source Tables | Tenant Dependency | Auth & RBAC | UX States (Loading / Empty / Error) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/dashboard` | `DashboardPage` | Canonical AppShell | `/command-center/summary`<br>`/leads`<br>`/revenue-intelligence/overview` | GET<br>GET<br>GET | `leads`, `deals`, `site_visits`, `tasks` | Required (`X-WefyLabs-Organization-Id`) | Bearer JWT (Agent, Manager, Owner) | Verified (Skeleton cards / Zero metric cards / Safe error banner) |
| `/dashboard/inbox` | `InboxPage` | Canonical AppShell | `/communication/v2/inbox`<br>`/communication/v2/conversations`<br>`/leads` | GET<br>GET<br>GET | `omnichannel_conversations`, `leads`, `unified_messages` | Required (`X-WefyLabs-Organization-Id`) | Bearer JWT | Verified (Skeleton thread list / "No active conversations" / Retry prompt) |
| `/dashboard/leads` | `LeadsPage` | Canonical AppShell | `/leads`<br>`/leads` (create) | GET<br>POST | `leads`, `identities`, `qualification_profiles` | Required | Bearer JWT | Verified (Pulse skeleton / "No leads found" / Error banner) |
| `/leads/[id]` | `LeadDetailPage` | Standalone Root Shell | `/leads/{id}`<br>`/leads/{id}/notes`<br>`/leads/{id}/tags` | GET<br>POST<br>POST | `leads`, `lead_notes`, `lead_tags` | Required (Server-side ownership verification) | Bearer JWT | Verified (Shimmer loader / 404 Not Found / Toast error) |
| `/dashboard/properties` | `PropertiesPage` | Canonical AppShell | `/property-listings`<br>`/property-listings` (create) | GET<br>POST | `property_listings`, `project_units` | Required (`organization_id` scoped) | Bearer JWT | Verified (Grid skeletons / "No properties found" / Error banner) |
| `/dashboard/matching` | `AIMatchingPage` | Canonical AppShell | `/matching/units`<br>`/matching/score`<br>`/leads` | GET<br>POST<br>GET | `leads`, `property_listings`, `qualification_facts` | Required | Bearer JWT | Verified (Progress pulse / Rich guidance empty state / Alert box) |
| `/dashboard/pipeline` | `PipelinePage` | Canonical AppShell | `/leads`<br>`/leads/{id}/stage` | GET<br>PATCH | `leads`, `deals` | Required | Bearer JWT | Verified (Column skeletons / "No leads in stage" / Drag rollback toast) |
| `/dashboard/tasks` | `TasksPage` | Canonical AppShell | `/tasks`<br>`/tasks` (create/update/delete) | GET<br>POST/PATCH/DELETE | `tasks`, `leads` | Required | Bearer JWT | Verified (Task skeleton / "No tasks found" / Error toast) |
| `/dashboard/calendar` | `CalendarPage` | Canonical AppShell | `/site-visits`<br>`/calendar/events`<br>`/meetings` | GET<br>GET<br>POST | `site_visits`, `meetings`, `leads` | Required | Bearer JWT | Verified (Agenda spinner / "No scheduled events" / Alert retry) |
| `/dashboard/deals` | `DealsPage` | Canonical AppShell | `/deals`<br>`/deals` (create)<br>`/deals/{id}/advance` | GET<br>POST<br>POST | `deals`, `deal_bookings`, `deal_commissions`, `site_visits` | Required | Bearer JWT (Owner/Manager approval for closing) | Verified (Card shimmer / "No deals found" / Modal rollback) |
| `/dashboard/revenue-intelligence` | `RevenueIntelligencePage` | Canonical AppShell | `/revenue-intelligence/overview`<br>`/revenue-intelligence/metrics` | GET<br>GET | `deal_bookings`, `deal_commissions`, `deals` | Required | Bearer JWT (Manager, Owner) | Verified (KPI skeletons / "No revenue data" / Inline alert) |
| `/dashboard/intelligence` | `IntelligenceOSPage` | Canonical AppShell | `/intelligence-os/overview`<br>`/intelligence-os/leakage`<br>`/intelligence-os/recommendations` | GET<br>GET<br>GET | `revenue_leakage_records`, `recommendations`, `pilot_observations` | Required | Bearer JWT | Verified (Tab loader / Zero-state explainers / Retry CTA) |
| `/dashboard/settings` | `SettingsPage` | Canonical AppShell | `/auth/me`<br>`/brokers/me`<br>`/billing/status`<br>`/google-calendar/status` | GET<br>PATCH<br>GET<br>GET | `brokers`, `organizations`, `organization_members` | Required | Bearer JWT (Owner for billing) | Verified (Form loader / Dynamic defaults / Toast error) |
| `/dashboard/autopilot` | `AutopilotPage` | Canonical AppShell | `/autonomous-loop/status`<br>`/autonomous-loop/queue` | GET<br>GET | `pilot_tenants`, `pilot_observations`, `pilot_human_decisions` | Required | Bearer JWT (Stage 1 Shadow Mode: Read-only) | Verified (Status badge pulse / "0 pending autonomous actions" / Error alert) |
| `/dashboard/lead-capture` | `LeadCaptureHubPage` | Canonical AppShell | `/lead-capture/sources`<br>`/lead-capture/stats` | GET<br>GET | `lead_sources`, `lead_acquisition_events` | Required | Bearer JWT | Verified (Stats loader / "No capture sources configured" / Error banner) |
| `/dashboard/lead-capture/sources` | `LeadCaptureSourcesPage` | Canonical AppShell | `/lead-capture/sources` | GET<br>POST | `lead_sources` | Required | Bearer JWT | Verified (Table skeleton / Empty state / Error alert) |
| `/dashboard/lead-capture/forms` | `LeadCaptureFormsPage` | Canonical AppShell | `/lead-capture/sources`<br>`/public/lead-capture/forms/{token}/embed.js` | GET<br>GET | `lead_sources` | Scoped via public token to tenant | Bearer JWT for builder / Public for embed | Verified (Interactive form preview / Code snippet / Copy feedback) |
| `/dashboard/lead-capture/events` | `LeadCaptureEventsPage` | Canonical AppShell | `/lead-capture/events` | GET | `raw_communication_events`, `lead_acquisition_events` | Required | Bearer JWT | Verified (Log loader / "No capture events recorded" / Retry prompt) |
| `/dashboard/lead-capture/import` | `LeadCaptureImportPage` | Canonical AppShell | `/lead-capture/import/preview`<br>`/lead-capture/import/commit` | POST<br>POST | `lead_import_batches`, `lead_import_items`, `leads` | Required | Bearer JWT | Verified (Dropzone progress / Table preview / Error summary modal) |
| `/dashboard/inventory` | `InventoryPage` | Canonical AppShell | `/inventory/units`<br>`/inventory/projects` | GET<br>GET | `property_listings`, `project_units` | Required | Bearer JWT | Verified (Table skeleton / "No inventory records" / Error toast) |
| `/dashboard/follow-ups` | `FollowUpsPage` | Canonical AppShell | `/follow-ups/work-queue`<br>`/follow-ups/policies` | GET<br>GET | `follow_up_policies`, `follow_up_automation_events` | Required | Bearer JWT | Verified (Queue loader / "All follow-ups completed" / Error prompt) |
| `/dashboard/partners` | `PartnersPage` | Canonical AppShell | `/channel-partners`<br>`/channel-partners/commissions` | GET<br>GET | `cp_commissions`, `cp_project_agreements` | Required | Bearer JWT | Verified (Partner table / "No channel partners registered" / Error alert) |
| `/dashboard/marketing` | `MarketingPage` | Canonical AppShell | `/marketing/campaigns`<br>`/marketing/listings` | GET<br>GET | `marketing_campaigns`, `marketing_landing_pages` | Required | Bearer JWT | Verified (Ribbon skeleton / "No active campaigns" / Error alert) |
| `/dashboard/marketing/campaigns` | `CampaignsPage` | Canonical AppShell | `/marketing/campaigns` | GET<br>POST | `marketing_campaigns` | Required | Bearer JWT | Verified (Card skeleton / Empty state / Form toast) |
| `/dashboard/marketing/listings` | `MarketingListingsPage`| Canonical AppShell | `/marketing/listings` | GET<br>POST | `property_listings`, `property_listing_publications` | Required | Bearer JWT | Verified (Table skeleton / Empty state / Error alert) |
| `/dashboard/marketing/launches` | `LaunchesPage` | Canonical AppShell | `/marketing/launches` | GET<br>POST | `project_launches` | Required | Bearer JWT | Verified (4-gate checklist loader / Empty state / Error alert) |
| `/dashboard/marketing/landing-pages` | `LandingPagesPage` | Canonical AppShell | `/marketing/landing-pages` | GET<br>POST | `marketing_landing_pages` | Required | Bearer JWT | Verified (Card grid loader / Empty state / Error alert) |
| `/dashboard/marketing/assets` | `MarketingAssetsPage` | Canonical AppShell | `/marketing/assets` | GET<br>POST | `marketing_assets` | Required | Bearer JWT | Verified (Asset grid / Empty dropzone / Upload error) |
| `/dashboard/analytics` | `AnalyticsPage` | Canonical AppShell | `/analytics/leads`<br>`/predictive/dashboard` | GET<br>GET | `leads`, `forecast_snapshot_records` | Required | Bearer JWT | Verified (Chart pulse / "Insufficient data" / Error banner) |
| `/dashboard/analytics/predictions` | `PredictionsPage` | Canonical AppShell | `/predictive/lead-scores`<br>`/predictive/drift` | GET<br>GET | `prediction_drift_records`, `forecast_snapshot_records` | Required | Bearer JWT | Verified (Score meter skeleton / Real zero state / Error toast) |
| `/dashboard/analytics/executive` | `ExecutiveBiPage` | Canonical AppShell | `/bi/executive-summary` | GET | `deal_bookings`, `deals`, `leads` | Required | Bearer JWT (Owner/Executive) | Verified (KPI loader / "No closed transactions" / Error banner) |
| `/dashboard/automations` | `AutomationsPage` | Canonical AppShell | `/workflows`<br>`/workflows/generate-ai` | GET<br>POST | `workflow_definitions`, `workflow_instances` | Required | Bearer JWT | Verified (Workflow tree loader / "No automations created" / Error toast) |
| `/dashboard/crm` | `CrmOverviewPage` | Canonical AppShell | `/crm/dashboard`<br>`/crm/stats` | GET<br>GET | `leads`, `tasks`, `deals` | Required | Bearer JWT | Verified (Dashboard shimmer / Zero stats / Retry banner) |
| `/dashboard/crm/leads` | `CrmLeadsPage` | Canonical AppShell | `/crm/leads` | GET<br>POST | `leads` | Required | Bearer JWT | Verified (Table skeleton / Empty state / Error alert) |
| `/dashboard/crm/pipeline` | `CrmPipelinePage` | Canonical AppShell | `/crm/pipeline` | GET<br>PATCH | `leads`, `deals` | Required | Bearer JWT | Verified (Kanban shimmer / Empty column / Error toast) |
| `/dashboard/crm/tasks` | `CrmTasksPage` | Canonical AppShell | `/crm/tasks` | GET<br>POST | `tasks` | Required | Bearer JWT | Verified (Task list skeleton / Empty state / Error alert) |
| `/dashboard/crm/activities` | `CrmActivitiesPage` | Canonical AppShell | `/timeline/events` | GET | `timeline_events`, `event_history` | Required | Bearer JWT | Verified (Feed shimmer / "No recent activities" / Error toast) |
| `/dashboard/crm/customers` | `CrmCustomersPage` | Canonical AppShell | `/crm/customers` | GET | `identities`, `leads` | Required | Bearer JWT | Verified (Table skeleton / Empty state / Error alert) |
| `/dashboard/crm/customers/[id]` | `CustomerDetailPage` | Canonical AppShell | `/crm/customers/{id}` | GET | `identities`, `identity_aliases`, `leads` | Required | Bearer JWT | Verified (360 profile loader / 404 / Error banner) |

---

## 3. Data Scoping and Multi-Tenancy Architecture

Every backend endpoint serving authenticated product routes executes under the following multi-tenant contract:
1. **Header Validation**: `X-WefyLabs-Organization-Id` must parse as a valid UUID and match an active `organization_members` entry for `current_broker.id`.
2. **Context Injection**: `get_current_tenant` produces a frozen `TenantContext` containing `organization_id`, `broker_id`, and `role`.
3. **Query Scoping**: SQLAlchemy statements mandate `.where(Model.organization_id == tenant.organization_id)` across all select, update, and delete queries.
4. **Ownership Verification**: Endpoints addressing sub-resources by ID (`/leads/{id}`, `/deals/{id}`, `/property-listings/{id}`) execute combined lookups:
   ```python
   stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == tenant.organization_id)
   ```
   If a resource belongs to another organization, the query returns 0 rows, triggering an immediate 404 (preventing IDOR or tenant leaks).
