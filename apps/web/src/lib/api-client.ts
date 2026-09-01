import { 
  Lead, LeadDetail, LeadListResponse, Broker, AdminStats, PipelineStage, LeadNote, LeadTag, Task, Conversation,
  CalendarSlotSearchResponse, CalendarBookingRequest, CalendarBookingResponse, MeetingPreparationBrief,
  MeetingNoShowPrediction, MeetingOutcome, ViewingItineraryResponse, CalendarConflict
} from '@/types';

export const getApiBase = (): string => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, '');
  }
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api/v1`;
  }
  return 'http://localhost:8000/api/v1';
};

export const getToken = (): string => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('beetlelabs_token') || '';
  }
  return '';
};

export const setToken = (token: string): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('beetlelabs_token', token);
  }
};

export const removeToken = (): void => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('beetlelabs_token');
  }
};

// Fallback Mock Data for resilient frontend rendering if backend API is offline
const MOCK_LEADS: Lead[] = [
  {
    id: 'demo-lead-1',
    broker_id: 'demo-broker-1',
    phone: '+919876543210',
    name: 'Rajesh Kumar',
    source: 'whatsapp_forward',
    score: 'hot',
    score_confidence: 0.94,
    budget_min: 4000000,
    budget_max: 5000000,
    property_type: '2bhk',
    transaction_type: 'buy',
    preferred_locations: ['Koramangala', 'HSR Layout'],
    timeline: '3_months',
    loan_status: 'not_started',
    status: 'qualified',
    stage_id: 'stg-contacted',
    stage_name: 'contacted',
    pipeline_stage: 'contacted',
    notes: [
      { id: 'note-1', content: 'Wants south-facing 2BHK in Koramangala. Flexible up to 55L if ready to move.', color_tag: 'blue', created_at: new Date().toISOString() }
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: 'demo-lead-2',
    broker_id: 'demo-broker-1',
    phone: '+919812345678',
    name: 'Priya Ananth',
    source: 'facebook',
    score: 'warm',
    score_confidence: 0.78,
    budget_min: 7500000,
    budget_max: 9000000,
    property_type: '3bhk',
    transaction_type: 'buy',
    preferred_locations: ['Indiranagar', 'Whitefield'],
    timeline: '3_months',
    loan_status: 'in_process',
    status: 'qualified',
    stage_id: 'stg-viewing',
    stage_name: 'viewing',
    pipeline_stage: 'viewing',
    notes: [
      { id: 'note-2', content: 'NRI client based in Dubai. Prefers gated community with pool.', color_tag: 'purple', created_at: new Date().toISOString() }
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  },
  {
    id: 'demo-lead-3',
    broker_id: 'demo-broker-1',
    phone: '+919988776655',
    name: 'Amitabh V',
    source: 'google',
    score: 'cold',
    score_confidence: 0.65,
    budget_min: 2000000,
    budget_max: 2500000,
    property_type: '1bhk',
    transaction_type: 'rent',
    preferred_locations: ['Electronic City'],
    timeline: '6_months',
    loan_status: 'not_needed',
    status: 'qualified',
    stage_id: 'stg-new',
    stage_name: 'new',
    pipeline_stage: 'new',
    notes: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
];

const MOCK_STAGES: PipelineStage[] = [
  { id: 'stg-new', broker_id: 'b1', name: 'new', order_index: 0, color: '#6B7280', is_default: 'true', created_at: '' },
  { id: 'stg-contacted', broker_id: 'b1', name: 'contacted', order_index: 1, color: '#3B82F6', is_default: 'true', created_at: '' },
  { id: 'stg-viewing', broker_id: 'b1', name: 'viewing', order_index: 2, color: '#EAB308', is_default: 'true', created_at: '' },
  { id: 'stg-negotiating', broker_id: 'b1', name: 'negotiating', order_index: 3, color: '#F97316', is_default: 'true', created_at: '' },
  { id: 'stg-won', broker_id: 'b1', name: 'closed_won', order_index: 4, color: '#22C55E', is_default: 'true', created_at: '' },
  { id: 'stg-lost', broker_id: 'b1', name: 'closed_lost', order_index: 5, color: '#EF4444', is_default: 'true', created_at: '' }
];

function formatFieldLabel(field: string): string {
  const parts = field.split('.').filter(p => p !== 'body');
  const last = parts[parts.length - 1] || field;
  return last
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function cleanValidationMessage(msg: string): string {
  return msg
    .replace(/^Value error,\s*/i, '')
    .replace(/^Assertion failed,\s*/i, '')
    .trim();
}

export function extractApiErrorMessage(errorText: string, status: number): string {
  try {
    const jsonErr = JSON.parse(errorText);

    // 1. Nested BeetleLabs error response: jsonErr.error.details.errors / jsonErr.details?.errors / list
    const errorsList =
      jsonErr.error?.details?.errors ||
      jsonErr.details?.errors ||
      (Array.isArray(jsonErr.details) ? jsonErr.details : null) ||
      (Array.isArray(jsonErr.detail) ? jsonErr.detail : null);

    if (Array.isArray(errorsList) && errorsList.length > 0) {
      const messages = errorsList.map((d: any) => {
        let fieldName = '';
        if (Array.isArray(d.loc)) {
          const filtered = d.loc.filter((l: any) => l !== 'body');
          if (filtered.length > 0) {
            fieldName = formatFieldLabel(String(filtered[filtered.length - 1]));
          }
        } else if (d.field) {
          fieldName = formatFieldLabel(String(d.field));
        }

        const rawMsg = d.msg || d.message || 'Invalid value';
        const msg = cleanValidationMessage(String(rawMsg));
        return fieldName ? `${fieldName}: ${msg}` : msg;
      });
      return messages.join('\n');
    }

    // 2. String detail
    if (typeof jsonErr.detail === 'string' && jsonErr.detail.trim()) {
      return jsonErr.detail.trim();
    }

    // 3. String message on error object or root
    if (typeof jsonErr.error?.message === 'string' && jsonErr.error.message.trim() && !jsonErr.error.message.toLowerCase().includes('validation failed')) {
      return jsonErr.error.message.trim();
    }
    if (typeof jsonErr.message === 'string' && jsonErr.message.trim() && !jsonErr.message.toLowerCase().includes('validation failed')) {
      return jsonErr.message.trim();
    }

    // 4. Fallback error string
    if (typeof jsonErr.error === 'string' && jsonErr.error.trim()) {
      return jsonErr.error.trim();
    }
  } catch {
    if (errorText && errorText.trim()) {
      return errorText.trim();
    }
  }

  return `Request failed with status ${status}`;
}

export async function fetcher<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const base = getApiBase();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${base}${cleanEndpoint}`;
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {})
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      const errMessage = extractApiErrorMessage(errorText, res.status);
      const apiError: any = new Error(errMessage);
      apiError.status = res.status;
      try {
        apiError.data = JSON.parse(errorText);
      } catch {}
      throw apiError;
    }
    
    return res.json();
  } catch (err: any) {
    if (typeof window !== 'undefined' && (err.name === 'TypeError' || (err.message && err.message.toLowerCase().includes('fetch')))) {
      console.warn(`[API Client Warning] Cannot reach API at ${url}:`, err.message || err);
      throw new Error('Authentication server unavailable. Please ensure backend services are active.');
    }
    console.warn(`[API Client Warning] Request failed (${endpoint}):`, err.message);
    throw err;
  }
}

export const api = {
  // Auth
  auth: {
    register: async (data: {
      email: string;
      password: string;
      phone: string;
      name: string;
      agency_name?: string;
      city?: string;
      whatsapp_number?: string;
    }) => {
      const res = await fetcher<{ access_token: string; token_type: string; broker: Broker }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          ...data,
          whatsapp_number: data.whatsapp_number || data.phone
        })
      });

      if (res.access_token) {
        setToken(res.access_token);
      }
      return res;
    },

    login: async (data: { email: string; password: string }) => {
      const res = await fetcher<{ access_token: string; token_type: string; broker: Broker }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data)
      });

      if (res.access_token) {
        setToken(res.access_token);
      }
      return res;
    },

    me: () => fetcher<Broker>('/auth/me'),

    getGoogleAuthUrl: (redirectUri?: string) => {
      const url = redirectUri ? `/auth/google/url?redirect_uri=${encodeURIComponent(redirectUri)}` : '/auth/google/url';
      return fetcher<{ auth_url: string; state: string }>(url);
    },

    exchangeGoogleCode: async (params: { code: string; state?: string; redirect_uri?: string }) => {
      const res = await fetcher<{ access_token: string; token_type: string; broker: Broker }>('/auth/google/exchange', {
        method: 'POST',
        body: JSON.stringify(params)
      });
      if (res.access_token) {
        setToken(res.access_token);
      }
      return res;
    },

    callback: async (data: {
      email: string;
      name: string;
      phone?: string;
      whatsapp_number?: string;
      agency_name?: string;
      city?: string;
    }) => {
      const res = await fetcher<{ access_token: string; token_type: string; broker: Broker }>('/auth/callback', {
        method: 'POST',
        body: JSON.stringify(data)
      });
      if (res.access_token) {
        setToken(res.access_token);
      }
      return res;
    },

    onboard: async (data: {
      name: string;
      phone: string;
      whatsapp_number: string;
      agency_name: string;
      city: string;
    }) => {
      return fetcher<Broker>('/auth/onboard', {
        method: 'POST',
        body: JSON.stringify(data)
      });
    },

    logout: () => {
      removeToken();
    }
  },

  // Brokers
  getBrokerProfile: () => fetcher<Broker>('/brokers/me').catch(() => ({
    id: 'demo-broker-1',
    email: 'broker@beetlelabs.ai',
    phone: '+919876543210',
    name: 'Authenticated Broker',
    agency_name: 'Unassigned Agency',
    city: 'Location Unspecified',
    whatsapp_number: '+919876543210',
    subscription_status: 'active',
    onboarding_status: 'ONBOARDED',
    created_at: new Date().toISOString()
  })),

  updateBrokerProfile: (data: Partial<Broker>) => fetcher<Broker>('/brokers/me', {
    method: 'PATCH',
    body: JSON.stringify(data)
  }),

  // Leads
  getLeads: (params?: { score?: string; stage?: string; source?: string; search?: string; page?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.score) query.append('score', params.score);
    if (params?.stage) query.append('stage', params.stage);
    if (params?.source) query.append('source', params.source);
    if (params?.search) query.append('search', params.search);
    if (params?.page) query.append('page', params.page.toString());
    if (params?.limit) query.append('limit', params.limit.toString());
    const qStr = query.toString() ? `?${query.toString()}` : '';

    return fetcher<LeadListResponse>(`/leads${qStr}`);
  },

  getLeadById: (id: string) => fetcher<LeadDetail>(`/leads/${id}`),

  createLead: (data: {
    phone: string;
    name?: string;
    source?: string;
    notes?: string;
    budget_min?: number;
    budget_max?: number;
    property_type?: string;
    transaction_type?: string;
    preferred_locations?: string[];
    timeline?: string;
    loan_status?: string;
  }) => 
    fetcher<Lead>('/leads', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateLead: (id: string, data: Partial<Lead>) =>
    fetcher<Lead>(`/leads/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),

  deleteLead: (id: string) =>
    fetcher<any>(`/leads/${id}`, { method: 'DELETE' }),

  updateLeadStatus: (id: string, status: string) => 
    fetcher<Lead>(`/leads/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    }),

  updateLeadStage: (id: string, stage: string) => 
    fetcher<any>(`/crm/services/leads/${id}/stage`, {
      method: 'PATCH',
      body: JSON.stringify({ stage_name: stage })
    }),

  getLeadNotes: (leadId: string) =>
    fetcher<LeadNote[]>(`/crm/services/leads/${leadId}/notes`),

  createLeadNote: (leadId: string, content: string, colorTag: string = 'blue') => 
    fetcher<LeadNote>(`/crm/services/leads/${leadId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ content, color_tag: colorTag })
    }),

  deleteLeadNote: (noteId: string) =>
    fetcher<any>(`/crm/services/notes/${noteId}`, { method: 'DELETE' }),

  // Tags
  getTags: () => fetcher<LeadTag[]>('/crm/services/tags'),

  createTag: (name: string, color: string = '#3B82F6') =>
    fetcher<LeadTag>('/crm/services/tags', {
      method: 'POST',
      body: JSON.stringify({ name, color })
    }),

  assignTagToLead: (leadId: string, tagId: string) =>
    fetcher<any>(`/crm/services/leads/${leadId}/tags/${tagId}`, {
      method: 'POST',
      body: JSON.stringify({ tag_id: tagId })
    }),

  removeTagFromLead: (leadId: string, tagId: string) =>
    fetcher<any>(`/crm/services/leads/${leadId}/tags/${tagId}`, { method: 'DELETE' }),

  getStages: () => fetcher<any[]>('/crm/services/stages'),

  // Tasks
  getTasks: (params?: { status?: string; lead_id?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.status) query.append('status', params.status);
    if (params?.lead_id) query.append('lead_id', params.lead_id);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    const qStr = query.toString() ? `?${query.toString()}` : '';
    return fetcher<any[]>(`/crm/services/tasks${qStr}`);
  },

  createTask: (data: { lead_id?: string; title: string; description?: string; due_at?: string; priority?: string }) =>
    fetcher<any>('/crm/services/tasks', {
      method: 'POST',
      body: JSON.stringify(data)
    }),

  updateTask: (taskId: string, data: { title?: string; description?: string; due_at?: string; priority?: string; status?: string; lead_id?: string }) =>
    fetcher<any>(`/crm/services/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }),

  completeTask: (taskId: string) =>
    fetcher<any>(`/crm/services/tasks/${taskId}/complete`, { method: 'PATCH' }),

  updateTaskStatus: (taskId: string, status: 'pending' | 'completed' | 'cancelled' | 'in_progress') =>
    fetcher<any>(`/crm/services/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    }),

  deleteTask: (taskId: string) =>
    fetcher<{ status: string; id: string }>(`/crm/services/tasks/${taskId}`, { method: 'DELETE' }),

  // Subscription & Profile top-level aliases
  subscribe: (planId: string) => fetcher<{ subscription_id: string; razorpay_subscription_id: string; short_url: string; amount: number; currency: string }>('/billing/subscribe', {
    method: 'POST',
    body: JSON.stringify({ plan_id: planId })
  }),

  triggerQualification: (id: string, force: boolean = false) => 
    fetcher<any>('/scoring/qualify', {
      method: 'POST',
      body: JSON.stringify({ lead_id: id, force })
    }).catch(() => ({ status: 'success', score: 'hot', confidence: 0.9 })),

  // Follow-ups
  getFollowUps: (leadId: string) => fetcher<any[]>(`/leads/${leadId}/follow-ups`),
  cancelFollowUps: (leadId: string) => fetcher<any>(`/leads/${leadId}/follow-ups/cancel`, { method: 'POST' }),

  // AI Prospect Intelligence (Part 21.2A)
  prospectIntelligence: {
    getProfile: (leadId: string) => fetcher<any>(`/leads/${leadId}/intelligence`),
    analyze: (leadId: string, forceRefresh: boolean = false) =>
      fetcher<any>(`/leads/${leadId}/intelligence/analyze`, {
        method: 'POST',
        body: JSON.stringify({ force_refresh: forceRefresh })
      }),
    refresh: (leadId: string) =>
      fetcher<any>(`/leads/${leadId}/intelligence/refresh`, { method: 'POST' }),
    getProperties: (leadId: string) =>
      fetcher<any[]>(`/leads/${leadId}/intelligence/properties`),
    getBrief: (leadId: string) =>
      fetcher<any>(`/leads/${leadId}/intelligence/brief`),
    override: (leadId: string, overrides: Record<string, any>, reason?: string) =>
      fetcher<any>(`/leads/${leadId}/intelligence/override`, {
        method: 'POST',
        body: JSON.stringify({ overrides, reason })
      })
  },

  // AI Property Matching & Recommendations (Part 21.3)
  recommendations: {
    getRecommendations: (leadId: string, topK: number = 5) =>
      fetcher<any>(`/leads/${leadId}/recommendations?top_k=${topK}`),
    generate: (leadId: string, topK: number = 5, includeTradeoffs: boolean = true) =>
      fetcher<any>(`/leads/${leadId}/recommendations/generate`, {
        method: 'POST',
        body: JSON.stringify({ lead_id: leadId, top_k: topK, include_tradeoffs: includeTradeoffs })
      }),
    refresh: (leadId: string) =>
      fetcher<any>(`/leads/${leadId}/recommendations/refresh`, { method: 'POST' }),
    getById: (leadId: string, recommendationId: string) =>
      fetcher<any>(`/leads/${leadId}/recommendations/${recommendationId}`),
    recordFeedback: (leadId: string, recommendationId: string, propertyId: string, action: string, feedbackReason?: string) =>
      fetcher<any>(`/leads/${leadId}/recommendations/${recommendationId}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ property_id: propertyId, action, feedback_reason: feedbackReason })
      }),
    compare: (propertyIds: string[], leadId?: string) =>
      fetcher<any>('/recommendations/compare', {
        method: 'POST',
        body: JSON.stringify({ property_ids: propertyIds, lead_id: leadId })
      }),
    simulate: (leadId: string, budgetDeltaPct: number = 0.0) =>
      fetcher<any>('/recommendations/simulate', {
        method: 'POST',
        body: JSON.stringify({ lead_id: leadId, budget_delta_pct: budgetDeltaPct })
      }),
    getMatchingLeads: (propertyId: string, limit: number = 10) =>
      fetcher<any>(`/recommendations/properties/${propertyId}/matching-leads?limit=${limit}`)
  },

  // Properties
  properties: {
    list: (params?: { property_type?: string; search?: string; page?: number; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.property_type && params.property_type !== 'all') q.append('property_type', params.property_type);
      if (params?.search) q.append('search', params.search);
      if (params?.page) q.append('page', params.page.toString());
      if (params?.limit) q.append('limit', params.limit.toString());
      const qStr = q.toString() ? `?${q.toString()}` : '';
      return fetcher<any>(`/properties${qStr}`);
    },
    getById: (id: string) => fetcher<any>(`/properties/${id}`),
    create: (data: any) =>
      fetcher<any>('/properties', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    delete: (id: string) =>
      fetcher<any>(`/properties/${id}`, { method: 'DELETE' }),
    getValuation: (id: string, params?: { price?: number; area_sqft?: number; locality?: string }) => {
      const q = new URLSearchParams();
      if (params?.price) q.append('price', params.price.toString());
      if (params?.area_sqft) q.append('area_sqft', params.area_sqft.toString());
      if (params?.locality) q.append('locality', params.locality);
      const qStr = q.toString() ? `?${q.toString()}` : '';
      return fetcher<any>(`/properties/${id}/valuation${qStr}`);
    }
  },

  // Deals & Transaction Lifecycle Management
  deals: {
    list: (params?: { stage?: string; page?: number; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.stage && params.stage !== 'all') q.append('stage', params.stage);
      if (params?.page) q.append('page', params.page.toString());
      if (params?.limit) q.append('limit', params.limit.toString());
      const qStr = q.toString() ? `?${q.toString()}` : '';
      return fetcher<any>(`/transactions${qStr}`);
    },
    create: (data: any) =>
      fetcher<any>('/transactions', {
        method: 'POST',
        body: JSON.stringify(data)
      }),
    advanceStage: (dealId: string, targetStage: string) =>
      fetcher<any>(`/transactions/${dealId}/advance-stage?target_stage=${targetStage}`, {
        method: 'POST'
      }),
    delete: (dealId: string) =>
      fetcher<any>(`/transactions/${dealId}`, { method: 'DELETE' }),
    getRiskAnalysis: (dealId: string, stage?: string, daysInStage?: number) => {
      const q = new URLSearchParams();
      if (stage) q.append('stage', stage);
      if (daysInStage) q.append('days_in_stage', daysInStage.toString());
      const qStr = q.toString() ? `?${q.toString()}` : '';
      return fetcher<any>(`/transactions/${dealId}/ai/risk-analysis${qStr}`);
    }
  },

  // Inbox & Unified Timeline
  inbox: {
    getConversations: (leadId: string) =>
      fetcher<any>(`/leads/${leadId}/conversations`).catch(() => []),
    sendMessage: (data: { lead_id: string; channel: string; content: string }) =>
      fetcher<any>('/communication/send', {
        method: 'POST',
        body: JSON.stringify(data)
      })
  },

  // Workflows & Visual Automation Engine
  workflows: {
    list: () => fetcher<any>('/workflows').catch(() => []),
    generateAI: (prompt: string) =>
      fetcher<any>('/workflows/generate', {
        method: 'POST',
        body: JSON.stringify({ prompt })
      })
  },

  // Simulator
  simulateWhatsApp: (data: { lead_phone: string; lead_name?: string; message: string }) =>
    fetcher<any>('/whatsapp/simulate', {
      method: 'POST',
      body: JSON.stringify(data)
    }).catch(() => ({
      lead_id: 'demo-lead-1',
      reply_message: 'Thank you! We received your details on budget and preferred location.',
      lead_status: 'qualified',
      score: 'hot'
    })),

  // Admin Stats
  getAdminStats: () => fetcher<AdminStats>('/admin/stats'),

  // Billing & Payments
  billing: {
    getPlans: () => fetcher<any[]>('/billing/plans').catch(() => []),

    createOrder: (planId: string, idempotencyKey?: string) =>
      fetcher<{
        order_id: string;
        razorpay_order_id: string;
        key_id: string;
        amount: number;
        currency: string;
        plan_id: string;
        plan_name: string;
        status: string;
      }>('/billing/orders', {
        method: 'POST',
        body: JSON.stringify({ plan_id: planId, idempotency_key: idempotencyKey })
      }),

    verifyPayment: (data: {
      razorpay_order_id: string;
      razorpay_payment_id: string;
      razorpay_signature: string;
    }) =>
      fetcher<{
        success: boolean;
        status: string;
        order_id: string;
        transaction_id: string;
        razorpay_payment_id: string;
        razorpay_order_id: string;
        amount: number;
        currency: string;
        plan_id: string;
        message: string;
      }>('/billing/orders/verify', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    getOrders: () => fetcher<any[]>('/billing/orders').catch(() => []),

    getOrder: (orderId: string) => fetcher<any>(`/billing/orders/${orderId}`),

    getTransactions: () => fetcher<any[]>('/billing/transactions').catch(() => []),

    requestRefund: (data: {
      razorpay_payment_id: string;
      amount?: number;
      reason?: string;
      idempotency_key?: string;
    }) =>
      fetcher<any>('/billing/refunds', {
        method: 'POST',
        body: JSON.stringify(data)
      }),

    getRefunds: () => fetcher<any[]>('/billing/refunds').catch(() => []),

    reconcile: (orderId: string) =>
      fetcher<any>(`/billing/reconcile/${orderId}`, {
        method: 'POST'
      }),

    subscribe: (planId: string) => fetcher<{ subscription_id: string; razorpay_subscription_id: string; short_url: string; amount: number; currency: string }>('/billing/subscribe', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId })
    }),

    getStatus: () => fetcher<{ subscription_status: string; subscription_plan?: string; trial_ends_at: string; trial_days_remaining: number; razorpay_customer_id?: string; razorpay_subscription_id?: string }>('/billing/status')
  },

  // Predictive Intelligence
  predictive: {
    getDashboard: () => fetcher<{
      quarter: string;
      projected_revenue: number;
      confidence_interval: { lower_bound: number; upper_bound: number };
      pipeline_health_score: number;
      deals_count: number;
      calculation_basis: string;
    }>('/predictive/dashboard'),
    getLeadIntelligence: (leadId: string) => fetcher<{
      lead_id: string;
      model_version: string;
      conversion_probability_pct: number;
      deal_close_probability_pct: number;
      churn_risk_pct: number;
      estimated_lifetime_value: number;
      best_followup_window: string;
      confidence_interval: string;
      feature_attributions: Array<{ feature: string; impact: number; explanation: string }>;
    }>(`/predictive/leads/${leadId}`)
  },

  // Executive BI & Tableau AI
  bi: {
    getExecutiveSummary: () => fetcher<{
      revenue_ytd: number;
      pipeline_total_value: number;
      avg_customer_acquisition_cost: number;
      marketing_campaign_roi_pct: number;
      conversion_rate_overall_pct: number;
      anomalies: Array<{
        id: string;
        severity: string;
        metric_name: string;
        description: string;
        root_cause: string;
        action: string;
      }>;
    }>('/bi/executive-summary'),
    askQuery: (query: string) => fetcher<{
      query: string;
      chart_type: string;
      explanation_markdown: string;
      data_points: Array<{ category: string; count: number }>;
    }>('/bi/ask-nl-query', {
      method: 'POST',
      body: JSON.stringify({ query })
    })
  },

  // Copilot AI
  copilotQuery: (
    query: string,
    routePath: string = '/dashboard',
    history?: Array<{ sender: 'user' | 'copilot'; text: string }>,
    activeEntityId?: string
  ) =>
    fetcher<{
      query: string;
      context_type: string;
      summary: string;
      reasoning?: string;
      answer_markdown: string;
      rich_cards?: Array<{
        type: string;
        title: string;
        subtitle?: string;
        details?: string;
        badge?: string;
        badge_color?: string;
      }>;
      action_buttons?: Array<{
        label: string;
        action_type: string;
        payload?: any;
      }>;
      confidence_score: number;
      citations?: string[];
      suggested_followups?: string[];
      executed_tools?: any[];
    }>('/copilot/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        route_path: routePath,
        history,
        active_entity_id: activeEntityId
      })
    }),

  executeCopilotAction: (action_type: string, target_id?: string, payload?: any) =>
    fetcher<{
      success: boolean;
      action_type: string;
      message: string;
      redirect_url?: string;
      [key: string]: any;
    }>('/copilot/actions/execute', {
      method: 'POST',
      body: JSON.stringify({
        action_type,
        target_id,
        payload
      })
    }),

  getCopilotSuggestedActions: (routePath: string = '/dashboard') =>
    fetcher<{
      route_path: string;
      context_type: string;
      suggested_actions: string[];
    }>(`/copilot/suggested-actions?route_path=${encodeURIComponent(routePath)}`),

  // ─── Knowledge Intelligence Platform ────────────────────────────────────────
  knowledge: {
    // Documents
    listDocuments: (params?: {
      status?: string;
      knowledge_type?: string;
      language?: string;
      project_id?: string;
      page?: number;
      limit?: number;
    }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.knowledge_type) q.set('knowledge_type', params.knowledge_type);
      if (params?.language) q.set('language', params.language);
      if (params?.project_id) q.set('project_id', params.project_id);
      if (params?.page) q.set('page', String(params.page));
      if (params?.limit) q.set('limit', String(params.limit));
      return fetcher<{
        documents: KnowledgeDocument[];
        total: number;
        page: number;
        limit: number;
        total_pages: number;
      }>(`/knowledge/documents?${q.toString()}`);
    },

    getDocument: (id: string) =>
      fetcher<KnowledgeDocument>(`/knowledge/documents/${id}`),

    uploadDocument: (formData: FormData) =>
      fetcher<{ document_id: string; version_id: string; status: string; job_id?: string; message: string; is_duplicate: boolean }>(
        '/knowledge/documents',
        { method: 'POST', body: formData }
      ),

    updateDocument: (id: string, data: Partial<KnowledgeDocumentUpdate>) =>
      fetcher<KnowledgeDocument>(`/knowledge/documents/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),

    deleteDocument: (id: string, reason?: string) =>
      fetcher<{ message: string; deletion_job_id: string }>(
        `/knowledge/documents/${id}?reason=${reason || 'admin_delete'}`,
        { method: 'DELETE' }
      ),

    publishDocument: (id: string) =>
      fetcher<{ message: string; document_id: string; status: string }>(
        `/knowledge/documents/${id}/publish`,
        { method: 'POST' }
      ),

    reindexDocument: (id: string) =>
      fetcher<{ message: string; document_id: string }>(
        `/knowledge/documents/${id}/reindex`,
        { method: 'POST' }
      ),

    archiveDocument: (id: string) =>
      fetcher<{ message: string; document_id: string }>(
        `/knowledge/documents/${id}/archive`,
        { method: 'POST' }
      ),

    // Search
    search: (req: {
      query: string;
      knowledge_types?: string[];
      project_id?: string;
      property_id?: string;
      language?: string;
      top_k?: number;
      rerank_top_n?: number;
      channel?: string;
    }) =>
      fetcher<{
        results: KnowledgeSearchResult[];
        query: string;
        total_vector_hits: number;
        total_keyword_hits: number;
        total_results: number;
        retrieval_latency_ms: number;
        reranking_latency_ms: number;
      }>('/knowledge/search', {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    // Chunks
    getChunks: (documentId: string) =>
      fetcher<KnowledgeChunk[]>(`/knowledge/chunks/${documentId}`),

    // Facts
    getFacts: (documentId: string) =>
      fetcher<KnowledgeFact[]>(`/knowledge/facts/${documentId}`),

    verifyFact: (factId: string, decision: 'VERIFIED' | 'REJECTED', notes?: string) =>
      fetcher<KnowledgeFact>(`/knowledge/verify/${factId}`, {
        method: 'POST',
        body: JSON.stringify({ decision, notes }),
      }),

    // Conflicts
    listConflicts: (params?: { resolution_status?: string; project_id?: string }) => {
      const q = new URLSearchParams();
      if (params?.resolution_status) q.set('resolution_status', params.resolution_status);
      if (params?.project_id) q.set('project_id', params.project_id);
      return fetcher<KnowledgeConflict[]>(`/knowledge/conflicts?${q.toString()}`);
    },

    resolveConflict: (conflictId: string, winningFactId: string, notes?: string) =>
      fetcher<KnowledgeConflict>(`/knowledge/conflicts/${conflictId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ winning_fact_id: winningFactId, resolution_notes: notes }),
      }),

    // Collections
    listCollections: () => fetcher<KnowledgeCollection[]>('/knowledge/collections'),

    createCollection: (data: { name: string; description?: string; knowledge_type?: string; project_id?: string; language?: string }) =>
      fetcher<KnowledgeCollection>('/knowledge/collections', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    // Feedback
    submitFeedback: (data: {
      query_id: string;
      feedback_type: 'POSITIVE' | 'NEGATIVE' | 'HALLUCINATION' | 'OUTDATED' | 'INCOMPLETE' | 'OFF_TOPIC';
      notes?: string;
      document_ids_flagged?: string[];
    }) =>
      fetcher<{ message: string; feedback_id: string }>('/knowledge/feedback', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    // Freshness policies
    listFreshnessPolicies: () => fetcher<KnowledgeFreshnessPolicy[]>('/knowledge/freshness/policies'),

    upsertFreshnessPolicy: (data: {
      knowledge_type: string;
      max_age_days: number;
      warn_at_days: number;
      auto_expire?: boolean;
    }) =>
      fetcher<KnowledgeFreshnessPolicy>('/knowledge/freshness/policies', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    // Processing jobs
    listJobs: (params?: { status?: string; document_id?: string }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.document_id) q.set('document_id', params.document_id);
      return fetcher<KnowledgeJob[]>(`/knowledge/jobs?${q.toString()}`);
    },

    // Full reindex
    fullReindex: () =>
      fetcher<{ message: string; documents_queued: number }>('/knowledge/reindex/full', {
        method: 'POST',
      }),

    // Health
    getHealth: () =>
      fetcher<{
        status: string;
        total_documents: number;
        published_documents: number;
        indexed_chunks: number;
        failed_documents: number;
        open_conflicts: number;
        embedding_provider: string;
        vector_store_provider: string;
        checked_at: string;
      }>('/knowledge/health'),
  },

  // ─── Calendar, Meeting & Scheduling Intelligence Engine ─────────────────────
  calendar: {
    searchSlots: (req: {
      lead_id: string;
      meeting_type?: string;
      property_id?: string;
      duration_minutes?: number;
      search_days_ahead?: number;
      customer_timezone?: string;
    }) =>
      fetcher<CalendarSlotSearchResponse>('/calendar/slots/search', {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    bookMeeting: (req: CalendarBookingRequest) =>
      fetcher<CalendarBookingResponse>('/calendar/book', {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    getBooking: (meetingId: string) =>
      fetcher<CalendarBookingResponse>(`/calendar/bookings/${meetingId}`),

    rescheduleBooking: (meetingId: string, req: { new_slot_start_utc: string; reason?: string }) =>
      fetcher<CalendarBookingResponse>(`/calendar/bookings/${meetingId}/reschedule`, {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    cancelBooking: (meetingId: string, req: { reason: string; cancelled_by?: string }) =>
      fetcher<{ status: string; meeting_id: string }>(`/calendar/bookings/${meetingId}/cancel`, {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    calculateItinerary: (req: {
      lead_id: string;
      broker_id?: string;
      property_ids: string[];
      start_date_utc: string;
    }) =>
      fetcher<ViewingItineraryResponse>('/calendar/itineraries', {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    getBrief: (meetingId: string) =>
      fetcher<MeetingPreparationBrief>(`/calendar/bookings/${meetingId}/brief`),

    getNoShowPrediction: (meetingId: string) =>
      fetcher<MeetingNoShowPrediction>(`/calendar/bookings/${meetingId}/no-show`),

    recordOutcome: (meetingId: string, req: {
      outcome_category: string;
      buyer_interest_level?: number;
      detailed_feedback?: string;
      agreed_next_step?: string;
      next_follow_up_date?: string;
      agent_notes?: string;
    }) =>
      fetcher<MeetingOutcome>(`/calendar/bookings/${meetingId}/outcome`, {
        method: 'POST',
        body: JSON.stringify(req),
      }),

    listConflicts: () =>
      fetcher<CalendarConflict[]>('/calendar/conflicts'),

    getGoogleConnectUrl: (redirectUri?: string) =>
      fetcher<{ auth_url: string; state: string }>(
        `/calendar/google/connect${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ''}`
      ),

    exchangeGoogleCallback: (code: string, state: string, redirectUri?: string) =>
      fetcher<{ success: boolean; account_email: string; provider: string; is_connected: boolean }>(
        '/calendar/google/callback',
        {
          method: 'POST',
          body: JSON.stringify({ code, state, redirect_uri: redirectUri }),
        }
      ),

    getGoogleStatus: () =>
      fetcher<{
        is_connected: boolean;
        provider: string;
        account_email: string | null;
        status: string;
        connected_at: string | null;
        last_sync_at: string | null;
      }>('/calendar/google/status'),

    disconnectGoogle: () =>
      fetcher<{ success: boolean; is_connected: boolean; message: string }>(
        '/calendar/google/disconnect',
        { method: 'POST' }
      ),

    reauthorizeGoogle: (redirectUri?: string) =>
      fetcher<{ auth_url: string; state: string }>('/calendar/google/reauthorize', {
        method: 'POST',
        body: JSON.stringify({ redirect_uri: redirectUri }),
      }),
  },

  // ─── Part 21.4.1 — AI Lead Qualification Domain Foundation ──────────────────
  qualification: {
    getLeadQualification: (leadId: string) =>
      fetcher<QualificationSnapshot>(`/leads/${leadId}/qualification`),

    getLeadFacts: (leadId: string, includeSuperseded: boolean = false) =>
      fetcher<QualificationFact[]>(`/leads/${leadId}/qualification/facts?include_superseded=${includeSuperseded}`),

    getLeadConflicts: (leadId: string) =>
      fetcher<QualificationConflict[]>(`/leads/${leadId}/qualification/conflicts`),

    getLeadHistory: (leadId: string, limit: number = 50) =>
      fetcher<QualificationAuditEvent[]>(`/leads/${leadId}/qualification/history?limit=${limit}`),

    listPolicies: () =>
      fetcher<QualificationPolicy[]>('/qualification/policies'),

    recordFact: (leadId: string, data: {
      field_name: string;
      raw_value?: string;
      normalized_value?: any;
      value_category?: string;
      value_type?: string;
      source_type?: string;
      source_id?: string;
      confidence?: number;
    }) =>
      fetcher<QualificationFact>(`/leads/${leadId}/qualification/facts`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    resolveConflict: (leadId: string, conflictId: string, data: {
      selected_fact_id?: string;
      resolution_reason: string;
    }) =>
      fetcher<QualificationConflict>(`/leads/${leadId}/qualification/conflicts/${conflictId}/resolve`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    applyHumanOverride: (leadId: string, data: {
      target_state: string;
      reason: string;
      notes?: string;
    }) =>
      fetcher<QualificationSnapshot>(`/leads/${leadId}/qualification/override`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    extractQualification: (leadId: string, data?: {
      message_id?: string;
      include_full_history?: boolean;
      force_refresh?: boolean;
    }) =>
      fetcher<QualificationExtractionSummary>(`/leads/${leadId}/qualification/extract`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),

    evaluateQualification: (leadId: string) =>
      fetcher<QualificationEvaluationResult>(`/leads/${leadId}/qualification/evaluate`, {
        method: 'POST',
      }),

    getMissingInfo: (leadId: string) =>
      fetcher<QualificationMissingInfo>(`/leads/${leadId}/qualification/missing`),

    startConversation: (leadId: string, channel: string = 'webchat', forceRestart: boolean = false) =>
      fetcher<QualificationConversationResponse>(`/leads/${leadId}/qualification/conversation/start`, {
        method: 'POST',
        body: JSON.stringify({ channel, force_restart: forceRestart }),
      }),

    sendMessage: (leadId: string, message: string, channel: string = 'webchat') =>
      fetcher<QualificationConversationResponse>(`/leads/${leadId}/qualification/conversation/message`, {
        method: 'POST',
        body: JSON.stringify({ message, channel }),
      }),

    getConversationState: (leadId: string) =>
      fetcher<QualificationConversationStateData>(`/leads/${leadId}/qualification/conversation/state`),
  },

  // ─── Part 21.5 — AI Sales Action & Follow-Up Engine ───────────────────────
  salesAction: {
    getNextAction: (leadId: string) =>
      fetcher<SalesActionDecisionData>(`/leads/${leadId}/sales-actions/next`),

    getHistory: (leadId: string) =>
      fetcher<SalesActionDecisionData[]>(`/leads/${leadId}/sales-actions`),

    evaluate: (leadId: string, data?: { trigger_event?: string; target_property_id?: string; force_refresh?: boolean }) =>
      fetcher<SalesActionDecisionData>(`/leads/${leadId}/sales-actions/evaluate`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      }),

    approve: (leadId: string, actionId: string, customMessage?: string) =>
      fetcher<SalesActionDecisionData>(`/leads/${leadId}/sales-actions/${actionId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ custom_message_body: customMessage }),
      }),

    execute: (leadId: string, actionId: string, customMessage?: string) =>
      fetcher<SalesActionExecutionResultData>(`/leads/${leadId}/sales-actions/${actionId}/execute`, {
        method: 'POST',
        body: JSON.stringify({ custom_message_body: customMessage }),
      }),

    cancel: (leadId: string, actionId: string) =>
      fetcher<{ action_id: string; status: string; lead_id: string }>(`/leads/${leadId}/sales-actions/${actionId}/cancel`, {
        method: 'POST',
      }),

    getFollowUpState: (leadId: string) =>
      fetcher<FollowUpStateData>(`/leads/${leadId}/follow-up/state`),

    pauseFollowUp: (leadId: string) =>
      fetcher<FollowUpStateData>(`/leads/${leadId}/follow-up/pause`, {
        method: 'POST',
      }),

    resumeFollowUp: (leadId: string) =>
      fetcher<FollowUpStateData>(`/leads/${leadId}/follow-up/resume`, {
        method: 'POST',
      }),
  },
};

export interface SalesBriefData {
  lead_id: string;
  lead_name: string;
  lead_intent: string;
  budget_range: string;
  preferred_location: string;
  property_type: string;
  timeline: string;
  financing: string;
  matched_properties_count: number;
  handoff_reason: string;
  recent_conversation_summary: string;
  recommended_human_action: string;
}

export interface SalesActionDecisionData {
  action_id: string;
  lead_id: string;
  organization_id: string;
  action_type: string;
  status: string;
  reason: string;
  priority: number;
  confidence: number;
  recommended_channel: string;
  automation_allowed: boolean;
  human_approval_required: boolean;
  blocked_reason?: string | null;
  scheduled_for_utc?: string | null;
  customer_timezone: string;
  required_facts: string[];
  matched_properties_count: number;
  matched_properties_summary?: Array<{
    property_id: string;
    title: string;
    price: number;
    currency: string;
    bedrooms?: number;
    location: string;
    match_score?: number;
  }> | null;
  draft_message_body?: string | null;
  draft_message_subject?: string | null;
  sales_brief?: SalesBriefData | null;
  source_evidence?: Record<string, any>;
  policy_version: string;
  evaluated_at: string;
  next_evaluation_at?: string | null;
}

export interface SalesActionExecutionResultData {
  action_id: string;
  lead_id: string;
  organization_id: string;
  action_type: string;
  status: string;
  channel: string;
  provider: string;
  provider_message_id?: string | null;
  executed_at: string;
  details: Record<string, any>;
}

export interface FollowUpStateData {
  lead_id: string;
  organization_id: string;
  is_paused: boolean;
  is_dormant: boolean;
  is_suppressed: boolean;
  suppression_reason?: string | null;
  fatigue_score: number;
  consecutive_no_replies: number;
  total_messages_sent: number;
  last_contacted_at?: string | null;
  last_responded_at?: string | null;
  active_scheduled_actions: Array<{
    id: string;
    channel: string;
    reason_type: string;
    status: string;
    scheduled_for_utc?: string | null;
  }>;
}

// ─── Knowledge Type Definitions ───────────────────────────────────────────────

export interface KnowledgeDocument {
  id: string;
  organization_id: string;
  title: string;
  description?: string;
  file_name?: string;
  file_size_bytes: number;
  mime_type?: string;
  file_type?: string;
  status: string;
  knowledge_type: string;
  language: string;
  country?: string;
  currency?: string;
  visibility: string;
  ai_allowed: boolean;
  customer_facing_allowed: boolean;
  effective_at?: string;
  expires_at?: string;
  published_at?: string;
  total_pages: number;
  total_chunks: number;
  total_facts: number;
  total_conflicts: number;
  ocr_used: boolean;
  ocr_confidence?: number;
  project_id?: string;
  property_id?: string;
  collection_id?: string;
  uploaded_by?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  processing_error?: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentUpdate {
  title?: string;
  description?: string;
  knowledge_type?: string;
  visibility?: string;
  ai_allowed?: boolean;
  customer_facing_allowed?: boolean;
  language?: string;
  effective_at?: string;
  expires_at?: string;
}

export interface KnowledgeSearchResult {
  chunk_id: string;
  document_id: string;
  text: string;
  score: number;
  rank_position: number;
  retrieval_method: string;
  metadata: Record<string, any>;
}

export interface KnowledgeChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  chunk_type: string;
  content: string;
  heading?: string;
  section?: string;
  page_number?: number;
  knowledge_type: string;
  language: string;
  token_count: number;
  is_expired: boolean;
  created_at: string;
}

export interface KnowledgeFact {
  id: string;
  document_id: string;
  chunk_id?: string;
  fact_type: string;
  value_text?: string;
  value_numeric?: number;
  currency?: string;
  unit?: string;
  confidence: number;
  extraction_method: string;
  verification_status: string;
  verified_by?: string;
  verified_at?: string;
  rejection_reason?: string;
  created_at: string;
}

export interface KnowledgeConflict {
  id: string;
  organization_id: string;
  fact_type: string;
  fact_a_id: string;
  fact_a_value?: string;
  fact_a_document_id?: string;
  fact_a_confidence: number;
  fact_b_id: string;
  fact_b_value?: string;
  fact_b_document_id?: string;
  fact_b_confidence: number;
  resolution_status: string;
  resolved_by?: string;
  resolved_at?: string;
  resolution_notes?: string;
  created_at: string;
}

export interface KnowledgeCollection {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  knowledge_type?: string;
  project_id?: string;
  language: string;
  is_active: boolean;
  document_count: number;
  created_at: string;
}

export interface KnowledgeFreshnessPolicy {
  id: string;
  organization_id: string;
  knowledge_type: string;
  max_age_days: number;
  warn_at_days: number;
  auto_expire: boolean;
  auto_publish: boolean;
  is_active: boolean;
  created_at: string;
}

export interface KnowledgeJob {
  id: string;
  document_id: string;
  job_type: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  retry_count: number;
  last_error?: string;
  result_summary: Record<string, any>;
  created_at: string;
}

export interface QualificationFact {
  id: string;
  organization_id: string;
  lead_id: string;
  field_name: string;
  raw_value?: string;
  normalized_value?: any;
  value_category: string;
  value_type: string;
  source_type: string;
  source_id?: string;
  confidence: number;
  observed_at: string;
  extracted_by?: string;
  model_version?: string;
  evidence_text_reference?: string;
  status: string;
  supersedes_fact_id?: string;
  created_at: string;
  updated_at: string;
}

export interface QualificationConflict {
  id: string;
  organization_id: string;
  lead_id: string;
  field_name: string;
  existing_fact_id?: string;
  conflicting_fact_id?: string;
  status: string;
  resolved_by?: string;
  resolution_reason?: string;
  resolved_fact_id?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
}

export interface QualificationPolicy {
  id: string;
  organization_id?: string;
  policy_name: string;
  policy_version: string;
  country_code?: string;
  market_id?: string;
  transaction_type?: string;
  property_type?: string;
  required_fields: string[];
  recommended_fields: string[];
  optional_fields: string[];
  min_completeness_for_qualified: number;
  min_confidence_for_qualified: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface QualificationAuditEvent {
  id: string;
  organization_id: string;
  lead_id: string;
  actor_type: string;
  actor_id?: string;
  event_type: string;
  previous_state?: string;
  new_state?: string;
  reason?: string;
  correlation_id?: string;
  details_json: Record<string, any>;
  created_at: string;
}

export interface QualificationSnapshot {
  id?: string;
  organization_id: string;
  lead_id: string;
  state: string;
  intent: string;
  buyer_type: string;
  budget_min?: number;
  budget_max?: number;
  budget_currency?: string;
  location: string;
  property_type: string;
  bedrooms?: number;
  timeline: string;
  financing: string;
  completeness_score: number;
  confidence_score: number;
  missing_fields: string[];
  conflicting_fields: string[];
  policy_version: string;
  summary_notes?: string;
  generated_at: string;
}

export interface QualificationExtractionSummary {
  lead_id: string;
  organization_id: string;
  facts_extracted_count: number;
  facts_persisted_count: number;
  conflicts_detected_count: number;
  snapshot: QualificationSnapshot;
  extracted_facts: QualificationFact[];
  open_conflicts: QualificationConflict[];
  processing_time_ms: number;
}

export interface QualificationEvaluationResult {
  lead_id: string;
  organization_id: string;
  qualification_state: string;
  completeness_score: number;
  confidence_score: number;
  policy_version: string;
  missing_required_information: string[];
  missing_recommended_information: string[];
  blocking_conflicts: string[];
  next_best_question_field?: string | null;
  next_best_question?: string | null;
  snapshot: QualificationSnapshot;
  evaluated_at: string;
}

export interface QualificationMissingInfo {
  lead_id: string;
  organization_id: string;
  missing_required_fields: string[];
  missing_recommended_fields: string[];
  next_best_question_field?: string | null;
  next_best_question?: string | null;
  field_questions: Record<string, string>;
}

export interface QualificationConversationResponse {
  lead_id: string;
  organization_id: string;
  conversation_state: string;
  qualification_state: string;
  question?: string | null;
  question_field?: string | null;
  is_fallback_question: boolean;
  missing_fields: string[];
  completeness_score: number;
  confidence_score: number;
  human_handoff: boolean;
  handoff_reason?: string | null;
  extracted_facts_count: number;
  extracted_facts_summary: Record<string, any>;
  matched_properties_summary?: {
    count: number;
    top_matches: Array<{
      property_id: string;
      title: string;
      price: number;
      location: string;
      bedrooms?: number;
      match_score: number;
    }>;
  } | null;
  processed_at: string;
}

export interface QualificationConversationStateData {
  lead_id: string;
  organization_id: string;
  conversation_state: string;
  qualification_state: string;
  current_question?: string | null;
  current_question_field?: string | null;
  missing_required_fields: string[];
  missing_recommended_fields: string[];
  completeness_score: number;
  confidence_score: number;
  human_handoff: boolean;
  handoff_reason?: string | null;
  previously_asked_fields: string[];
  field_attempts: Record<string, number>;
  total_turns: number;
  last_interaction_at?: string | null;
}

export const apiClient = api;





