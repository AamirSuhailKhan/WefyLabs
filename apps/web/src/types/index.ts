export type ScoreType = 'hot' | 'warm' | 'cold' | 'spam' | 'pending';
export type LeadStatus = 'pending' | 'active' | 'qualified' | 'converted' | 'lost' | 'spam';
export type SourceType = 'whatsapp_forward' | 'facebook' | 'google' | 'referral' | 'walk_in' | 'manual' | 'website';

export interface PipelineStage {
  id: string;
  broker_id: string;
  name: string;
  order_index: number;
  color: string;
  is_default: string;
  created_at: string;
}

export interface LeadNote {
  id: string;
  lead_id?: string;
  broker_id?: string;
  content: string;
  color_tag?: string;
  created_at: string;
}

export interface LeadTag {
  id: string;
  broker_id: string;
  name: string;
  color: string;
  created_at: string;
}

export interface Task {
  id: string;
  broker_id: string;
  lead_id?: string;
  title: string;
  due_at: string;
  status: 'pending' | 'completed' | 'cancelled';
  reminder_sent: string;
  created_at: string;
}

export interface Broker {
  id: string;
  email: string;
  phone?: string;
  name: string;
  agency_name?: string;
  city?: string;
  whatsapp_number?: string;
  subscription_status: string;
  subscription_plan?: string;
  trial_ends_at?: string;
  trial_days_remaining?: number;
  onboarding_status: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  lead_id: string;
  direction: 'inbound' | 'outbound';
  sender_type: 'bot' | 'lead' | 'broker';
  message: string;
  message_type: string;
  created_at: string;
}

export interface ScoreAudit {
  id: string;
  lead_id: string;
  score: ScoreType;
  confidence: number;
  reasoning: string;
  extracted_data?: ExtractedData;
  created_at: string;
}

export interface ExtractedData {
  budget_min?: number;
  budget_max?: number;
  property_type?: string;
  transaction_type?: string;
  preferred_locations?: string[];
  timeline?: string;
  loan_status?: string;
}

export interface Lead {
  id: string;
  broker_id: string;
  phone: string;
  name?: string;
  source: SourceType;
  score: ScoreType;
  score_confidence: number;
  budget_min?: number;
  budget_max?: number;
  property_type?: string;
  transaction_type?: string;
  preferred_locations?: string[];
  timeline?: string;
  loan_status?: string;
  status: LeadStatus;
  stage_id?: string;
  stage_name?: string;
  pipeline_stage?: string;
  tags?: LeadTag[];
  notes?: LeadNote[];
  tasks?: Task[];
  last_message_at?: string;
  qualified_at?: string;
  created_at: string;
  updated_at: string;
}

export interface LeadDetail extends Lead {
  conversations: Conversation[];
  latest_score?: ScoreAudit;
}

export interface LeadListResponse {
  total: number;
  items?: Lead[];
  data?: Lead[];
  page?: number;
  pages?: number;
}

export interface AdminStats {
  total_brokers: number;
  active_brokers: number;
  total_leads: number;
  qualified_leads: number;
  hot_leads: number;
  mrr_inr: number;
}

// ─── Calendar & Scheduling Intelligence Engine Types ─────────────────────────
export interface CalendarTimeSlot {
  start_utc: string;
  end_utc: string;
  broker_local_start: string;
  customer_local_start: string;
  broker_id: string;
  suitability_score: number;
}

export interface CalendarSlotSearchResponse {
  lead_id: string;
  meeting_type: string;
  customer_timezone: string;
  broker_timezone: string;
  available_slots: CalendarTimeSlot[];
}

export interface CalendarBookingRequest {
  lead_id: string;
  broker_id?: string;
  property_id?: string;
  meeting_type: 'PROPERTY_VIEWING' | 'SITE_VISIT' | 'CALL' | 'VIDEO_CALL' | 'OFFICE_MEETING';
  slot_start_utc: string;
  duration_minutes?: number;
  location_type?: string;
  location_address?: string;
  virtual_provider?: 'GOOGLE_MEET' | 'MICROSOFT_TEAMS' | 'ZOOM' | 'NONE';
  notes?: string;
  idempotency_key?: string;
}

export interface CalendarBookingResponse {
  id: string;
  organization_id: string;
  broker_id: string;
  lead_id?: string;
  meeting_type: string;
  title: string;
  status: string;
  start_utc: string;
  end_utc: string;
  customer_timezone: string;
  broker_timezone: string;
  duration_minutes: number;
  location_type: string;
  location_address?: string;
  virtual_provider: string;
  meeting_url?: string;
  external_event_id?: string;
}

export interface MeetingPreparationBrief {
  id: string;
  meeting_id: string;
  lead_id: string;
  buyer_summary: string;
  verified_budget: string;
  key_objections: string[];
  recommended_properties: Array<{ title: string; price?: string; locality?: string }>;
  suggested_questions: string[];
  next_best_action: string;
  generated_at: string;
}

export interface MeetingNoShowPrediction {
  id: string;
  meeting_id: string;
  no_show_probability: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  confidence: number;
  influencing_factors: string[];
  preventative_action?: string;
  calculated_at: string;
}

export interface MeetingOutcome {
  id: string;
  meeting_id: string;
  outcome_category: 'INTERESTED' | 'VERY_INTERESTED' | 'NEEDS_FOLLOW_UP' | 'NOT_INTERESTED' | 'NEGOTIATION' | 'CONVERTED' | 'NO_SHOW';
  buyer_interest_level: number;
  detailed_feedback?: string;
  agreed_next_step?: string;
  next_follow_up_date?: string;
  agent_notes?: string;
  recorded_at: string;
}

export interface ViewingItineraryStop {
  property_id: string;
  property_title: string;
  estimated_arrival_utc: string;
  estimated_duration_minutes: number;
  locality?: string;
}

export interface ViewingItineraryResponse {
  lead_id: string;
  broker_id: string;
  total_stops: number;
  total_duration_minutes: number;
  stops: ViewingItineraryStop[];
}

export interface CalendarConflict {
  id: string;
  meeting_id: string;
  external_event_id: string;
  conflict_description: string;
  resolution_status: string;
  detected_at: string;
}

