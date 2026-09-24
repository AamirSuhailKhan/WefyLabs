# WEFYLABS INFORMATION ARCHITECTURE (IA) SPECIFICATION
## Navigation, Workspaces, and Module Groupings for WefyLabs

---

## 1. Information Architecture Problem Statement

The previous navigation model presented **14 flat top-level links** across the viewport:
```
[Dashboard] [CRM] [Deals] [Inventory] [Marketing] [Partners] [Revenue Intel] [Predictive AI] [Leads] [Lead Capture] [Pipeline] [Tasks] [Knowledge] [Settings]
```

### Critical Flaws:
1. **Cognitive Overload**: Users were confronted with 14 equal-weight options with no grouping.
2. **Duplication**: `Leads`, `Pipeline`, and `Tasks` existed both in the top nav and as nested routes under `/dashboard/crm/*`.
3. **Viewport Breakage**: At 1024px–1440px desktop resolutions, links wrapped into multiple jagged rows, pushing down page content.
4. **Engineering Architecture Leaks**: Features were presented by backend engineering sprint rather than user workflow.

---

## 2. Unified Information Architecture (User Workflow Grouping)

The redesigned WefyLabs Information Architecture arranges the platform into **8 logical workspaces**, with clean sub-navigation where appropriate:

```
WEFYLABS OS
├── 1. HOME
│   ├── Command Center (`/dashboard`)
│   └── Revenue Autopilot View
│
├── 2. CRM
│   ├── All Leads (`/dashboard/leads`)
│   ├── Visual Pipeline (`/dashboard/pipeline`)
│   ├── Lead Capture & Forms (`/dashboard/lead-capture`)
│   └── Activity Stream (`/dashboard/crm/activities`)
│
├── 3. SALES
│   ├── Deal Matrix (`/dashboard/deals`)
│   ├── Negotiations & Offers
│   ├── Unit Reservations & Bookings
│   └── Closing & Commission
│
├── 4. INVENTORY (Supply OS)
│   ├── Project & Unit Matrix (`/dashboard/inventory`)
│   ├── Inventory 360 Drawer
│   ├── Pricing Books
│   └── Unit Matching (`/dashboard/matching`)
│
├── 5. MARKETING (Demand OS)
│   ├── Campaign Manager (`/dashboard/marketing`)
│   ├── Listing Studio (`/dashboard/marketing/listings`)
│   ├── Project Launches (`/dashboard/marketing/launches`)
│   └── Landing Pages & Tracking (`/dashboard/marketing/landing-pages`)
│
├── 6. PARTNERS
│   ├── Broker Directory (`/dashboard/partners`)
│   ├── KYC & Accreditations
│   ├── Project Commercial Agreements
│   └── Co-Broking Commission Ledger
│
├── 7. INTELLIGENCE
│   ├── Revenue Intelligence (`/dashboard/revenue-intelligence`)
│   └── Predictive AI & Target Catalog (`/dashboard/analytics/predictions`)
│
└── 8. OPERATIONS
    ├── Tasks & Reminders (`/dashboard/tasks`)
    ├── Knowledge Base (`/knowledge`)
    └── Settings & Team (`/dashboard/settings`)
```

---

## 3. Navigation Component Architecture

### 3.1 Primary Navigation Bar
- Fixed at top (`h-16`, `bg-[rgba(240,237,232,0.92)]`, `backdrop-blur-md`, `border-b border-[#D4D0C8]`).
- Left: WefyLabs Logo + Workspace Breadcrumb / Context.
- Center: **Primary Workspaces** (max 7 primary tabs: `Home`, `CRM`, `Deals`, `Inventory`, `Marketing`, `Partners`, `Intelligence`).
- Right: Entitlement Badge (clean, unobtrusive), Quick Actions (`+ Add Lead`), Global Search (`Cmd+K`), User Profile Menu.

### 3.2 Secondary Context Bar (Where Needed)
For complex workspaces (such as CRM or Marketing), a clean secondary horizontal tab bar appears directly under the page header:
- **Marketing OS**: `[Campaigns]` `[Listing Studio]` `[Project Launches]` `[Landing Pages]`
- **CRM OS**: `[Leads]` `[Pipeline]` `[Lead Capture]` `[Activities]`
- **Intelligence OS**: `[Revenue Funnel]` `[Predictive AI Models]` `[Quality & Drift]`

### 3.3 Mobile & Responsive Navigation
- Breakpoints:
  - `< 1024px`: Primary nav collapses into a slide-over mobile drawer with grouped accordion sections.
  - No horizontal scrolling of critical navigation elements.
  - Accessible touch targets: minimum `44px` height on interactive items.
