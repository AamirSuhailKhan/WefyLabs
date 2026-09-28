# WEFYLABS REVENUE COMMAND CENTER ARCHITECTURE

## 1. Overview & Integration with Build 09

The Revenue Command Center (`/dashboard/revenue-intelligence`) exposes the enterprise revenue intelligence and attribution ledger created in Master Build 09.

It serves as the definitive financial truth for real estate developers, brokerage founders, and sales directors, eliminating disconnected spreadsheets and manual accounting reconciliations.

---

## 2. Core Views & Navigational Surfaces

The Revenue workspace is organized into seven canonical sub-views:
1. **Overview**: Executive financial scorecards, booking velocities, collected deposits, and net revenue.
2. **Pipeline**: Stage-by-stage commercial pipeline value, win probability, and stall alerts.
3. **Funnel**: End-to-end conversion efficiency (Lead → Contacted → Qualified → Site Visit → Offer → Booking).
4. **Attribution**: Multi-touch marketing attribution models measuring channel ROI and deal origin.
5. **Forecast**: Stage-weighted commercial forecasts strictly separated into Actual, Forecast, Committed, and Pipeline.
6. **Leakage**: Active revenue leakage detection center identifying stalled transactions and expiring reservations.
7. **Economics**: Real estate unit economics, average deal size, commission structures, and acquisition cost.

---

## 3. Strict Forecast Separation

To prevent misleading financial reporting, the user interface enforces strict visual and mathematical separation between four commercial categories:

```text
┌───────────────────────┬───────────────────────┬───────────────────────┬───────────────────────┐
│     ACTUAL (CASH)     │       COMMITTED       │       FORECAST        │       PIPELINE        │
│      ₹21.50 Cr        │       ₹18.00 Cr       │       ₹49.00 Cr       │       ₹68.00 Cr       │
│  Verified in ledger   │  Signed booking form  │  Stage-weighted calc  │   Unweighted total    │
└───────────────────────┴───────────────────────┴───────────────────────┴───────────────────────┘
```

The UI never visually blends pipeline possibilities with actual realized revenue.

---

## 4. Multi-Touch Attribution Engine

Brokers can toggle between five canonical attribution models in real time:
- **First Touch**: 100% attribution to initial acquisition source (e.g. Meta Ads, Google Ads).
- **Last Touch**: 100% attribution to final interaction preceding reservation.
- **Linear**: Equal distribution across all touchpoints in customer journey.
- **Time Decay**: Exponentially higher weight to touchpoints closer to booking date.
- **Position-Based (U-Shaped)**: 40% First Touch, 40% Lead Creation, 20% Middle Touchpoints.

Every view clearly discloses the active lookback window (e.g., 90-day window) and data freshness timestamp.

---

## 5. Revenue Leakage Center & WorkItem Connection

Detected revenue leakage items connect directly to the WorkItem engine (Build 07):
- Expiring unit reservations trigger an instant high-priority WorkItem for the assigned broker.
- Stalled negotiation phases automatically recommend a Next Best Action (e.g., "Schedule senior partner consultation").
