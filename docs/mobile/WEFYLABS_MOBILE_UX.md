# WEFYLABS MOBILE OS & ERGONOMIC UX ARCHITECTURE

## 1. Mobile Design Philosophy

Real estate sales happens on the move — in golf carts during site visits, inside developer sales galleries, and in transit between buyer consultations.

WefyLabs Mobile OS is not a shrunken desktop layout; it is a **thumb-zone-optimized mobile sales operating environment** designed for rapid decision-making with one hand.

---

## 2. Mobile Information Hierarchy & Priority

On screens below 768px wide, WefyLabs strictly re-orders information priority:

| Priority | Mobile Surface | Immediate Action |
| :--- | :--- | :--- |
| **1. Primary** | **Omnichannel Inbox** | Read incoming WhatsApp messages, approve AI drafts, 1-click reply. |
| **2. High** | **Today's Urgent Layer** | Resolve SLA breaches, callbacks waiting >15 minutes, unit hold alerts. |
| **3. High** | **Lead Quick Action** | 1-tap `Call Lead` (`tel:`), 1-tap `WhatsApp`, view qualification badge. |
| **4. Core** | **Tasks & WorkItems** | Swipe to complete follow-ups, snooze callbacks to evening. |
| **5. Core** | **Calendar & Site Visits** | View today's villa/apartment visits, access client briefing before arrival. |
| **6. Secondary** | **Pipeline Deals** | Compact stage card with deal value and next commercial action. |
| **7. Background** | **Advanced Analytics** | Deep multi-touch attribution & financial modeling deferred to desktop/tablet. |

---

## 3. Thumb-Zone Ergonomics & Touch Targets

- **Accessible Touch Target Guarantee**: Every button, pill, tab, and interactive trigger has a minimum hit target of **44 × 44 pixels** in accordance with WCAG 2.2 Success Criterion 2.5.8.
- **Bottom Navigation Bar**: Critical workspaces (Today, Inbox, Leads, Calendar, Menu) are anchored at the bottom of the viewport within natural thumb reach.
- **Slide-Over Drawers**: Lead intelligence drawers and property previews slide up from the bottom with clear drag handles and instant Escape / tap-backdrop dismissal.
- **Zero Horizontal Scrolling**: Tables and cards collapse gracefully into stacked, vertical cards with zero accidental horizontal drift.

---

## 4. Mobile Property Sharing Workflow

A broker standing with a client can share verified property options in seconds:
1. Tap **Inbox** or **Lead**
2. Swipe to **Matched Properties**
3. Tap **Share Unit in WhatsApp**
4. WefyLabs generates a formatted, verified unit summary with price in Cr, area, configuration, and a tracking token for multi-touch revenue attribution.
5. The message is dispatched through the canonical communication gateway.

---

## 5. Security on Mobile Devices

- Tokens are stored in secure browser storage scoped strictly to the origin.
- Session tokens are cleared automatically upon sign-out.
- No customer financial details or raw messages are written to unencrypted local storage.
