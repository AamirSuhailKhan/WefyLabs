# WEFYLABS GLOBAL SEARCH & COMMAND PALETTE ARCHITECTURE

## 1. Overview & Objectives

Universal Search in WefyLabs Master Build 10 enables brokers, sales agents, and managers to query the entire commercial platform from any surface in under 100 milliseconds without losing page context.

The search architecture unifies:
1. **Customer & Lead Records**: Name, phone, email, micro-market, qualification score.
2. **Properties & Inventory**: Project name, unit number, tower, BHK, price range, city, availability.
3. **Deals & Opportunities**: Customer deal, commercial milestone, pipeline stage, expected booking value.
4. **Tasks & Work Items**: Callbacks, site visit follow-ups, document verifications, SLA alerts.

---

## 2. Keyboard-First Interaction & Chord System

WefyLabs implements an ergonomic two-tier keyboard navigation pattern:

### Tier 1: Global Triggers
- `Cmd + K` (Mac) or `Ctrl + K` (Windows / Linux): Opens Universal Command Palette.
- `/` (Single key when no input/textarea is focused): Instant focus into command palette.
- `Escape`: Closes palette, clears query, restores focus to the previously active element.
- `ArrowDown` / `ArrowUp`: Navigates through categorized result lists.
- `Enter`: Selects and executes navigation or quick action.

### Tier 2: Two-Key Chord Shortcuts
When the command palette is closed and user is not inside an editable form, typing two consecutive keys navigates immediately:
- `g + h` → **Home** (`/dashboard`)
- `g + i` → **Omnichannel Inbox** (`/dashboard/inbox`)
- `g + l` → **Leads Workspace** (`/dashboard/leads`)
- `g + p` → **Pipeline Board** (`/dashboard/pipeline`)
- `g + t` → **Task Center** (`/dashboard/tasks`)
- `g + c` → **Calendar & Site Visits** (`/dashboard/calendar`)
- `g + r` → **Revenue Intelligence** (`/dashboard/revenue-intelligence`)

---

## 3. Query Execution & Tenant Isolation

Every query issued through `api.crm.search(q)` or `api.search.global(q)` strictly enforces multi-tenant boundary constraints:
```typescript
// Client-side query dispatch
const res = await api.crm.search(query.trim());
// Automatically carries header:
// headers['X-WefyLabs-Organization-Id'] = orgId;
```

Backend database queries join against the authenticated user's `organization_id`. Cross-tenant search leaks are mathematically impossible.

---

## 4. Result Categorization & Semantic Icons

Search results are grouped into distinct semantic buckets with entity counts:
- `Leads (N)`: User icon, phone number, qualification badge, current pipeline stage.
- `Properties (N)`: Building icon, project name, location, price in Cr, availability badge.
- `Deals (N)`: Briefcase icon, deal title, value in INR, stage pill.
- `Tasks (N)`: CheckSquare icon, task title, due status.
