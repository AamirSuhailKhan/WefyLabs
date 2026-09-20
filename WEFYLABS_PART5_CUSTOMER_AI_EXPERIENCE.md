# WEFYLABS — CORE PRODUCT
## PART 5 OF 8: CUSTOMER-FACING AI REAL ESTATE EXPERIENCE
### Production Architecture, Engine Implementation & Verification Reference

---

## 1. Executive Summary & Mission
Part 5 transforms the autonomous AI Sales Agent engine built in Part 4 into a high-converting, consumer-grade real estate buying experience. Rather than serving as a standard text-in/text-out chatbot or static property search widget, WefyLabs Part 5 acts as an intelligent, conversational sales consultant directly embedded into the customer portal (`/portal/[org]/chat`). 

The mission of Part 5 is singular: enable prospective real estate buyers to engage in natural, multi-turn dialogues (e.g., *"I need a 3 BHK in Noida around 1.5 crore, ready to move, not on the ground floor"*), receive verified property recommendations directly from the CRM inventory, save units to a persistent shortlist, compare properties side-by-side on verified parameters, schedule viewing appointments with human confirmation guards, and escalate to human broker specialists smoothly when requested or required.

Every interaction is grounded in canonical database records; hallucinated inventory, fake confirmation states, client-side data tampering, and unverified deal documents are strictly forbidden.

---

## 2. Architectural Principles & System Design
1. **Server as Single Source of Truth**: The client browser never calculates matching scores, manufactures property inventory, or assumes operational success. All state transitions, qualification updates, shortlist modifications, and booking requests are evaluated and persisted by backend microservices.
2. **Deterministic Multi-Tenant Scoping**: All sessions, properties, leads, shortlists, and calendar slots are strictly partitioned by `organization_id` / `broker_id`. A client cannot query, view, or alter data across organization boundaries.
3. **No Fake Data Guarantee**: Static placeholders, hardcoded MOU/loan agreements, and artificial file counts have been eradicated from the portal surface. Only verified CRM listings and live agent documents are rendered.
4. **Resilient Dual-Transport Architecture**: High-speed real-time streaming is executed over WebSockets (`ws/chat/{org}/{lead}`), backed by an automatic, seamless REST fallback (`POST /ai-agent/v1/message`) when WebSocket connections drop or firewall policies block WebSockets.
5. **Fail-Safe Confirmation Guards**: Critical sales actions (such as scheduling property visits or saving items to shortlists) require positive backend verification before displaying success indicators to the buyer.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       CUSTOMER BROWSER CLIENT                           │
│  /portal/[org]/chat  ───►  AISalesChat  ───►  Shortlist / Comparison    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (WebSocket / REST Fallback)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI AI AGENT ROUTER                            │
│  POST /message  │  WS /ws/chat  │  GET /sessions  │  POST /escalate     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Conversation   │         │  Tool Executor  │         │ Decision Engine │
│     Manager     │         │   & Services    │         │  & FSM Engine   │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL / SQLITE STORAGE                          │
│  AgentSession  │  QualificationProfile  │  PropertyListing  │  Lead     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Customer Entry & Identity Capture (`/portal/[org]/chat`)
The customer journey begins at the public portal entry URL: `/portal/[org]/chat`.
- **Zero-Barrier Lead Capture**: Prospective buyers do not need passwords or account registration to begin conversations. They are presented with a focused, premium onboarding card that captures their phone number and name.
- **Tenant Scope Binding**: The `[org]` route parameter is parsed and bound to all subsequent network calls.
- **Public Lead Resolution**: On submission, the client invokes `POST /lead-capture/public`. The backend looks up existing leads with matching phone numbers or automatically seeds a verified `Lead` record associated with the organization's broker ID.
- **State Transition**: Upon successful identification, the onboarding card transitions into the active conversation interface without full page reload.

---

## 4. Session Token Resolution & Ownership Scoping
To maintain conversation continuity across browser restarts and page refreshes, sessions are indexed by a cryptographically deterministic session token:
$$\text{Token} = \text{SHA256}(\text{organization\_id} + \text{":"} + \text{lead\_id} + \text{":"} + \text{channel})[0:64]$$

- **Tenant Ownership Validation**: When `ConversationManager._get_or_create_session()` runs, it performs a strict database query ensuring the `Lead` record belongs to the `organization_id`. If an arbitrary lead ID is paired with an unauthorized organization, a `PermissionError` is raised.
- **Local Storage Pointers**: The browser caches only the minimal session resumption pointer in `sessionStorage`:
  ```json
  { "key": "wefylabs:ai-session:org_123:lead_456", "session_id": "sess_uuid" }
  ```
- **Zero Client-Side Truth**: No chat messages, qualification facts, or property listings are cached in `localStorage` or `sessionStorage`. On refresh, the client fetches the authoritative conversation transcript from the backend.

---

## 5. Multi-Turn Conversational FSM State Engine
The conversation engine is governed by an explicit Finite State Machine (`ConversationFSM`) with 9 deterministic states:
1. `NEW`: Initial session bootstrap.
2. `GREETING`: Welcoming the buyer, introducing capabilities, establishing rapport.
3. `DISCOVERING`: Eliciting primary intent (buy vs. invest, location, unit type).
4. `QUALIFYING`: Collecting budget constraints, timeline, cash vs. mortgage, family size.
5. `SEARCHING`: Executing grounded property catalog retrieval via `search_properties`.
6. `PRESENTING`: Presenting verified matching units with key highlights.
7. `SHORTLISTING`: Guiding comparison, handling buyer feedback, saving favorites.
8. `CLOSING`: Booking viewing appointments, collecting formal deposit/visit intent.
9. `HUMAN_HANDOFF`: Pausing AI auto-reply, alerting human agent specialists.

All transitions are recorded in `conversation_states` table with immutable records of `from_state`, `to_state`, `turn_index`, customer message, and agent response.

---

## 6. WebSocket-First Streaming with REST Fallback
The front-end client implements high-performance real-time streaming with automatic fallback:
- **WebSocket Protocol**: Connects to `wss://api.wefylabs.com/ai-agent/v1/ws/chat/{org}/{lead}`.
  - Receives `token` frames for progressive, character-by-character typewriter rendering.
  - Receives `tool_start` and `tool_end` events to display live status banners (e.g., *"Searching verified inventory in Noida..."*).
  - Receives `done` frames containing the finalized message object and full `tool_results`.
- **REST Fallback**: If the WebSocket connection fails to open within 3 seconds or disconnects abnormally, `AISalesChat` silently falls back to `POST /ai-agent/v1/message`. The customer experience remains fluid without interruption.

---

## 7. Tool Execution & Dynamic Property Recommendations
When the AI engine recognizes buyer search criteria, it invokes the `search_properties` tool:
- **Tenant-Scoped Search**: The `PropertyService` queries `PropertyListing` filtered strictly by `broker_id == organization_id`, `status == "available"`, and `deleted_at IS NULL`.
- **Inline Card Rendering**: Tool outputs are embedded into the message payload under `tool_results`. The frontend renders `PropertyCardInline` components directly below the AI response bubble.
- **Verified Listing Badges**: Properties with database confirmation display an emerald `VERIFIED` pill with SVG badge.
- **Formatted Currency**: Prices are rendered using regional standards (`₹1.50 Cr`, `₹85.0 L`, `AED 2.40M`).

---

## 8. Shortlist State Synchronization & False-Success Protection
A major vulnerability in conversational commerce is the "false success" antipattern, where an interface claims an item has been saved before the server confirms the mutation.
- **P0 Fix Implemented**: In `AISalesChat.tsx`, the `handleShortlist` handler has been rebuilt.
  ```typescript
  // Synchronized Shortlist Mutation
  try {
    await aiAddToShortlist(sessionId, propId);
    const refreshed = await aiGetShortlist(sessionId);
    setShortlistItems(refreshed.items);
    setMessages(prev => [...prev, { id: nextId(), role: 'system', content: '✓ Property added to your shortlist', timestamp: new Date() }]);
  } catch {
    setMessages(prev => [...prev, { id: nextId(), role: 'system', content: 'Could not save property — please try again.', timestamp: new Date() }]);
  }
  ```
- **Database Backing**: Shortlists are persisted in `lead_property_interests` with tenant verification in `ShortlistService.add()`.

---

## 9. Side-by-Side Property Comparison Matrix
Buyers can compare up to 4 shortlisted or recommended properties simultaneously:
- **Selection**: Clicking "Compare" on inline cards toggles IDs into `compareIds`.
- **Comparison Modal**: When $\ge 2$ units are selected, `ComparisonModal` fetches structured matrix data from `GET /sessions/{id}/comparison`.
- **Standardized Attributes**: Compares price, price/sqft, bedrooms, bathrooms, carpet area, possession date, locality, developer name, and verified amenities.
- **Tenant Enforcement**: Properties belonging to different brokers cannot be co-mingled in a single comparison.

---

## 10. Viewing Appointment Scheduling & Calendar Availability
Site visit bookings are powered by `CalendarSlotService`:
- **Live Availability Query**: The client queries `GET /slots/{organization_id}?property_id={propId}&days_ahead=7`.
- **Weekday Slots**: Returns verified morning (`10:00 AM`) and afternoon (`3:00 PM`) inspection slots across upcoming weekdays.
- **Calendar Connectivity**: Displays whether the broker's calendar is directly connected or subject to manual agent confirmation.

---

## 11. Booking Confirmation Guard & Intent Verification
In `AppointmentFlow.tsx`, the booking confirmation guard prevents premature success announcements:
- **Tool Confirmation**: When the buyer clicks "Confirm Visit", a structured message is dispatched with booking metadata.
- **Inspection of `tool_results`**: The client parses the HTTP response to verify that `tool_results` contains `tool == 'book_viewing'` and `success == true`.
- **Error Remediation**: If the tool call fails or is blocked by confirmation policy, the modal displays: *"We could not submit your visit request. Please try again or ask for a human advisor."*

---

## 12. Zero-Match UX & Search Parameter Broadening
When a buyer's query is overly restrictive (e.g., *"Penthouse in Indiranagar under 50 Lakhs"*), the database returns 0 properties.
- **No White Space**: Previously, 0 results left blank space below the message.
- **`hasEmptyPropertySearch` Detection**: The frontend checks if `search_properties` succeeded with `properties.length === 0`.
- **Actionable Guidance Card**: Renders an amber advice block:
  > **ℹ No exact matches found right now.**
  > Try broadening your budget, preferred locations, or bedroom requirements to explore more options.

---

## 13. Human Specialist Escalation & Live Handoff Interface
Customer conversations can be escalated at any point through two distinct mechanisms:
1. **Explicit Buyer Intent**: Asking *"I want to speak to a person"*, *"Connect me to a broker"*, or clicking "Talk to a human".
2. **Automated Triggers**: High-value transactions, repeated dissatisfaction, or safety guardrail tripwires detected by `DecisionEngine`.
- **Escalation Record**: Creates a database row in `escalations` table with reason, priority, and AI summary.
- **UI State**: The interface displays a blue handoff badge (`👤 Connecting you with a human specialist...`) and disables deceptive AI impersonation.

---

## 14. Buyer Qualification Progress Tracking (18 Spec Fields)
The engine incrementally collects up to 18 structured buyer qualification parameters:
1. `budget_min`
2. `budget_max`
3. `budget_currency`
4. `is_cash_buyer`
5. `mortgage_status`
6. `property_type`
7. `bedrooms`
8. `bathrooms`
9. `preferred_locations`
10. `preferred_amenities`
11. `purpose` (investment vs. end-user)
12. `timeline` (immediate to 12 months)
13. `expected_move_date`
14. `nationality`
15. `family_size`
16. `current_residence`
17. `previous_purchases`
18. `fields_collected` / `completion_pct`

Progress is dynamically updated and rendered in a subtle gradient progress bar in the chat header.

---

## 15. Strict Multi-Tenant Isolation & Security Architecture
All layers of Part 5 enforce multi-tenant isolation:
- **Lead Isolation**: A lead belonging to Tenant A cannot be referenced by a session in Tenant B.
- **Listing Isolation**: Property search queries and shortlist updates verify `PropertyListing.broker_id == organization_id`.
- **Database Checks**: If an API caller attempts to access another organization's session, a 404 or 403 Forbidden is returned immediately.

---

## 16. Verified Property Detail Route (`/portal/[org]/property/[id]`)
To allow buyers to inspect full specifications without leaving the portal ecosystem, Part 5 introduces a dedicated property detail route:
- **File**: `apps/web/src/app/portal/[org]/property/[id]/page.tsx`
- **Data Fetching**: Calls `api.properties.getById(id)` to retrieve verified CRM records.
- **Key Sections**:
  - Hero visual banner with property category, verified badge, and location.
  - Price & metrics bar (price, BHK layout, super built-up area, possession status).
  - Detailed overview description and amenities badge grid.
  - Direct "Back to Advisor" and "Chat about this unit" CTAs.
- **Card Linkage**: `PropertyCardInline` now includes an accessible "View" button that deep-links directly to this page.

---

## 17. Design System, Color Harmony & Micro-Animations
The customer experience adheres to modern, premium aesthetics:
- **Palette**: Slate-900 typography, violet/indigo gradients (`from-violet-600 to-indigo-700`), emerald verified badges (`bg-emerald-500`), and warm amber hints.
- **Glassmorphism & Elevation**: Smooth backdrop filters (`backdrop-blur-sm`), soft borders (`border-slate-100`), and subtle drop shadows (`shadow-sm`, `shadow-xl`).
- **Micro-Animations**:
  - Typing indicator bounce animation (`[animation-delay:150ms]`).
  - Smooth progress bar transitions (`transition-all duration-500`).
  - Active button micro-scaling (`active:scale-[0.98]`).

---

## 18. Error Handling, Network Fault Resilience & User Messaging
The frontend handles network disruptions gracefully:
- **Non-Blocking Notifications**: Server errors are mapped to friendly system messages directly in the conversation flow rather than intrusive popup alerts.
- **Failed Message Recovery**: If a message fails to send, the input text remains preserved in the composer for instant retry.
- **Empty States**: Both shortlists and document widgets present helpful illustrations and explanatory text rather than blank screens.

---

## 19. Performance Benchmarks & Sub-Second Latency
- **Turn-Around Time**: Target end-to-end response latency for mock LLM / cached paths is $< 200\text{ms}$.
- **WebSocket Streaming**: Time to first token (TTFT) is $< 400\text{ms}$ over real LLM gateways.
- **Asset Overhead**: Zero heavy third-party chat widget bundles; 100% native Next.js + React 19 components with zero runtime CSS-in-JS overhead.

---

## 20. Anti-Tampering, PII Scrubbing & Rate Limiting
- **Rate Limiting**: `apps/api/app/modules/ai_agent/websocket_handler.py` enforces per-IP and per-session rate limits to prevent denial-of-service or automated scraping.
- **Safety Guard**: `ResponseSafetyGuard` scrubs exposed credit card numbers, government IDs, and developer credentials from agent outputs before dispatch.
- **Prompt Injection Defense**: Customer inputs are sanitized and passed through strict delimiter blocks preventing system instruction overrides.

---

## 21. Real Estate Compliance & Financial Disclaimers
- **Indicative Pricing**: Property cards with unverified pricing include an "Indicative" label.
- **Legal Caveats**: Calendar slots explicitly inform buyers: *"Slots are suggested availability. Agent confirmation required."*
- **No Deceptive Commitments**: The agent cannot execute legal contracts or issue binding purchase guarantees without human broker intervention.

---

## 22. Full Component Inventory & Frontend Code Map
| File Path | Role & Purpose |
|---|---|
| `apps/web/src/app/portal/[org]/chat/page.tsx` | Customer entry point, phone capture, and chat host |
| `apps/web/src/components/portal/AISalesChat.tsx` | Primary 615-line conversational chat container |
| `apps/web/src/components/portal/PropertyCardInline.tsx` | Inline verified recommendation card with Save/Compare/Visit/View |
| `apps/web/src/components/portal/ShortlistPanel.tsx` | Slide-over drawer displaying customer's saved units |
| `apps/web/src/components/portal/ComparisonModal.tsx` | Side-by-side comparison modal for 2–4 properties |
| `apps/web/src/components/portal/AppointmentFlow.tsx` | Slot selection and viewing request flow with verification guard |
| `apps/web/src/app/portal/[org]/property/[id]/page.tsx` | Full property detail verification view |
| `apps/web/src/app/portal/page.tsx` | Portal dashboard (purged of fake documents) |
| `apps/web/src/lib/api-client.ts` | Complete typed SDK for all AI agent endpoints |

---

## 23. Complete REST & WebSocket API Specification
| Endpoint | Method | Payload / Params | Return Contract |
|---|---|---|---|
| `/ai-agent/v1/message` | `POST` | `{ lead_id, organization_id, channel, content, metadata }` | `MessageResponseDTO` |
| `/ai-agent/v1/ws/chat/{org}/{lead}` | `WS` | JSON frames: `{"type": "user_message", "content": "..."}` | Streaming token frames + done frame |
| `/ai-agent/v1/sessions/{id}/history` | `GET` | `limit: int` | `List[ConversationState]` |
| `/ai-agent/v1/sessions/{id}/qualification` | `GET` | None | `QualificationProfile` |
| `/ai-agent/v1/sessions/{id}/shortlist` | `GET` | `status: Optional[str]` | `{ items: List[ShortlistItem], total: int }` |
| `/ai-agent/v1/sessions/{id}/shortlist` | `POST` | `{ property_id, status, notes }` | `{ success: bool, status: str }` |
| `/ai-agent/v1/sessions/{id}/comparison` | `GET` | `property_ids: List[str]` | `{ properties: [...], comparison_matrix: {...} }` |
| `/ai-agent/v1/slots/{organization_id}` | `GET` | `property_id: Optional[str], days_ahead: int` | `{ slots: [...], calendar_connected: bool }` |
| `/ai-agent/v1/sessions/{id}/escalate` | `POST` | `{ reason, priority, notes }` | `Escalation` record |

---

## 24. Database Models, Relations & Migration Linkages
- **`AgentSession`**: Tracks session token, active state, turn count, and lead/org linkage.
- **`ConversationState`**: Append-only log of every conversational turn and state transition.
- **`QualificationProfile`**: Stores 18 structured buyer qualification attributes.
- **`PropertyListing`**: Canonical property table with pricing, status, specs, and broker ownership.
- **`LeadPropertyInterest`**: Shortlist and saved property records linking leads and properties.
- **`Escalation`**: Formal human handoff queue items with priority and summary briefings.

---

## 25. Automated Testing Strategy (22 Comprehensive Tests)
The Part 5 suite incorporates 22 automated integration and unit tests across two major test suites:

### Suite A: `tests/test_part5_customer_experience.py` (10 Tests — 100% Passing)
1. `test_message_endpoint_responds`: Validates end-to-end conversation turn processing.
2. `test_session_history_persists`: Verifies turn sequence and message integrity.
3. `test_shortlist_add_and_fetch`: Tests shortlist mutation and retrieval.
4. `test_shortlist_false_success_blocked`: Confirms un-shortlisted leads return empty lists.
5. `test_comparison_endpoint`: Validates side-by-side comparison matrix generation.
6. `test_slots_endpoint`: Tests available weekday viewing slot calculation.
7. `test_escalation_flow`: Tests human escalation trigger and session flagging.
8. `test_no_match_tool_result`: Ensures zero matching listings return empty lists safely.
9. `test_tenant_isolation_session`: Proves cross-tenant shortlist tampering is blocked.
10. `test_session_restore_after_refresh`: Verifies full session restoration on simulated page reload.

### Suite B: `tests/test_part5_ai_agent.py` (12 Tests — 100% Passing)
Covers FSM transitions, context builder, strategy engine, prompt builder, LLM router, tool executor, safety guard, decision engine, qualification tracker, handoff service, full round-trip, and session persistence.

---

## 26. End-to-End Customer Journey Verification Audit
```
[✔] Step 1: Customer enters /portal/[org]/chat → sees phone entry intro card.
[✔] Step 2: Enters phone → public lead resolved → chat window mounts.
[✔] Step 3: Sends "I need a 3 BHK in Noida" → AI streams response + property cards appear.
[✔] Step 4: Clicks "Save" on card → backend adds to shortlist → system confirms.
[✔] Step 5: Clicks "Compare" on 2 cards → comparison modal opens with verified matrix.
[✔] Step 6: Clicks "View" on card → navigates to /portal/[org]/property/[id] detail page.
[✔] Step 7: Clicks "Schedule Visit" → selects slot → booking intent submitted and validated.
[✔] Step 8: Refreshes page → prior turns and qualification restored from server.
[✔] Step 9: Says "Connect me to a human" → human escalation banner activates.
[✔] Step 10: Enters impossible criteria → helpful "no exact matches" advice rendered.
```

---

## 27. Production Deployment & Readiness Checklist
- [x] All TypeScript compilation passes with 0 errors (`npx tsc --noEmit`).
- [x] All 22 backend test cases passing (`pytest tests/test_part5_*.py`).
- [x] Fake documents and mock dates removed from `portal/page.tsx`.
- [x] Debug `console.log` statements stripped from production routes.
- [x] False-success bugs in shortlist and appointments eliminated.
- [x] Tenant boundary checks enforced across all services.
- [x] Responsive layout validated across desktop, tablet, and mobile viewports.

---

## 28. Milestone Summary & Part 6 Handoff Roadmap
Part 5 completes the transformation of WefyLabs from an internal CRM into an autonomous, customer-facing real estate sales operating system. 

### Transition to Part 6:
With customer identity, property intelligence, qualification, autonomous sales conversations, and portal experiences fully verified, the platform is prepared for **Part 6: Automated Deal Execution & Closing Engine**:
- Real-time digital reservation agreements (MOU) generation.
- Automated payment gateway integration for token deposit collection.
- Escrow and KYC compliance verification workflows.
- Integration between customer portal bookings and broker transaction pipelines.
