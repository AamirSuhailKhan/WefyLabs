# WEFYLABS UI BUG REGISTER — PART 21
## Prioritized Defect Tracking for Unified Product Experience OS

---

## 1. Bug Summary by Severity

| Severity | Count | Status | Definition |
| :--- | :---: | :---: | :--- |
| **P0 (Critical)** | 4 | **OPEN** | Broken navigation, trapping the user, layout breaking shift, or critical interaction crash. |
| **P1 (High)** | 6 | **OPEN** | Disconnected theme/dark mode standalone page, non-functional/unconnected route, raw browser prompts. |
| **P2 (Medium)** | 8 | **OPEN** | Navigation wrapping at standard desktop widths, visual inconsistency, sprint labels in user UI, duplicate CTAs. |
| **P3 (Cosmetic)** | 5 | **OPEN** | Minor padding variance, inconsistent border radius, icon stroke mismatch. |

---

## 2. Defect Register

| Bug ID | Page / Route | Severity | Description | Root Cause | Status | Resolution Plan |
| :--- | :--- | :---: | :--- | :--- | :---: | :--- |
| **BUG-21-001** | `/dashboard/analytics/predictions` | **P0** | Page has no navigation header or sidebar; user is trapped with no way to return to Dashboard. | Page component does not import or render `<DashboardNav />` or use a shared layout shell. | **OPEN** | Migrate to global layout shell in `DashboardLayoutClient` so navigation is guaranteed on all routes. |
| **BUG-21-002** | `/dashboard/marketing/*` | **P0** | Marketing sub-pages (`listings`, `launches`, `campaigns`) have no global navigation; user must click browser back. | Sub-pages were implemented as standalone views without `DashboardNav`. | **OPEN** | Embed in global shell; rebuild header and navigation. |
| **BUG-21-003** | Global (`*`) | **P0** | When trial expires, full-width red banner pushes fixed navbar by `mt-8`, creating layout jitter, clipping, and overlay. | Ad-hoc inline CSS condition in `DashboardNav.tsx` shifting fixed element. | **OPEN** | Implement unified Entitlement banner inside layout flow without fixed coordinate offsets. |
| **BUG-21-004** | Global (`*`) | **P0** | Global AI Copilot floating button and modal (`z-50`) covers primary CTAs, modal submit buttons, and table pagination. | Hardcoded `fixed bottom-6 right-6` with large static dimensions and no responsive drawer collapse. | **OPEN** | Add responsive positioning, z-index hierarchy, backdrop collapse, and workspace docking. |
| **BUG-21-005** | `/dashboard/marketing` | **P1** | Visual disconnect: Marketing OS renders pitch black (`#080c14`) with glowing violet blurs inside a warm beige SaaS application. | Marketing was styled using an uncoordinated dark theme palette. | **OPEN** | Completely rebuild Marketing OS presentation using canonical WefyLabs warm tokens (`#F0EDE8`, `#FAF7F2`, `#D4D0C8`). |
| **BUG-21-006** | `/dashboard/deals` | **P1** | Deal stage progression uses browser-native `window.prompt()` and `window.alert()`. | Stage transition handler calls `prompt()` for transition reason. | **OPEN** | Replace with canonical `ConfirmDialog` / `StageAdvanceModal` component. |
| **BUG-21-007** | `/dashboard/inventory` & `/partners` | **P1** | Inconsistent dark mode classes (`dark:bg-[#0E0F12]`, `dark:text-zinc-100`) without global dark mode toggling. | Arbitrary dark classes copied from Tailwind templates. | **OPEN** | Normalize to canonical WefyLabs tokens and theme provider. |
| **BUG-21-008** | `/dashboard/marketing/landing-pages` | **P1** | Route directory exists but returns 404 because `page.tsx` was missing. | Incomplete folder created in previous sprint. | **OPEN** | Create canonical landing pages builder page. |
| **BUG-21-009** | `/dashboard/marketing/assets` | **P1** | Route directory exists but returns 404 because `page.tsx` was missing. | Incomplete folder created in previous sprint. | **OPEN** | Create canonical marketing asset library page. |
| **BUG-21-010** | Multiple Pages | **P1** | Internal sprint labels (`"Part 11 Enterprise Analytics"`, `"Part 16 Predictive Intelligence"`) exposed to customer. | Developer sprint tags hardcoded into page titles. | **OPEN** | Replace with clean real estate domain terminology. |
| **BUG-21-011** | Global Navigation | **P2** | 14 top-level horizontal navigation links wrap and collide between 1024px and 1440px viewports. | Flat horizontal nav array without information architecture hierarchy. | **OPEN** | Implement grouped information architecture with professional workspace selector or sidebar. |
| **BUG-21-012** | Global Navigation | **P2** | `<DashboardNav />` is manually imported and rendered in 40+ page files with differing margins. | Absence of layout-level shell enforcement. | **OPEN** | Move navigation directly into `apps/web/src/app/dashboard/layout.tsx` / `DashboardLayoutClient.tsx`. |
| **BUG-21-013** | `/dashboard/marketing` | **P2** | Duplicate "New Campaign" buttons in the same viewport. | Header and empty state both render identical primary CTAs with different styling. | **OPEN** | Consolidate to single primary header CTA and contextual empty state. |
| **BUG-21-014** | `/dashboard` vs `/dashboard/crm/*` | **P2** | Pipeline, Leads, and Tasks duplicated across both root `/dashboard` and `/dashboard/crm/*`. | Fragmented module development. | **OPEN** | Consolidate navigation links and create unified canonical routes with proper redirects. |
| **BUG-21-015** | `/dashboard/settings` | **P2** | Duplicate trial expiration pill and banner shown simultaneously. | Redundant state rendering. | **OPEN** | Centralize through `useEntitlement` hook. |
| **BUG-21-016** | Multiple Pages | **P2** | Zero states display raw "0" without descriptive empty state context or action. | Missing empty state component usage. | **OPEN** | Implement unified `EmptyState` component across all tables and lists. |
| **BUG-21-017** | Multiple Pages | **P2** | Unstandardized loading states (some use spinners, some blank, some skeletons). | Lack of standard skeleton components. | **OPEN** | Deploy `PageSkeleton`, `TableSkeleton`, and `KpiSkeleton`. |
| **BUG-21-018** | Multiple Pages | **P2** | Form buttons do not display loading state or prevent double submission during mutations. | Missing pending mutation guards on action buttons. | **OPEN** | Standardize `Button` component with `isLoading` and `disabled` states. |
| **BUG-21-019** | Multiple Pages | **P3** | Inconsistent button corner radius (`rounded-full`, `rounded-xl`, `rounded-lg`). | Ad-hoc Tailwind utility classes. | **OPEN** | Standardize on design tokens (`rounded-xl` for buttons, `rounded-2xl` for cards). |
| **BUG-21-020** | Multiple Pages | **P3** | Inconsistent typography: some headers use monospace, others sans-serif with varied font sizes. | Ad-hoc font definitions. | **OPEN** | Enforce unified typography scale via `PageHeader` and design tokens. |
| **BUG-21-021** | Global Navigation | **P3** | Inactive nav tabs have varying hover states across pages. | Dispersed nav implementations. | **OPEN** | Single source of truth in unified navigation component. |
| **BUG-21-022** | Multiple Pages | **P3** | Table padding varies between 8px and 24px across CRM, Deals, Inventory, and Leads. | Unstandardized table layouts. | **OPEN** | Standardize table tokens and header styling. |
| **BUG-21-023** | Multiple Pages | **P3** | Status badge colors differ for same semantic states (e.g. green for available vs active). | Differing badge maps across files. | **OPEN** | Standardize canonical `StatusBadge` component. |
