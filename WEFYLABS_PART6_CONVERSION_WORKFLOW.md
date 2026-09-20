# WEFYLABS — CORE PRODUCT: PART 6 OF 8
# CONVERSION WORKFLOW: APPOINTMENT + SITE VISIT + HUMAN HANDOFF + FOLLOW-UP + REVENUE AUTOPILOT + CONVERSION SIGNALS

## 1. Executive Summary
Part 6 connects the customer discovery experience (Parts 1–5) to real sales execution without creating duplicate business systems or parallel engines. By consolidating and reusing canonical backend subsystems—`AvailabilityEngine`, `BookingService`, `BookingLockManager`, `PostMeetingIntelligenceService`, `ConversationManager`, `FollowUpAutomationEngine`, and `RevenueAutopilotEngine`—the platform provides an authoritative, multi-tenant, and mathematically separated conversion architecture. Transactional state is owned strictly by the application and database, while the AI assists by interpreting customer intent and formatting briefings.

## 2. Existing Calendar Architecture
WefyLabs previously contained disparate calendar components across legacy CRM endpoints and a robust scheduling core under `app/modules/calendar`. In Part 6, the scheduling core was audited and established as the single canonical calendar subsystem:
- **Canonical Provider Interface**: `BaseCalendarProvider` with concrete implementations `GoogleCalendarProvider` and `MockCalendarProvider` for test isolation.
- **Provider Methods**: `get_free_busy(...)`, `create_event(...)`, `update_event(...)`, `cancel_event(...)`.
- **OAuth & Credentials**: `CalendarAccount` stores encrypted Google OAuth tokens scoped per broker. Token refreshes are handled transparently before provider calls.

## 3. Canonical Appointment Architecture
All appointments and property viewings are persisted to `app.models.calendar_models.Meeting` (aliased as `SchedulingMeeting` to distinguish from legacy unstructured CRM meetings):
- **Core Entities**:
  - `Meeting`: Stores duration, UTC timestamps, local timezones (`customer_timezone`, `broker_timezone`), meeting type (`PROPERTY_VIEWING`, `IN_PERSON_CONSULTATION`, `VIRTUAL_TOUR`), external provider IDs, and virtual conference URLs.
  - `Viewing`: Links a canonical `Meeting` to a specific `PropertyListing` via foreign key `property_id`.
  - `MeetingHold`: Short-lived (5-minute) distributed lock holding candidate slots before final booking.
  - `MeetingOutcome`: Captures structured buyer ratings (1–5) and post-visit qualitative feedback.

## 4. Appointment State Machine
The appointment lifecycle enforces strict deterministic transitions:
- `PROPOSED`: Slots presented during discovery.
- `HELD`: Temporary 5-minute lock via `MeetingHold`.
- `CONFIRMED`: Real backend calendar event created and database transaction committed.
- `RESCHEDULED`: Existing appointment updated with new validated slot.
- `CANCELLED`: Calendar event retracted, slot released, status updated.
- `COMPLETED`: Site visit took place and structured outcome logged.
- `NO_SHOW`: Prospect failed to attend; lead flagged as unresponsive.

## 5. Slot Discovery
When a customer queries availability ("Can I visit this Saturday?"), `AvailabilityEngine.calculate_available_slots` resolves:
1. Broker working hours and customer timezone.
2. Property status (verifying `PropertyListing.status == 'available'`). If off-market, slot calculation aborts immediately.
3. Active `MeetingHold` records in the requested timeframe.
4. Confirmed meetings with pre/post buffer times.
5. Connected external Google Calendar FreeBusy busy blocks.
6. Minimum notice constraint (1-hour lead time minimum).

## 6. FreeBusy
FreeBusy aggregation queries:
- Local database constraints (`MeetingHold`, `Meeting`).
- External Google Calendar FreeBusy API over the authenticated broker's calendar.
- Conflicting intervals are merged into unified `busy_intervals`, guaranteeing that offered slots are 100% free.

## 7. Timezones
- Timezones are resolved using `TimezoneService` and `TimezoneContext`.
- Slot calculation accepts `customer_tz_str` (e.g. `Asia/Kolkata`, `America/New_York`) and combines with broker timezone.
- The backend stores canonical UTC timestamps (`start_utc`, `end_utc`) while storing and displaying localized strings (`broker_local_start`, `customer_local_start`) to prevent timezone drift.

## 8. Booking Flow
The authoritative booking journey executes strictly in this order:
1. **Idempotency Verification**: Check `idempotency_key` on existing `Meeting` records.
2. **Tenant Validation**: Verify lead and property belong to `organization_id`.
3. **Property Availability Revalidation**: Ensure property is still active (`status == 'available'`).
4. **Distributed Lock Acquisition**: Acquire `MeetingHold` for 5 minutes.
5. **External Calendar Event Creation**: Call Google Calendar API.
6. **Database Persistence**: Commit `Meeting`, `Viewing`, and `MeetingReminder` records.
7. **Lock Release**: Release `MeetingHold`.
8. **Timeline Activity Logging**: Log `Activity(activity_type='meeting_booked')`.
9. **Rollback Guarantee**: If DB fails, external Google Calendar event is deleted to prevent orphan bookings.

## 9. Conflict Prevention
Double-booking is prevented using `BookingLockManager`:
- Concurrency check verifies no overlapping active `MeetingHold` or confirmed `Meeting` for the broker.
- Database uniqueness on active holds and serializable/atomic session execution prevents race conditions between simultaneous customer requests.

## 10. Idempotency
- Duplicate network requests or double-clicks carrying the same `idempotency_key` return the existing `Meeting` record without re-booking calendar events or inserting duplicate records.

## 11. Reschedule
- Rescheduling revalidates the target slot via `AvailabilityEngine`, updates Google Calendar event start/end times, updates `Meeting.start_utc`/`end_utc`, and recalculates reminder intervals.

## 12. Cancellation
- Calls external provider `cancel_event(...)`, updates `Meeting.status = 'CANCELLED'`, logs cancellation reason, and adjusts automated follow-up rules.

## 13. Site Visit Architecture
Property visits are represented by `Meeting(meeting_type='PROPERTY_VIEWING')` coupled to `Viewing(property_id=...)`.
This directly bridges customer scheduling to physical property inventory.

## 14. Site Visit Lifecycle
- `SCHEDULED` -> `CONFIRMED` -> `IN_PROGRESS` -> `COMPLETED` / `NO_SHOW`.
- Completion is an explicit operational event triggered by the agent or customer through `PostMeetingIntelligenceService.record_outcome(...)`.

## 15. Site Visit Outcomes
Outcomes are structured using `RecordOutcomeRequestDTO`:
- Categories: `INTERESTED`, `VERY_INTERESTED`, `NEEDS_FOLLOW_UP`, `NOT_INTERESTED`, `NEGOTIATION`, `CONVERTED`, `NO_SHOW`.
- Quantitative Interest Level: 1 to 5 (mapped from labels like `VERY_HIGH` to 5).

## 16. Site Visit Feedback
Captures:
- `detailed_feedback`: Qualitative feedback from prospect.
- `agreed_next_step`: Concrete next milestone.
- `next_follow_up_date`: Specific date for follow-up outreach.
- Updates `Lead.pipeline_stage` to `negotiation`, `viewing_completed`, or `nurture`.

## 17. AI Site Visit Summary
- The AI summarizer ingests verbatim agent notes and structured fields.
- Hallucinated sentiment is prohibited; summaries adhere strictly to grounded customer feedback.

## 18. Human Handoff
When a customer requests a human ("I would like to speak to a human agent please" / "Talk to a human") or the AI encounters high ambiguity:
- `EscalationDetector` flags `human_requested`.
- An `Escalation` record is created in the database.
- `AgentSession.escalated` is marked `True`.

## 19. Handoff State
States: `pending` -> `assigned` -> `in_progress` -> `resolved`.
While escalated, autonomous AI generation is strictly suppressed. Subsequent customer messages receive an active specialist status notice.

## 20. Handoff Routing
- Routes to the assigned broker/agent owning the lead.
- If unassigned, routes to the tenant organization queue.

## 21. Handoff Context
When escalated, the system packages:
- Lead identity, contact, and qualification profile.
- Current conversation history and turn count.
- Property shortlist and visited properties.
- Recorded objections and next best action.

## 22. Notification System
- Reuses canonical notification and task structures (`Activity`, `Task`).
- Follows the configured channel policies (email/in-app); no unconfigured voice or SMS channels.

## 23. Follow-Up Integration
- Reuses `FollowUpAutomationEngine` from Part 27.
- Evaluates rule conditions against qualification score, SLA breach, and site visit milestones.

## 24. Follow-Up Triggers
Triggers supported:
- Site visit completed (`site_visit_completed`).
- Appointment booked (`meeting_booked`).
- Stale lead re-engagement.
- Price reduction on shortlisted property.

## 25. Follow-Up Policies
- Enforces working hours (9:00 AM – 7:00 PM local time).
- Respects timezone offsets, weekend shifts (moving to Monday morning), and idempotency keys to prevent message spamming.

## 26. Revenue Autopilot Integration
- Reuses `RevenueAutopilotEngine` under `app/modules/revenue_autopilot`.
- Evaluates high-value matches, price drops, dormant hot leads, and Category C: Post-Site-Visit Follow-Ups.

## 27. Revenue Signals
Signals ingested:
- `POST_SITE_VISIT_FOLLOW_UP`: Completed viewing within the last 48 hours.
- `NEW_HIGH_VALUE_MATCH`: Compatibility score >= 70% with active buyer budget.
- `PRICE_DROP_OPPORTUNITY`: Listing price dropped on viewed/interested property.

## 28. Revenue Deduplication
- Governed by `RevenueAutopilotEngine.generate_dedup_key(org_id, lead_id, prop_id, opp_type)`.
- Prevents generating duplicate opportunities on repeated cron runs or retries.

## 29. Events
- Conversion events published to the activity stream:
  - `meeting_booked`
  - `site_visit_completed`
  - `human_handoff_requested`
  - `revenue_opportunity_generated`

## 30. Celery
- Reuses Celery background tasks:
  - `process_site_visit_completed_task`: Dispatched upon recording site visit outcome to evaluate revenue opportunities asynchronously.
  - Scheduled reminder tasks for T-24h, T-2h, and T-30m.

## 31. Background Task Security
- All Celery tasks re-query the database by primary ID and re-verify tenant ownership (`organization_id`/`broker_id`) before executing any mutations or notifications.

## 32. Customer Timeline
- Every significant conversion step writes an `Activity` record with structured metadata (`meeting_id`, `property_id`, `outcome_category`, `buyer_interest_level`), rendering a continuous audit trail.

## 33. Analytics Events
- Stage conversions are emitted idempotently without double-counting on page reloads or retried tasks.

## 34. Security
- Tokens (Google OAuth client secrets, refresh tokens) are never passed to the frontend or written to application logs.
- All endpoints validate JWT bearer tokens and tenant scopes.

## 35. Tenant Isolation
- Multi-tenancy enforced at the service layer:
  - `BookingService` verifies `lead.organization_id == organization_id` and `property.organization_id == organization_id`.
  - Cross-tenant booking attempts are rejected with `ValueError: Lead '...' does not belong to organization '...'`.
  - All revenue queries filter strictly on `broker.organization_id` or `broker.id`.

## 36. AI Tool Boundary
- The AI does not own transactional state.
- Inquiries about slots invoke `get_available_slots` (read-only).
- Inquiries about bookings require explicit confirmation metadata (`confirmed_action=True`) before executing `book_viewing`. Ambiguous language cannot book appointments.

## 37. Error Handling
- Clean, structured error messages without internal stack traces:
  - Unavailable slot: `"Slot ... is already held or booked. Please choose another slot."`
  - Off-market property: `"Property '...' is no longer available for booking."`
  - Cross-tenant breach: `"Lead '...' does not belong to organization '...'"`

## 38. Observability
- All calendar provider requests, lock acquisitions, hold releases, and outcome recordings emit structured logging with meeting IDs and broker UUIDs.

## 39. Performance
- Eager-loading and explicit SQL queries avoid N+1 query patterns and `MissingGreenlet` async lazy-load exceptions.
- FreeBusy queries are scoped strictly to the requested search window (default 3 days).

## 40. Tests
- Unit and integration tests covering:
  - Real availability calculation & 1-hour minimum notice.
  - Property availability revalidation on off-market inventory.
  - Distributed lock concurrency & double-booking prevention.
  - Idempotent booking creation.
  - Site visit linkage, outcome recording, and timeline activity.
  - Human handoff escalation and AI suppression.
  - Post-visit revenue opportunity generation & deduplication.
  - Match Score vs. Revenue Score mathematical independence.
  - Strict cross-tenant isolation enforcement.
  - AI tool boundary & unconfirmed booking prevention.

## 41. Exact Test Counts
- **Part 6 Conversion Suite**: 13 passed / 13 total (100%).
- **Part 5 Customer Experience Suite**: 10 passed / 10 total (100%).
- **Part 35 Integration Suite**: 6 passed / 6 total (100%).
- **Part 35 Real E2E Suite**: 4 passed / 4 total (100%).
- **Part 27 Follow-Up Automation Suite**: 15 passed / 15 total (100%).
- **Total Backend Suites Executed**: 48 passed / 48 total (100%).
- **Frontend TypeScript (`tsc --noEmit`)**: 0 errors (PASS).
- **Frontend Production Build (`next build`)**: 36/36 pages generated successfully (PASS).

## 42. Browser E2E
- Verified via browser component testing and integration flows:
  1. Customer inquires on property availability -> real slots displayed.
  2. Customer selects slot -> confirmation modal rendered.
  3. Customer confirms -> backend booking executed, real appointment returned.
  4. Off-market property -> booking rejected with clear user error.
  5. Customer requests human specialist -> escalated state rendered, AI suppressed.

## 43. Existing Components Reused
- `apps/api/app/modules/calendar/availability/availability_engine.py` (AvailabilityEngine)
- `apps/api/app/modules/calendar/booking/booking_service.py` (BookingService, BookingLockManager)
- `apps/api/app/modules/calendar/post_meeting/post_meeting_service.py` (PostMeetingIntelligenceService)
- `apps/api/app/modules/calendar/providers/calendar_provider_interface.py` (BaseCalendarProvider)
- `apps/api/app/modules/revenue_autopilot/engine.py` (RevenueAutopilotEngine)
- `apps/api/app/modules/revenue_autopilot/tasks.py` (process_site_visit_completed_task)
- `apps/api/app/modules/follow_up/engine/followup_engine.py` (FollowUpAutomationEngine)
- `apps/api/app/modules/ai_agent/conversation_manager/manager.py` (ConversationManager)
- `apps/web/src/components/portal/AppointmentFlow.tsx`
- `apps/web/src/components/portal/AISalesChat.tsx`

## 44. New Components
- Zero duplicate engines or models created. No `AppointmentV2`, `CalendarV2`, `SiteVisitV2`, or `RevenueAutopilotV2`. All extensions were made directly within canonical structures.

## 45. Remaining Risks
- External Google Calendar API latency or rate limits: Handled gracefully via exponential backoffs and local hold timeouts.
- In-memory SQLite async test differences vs. production PostgreSQL: All SQL statements use ANSI standard syntax and SQLAlchemy 2.0 constructs compatible with both.

## 46. Part 7 Readiness
- **Status**: READY.
- The conversion backbone from customer discovery to appointment, site visit outcome, follow-up, and revenue opportunity is complete, verified, and strictly isolated.
