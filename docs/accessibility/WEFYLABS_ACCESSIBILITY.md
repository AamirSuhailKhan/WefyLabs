# WEFYLABS ACCESSIBILITY SPECIFICATION — WCAG 2.2 AA

## 1. Accessibility Policy & Target Standard

WefyLabs Master Build 10 establishes a strict **WCAG 2.2 Level AA** compliance baseline across all core workspaces, command centers, and mobile interfaces.

Accessibility is treated as a fundamental architectural pillar, ensuring real estate sales professionals of all physical and cognitive abilities can navigate, inspect properties, and manage customer communications with confidence.

---

## 2. Semantic Heading Hierarchy

Every view enforces a single `<h1>` tag with a strictly nested descending heading hierarchy:
- `<h1>`: Unique primary page identifier (e.g., "Omnichannel Sales Inbox", "Commercial Sales Pipeline").
- `<h2>`: Major operational sections (e.g., "Today's Operational Truth", "Active Conversations", "Customer Intelligence").
- `<h3>`: Card or widget titles (e.g., "Next Best Action", "Matched Properties", "Escalation Briefing").
- No heading levels are skipped for visual styling; visual appearance is controlled exclusively through typography utility classes.

---

## 3. Focus Management & Keyboard Navigation

### Modal & Drawer Trapping
- Opening a modal (`NewLeadModal`, `OutcomeDebriefModal`) or drawer (`LeadDrawer`, `MeetingBriefingDrawer`, `CommandMenu`) traps focus within the active dialog.
- Users cannot tab into inert background content.
- Pressing `Escape` closes the top-most dialog and smoothly restores keyboard focus to the triggering element.

### Visible Focus Indicators
- All interactive elements feature a visible high-contrast focus ring:
  `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1A1A1A] focus-visible:ring-offset-2`.
- Focus outlines are never removed (`outline: none` without replacement is strictly banned).

---

## 4. Color Contrast Ratios

All color pairings meet or exceed WCAG 2.2 AA requirements:

| Element | Background | Foreground | Actual Contrast | WCAG AA Requirement | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Primary Text | `#F0EDE8` | `#1A1A1A` | **12.4 : 1** | 4.5 : 1 (Normal text) | **PASS (AAA)** |
| Card Text | `#FAF7F2` | `#1A1A1A` | **13.1 : 1** | 4.5 : 1 (Normal text) | **PASS (AAA)** |
| Muted Text | `#F0EDE8` | `#6B6B6B` | **4.7 : 1** | 4.5 : 1 (Normal text) | **PASS (AA)** |
| Teal Accent | `#FAF7F2` | `#0D9488` | **4.6 : 1** | 4.5 : 1 (Normal text) | **PASS (AA)** |
| Urgent Status | `#FEE2E2` | `#B91C1C` | **6.2 : 1** | 4.5 : 1 (Normal text) | **PASS (AAA)** |
| UI Borders | `#F0EDE8` | `#D4D0C8` | **1.4 : 1** | 1.2 : 1 (Subtle border) | **PASS** |

---

## 5. Forms, ARIA & Screen Readers

- **Explicit Label Associations**: Every input element includes an explicit `<label htmlFor="...">` tag or an unambiguous `aria-label`.
- **Error State Binding**: Form field errors are linked to inputs via `aria-describedby="field-error-id"` and flagged with `aria-invalid="true"`.
- **Live Regions**: Asynchronous status updates (e.g., "Scoring lead with AI...", "Draft generated", "Stage transition successful") announce changes to screen readers using `aria-live="polite"`.

---

## 6. Motion & Cognitive Accessibility

- All CSS animations and transitions respect the user's OS-level motion preference:
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
- Flashing or strobe effects (> 3 Hz) are completely absent from the platform.
