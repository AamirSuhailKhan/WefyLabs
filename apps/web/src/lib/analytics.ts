/**
 * WefyLabs Product Analytics & Telemetry Layer (Master Build 10)
 *
 * Implements canonical event taxonomy, tenant-scoped tracking, activation funnels,
 * and strict privacy sanitization (no passwords, API keys, or raw sensitive messages).
 */

import { getOrganizationId } from './api-client';

export type ProductAnalyticsEvent =
  | 'login'
  | 'dashboard_viewed'
  | 'lead_opened'
  | 'conversation_opened'
  | 'message_sent'
  | 'property_searched'
  | 'property_shared'
  | 'property_shortlisted'
  | 'opportunity_opened'
  | 'stage_changed'
  | 'task_completed'
  | 'appointment_created'
  | 'site_visit_completed'
  | 'booking_created'
  | 'ai_action_approved'
  | 'ai_action_rejected'
  | 'global_search_executed';

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

// Session management
let currentSessionId: string | null = null;
function getSessionId(): string {
  if (typeof window === 'undefined') return 'srv-session';
  if (!currentSessionId) {
    let stored = window.sessionStorage.getItem('wefylabs_analytics_sid');
    if (!stored) {
      stored = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      try {
        window.sessionStorage.setItem('wefylabs_analytics_sid', stored);
      } catch {
        // storage disabled or quota exceeded
      }
    }
    currentSessionId = stored;
  }
  return currentSessionId;
}

// Strict Privacy Filter (Spec #102)
const SENSITIVE_KEY_REGEX = /(password|token|secret|apiKey|api_key|credit_card|card_number|cvv|auth_header)/i;

function sanitizeProperties(props?: Record<string, any>): Record<string, any> {
  if (!props) return {};
  const cleaned: Record<string, any> = {};
  for (const [k, v] of Object.entries(props)) {
    if (SENSITIVE_KEY_REGEX.test(k)) {
      cleaned[k] = '[REDACTED]';
    } else if (typeof v === 'string' && v.length > 500) {
      cleaned[k] = v.substring(0, 500) + '...[TRUNCATED]';
    } else if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      cleaned[k] = sanitizeProperties(v);
    } else {
      cleaned[k] = v;
    }
  }
  return cleaned;
}

// Queue & Dispatcher
const eventQueue: EventPayload[] = [];
let flushTimeout: any = null;

async function flushEvents() {
  if (eventQueue.length === 0) return;
  const batch = eventQueue.splice(0, 25);

  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const orgId = getOrganizationId();

    if (typeof window !== 'undefined' && window.navigator && window.navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify({ events: batch })], { type: 'application/json' });
      window.navigator.sendBeacon(`${apiBase}/analytics/telemetry`, blob);
    } else {
      await fetch(`${apiBase}/analytics/telemetry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(orgId ? { 'X-WefyLabs-Organization-Id': orgId } : {}),
        },
        body: JSON.stringify({ events: batch }),
      }).catch(() => {
        // Silently discard failed telemetry in client
      });
    }
  } catch {
    // Analytics failures must never crash client apps
  }
}

function queueEvent(payload: EventPayload) {
  eventQueue.push(payload);
  if (typeof window !== 'undefined') {
    if (flushTimeout) clearTimeout(flushTimeout);
    flushTimeout = setTimeout(flushEvents, 2000);
  }
}

export const analytics = {
  track: (
    eventName: ProductAnalyticsEvent,
    options?: {
      entityType?: EventPayload['entity_type'];
      entityId?: string;
      properties?: Record<string, any>;
    }
  ) => {
    const payload: EventPayload = {
      event_name: eventName,
      organization_id: getOrganizationId() || 'org-default',
      session_id: getSessionId(),
      entity_type: options?.entityType,
      entity_id: options?.entityId,
      timestamp: new Date().toISOString(),
      source: typeof window !== 'undefined' && window.innerWidth < 768 ? 'mobile_web' : 'web',
      properties: sanitizeProperties(options?.properties),
    };

    queueEvent(payload);
  },

  // Dedicated Semantic Trackers
  trackDashboardViewed: (viewMode: string) => {
    analytics.track('dashboard_viewed', { properties: { view_mode: viewMode } });
  },

  trackLeadOpened: (leadId: string, source?: string) => {
    analytics.track('lead_opened', { entityType: 'lead', entityId: leadId, properties: { source } });
  },

  trackConversationOpened: (leadId: string, channel: string) => {
    analytics.track('conversation_opened', { entityType: 'conversation', entityId: leadId, properties: { channel } });
  },

  trackMessageSent: (channel: string, recipientId: string) => {
    analytics.track('message_sent', { entityType: 'conversation', entityId: recipientId, properties: { channel } });
  },

  trackPropertySearched: (query: string, filters: Record<string, any>, resultCount: number) => {
    analytics.track('property_searched', { properties: { query, filters, resultCount } });
  },

  trackPropertyShared: (propertyId: string, channel: string, recipientId?: string) => {
    analytics.track('property_shared', { entityType: 'property', entityId: propertyId, properties: { channel, recipientId } });
  },

  trackPropertyShortlisted: (propertyId: string) => {
    analytics.track('property_shortlisted', { entityType: 'property', entityId: propertyId });
  },

  trackOpportunityOpened: (opportunityId: string, stage?: string) => {
    analytics.track('opportunity_opened', { entityType: 'opportunity', entityId: opportunityId, properties: { stage } });
  },

  trackStageChanged: (opportunityId: string, fromStage: string, toStage: string, value?: number) => {
    analytics.track('stage_changed', { entityType: 'opportunity', entityId: opportunityId, properties: { fromStage, toStage, value } });
  },

  trackTaskCompleted: (taskId: string, type?: string) => {
    analytics.track('task_completed', { entityType: 'task', entityId: taskId, properties: { type } });
  },

  trackAppointmentCreated: (appointmentId: string, meetingType: string) => {
    analytics.track('appointment_created', { entityType: 'appointment', entityId: appointmentId, properties: { meetingType } });
  },

  trackSiteVisitCompleted: (siteVisitId: string, outcome: string) => {
    analytics.track('site_visit_completed', { entityType: 'appointment', entityId: siteVisitId, properties: { outcome } });
  },

  trackBookingCreated: (bookingId: string, unitId?: string, value?: number) => {
    analytics.track('booking_created', { entityType: 'booking', entityId: bookingId, properties: { unitId, value } });
  },

  trackAiActionApproved: (actionType: string, actionId?: string) => {
    analytics.track('ai_action_approved', { entityType: 'ai_action', entityId: actionId, properties: { actionType } });
  },

  trackAiActionRejected: (actionType: string, actionId?: string, reason?: string) => {
    analytics.track('ai_action_rejected', { entityType: 'ai_action', entityId: actionId, properties: { actionType, reason } });
  },

  trackGlobalSearch: (query: string, resultTypes: string[], resultCount: number) => {
    analytics.track('global_search_executed', { properties: { query, resultTypes, resultCount } });
  },
};
