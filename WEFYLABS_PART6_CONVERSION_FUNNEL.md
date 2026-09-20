# WEFYLABS — PART 6 CONVERSION FUNNEL ARCHITECTURE REPORT

```
PROPERTY VIEW
     ↓
SHORTLIST
     ↓
APPOINTMENT INTENT
     ↓
SLOT DISCOVERY & HOLD
     ↓
CONFIRMED APPOINTMENT
     ↓
SITE VISIT (VIEWING)
     ↓
SITE VISIT COMPLETED & OUTCOME
     ↓
FOLLOW-UP AUTOMATION
     ↓
REVENUE AUTOPILOT
     ↓
SALES ACTION / BOOKING PATH
```

---

### Stage 1: Property View
- **Source**: Customer portal browsing or AI-recommended property cards.
- **Database Entity**: `PropertyListing`, `LeadPropertyInterest(status='interested')`.
- **API**: `GET /api/v1/properties/{id}`, `GET /api/v1/portal/properties`.
- **Event**: `property_viewed`.
- **Workflow**: Context tracking in `AgentContext.discussed_property_ids`.
- **AI Involvement**: Identifies match compatibility based on buyer preferences.
- **Human Involvement**: None (autonomous discovery).
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part5_customer_experience.py::test_message_endpoint_responds`.

---

### Stage 2: Shortlist
- **Source**: Customer clicking "Add to Shortlist" or AI calling `add_to_shortlist`.
- **Database Entity**: `LeadPropertyInterest(status='shortlisted')`.
- **API**: `POST /api/v1/portal/shortlist`.
- **Event**: `property_shortlisted`.
- **Workflow**: Updates lead shortlist array; informs recommendation re-ranking.
- **AI Involvement**: Suggests shortlisting when compatibility score >= 75%.
- **Human Involvement**: None.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part5_customer_experience.py::test_shortlist_add_and_fetch`.

---

### Stage 3: Appointment Intent
- **Source**: Customer conversational request ("Can I visit this Saturday?").
- **Database Entity**: `AgentSession`, `Message`.
- **API**: `POST /api/v1/portal/chat/message`.
- **Event**: `appointment_intent_detected`.
- **Workflow**: Parses temporal expressions, property ID, and customer timezone.
- **AI Involvement**: Interprets intent and queries availability tool (`get_available_slots`). Does NOT fabricate bookings.
- **Human Involvement**: None.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_ai_tool_unconfirmed_booking_blocked`.

---

### Stage 4: Slot Discovery & Hold
- **Source**: `AvailabilityEngine.calculate_available_slots(...)`.
- **Database Entity**: `MeetingHold` (5-minute distributed lock), `CalendarEvent` (FreeBusy).
- **API**: `GET /api/v1/calendar/slots`, `GET /api/v1/portal/slots`.
- **Event**: `slots_calculated`, `slot_held`.
- **Workflow**: Rechecks property status (`status == 'available'`), working hours, and 1-hour minimum notice.
- **AI Involvement**: Reads structured slot options to present formatted timing to the customer.
- **Human Involvement**: None.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_slot_discovery_real_availability`, `test_double_booking_lock_protection`.

---

### Stage 5: Confirmed Appointment
- **Source**: Explicit customer confirmation (`confirmed_action=True` / "Confirm Booking").
- **Database Entity**: `Meeting` (`app.models.calendar_models.Meeting`), `Viewing`, `MeetingReminder`.
- **API**: `POST /api/v1/calendar/book`.
- **Event**: `meeting_booked`.
- **Workflow**: Revalidates property status, acquires lock, creates Google Calendar event, commits DB transaction, logs `Activity`.
- **AI Involvement**: Strictly bounded. Transaction owned 100% by backend application.
- **Human Involvement**: Calendar invites delivered to broker.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_slot_revalidation_race_condition`, `test_idempotent_appointment_creation`.

---

### Stage 6: Site Visit (Viewing)
- **Source**: Physical in-person inspection or virtual property walkthrough.
- **Database Entity**: `Viewing(meeting_id=..., property_id=...)`.
- **API**: `GET /api/v1/calendar/meetings/{id}`.
- **Event**: `site_visit_in_progress`.
- **Workflow**: Links customer calendar schedule directly to physical inventory.
- **AI Involvement**: Generates pre-meeting briefing (`MeetingPreparationBriefDTO`).
- **Human Involvement**: Broker hosts visit with prospect.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_site_visit_linkage_and_outcome`.

---

### Stage 7: Site Visit Completed & Outcome
- **Source**: Broker operational outcome submission via `PostMeetingIntelligenceService`.
- **Database Entity**: `MeetingOutcome`, `LeadPropertyInterest(status='visited')`, `Activity`.
- **API**: `POST /api/v1/calendar/meetings/{id}/outcome`.
- **Event**: `site_visit_completed`.
- **Workflow**: Updates meeting status to `COMPLETED`, updates lead pipeline stage, updates interest to `visited`, logs customer timeline activity.
- **AI Involvement**: Summarizes verbatim notes and parses objections without hallucinating sentiment.
- **Human Involvement**: Broker submits rating (1–5) and qualitative notes.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_site_visit_linkage_and_outcome`.

---

### Stage 8: Follow-Up Automation
- **Source**: Automated event trigger or Celery background task (`process_site_visit_completed_task`).
- **Database Entity**: `Task`, `Activity`, `FollowupRule`.
- **API**: `POST /api/v1/follow-up/evaluate`.
- **Event**: `followup_task_created`.
- **Workflow**: Checks SLA breach, working hours (9 AM–7 PM), weekend shift to Monday, and idempotency deduplication.
- **AI Involvement**: Drafts recommended follow-up opening lines. Execution governed by deterministic workflow rules.
- **Human Involvement**: Agent reviews/approves outreach task.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part27_followup_automation.py` (15/15 passed).

---

### Stage 9: Revenue Autopilot
- **Source**: `RevenueAutopilotEngine.evaluate_tenant_opportunities(...)`.
- **Database Entity**: `RevenueOpportunity(opportunity_type='POST_SITE_VISIT_FOLLOW_UP')`.
- **API**: `GET /api/v1/autopilot/opportunities`, `POST /api/v1/autopilot/evaluate`.
- **Event**: `revenue_opportunity_generated`.
- **Workflow**: Calculates Revenue Opportunity Score (distinct from Property Match Score), computes urgency, assigns priority (`CRITICAL`), generates call brief and draft.
- **AI Involvement**: Drafts contextual reasoning ("Why now", "Why property", "Risk of inactivity").
- **Human Involvement**: Sales manager/agent executes action from Command Center.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_post_site_visit_revenue_opportunity`, `test_revenue_opportunity_deduplication`, `test_revenue_score_vs_match_score_separation`.

---

### Stage 10: Sales Action / Booking Path
- **Source**: Agent actioning high-priority Revenue Opportunity or customer requesting human handoff.
- **Database Entity**: `Escalation`, `Lead(pipeline_stage='negotiation'/'converted')`.
- **API**: `POST /api/v1/autopilot/action/{id}/execute`, `POST /api/v1/portal/chat/escalate`.
- **Event**: `lead_negotiation_initiated`, `human_handoff_active`.
- **Workflow**: Human specialist assumes conversation ownership; autonomous AI generation is suppressed.
- **AI Involvement**: Fully suppressed while human specialist is active.
- **Human Involvement**: 100% human-driven negotiation and deal closure.
- **Status**: VERIFIED.
- **Test Coverage**: `tests/test_part6_conversion_workflow.py::test_human_handoff_explicit_request`, `test_human_handoff_ai_suppression`.
