# Phase Frontend Design System: WefyLabs Semantic Tokens & Primitives

## 1. Design Token System

WefyLabs uses a disciplined, restrained color and surface system:

```css
:root {
  /* Surfaces & Backgrounds */
  --bg-primary: #F0EDE8;           /* Warm cream application canvas */
  --bg-surface: #FAF7F2;           /* Primary card surface */
  --bg-surface-hover: #F5F0EB;     /* Interactive card hover */
  --bg-surface-elevated: #FFFFFF;  /* Modals, popovers, dropdowns */
  
  /* Borders */
  --border-subtle: #E5E1DA;        /* Divider lines */
  --border-default: #D4D0C8;       /* Card and input borders */
  --border-strong: #A8A29E;        /* Active focus / highlighted boundaries */

  /* Typography / Foregrounds */
  --text-primary: #1A1A1A;         /* Primary headings & dark body text */
  --text-secondary: #4A4A4A;       /* Secondary details & descriptions */
  --text-muted: #6B6B6B;           /* Timestamps, labels, meta information */
  --text-disabled: #9CA3AF;        /* Inactive states */

  /* Brand & Accents */
  --brand-blue: #2C4BFB;           /* WefyLabs signature electric blue */
  --brand-blue-hover: #1D3BE6;     /* Brand button hover */
  --brand-lime: #E8F5A8;           /* Primary action button (btn-lime) */
  --brand-lime-hover: #D4E894;     /* Lime hover */
  
  /* Semantic Statuses */
  --status-success: #10B981;       /* Emerald: Hot leads, healthy, high confidence */
  --status-success-bg: #ECFDF5;
  --status-warning: #F59E0B;       /* Amber: Medium confidence, follow-up due */
  --status-warning-bg: #FFFBEB;
  --status-danger: #EF4444;        /* Rose: Expired trial, critical escalation */
  --status-danger-bg: #FEF2F2;
  --status-ai: #0D9488;            /* Teal: AI Copilot, autonomous signals, intelligence */
  --status-ai-bg: #F0FDFA;
}
```

---

## 2. Typography Hierarchy

| Token | Family | Weight | Size | Letter Spacing | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `display-1` | Geist Mono / JetBrains Mono | 800 (Black) | 28px - 32px | -0.02em | Main Page Titles |
| `heading-2` | Geist Mono / JetBrains Mono | 700 (Bold) | 20px - 24px | -0.01em | Section Headings |
| `heading-3` | Inter | 600 (Semibold) | 16px - 18px | Normal | Card Titles |
| `body-sm` | Inter | 400 - 500 | 13px - 14px | Normal | Standard body text |
| `label-mono` | JetBrains Mono | 700 | 10px - 11px | +0.05em (Upper) | Category Badges & Pills |
| `metric-val` | Geist Mono | 800 | 24px - 32px | -0.02em | KPI Numbers |

---

## 3. Component Primitive Library

1. `PageContainer`: Wraps page content with max-w 1440px, standardized gutters, and vertical spacing.
2. `PageHeader`: Standard header with badge pill, title, subtitle, and primary actions slot.
3. `Card`: Consistent rounded-2xl cards with warm borders and optional elevated/hover variants.
4. `Button`: Normalized height, radii, hover states, and keyboard focus outlines.
5. `EmptyState`: Contextual illustration/icon, clear explanation, and primary action button.
6. `Skeletons`: Smooth pulse skeleton placeholders for cards, tables, and dashboards.
7. `ErrorState`: Friendly inline, block, and retry error handlers.
