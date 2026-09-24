# WEFYLABS_PART22_BASELINE.md

## 1. Project Context
**Part 22: WEFYLABS UNIFIED PRODUCT EXPERIENCE OS**

WefyLabs has evolved rapidly from Lead OS to 21 distinct modules. While the backend architecture is robust, the frontend has accumulated inconsistencies in typography, layout, spacing, and design tokens across different domains (CRM, Deals, Marketing, Inventory, Analytics). 

The goal of Part 22 is to implement a product-wide frontend consolidation. We will establish a unified Design System, strict Information Architecture, and a cohesive Global Shell that spans the entire platform.

## 2. Page & Layout Inventory

The `apps/web/src/app` directory currently contains 12 top-level domains:
- `/admin`
- `/auth`
- `/dashboard` (Core Command Center with 19 sub-domains)
- `/knowledge`
- `/leads`
- `/login`
- `/mobile`
- `/onboarding`
- `/portal` (Customer Portal - Part 21)
- `/register`
- `/settings`
- `/simulator`

### Dashboard Sub-domains (The Core Experience):
- `/dashboard/analytics`, `/dashboard/automations`, `/dashboard/autopilot`
- `/dashboard/crm`, `/dashboard/deals`, `/dashboard/follow-ups`, `/dashboard/inbox`
- `/dashboard/inventory`, `/dashboard/lead-capture`, `/dashboard/leads`
- `/dashboard/marketing`, `/dashboard/matching`, `/dashboard/partners`
- `/dashboard/performance`, `/dashboard/pipeline`, `/dashboard/properties`
- `/dashboard/revenue-intelligence`, `/dashboard/settings`, `/dashboard/tasks`

## 3. The "UI Bug Register" & Inconsistencies

### A. Design Tokens & Theming
- **Colors**: `globals.css` and `tailwind.config.ts` have hardcoded `#F0EDE8` backgrounds and a mix of beige/lime/ink. Some parts use `brand-primary` (#2C4BFB) while others default to neutral grays.
- **Typography**: Inter and Geist Mono/JetBrains Mono are applied inconsistently. Monospace is often forced on headlines arbitrarily.

### B. Global Shell & Navigation
- Navbar and Sidebar layout patterns vary across `/dashboard` modules. Some have full-width layouts, others are constrained.
- Deep navigation hierarchies cause context loss when switching modules.

### C. Components & Empty States
- Tables, Cards, Inputs, and Modals have disparate padding, border-radius (`4xl`, `3xl`, `2xl`), and hover effects.
- Empty, Error, and Loading states are not standardized. 

### D. Responsive & Accessibility
- Several complex tables and kanban boards break on mobile viewports.
- ARIA labels and focus rings are inconsistently applied across custom UI elements.

## 4. 11-Wave Migration Plan

This consolidation will be executed in 11 waves:

1.  **Global Shell & Navigation**: Standardize the Sidebar and Top Navbar.
2.  **Design System Foundation**: Solidify colors, typography, spacing tokens.
3.  **Core Components Library**: Unify buttons, inputs, modals, and badges.
4.  **Tables & Data Grids**: Standardize list views and pagination.
5.  **Kanban & Drag-and-Drop**: Unify Deal/Lead pipeline views.
6.  **Forms & Modals**: Consolidate creation and edit workflows.
7.  **Empty & Error States**: Standardize fallbacks across all 21 modules.
8.  **Dashboards & KPI Cards**: Unified analytics card layouts.
9.  **Mobile & Responsive**: Guarantee usability on small viewports.
10. **Accessibility & QA**: Focus management, ARIA roles, and high contrast.
11. **Final Polish**: Micro-interactions, transitions, and performance tuning.

## 5. Next Steps
Execute Wave 1 and Wave 2: Standardizing the layout shell and creating the core unified token system in `globals.css` and `tailwind.config.ts`.
