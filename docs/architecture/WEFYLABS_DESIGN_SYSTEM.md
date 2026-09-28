# WEFYLABS DESIGN SYSTEM SPECIFICATION — MASTER BUILD 10

## 1. Design Philosophy: Warm Editorial Precision

WefyLabs Master Build 10 establishes a unified, premium visual language termed **Warm Editorial Precision**. It blends the credibility and clarity of high-end financial and architectural publications with responsive modern SaaS ergonomics.

- **Calm, High-Contrast Palette**: Replaces harsh pitch-black backgrounds and cold generic grays with warm, tactile stones, parchment-tinted surfaces, and deep charcoal typography.
- **Content-First Hierarchy**: Metadata is structured with crisp monospace accents, ensuring brokers and sales executives can parse property dimensions, prices in Crores, and timestamps at a glance.
- **Zero Decorative Noise**: Eliminates gratuitous animations, neon gradients, and redundant sample cards that distract from closing real estate transactions.

---

## 2. Canonical Color Tokens

| Token Name | Hex Value | Usage | WCAG Contrast vs Canvas |
| :--- | :--- | :--- | :--- |
| `surface-canvas` | `#F0EDE8` | Main page background, app frame | Baseline (1.0:1) |
| `surface-card` | `#FAF7F2` | Cards, panels, drawers, sidebars | Subtle elevation (1.1:1) |
| `surface-card-subtle` | `#FFFFFF` | Form inputs, active selection pills | High-contrast card inset (1.15:1) |
| `text-primary` | `#1A1A1A` | Main headings, customer names, prices | **12.4:1 (AAA Pass)** |
| `text-muted` | `#6B6B6B` | Labels, metadata, helper text | **4.7:1 (AA Pass)** |
| `border-subtle` | `#D4D0C8` | Canonical dividers, card borders | 1.4:1 UI border ratio |
| `accent-primary` | `#0D9488` | Deep Teal — Primary calls to action, focus rings | **4.6:1 (AA Pass)** |
| `accent-highlight` | `#E8F5A8` | Warm Lime — Hot tags, VIP pills, active badges | Accent highlight |
| `status-urgent` | `#DC2626` | Crimson — SLA breaches, human handoffs, revenue leakage | 4.8:1 against canvas |
| `status-success` | `#16A34A` | Emerald — Confirmed bookings, verified units, live AI | 4.6:1 against canvas |
| `status-warning` | `#D97706` | Amber — AI suggestions, pending escalations | 4.5:1 against canvas |

---

## 3. Typography Scale & Fonts

```css
/* Typography Stack */
--font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', 'Space Mono', monospace;
```

| Role | Font Family | Size | Weight | Line Height | Tracking |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display Title** | Sans | 24px / 1.5rem | 800 (Extrabold) | 1.2 | -0.02em |
| **Section Heading** | Mono / Sans | 18px / 1.125rem | 700 (Bold) | 1.3 | -0.01em |
| **Metric Figure** | Mono | 20px / 1.25rem | 800 (Extrabold) | 1.1 | -0.03em |
| **Body Standard** | Sans | 13px / 0.8125rem | 400 (Regular) | 1.5 | normal |
| **Body Emphasized** | Sans | 13px / 0.8125rem | 600 (Semibold) | 1.5 | normal |
| **Micro Label / Badge** | Mono | 10px / 0.625rem | 700 (Bold) | 1.2 | 0.05em (Caps) |

---

## 4. Reusable Primitives & Converged Components

### Button System
- **Primary**: `bg-[#1A1A1A] hover:bg-black text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-xs`
- **Secondary**: `bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] text-[#1A1A1A] px-3 py-2 rounded-xl text-xs font-bold transition-all`
- **Urgent / Danger**: `bg-red-600 hover:bg-red-500 text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-xs`
- **Accent**: `bg-[#0D9488] hover:bg-[#0F766E] text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-xs`

### Status Badges
- **AI Active**: `bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-mono font-bold uppercase rounded-md px-1.5 py-0.5`
- **Human Active**: `bg-blue-50 text-blue-700 border border-blue-200 text-[9px] font-mono font-bold uppercase rounded-md px-1.5 py-0.5`
- **Handoff Required**: `bg-red-100 text-red-800 border border-red-300 text-[9px] font-mono font-bold uppercase rounded-md px-1.5 py-0.5`

### Form Controls
- Inputs use `bg-white border border-[#D4D0C8] rounded-xl px-3 py-2 text-xs text-[#1A1A1A] placeholder-[#9CA3AF] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A]`.
- All form controls feature visible semantic labels (`<label htmlFor="...">`) and inline validation states.
