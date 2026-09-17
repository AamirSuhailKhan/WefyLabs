# WefyLabs Official Brand System & Design Guide
============================================================
**Brand Name**: WefyLabs  
**Primary Domain**: `wefylabs.com`  
**Web Application**: `https://app.wefylabs.com`  
**REST API**: `https://api.wefylabs.com`  
**Version**: 1.0.0 — Production Standard  
**Date**: September 17, 2026  

---

## 1. Brand Identity & Principles

WefyLabs is an autonomous real estate AI CRM company. The brand identity conveys:
- **Technological Precision**: Autonomous AI qualification, deterministic matching, and real-time synchronization.
- **Trust & Reliability**: Enterprise grade, secure multi-tenancy, zero customer data training.
- **Modern Simplicity**: Minimalist, uncluttered visual hierarchy, intuitive operational speed.

### Core Geometry
The WefyLabs brand mark represents a continuous 3D ribbon loop / Möbius strip forming a dynamic "W" and infinity mark.
- **Left Loop**: Broad, rounded petal with a smooth silver-to-slate gradient.
- **Center Crossing**: Deep slate-indigo twist passing underneath and ascending to an illuminated highlight.
- **Right Loop**: Slender, energetic loop highlighted with vibrant cobalt/electric blue on the rim and bright cyan/azure along the interior curve.

> **Absolute Rule**: Never stretch, compress, rotate, invert, mirror, or add artificial drop shadows or 3D extrusions to the mark.

---

## 2. Color System & Tokens

### 2.1 Brand Color Palette

| Token Name | Hex Value | RGB | Description / Usage |
| :--- | :--- | :--- | :--- |
| `--brand-primary` | `#2C4BFB` | `rgb(44, 75, 251)` | Vibrant Cobalt Blue (Right loop highlight, primary brand accent) |
| `--brand-primary-hover` | `#1D3BE6` | `rgb(29, 59, 230)` | Active/Hover state for brand actions |
| `--brand-primary-light` | `#60A5FA` | `rgb(96, 165, 250)` | Cyan/Sky Blue (Dark mode wordmark accent, secondary highlight) |
| `--brand-secondary` | `#1E293B` | `rgb(30, 41, 59)` | Deep Slate Indigo (Center crossing & shadows) |
| `--brand-silver` | `#CBD5E1` | `rgb(203, 213, 225)` | Cool Silver (Left loop gradient) |
| `--brand-silver-light` | `#F1F5F9` | `rgb(241, 245, 249)` | Soft highlight silver |
| `--brand-mark-muted` | `#94A3B8` | `rgb(148, 163, 184)` | Subdued / auxiliary icon fill |

### 2.2 Website Surface Harmonization

The WefyLabs mark has been deliberately harmonized with the established application design system:
- **Light Surfaces (`#F0EDE8`, `#FAF7F2`, `#FFFFFF`)**:
  - The native multi-tonal mark provides rich contrast and visual depth.
  - Paired with `#1A1A1A` bold "Wefy" and `#2C4BFB` medium "Labs" wordmark.
- **Dark Surfaces (`#1A1A1A`, `#181B22`, `#0B0F17`)**:
  - The silver left loop and cobalt right loop glow naturally on dark charcoal backgrounds.
  - Paired with `#FFFFFF` bold "Wefy" and `#93C5FD` medium "Labs" wordmark.
- **Functional Semantics**:
  - Action CTAs retain the signature `#E8F5A8` (pale lime) and `#0D9488` (teal) to prevent disrupting existing UX workflows.

---

## 3. Component Architecture: `<WefyLabsLogo />`

The central component `WefyLabsLogo` is located at `apps/web/src/components/shared/WefyLabsLogo.tsx`.

### 3.1 Supported Props
- `variant`: `'full' | 'mark' | 'compact'` (default `'full'`)
- `size`: `'sm' (18px) | 'md' (24px) | 'lg' (32px) | 'xl' (40px) | number`
- `theme`: `'light' | 'dark' | 'monochrome-light' | 'monochrome-dark' | 'auto'`
- `showWordmark`: `boolean` (default `true`, suppressed if `variant="mark"`)
- `href`: `string | null` (default `'/'`)
- `className`: `string`
- `ariaLabel`: `string` (default `'WefyLabs'`)

### 3.2 Usage Examples

```tsx
// Default full lockup on light background
<WefyLabsLogo />

// Large dark-mode lockup on dark background
<WefyLabsLogo theme="dark" size="lg" />

// Mark only for collapsed sidebars or compact status headers
<WefyLabsLogo variant="mark" size={20} />

// Unlinked logo for modal headers or non-navigable states
<WefyLabsLogo href={null} size="md" />
```

---

## 4. Asset Inventory & Formats

All official brand assets reside under `apps/web/public/branding/`:

```
apps/web/public/
├── branding/
│   ├── wefylabs-mark.png          # Transparent high-density source mark (unmatted, zero halo)
│   ├── wefylabs-mark.webp         # Modern WebP compressed mark
│   ├── wefylabs-mark.svg          # Responsive scalable SVG mark
│   ├── wefylabs-mark-light.svg    # Light-background optimized SVG
│   ├── wefylabs-mark-dark.svg     # Dark-background optimized SVG
│   ├── wefylabs-logo.svg          # Full lockup: Mark + 'WefyLabs' wordmark
│   ├── wefylabs-logo-light.svg    # Light mode full lockup
│   ├── wefylabs-logo-dark.svg     # Dark mode full lockup
│   └── favicon/
│       ├── favicon-16x16.png      # 16px browser tab favicon
│       ├── favicon-32x32.png      # 32px standard favicon
│       ├── favicon-48x48.png      # 48px desktop favicon
│       ├── apple-touch-icon.png   # 180px iOS home screen icon
│       ├── android-chrome-192x192.png # 192px Android PWA icon
│       ├── android-chrome-512x512.png # 512px splash screen icon
│       └── favicon.ico            # Multi-res ICO container
├── icon.svg                       # Root vector icon for Next.js App Router
├── favicon.ico                    # Root multi-res ICO
└── site.webmanifest               # PWA configuration manifest
```

---

## 5. Spacing, Sizing & Clear Space Rules

1. **Clear Space**: Maintain a minimum clear space equal to 50% of the mark's height on all four sides. No text, borders, buttons, or icons should encroach within this perimeter.
2. **Minimum Sizes**:
   - Full Lockup (`[Mark] WefyLabs`): Minimum height **20px** (desktop/tablet). Never render below 20px with the wordmark.
   - Mark Only: Minimum height **14px** (operational headers, badges, favicons).
3. **Responsive Sizing Guidelines**:
   - **Desktop (≥ 1280px)**: Full lockup, size `md` (24px) or `lg` (32px).
   - **Tablet (768px - 1279px)**: Full lockup, size `md` (24px).
   - **Mobile (< 768px)**: Full lockup in main nav, mark-only or compact lockup in dense action bars.

---

## 6. Email Branding Standards

Transactional emails sent via Brevo SMTP follow these rules:
- **Logo Asset**: Rendered via configuration-driven HTTPS asset URL (`{ASSET_URL}/branding/wefylabs-mark.png`).
- **Dimensions**: Displayed at a maximum width of `120px` with `height: auto`, centered at the top of transactional cards.
- **Fallbacks**: Always include `alt="WefyLabs"` and clean HTML table/div wrappers supported across Gmail, Apple Mail, and Outlook.
- **Sender Identity**: Default sender name is **WefyLabs Real Estate** (`noreply@wefylabs.com`).

---

## 7. Do's and Don'ts

| Do | Don't |
| :--- | :--- |
| **DO** use the official source ribbon mark across all platforms | **DON'T** replace the mark with a generic infinity symbol |
| **DO** use exact capitalization **WefyLabs** | **DON'T** use *Wefylabs*, *Wefy Labs*, or *WEFylabs* |
| **DO** use the transparent unmultiplied assets | **DON'T** use assets with white background boxes on dark themes |
| **DO** use the mark-only variant at sizes below 20px | **DON'T** shrink the wordmark until it becomes unreadable |
| **DO** use subtle hover and transition animations | **DON'T** rotate, wobble, or aggressively pulse the logo |
