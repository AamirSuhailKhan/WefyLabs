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
  phone: string;
  name: string;
  agency_name?: string;
  city: string;
  whatsapp_number?: string;
  subscription_status: string;
  subscription_plan?: string;
  trial_ends_at?: string;
  trial_days_remaining?: number;
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
