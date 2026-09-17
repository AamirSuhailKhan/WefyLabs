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

// ─── Part 30: AI Agent Daily Command Center & Inventory Intelligence ─────────
export type CommandCenterPriorityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export interface PriorityItem {
  id: string;
  item_key: string;
  priority: CommandCenterPriorityLevel;
  priority_score: number;
  score?: number;
  category: string;
  title: string;
  description: string;
  reason?: string;
  entity_type: string;
  entity_id: string;
  recommended_action: string;
  action_url?: string | null;
  due_at?: string | null;
  overdue_minutes?: number | null;
  lead_id?: string | null;
  lead_name?: string | null;
  lead_phone?: string | null;
  property_id?: string | null;
  property_title?: string | null;
  match_score?: number | null;
  metadata?: Record<string, any>;
}

export interface FirstContactSlaItem {
  lead_id: string;
  lead_name: string;
  lead_phone?: string | null;
  source: string;
  created_at: string;
  sla_deadline: string;
  is_overdue: boolean;
  overdue_minutes?: number | null;
  time_remaining_minutes?: number | null;
  pipeline_stage: string;
}

export interface OverdueFollowupItem {
  task_id: string;
  lead_id?: string | null;
  lead_name?: string | null;
  title: string;
  description?: string | null;
  due_at: string;
  overdue_days: number;
  overdue_hours: number;
  priority: string;
}

export interface TodayScheduleItem {
  id: string;
  meeting_type: string;
  title: string;
  scheduled_at: string;
  duration_minutes: number;
  lead_id?: string | null;
  lead_name?: string | null;
  location?: string | null;
  meeting_url?: string | null;
  status: string;
  is_starting_soon: boolean;
}

export interface HotLeadItem {
  lead_id: string;
  name: string;
  phone?: string | null;
  pipeline_stage: string;
  temperature: string;
  last_activity_at?: string | null;
  budget_max?: number | null;
  preferred_locations?: string[];
  property_type?: string | null;
  strongest_property_match?: string | null;
  match_score?: number | null;
  uncontacted_days: number;
}

export interface StaleLeadSummary {
  stale_7_days_count: number;
  stale_14_days_count: number;
  stale_30_plus_days_count: number;
  total_stale_leads: number;
  sample_stale_leads: Array<{
    lead_id: string;
    name: string;
    days_inactive: number;
    stage: string;
    score: string;
  }>;
}

export interface InventoryOpportunity {
  property_id: string;
  title: string;
  locality?: string | null;
  price?: number | null;
  property_type: string;
  bhk?: number | null;
  potential_leads_count: number;
  strong_matches_count: number;
}

export interface DemandHeatmap {
  top_locations: Array<{ location: string; count: number }>;
  top_bhk: Array<{ bhk: string; count: number }>;
  top_property_types: Array<{ property_type: string; count: number }>;
  top_budget_ranges: Array<{ budget_range: string; count: number }>;
  top_transaction_types?: Array<{ transaction_type: string; count: number }>;
  disclaimer?: string;
}

export interface InventoryGapItem {
  segment_label?: string | null;
  location?: string | null;
  bhk?: string | null;
  property_type?: string | null;
  budget_range?: string | null;
  demand_count: number;
  supply_count: number;
  gap?: number | null;
  gap_count?: number | null;
  status?: string | null;
}

export interface InventoryIntelligence {
  demand_heatmap: DemandHeatmap;
  gaps: InventoryGapItem[];
  opportunities: InventoryOpportunity[];
  disclaimer: string;
}

export interface DailyBriefing {
  greeting?: string;
  briefing_text: string;
  highlights: string[];
  generated_at: string;
  is_ai_generated: boolean;
  facts_used?: Record<string, any>;
}

export interface CommandCenterSummary {
  critical_actions_count: number;
  high_actions_count: number;
  medium_actions_count: number;
  total_priority_actions: number;
  overdue_followups_count: number;
  sla_breaches_count: number;
  meetings_today_count: number;
  site_visits_today_count: number;
  hot_leads_count: number;
  strong_matches_count: number;
  stale_leads_count: number;
  inventory_gaps_count: number;
}

export interface CommandCenterResponse {
  organization_id: string;
  broker_id: string;
  broker_name: string;
  timezone: string;
  summary: CommandCenterSummary;
  daily_briefing: DailyBriefing;
  priorities: PriorityItem[];
  first_contact_queue: FirstContactSlaItem[];
  overdue_followups: OverdueFollowupItem[];
  today_schedule: TodayScheduleItem[];
  hot_leads: HotLeadItem[];
  stale_leads_summary: StaleLeadSummary;
  inventory_opportunities: InventoryOpportunity[];
  inventory_gaps: InventoryGapItem[];
  demand_heatmap: DemandHeatmap;
  recent_activities: any[];
}

export interface StartMyDayStep {
  step_number: number;
  total_steps: number;
  item: PriorityItem;
}

export interface StartMyDayResponse {
  total_items: number;
  steps: StartMyDayStep[];
}

// ─── Part 31 — Customer Onboarding, Tenant Activation & Demo Mode ────────────

export interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  is_completed: boolean;
  is_skipped: boolean;
  action_route: string;
  action_label: string;
  order: number;
}

export interface OnboardingStatusResponse {
  organization_id: string;
  broker_id: string;
  current_step: string;
  completed_steps: string[];
  skipped_steps: string[];
  is_completed: boolean;
  progress_percentage: number;
  completed_at?: string | null;
  checklist: ChecklistItem[];
  is_activated: boolean;
  activation_score: number;
  is_demo: boolean;
}

export interface MilestoneProgress {
  code: string;
  label: string;
  achieved: boolean;
  achieved_at?: string | null;
  weight: number;
  description: string;
}

export interface TenantActivationResponse {
  organization_id: string;
  is_activated: boolean;
  activation_score: number;
  completed_milestones: string[];
  missing_requirements: string[];
  milestone_breakdown: MilestoneProgress[];
  activated_at?: string | null;
  time_to_activate_seconds?: number | null;
  is_demo: boolean;
}

export interface BusinessProfileSetup {
  agency_name: string;
  business_type: string;
  city: string;
  country_code: string;
  timezone: string;
  currency_code: string;
  team_size?: string;
  primary_business_model?: string;
  website?: string;
}

export interface DemoSessionResponse {
  session_token: string;
  demo_organization_id: string;
  demo_broker_id: string;
  demo_email: string;
  agency_name: string;
  expires_at: string;
  seeded_leads_count: number;
  seeded_properties_count: number;
  seeded_matches_count: number;
  seeded_tasks_count: number;
  banner_message: string;
}

export interface CsvImportPreview {
  entity_type: 'leads' | 'properties';
  filename: string;
  total_rows: number;
  valid_rows_count: number;
  duplicate_rows_count: number;
  invalid_rows_count: number;
  preview_items: Record<string, any>[];
  validation_errors: string[];
}

export interface CsvImportResult {
  status: string;
  entity_type: string;
  imported_count: number;
  skipped_count: number;
  imported_ids: string[];
  message: string;
}

export interface OnboardingTeamInvite {
  email: string;
  role: 'admin' | 'manager' | 'agent';
}

// ─── Part 35 — AI Real Estate Revenue Autopilot ──────────────────────────────
export interface ActionQueueItem {
  id: string;
  opportunity_type: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  urgency: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  opportunity_score: number;
  match_score: number;
  confidence: number;
  lead_id: string;
  lead_name: string;
  lead_phone: string;
  lead_score: string;
  lead_stage?: string | null;
  property_id?: string | null;
  property_title?: string | null;
  property_price?: number | null;
  property_currency: string;
  property_locality?: string | null;
  property_bedrooms?: number | null;
  property_status?: string | null;
  reason: string;
  why_now: string;
  why_property?: string | null;
  risk_of_inactivity?: string | null;
  recommended_action: string;
  recommended_channel: string;
  positive_signals: string[];
  negative_signals: string[];
  data_freshness: Record<string, any>;
  status: string;
  created_at: string;
  expires_at?: string | null;
}

export interface ActionQueueResponse {
  items: ActionQueueItem[];
  total_count: number;
  critical_count: number;
  high_count: number;
  briefing_headline: string;
  active_leads_count?: number;
  active_properties_count?: number;
  completed_today_count?: number;
  last_scan_at?: string | null;
}

export interface RevenueOpportunity extends ActionQueueItem {
  recommended_property_snapshot: Record<string, any>;
  alternative_properties: Array<{
    property_id: string;
    title: string;
    price: number;
    currency: string;
    match_score: number;
    bedrooms?: number;
    locality?: string;
  }>;
  call_brief: {
    lead_name?: string;
    objective?: string;
    key_requirements?: string;
    talking_points?: string[];
    potential_objection?: string;
    suggested_opening?: string;
  };
  email_draft: {
    subject?: string;
    body?: string;
    cta?: string;
  };
  provenance: string[];
  scoring_version: string;
  dedup_key: string;
  actioned_at?: string | null;
  completed_at?: string | null;
  dismissed_at?: string | null;
  dismissal_reason?: string | null;
  feedback_rating?: string | null;
  feedback_notes?: string | null;
  actual_outcome?: string | null;
}

export interface DemandGapItem {
  segment_id: string;
  locality: string;
  bedrooms: number;
  property_type: string;
  budget_band: string;
  active_buyer_demand_count: number;
  matching_inventory_count: number;
  deficit_count: number;
  urgency: string;
  recommended_action: string;
}

export interface DemandIntelligenceResponse {
  total_active_buyers: number;
  total_available_listings: number;
  top_demand_gaps: DemandGapItem[];
  high_demand_localities: string[];
}

export interface RevenueBriefing {
  greeting: string;
  headline: string;
  immediate_actions_count: number;
  critical_actions_count: number;
  hot_leads_count: number;
  top_recommendation_text: string;
  evidence_points: string[];
  generated_at: string;
}

export interface OutreachDraft {
  opportunity_id: string;
  lead_name: string;
  channel: string;
  call_brief: Record<string, any>;
  email_draft: Record<string, any>;
  is_ai_generated: boolean;
  model_used: string;
}
