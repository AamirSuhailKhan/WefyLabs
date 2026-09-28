# WEFYLABS GLOBAL COMMAND CENTER ARCHITECTURE

## 1. Role of the Command Center

The Command Center (`/dashboard`) is the central operational cockpit of WefyLabs. It answers five fundamental questions for a sales professional or manager within 3 seconds of login:

1. **What happened?** (Overnight replies, incoming portal inquiries, payments received)
2. **What is happening now?** (Active customer waiting times, live AI agent conversations)
3. **What needs attention immediately?** (SLA breaches, unit holds expiring, AI handoffs)
4. **What should happen next?** (Next Best Actions, upcoming appointments, scheduled follow-ups)
5. **What revenue is at risk?** (Stalled deals, uncontacted qualified leads, expiring options)

---

## 2. Today's Urgent Layer Architecture

Located directly below the dashboard header, the **Today's Operational Truth** banner synthesizes high-priority items across four distinct backend engines:

```text
┌────────────────────────────────────────────────────────────────────────┐
│  TODAY'S OPERATIONAL TRUTH                                             │
│  [1 SLA Breach]  [2 Waiting >15m]  [3 Events Today]  [₹4.5 Cr at Risk]  │
└────────────────────────────────────────────────────────────────────────┘
```

### Data Sources & Authoritative Endpoints:
- `api.crm.getLeads()` & `api.inbox.getInbox()`: Aggregates leads in urgent state or waiting on WhatsApp.
- `api.commandCenter.getData()`: Fetches tenant-level summary metrics and high-priority action items.
- `api.revenueIntelligence.getOverview()`: Provides authoritative net revenue and pipeline at risk.
- `api.calendar.getUpcomingBookings()`: Surfaces visits and appointments scheduled for today.

---

## 3. Concrete Attention Reasons vs Opaque Scores

WefyLabs Master Build 10 explicitly bans arbitrary, opaque composite scores (such as a generic "Attention Score: 78"). Instead, attention items display concrete, human-verifiable operational facts:
- `"Customer waiting 18m on WhatsApp"`
- `"Site visit in 45m with Meera Nambiar"`
- `"SLA breached: Lead uncontacted for 24h"`
- `"Unit hold on Unit 402 expires in 2 hours"`
- `"Opportunity stalled 5 days in Proposal stage"`

Each item links directly to the relevant customer record, WhatsApp conversation, or calendar briefing drawer.

---

## 4. Multi-View Workspace Switching
The Command Center allows brokers to toggle seamlessly between operational modes:
- **Board View (Kanban)**: Visual pipeline flow across qualification, site visits, and booking.
- **Table View**: High-density tabular layout with sorting, filtering, selection, and CSV export.
- **Autopilot View**: Autonomous AI sales loop monitoring with pause/resume controls.
- **Command Center Summary**: Executive birds-eye view of team velocity and revenue targets.
