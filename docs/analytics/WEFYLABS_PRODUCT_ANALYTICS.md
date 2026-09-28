# WEFYLABS PRODUCT ANALYTICS & TELEMETRY SPECIFICATION

## 1. Objectives & Governance

WefyLabs Master Build 10 implements product analytics to measure real user activation, time-to-value, operational friction, and AI copilot acceptance without capturing sensitive customer communications or financial secrets.

---

## 2. Event Taxonomy & Canonical Schema

Every telemetry event emitted by the client library (`apps/web/src/lib/analytics.ts`) complies with the standard event envelope:

```typescript
export interface EventPayload {
  event_name: ProductAnalyticsEvent;
  organization_id: string;
  user_id?: string;
  session_id: string;
  entity_type?: 'lead' | 'conversation' | 'property' | 'opportunity' | 'task' | 'appointment' | 'booking' | 'ai_action';
  entity_id?: string;
  timestamp: string;
  source: 'web' | 'mobile_web' | 'pwa';
  properties?: Record<string, any>;
}
```

### Core Tracked Events

| Event Name | Entity Type | Trigger Context |
| :--- | :--- | :--- |
| `login` | `user` | Successful broker login |
| `dashboard_viewed` | `workspace` | Command Center loaded (tracks `view_mode`) |
| `lead_opened` | `lead` | Lead detail workspace visited |
| `conversation_opened` | `conversation` | Conversation selected in Omnichannel Inbox |
| `message_sent` | `conversation` | Message sent via WhatsApp, Web, SMS, or Email |
| `property_searched` | `property` | Search query executed (tracks filters, count) |
| `property_shared` | `property` | Unit shared with client via WhatsApp |
| `property_shortlisted` | `property` | Unit added to customer proposal |
| `opportunity_opened` | `opportunity` | Commercial deal workspace viewed |
| `stage_changed` | `opportunity` | Deal moved between pipeline stages |
| `task_completed` | `task` | WorkItem marked completed |
| `appointment_created` | `appointment` | Site visit or call scheduled |
| `site_visit_completed` | `appointment` | Visit debrief logged with client outcome |
| `booking_created` | `booking` | Deposit verified and booking confirmed |
| `ai_action_approved` | `ai_action` | Broker approved AI-suggested action or draft |
| `ai_action_rejected` | `ai_action` | Broker dismissed/rejected AI action |
| `global_search_executed`| `search` | Global command palette query |

---

## 3. Strict Privacy & Data Redaction (Spec #102)

Client telemetry implements automatic parameter sanitization prior to batching or transmission:
```typescript
const SENSITIVE_KEY_REGEX = /(password|token|secret|apiKey|api_key|credit_card|card_number|cvv|auth_header)/i;
```
- Any payload key matching sensitive patterns is replaced with `[REDACTED]`.
- Freeform text fields are capped at 500 characters to prevent accidental leakage of confidential customer agreements.
- Raw customer conversation transcripts are never included in analytical telemetry payloads.

---

## 4. Activation Funnel & Time-to-Value

Product telemetry instruments the critical onboarding activation funnel:
```text
Signup 
  → First Lead Imported 
  → First AI Qualification 
  → First Matched Property 
  → First Appointment / Site Visit 
  → First Opportunity Created 
  → First Booking Confirmed
```

Time-to-Value (TTV) is calculated directly from verifiable event timestamps (`timestamp_first_booking - timestamp_signup`).
