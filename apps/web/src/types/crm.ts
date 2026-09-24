export interface CustomerPreferences {
  budget_min?: number;
  budget_max?: number;
  budget_currency: string;
  property_type?: string;
  transaction_type?: string;
  preferred_locations: string[];
  timeline?: string;
  loan_status?: string;
  amenities: string[];
}

export interface CustomerRevenueJourney {
  stage: string;
  source_channel: string;
  first_seen_at: string;
  qualified_at?: string;
  appointment_booked_at?: string;
  site_visit_completed_at?: string;
  opportunity_created_at?: string;
  deal_agreed_price?: number;
  recorded_revenue?: number;
}

export interface CustomerTimelineEvent {
  id: string;
  event_type: string;
  title: string;
  description?: string;
  timestamp: string;
  actor: string;
  actor_type: 'HUMAN' | 'AI_AGENT' | 'AUTOMATION' | 'CUSTOMER' | 'SYSTEM';
  source: string;
  channel?: string;
  metadata: Record<string, any>;
}

export interface CRMTask {
  id: string;
  organization_id?: string;
  broker_id: string;
  lead_id?: string;
  assigned_broker_id?: string;
  title: string;
  description?: string;
  due_at?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'low' | 'normal' | 'high' | 'urgent';
  is_overdue: boolean;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface CRMActivity {
  id: string;
  organization_id?: string;
  lead_id?: string;
  actor_id?: string;
  actor_type: string;
  activity_type: string;
  title: string;
  description?: string;
  activity_data: Record<string, any>;
  created_at: string;
}

export interface CRMNote {
  id: string;
  lead_id: string;
  broker_id: string;
  content: string;
  visibility: 'PRIVATE' | 'TEAM' | 'ORGANIZATION';
  is_ai_generated: boolean;
  created_at: string;
}

export interface OpportunitySummary {
  id: string;
  lead_id: string;
  lead_name?: string;
  lead_phone: string;
  property_id?: string;
  deal_name: string;
  agreed_price: number;
  currency: string;
  current_stage: string;
  commission_percentage: number;
  estimated_commission_amount: number;
  risk_level: string;
  closing_probability_pct: number;
  is_stalled: boolean;
  days_in_stage: number;
  created_at: string;
  updated_at: string;
}

export interface Customer360Response {
  customer_id: string;
  organization_id: string;
  name?: string;
  primary_email?: string;
  primary_phone: string;
  owner_id: string;
  owner_name?: string;
  lead_status: string;
  pipeline_stage: string;
  temperature: string;
  source: string;
  campaign?: string;
  created_at: string;
  last_activity_at?: string;
  sla_state: string;
  next_best_action?: string;

  preferences: CustomerPreferences;
  qualification: Record<string, any>;
  property_interests: Array<Record<string, any>>;
  property_matches: Array<Record<string, any>>;
  conversations: Array<Record<string, any>>;
  tasks: CRMTask[];
  activities: CRMActivity[];
  notes: CRMNote[];
  appointments: Array<Record<string, any>>;
  site_visits: Array<Record<string, any>>;
  opportunities: OpportunitySummary[];
  revenue_journey: CustomerRevenueJourney;
  timeline: CustomerTimelineEvent[];
  ai_insights: Record<string, any>;
}

export interface LeadCRMListItem {
  id: string;
  name?: string;
  phone: string;
  email?: string;
  source: string;
  campaign?: string;
  score: string;
  status: string;
  pipeline_stage: string;
  budget_min?: number;
  budget_max?: number;
  budget_currency: string;
  preferred_locations: string[];
  property_type?: string;
  owner_id: string;
  owner_name?: string;
  sla_status: string;
  last_activity_at?: string;
  next_action?: string;
  created_at: string;
  updated_at: string;
}

export interface PipelineCard {
  id: string;
  lead_id: string;
  deal_id?: string;
  customer_name?: string;
  phone: string;
  email?: string;
  stage: string;
  score: string;
  property_interest?: string;
  owner_id: string;
  owner_name?: string;
  deal_value?: number;
  currency: string;
  age_days: number;
  last_activity_at?: string;
  next_action?: string;
  has_revenue_alert: boolean;
}

export interface PipelineColumn {
  stage_key: string;
  stage_name: string;
  order_index: number;
  color: string;
  total_cards: number;
  total_pipeline_value: number;
  cards: PipelineCard[];
}

export interface PipelineKanbanResponse {
  total_pipeline_value: number;
  total_active_deals: number;
  columns: PipelineColumn[];
}

export interface CRMSearchResultItem {
  id: string;
  entity_type: 'customer' | 'lead' | 'opportunity' | 'property' | 'task' | 'appointment';
  title: string;
  subtitle?: string;
  status?: string;
  created_at?: string;
  deep_link: string;
  metadata: Record<string, any>;
}

export interface CRMSearchResponse {
  query: string;
  total_results: number;
  results: CRMSearchResultItem[];
}

export interface CRMDashboardMetrics {
  my_open_leads: number;
  new_leads_today: number;
  sla_risks_count: number;
  todays_appointments_count: number;
  upcoming_site_visits_count: number;
  active_opportunities_count: number;
  pipeline_total_value: number;
  pipeline_currency: string;
  recorded_revenue_total: number;
  overdue_tasks_count: number;
  revenue_opportunities_count: number;
}

export interface BulkOperationResult {
  operation: string;
  total_requested: number;
  successful_count: number;
  failed_count: number;
  failed_items: Array<{ lead_id: string; reason: string }>;
  audit_id?: string;
}
