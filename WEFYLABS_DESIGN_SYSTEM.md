# WEFYLABS DESIGN SYSTEM SPECIFICATION
## The Unified Design Language for the AI-Native Real Estate Revenue OS
### Canonical Architecture: Warm Editorial Enterprise SaaS

---

## 1. Core Visual Principles

1. **One Platform, One Voice**:
   Every module — from Lead Capture and CRM to Deals, Inventory, Marketing, and Revenue Intelligence — belongs to a single cohesive design system. No module may independently adopt a dark standalone theme or alien color palette.

2. **Warm Editorial Elegance**:
   WefyLabs combines high-precision financial software with warm editorial typography and restrained micro-accents. The palette avoids cold sterile grays in favor of warm bones, rich inks, and subtle lime highlights.

3. **High Information Density with Visual Calm**:
   Dashboards prioritize clarity: "What is important?", "What needs action?", and "What can I do?". Blank unexplained voids and decorative non-functional clutter are eliminated.

---

## 2. Design Tokens

### 2.1 Color Palette
```css
:root {
  /* Surfaces & Backgrounds */
  --bg-app: #F0EDE8;            /* Main application canvas (warm bone) */
  --bg-surface: #FAF7F2;        /* Primary card & panel surface */
  --bg-elevated: #FFFFFF;       /* Elevated modals, dropdowns, popovers */
  --bg-subtle: #F5F0EB;         /* Subtle table stripes & input backgrounds */
  --bg-hover: #EBE6E0;          /* Interactive hover state */

  /* Text & Inks */
  --ink-primary: #1A1A1A;       /* Primary headlines, body text, data values */
  --ink-secondary: #4A4A4A;     /* Field labels, secondary descriptions */
  --ink-muted: #6B6B6B;         /* Timestamps, helper text, captions */
  --ink-inverse: #FFFFFF;       /* Text on dark buttons or badges */

  /* Borders & Dividers */
  --border-default: #D4D0C8;    /* Standard card, table, and input borders */
  --border-subtle: #E5E1DA;     /* Inner card dividers */
  --border-focus: #1A1A1A;      /* Active focus outlines */

  /* Accents & Brand */
  --accent-lime: #E8F5A8;        /* Signature highlighter accent */
  --accent-lime-hover: #D4E894;  /* Hover state for lime CTAs */
  --brand-primary: #2C4BFB;     /* Primary brand electric blue */
  --brand-primary-hover: #1D3BE6;
  --brand-primary-subtle: #EFF3FF;

  /* Semantic Feedback */
  --success-bg: #ECFDF5;
  --success-text: #065F46;
  --success-border: #A7F3D0;

  --warning-bg: #FFFBEB;
  --warning-text: #92400E;
  --warning-border: #FDE68A;

  --danger-bg: #FEF2F2;
  --danger-text: #991B1B;
  --danger-border: #FECACA;

  --info-bg: #EFF6FF;
  --info-text: #1E40AF;
  --info-border: #BFDBFE;
}
```

### 2.2 Typography Scale
- **Display / Headers (Brand & Numerics)**: `font-family: 'JetBrains Mono', 'Geist Mono', monospace;`
  - Page Title (`Display`): `24px` to `28px` (desktop), weight `700`, line-height `1.2`, tracking `-0.02em`
  - Section Header (`H2`): `18px` to `20px`, weight `700`, line-height `1.3`
  - Card Header (`H3`): `14px` to `16px`, weight `600`, line-height `1.4`
  - KPI Metrics (`Numeric`): `28px` to `36px`, weight `800`, tabular numbers
- **Body & Labels**: `font-family: 'Inter', system-ui, sans-serif;`
  - Body Normal: `14px`, weight `400` / `500`, line-height `1.5`
  - Body Small: `13px`, weight `400` / `500`, line-height `1.4`
  - Caption / Helper: `11px` to `12px`, weight `500`, line-height `1.4`
  - Button Text: `13px`, weight `600`, letter-spacing `0.01em`

### 2.3 Spacing & Radius
- **Border Radius**:
  - `rounded-lg`: `8px` (Inputs, sub-controls, inner chips)
  - `rounded-xl`: `12px` (Buttons, table cards, dropdown menus)
  - `rounded-2xl`: `16px` (Standard cards, stat containers)
  - `rounded-3xl`: `24px` (Major panels, modals, drawers)
  - `rounded-full`: `9999px` (Badges, pills, avatar rings)
- **Spacing**:
  - Container padding: `px-4 sm:px-6 lg:px-8`
  - Section gap: `space-y-6` or `space-y-8`
  - Card padding: `p-5 sm:p-6`
  - Table row padding: `py-3 px-4`

---

## 3. Component Standards

### 3.1 Buttons
| Variant | Background | Border | Text | Hover State | Loading State |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary** | `#1A1A1A` | None | `#FFFFFF` | `#000000` | Spinner + "Saving..." |
| **Accent (Lime)** | `#E8F5A8` | `#D4D0C8` | `#1A1A1A` | `#D4E894` | Spinner + "Processing..." |
| **Secondary** | `#FAF7F2` | `#D4D0C8` | `#1A1A1A` | `#F0EDE8` | Spinner |
| **Outline** | Transparent | `#1A1A1A` | `#1A1A1A` | `#1A1A1A` / White text | Spinner |
| **Danger** | `#FEF2F2` | `#FECACA` | `#991B1B` | `#FEE2E2` | Spinner + "Deleting..." |
| **Ghost** | Transparent | Transparent | `#6B6B6B` | `#F0EDE8` / `#1A1A1A` text | Spinner |

### 3.2 Real Estate Status Badges
| Domain State | Semantic Color | Visual Appearance |
| :--- | :--- | :--- |
| `AVAILABLE` / `ACTIVE` / `PUBLISHED` | Success Green | Green pill with solid green dot |
| `RESERVED` / `IN_REVIEW` / `PENDING` | Warning Amber | Amber pill with pulsing dot |
| `BOOKED` / `SCHEDULED` / `APPROVED` | Brand Blue | Electric blue pill with solid dot |
| `SOLD` / `CLOSED_WON` | Deep Emerald | Dark green pill |
| `BLOCKED` / `CANCELLED` / `CLOSED_LOST` | Danger Rose | Muted rose/red pill |
| `DRAFT` / `PAUSED` / `STALE` | Neutral Gray | Warm bone/gray pill |

### 3.3 Cards & KPI Metrics
- Every KPI card displays:
  - Metric Label (`text-xs font-semibold uppercase text-ink-muted`)
  - Icon in subtle rounded container
  - Large Metric Value (`font-mono text-2xl sm:text-3xl font-bold text-ink-primary`)
  - Sub-context or trend (`text-xs text-ink-secondary`)
  - Never fabricated or fake trend data

### 3.4 Tables
- Sticky Header with `#FAF7F2` background and `#D4D0C8` border
- Clean typography: column headers in `text-[11px] font-bold uppercase tracking-wider text-ink-muted`
- Empty state: centered icon, title, description, and action button
- Loading state: animated bone-colored skeletons
- Mobile: horizontal scroll with sticky primary identifier column

### 3.5 Modals & Confirmation Dialogs
- Backdrop: `rgba(26, 26, 26, 0.4)` with `backdrop-blur-sm`
- Container: `#FFFFFF` or `#FAF7F2`, `border border-[#D4D0C8]`, `rounded-2xl`
- Standard header with close button (`X`)
- Actions in sticky footer: Cancel (Secondary) + Confirm (Primary/Danger)
- Standardized `ConfirmDialog` replaces raw browser `alert()` and `prompt()`
