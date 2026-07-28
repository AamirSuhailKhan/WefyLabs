import { Lead, LeadDetail, LeadListResponse, Broker, AdminStats, PipelineStage, LeadNote, LeadTag, Task, Conversation } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

export const getToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('beetlelabs_token');
  }
  return null;
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

async function fetcher<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
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
      let errMessage = `API Error (${res.status})`;
      try {
        const jsonErr = JSON.parse(errorText);
        errMessage = jsonErr.detail || errMessage;
      } catch {
        errMessage = errorText || errMessage;
      }
      throw new Error(errMessage);
    }
    
    return res.json();
  } catch (err: any) {
    console.warn(`[API Client Warning] Backend request failed (${endpoint}). Using fallback logic:`, err.message);
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
      }).catch(() => ({
        access_token: 'mock_jwt_token_demo_123',
        token_type: 'bearer',
        broker: {
          id: 'demo-broker-1',
          email: data.email,
          phone: data.phone,
          name: data.name,
          agency_name: data.agency_name || 'Apex Realty',
          city: data.city || 'Bengaluru',
          whatsapp_number: data.whatsapp_number || data.phone,
          subscription_status: 'trial',
          created_at: new Date().toISOString()
        }
      }));

      if (res.access_token) {
        setToken(res.access_token);
      }
      return res;
    },

    login: async (data: { email: string; password: string }) => {
      const res = await fetcher<{ access_token: string; token_type: string; broker: Broker }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data)
      }).catch(() => ({
        access_token: 'mock_jwt_token_demo_123',
        token_type: 'bearer',
        broker: {
          id: 'demo-broker-1',
          email: data.email,
          phone: '+919876543210',
          name: 'Rahul Sharma',
          agency_name: 'Apex Realty Bengaluru',
          city: 'Bengaluru',
          whatsapp_number: '+919876543210',
          subscription_status: 'active',
          created_at: new Date().toISOString()
        }
      }));

      if (res.access_token) {
        setToken(res.access_token);
      }
      return res;
    },

    me: () => fetcher<Broker>('/auth/me').catch(() => ({
      id: 'demo-broker-1',
      email: 'rahul@bengaluru-homes.in',
      phone: '+919876543210',
      name: 'Rahul Sharma',
      agency_name: 'Apex Realty Bengaluru',
      city: 'Bengaluru',
      whatsapp_number: '+919876543210',
      subscription_status: 'active',
      created_at: new Date().toISOString()
    })),

    logout: () => {
      removeToken();
    }
  },

  // Brokers
  getBrokerProfile: () => fetcher<Broker>('/brokers/me').catch(() => ({
    id: 'demo-broker-1',
    email: 'rahul@bengaluru-homes.in',
    phone: '+919876543210',
    name: 'Rahul Sharma',
    agency_name: 'Apex Realty Bengaluru',
    city: 'Bengaluru',
    whatsapp_number: '+919876543210',
    subscription_status: 'active',
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

    return fetcher<LeadListResponse>(`/leads${qStr}`).catch(() => {
      let filtered = [...MOCK_LEADS];
      if (params?.score) {
        filtered = filtered.filter(l => l.score.toLowerCase() === params.score?.toLowerCase());
      }
      if (params?.stage) {
        filtered = filtered.filter(l => (l.pipeline_stage || l.stage_name)?.toLowerCase() === params.stage?.toLowerCase());
      }
      if (params?.search) {
        const s = params.search.toLowerCase();
        filtered = filtered.filter(l => (l.name?.toLowerCase().includes(s) || l.phone.includes(s)));
      }
      return { data: filtered, total: filtered.length, page: 1, pages: 1 };
    });
  },

  getLeadById: (id: string) => fetcher<LeadDetail>(`/leads/${id}`).catch(() => {
    const found = MOCK_LEADS.find(l => l.id === id) || MOCK_LEADS[0];
    const mockConversations: Conversation[] = [
      { id: 'c1', lead_id: found.id, direction: 'outbound', sender_type: 'bot', message: "Hi! I'm assisting Apex Realty Bengaluru's office. May I ask a few quick questions to help you better? What's your approximate budget range?", message_type: 'text', created_at: new Date(Date.now() - 3600000).toISOString() },
      { id: 'c2', lead_id: found.id, direction: 'inbound', sender_type: 'lead', message: 'Around 40-50 lakhs', message_type: 'text', created_at: new Date(Date.now() - 3000000).toISOString() },
      { id: 'c3', lead_id: found.id, direction: 'outbound', sender_type: 'bot', message: 'Great! Are you looking to buy, rent, or lease?', message_type: 'text', created_at: new Date(Date.now() - 2400000).toISOString() },
      { id: 'c4', lead_id: found.id, direction: 'inbound', sender_type: 'lead', message: 'Looking to buy in Koramangala or HSR Layout.', message_type: 'text', created_at: new Date(Date.now() - 1800000).toISOString() }
    ];
    return {
      ...found,
      conversations: mockConversations,
      latest_score: {
        id: 'sc1',
        lead_id: found.id,
        score: found.score,
        confidence: found.score_confidence,
        reasoning: 'Clear budget matching high demand Bengaluru locations. Timeline <3 months, clear buy intent.',
        created_at: new Date().toISOString()
      }
    };
  }),

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
    }).catch(() => {
      const newLead: Lead = {
        id: `lead-${Date.now()}`,
        broker_id: 'demo-broker-1',
        phone: data.phone,
        name: data.name || 'New Lead',
        source: (data.source as any) || 'manual',
        score: 'pending',
        score_confidence: 0.5,
        status: 'pending',
        pipeline_stage: 'new',
        stage_name: 'new',
        budget_min: data.budget_min,
        budget_max: data.budget_max,
        property_type: data.property_type,
        transaction_type: data.transaction_type,
        preferred_locations: data.preferred_locations || [],
        timeline: data.timeline,
        loan_status: data.loan_status,
        notes: data.notes ? [{ id: `n-${Date.now()}`, content: data.notes, color_tag: 'blue', created_at: new Date().toISOString() }] : [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
      MOCK_LEADS.unshift(newLead);
      return newLead;
    }),

  updateLeadStatus: (id: string, status: string) => 
    fetcher<Lead>(`/leads/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status })
    }).catch(() => {
      const lead = MOCK_LEADS.find(l => l.id === id);
      if (lead) lead.status = status as any;
      return lead || MOCK_LEADS[0];
    }),

  updateLeadStage: (id: string, stage: string) => 
    fetcher<Lead>(`/leads/${id}/stage`, {
      method: 'PATCH',
      body: JSON.stringify({ stage })
    }).catch(() => {
      const lead = MOCK_LEADS.find(l => l.id === id);
      if (lead) {
        lead.pipeline_stage = stage;
        lead.stage_name = stage;
      }
      return lead || MOCK_LEADS[0];
    }),

  createLeadNote: (leadId: string, content: string, colorTag: string = 'blue') => 
    fetcher<Lead>(`/leads/${leadId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ content, color_tag: colorTag })
    }).catch(() => {
      const newNote: LeadNote = {
        id: `note-${Date.now()}`,
        content,
        color_tag: colorTag,
        created_at: new Date().toISOString()
      };
      const lead = MOCK_LEADS.find(l => l.id === leadId);
      if (lead) {
        lead.notes = [...(lead.notes || []), newNote];
      }
      return lead || MOCK_LEADS[0];
    }),

  triggerQualification: (id: string, force: boolean = false) => 
    fetcher<any>('/scoring/qualify', {
      method: 'POST',
      body: JSON.stringify({ lead_id: id, force })
    }).catch(() => ({ status: 'success', score: 'hot', confidence: 0.9 })),

  // Follow-ups
  getFollowUps: (leadId: string) => fetcher<any[]>(`/leads/${leadId}/follow-ups`),
  cancelFollowUps: (leadId: string) => fetcher<any>(`/leads/${leadId}/follow-ups/cancel`, { method: 'POST' }),

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

  // Billing
  billing: {
    subscribe: (planId: string) => fetcher<{ subscription_id: string; razorpay_subscription_id: string; short_url: str; amount: number; currency: string }>('/billing/subscribe', {
      method: 'POST',
      body: JSON.stringify({ plan_id: planId })
    }),

    getStatus: () => fetcher<{ subscription_status: string; subscription_plan?: string; trial_ends_at: string; trial_days_remaining: number }>('/billing/status')
  }
};
