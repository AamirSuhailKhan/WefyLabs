# Phase Frontend Shell Audit: AppShell vs Page-Level Structure

## 1. Inventory of Layouts & Shells

The repository Next.js 15 App Router architecture was evaluated across all route folders:

| Route Path | Layout Level | Current Behavior | Target Remediation |
| :--- | :--- | :--- | :--- |
| `/` (Landing Page) | Root Layout (`app/layout.tsx`) | Public Marketing Shell (`<Navbar />`) | Kept as canonical public shell |
| `/login`, `/register` | Root Layout (`app/layout.tsx`) | Centered Auth Shell | Kept as canonical auth entry shell |
| `/auth/callback` | Root Layout (`app/layout.tsx`) | Session Exchange Shell | Kept as canonical OAuth callback shell |
| `/dashboard/*` (42 routes) | Dashboard Layout (`app/dashboard/layout.tsx`) | Child renders into `DashboardLayoutClient` but `DashboardNav` was missing from layout! | **CANONICAL_APP_SHELL**: Layout shell renders `DashboardNav` once. Pages render pure content. |
| `/leads/[id]` | Root Layout (`app/layout.tsx`) | Standalone page importing `DashboardNav` | Integrated into Canonical App Shell |
| `/knowledge` | Root Layout (`app/layout.tsx`) | Standalone page importing `DashboardNav` | Integrated into Canonical App Shell |
| `/operations` | Root Layout (`app/layout.tsx`) | Standalone page without navbar | Integrated into Canonical App Shell |
| `/settings/*` (standalone) | Root Layout (`app/layout.tsx`) | Legacy settings without shell | Redirect to `/dashboard/settings` or wrap in Canonical App Shell |
| `/portal/*` | Root Layout (`app/layout.tsx`) | End-client property portal | Specialized Client Shell |
| `/mobile` | Root Layout (`app/layout.tsx`) | Mobile voice assistant view | Specialized Mobile Shell |
| `/simulator` | Root Layout (`app/layout.tsx`) | WhatsApp Simulator | Specialized Developer Shell |

---

## 2. Shell Duplication & Failure Root Cause

### The Architectural Flaw
In `apps/web/src/app/dashboard/layout.tsx`:
```tsx
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardLayoutClient>{children}</DashboardLayoutClient>
    </div>
  );
}
```
`DashboardLayoutClient` only verified the auth session and rendered `{children}` without rendering any navigation bar.
Consequently:
1. Every engineer creating a page in `/dashboard/*` had to manually import `<DashboardNav />` and add `<div className="pt-16">` or `<div className="pt-20">`.
2. When engineers forgot to add `<DashboardNav />`, the route had **no navigation bar at all** (e.g. `/dashboard/inbox`, `/dashboard/analytics`, `/dashboard/automations`, `/dashboard/intelligence`).
3. On every route change (e.g., clicking from `/dashboard/leads` to `/dashboard/calendar`), Next.js completely unmounted and remounted `DashboardNav`, triggering re-fetches of billing status and causing visible layout shifts.

### Canonical Shell Architecture Design
```
AppShell (inside DashboardLayoutClient)
├── GlobalNavbar (DashboardNav - rendered ONCE)
│   ├── Logo & Brand Mark
│   ├── Responsive Workspaces (Home, Inbox, Leads, Properties, Pipeline, Tasks, Calendar, Revenue, Settings)
│   ├── Global Search Trigger (⌘K)
│   ├── Global AI Copilot Trigger
│   ├── Trial / Entitlement Status Pill
│   └── Broker Account Profile Menu
├── Optional Secondary Navigation (e.g., LeadCaptureNav in lead-capture routes)
└── MainContent (<main id="main-content" className="w-full"> with standardized PageContainer)
```
Pages no longer manage top navigation, logos, search triggers, or profile menus.
