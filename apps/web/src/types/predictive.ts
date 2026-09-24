// Part 16 — Prediction Types for TypeScript / Next.js Frontend
// These match exactly the API response from the CRM Intelligence Surface endpoint:
// GET /api/v1/predictions/leads/{lead_id}/intelligence

export interface PropensityScoreDTO {
  target_id: string;
  entity_id: string;
  organization_id: string;
  probability: number;         // [0.0, 1.0]
  probability_pct: number;     // [0.0, 100.0]
  confidence: 'LOW' | 'MEDIUM' | 'HIGH';
  method: 'DETERMINISTIC_HEURISTIC' | 'STATISTICAL_BASELINE' | 'VALIDATED_ML' | 'UNAVAILABLE';
  signal_count: number;
  drivers_positive: string[];
  drivers_negative: string[];
  explanation: string;
  computed_at: string;
  valid_until: string;
}

export interface ScoredActionDTO {
  action_type: string;
  utility_score: number;       // [0.0, 1.0]
  priority: 'URGENT' | 'HIGH' | 'MEDIUM' | 'LOW';
  rationale: string;
  estimated_impact: string;
  cta_label: string;
  target_entity_id: string;
  organization_id: string;
  eligible: boolean;
  ineligible_reason?: string;
  computed_at: string;
}

export interface NextBestActionsDTO {
  entity_id: string;
  organization_id: string;
  top_action: ScoredActionDTO | null;
  ranked_actions: ScoredActionDTO[];
  action_count: number;
  reasoning_summary: string;
  computed_at: string;
  valid_until: string;
}

export interface FeatureDriverDTO {
  feature: string;
  impact: number;
  description: string;
}

export interface LeadIntelligenceSurfaceDTO {
  lead_id: string;
  organization_id: string;

  // Core conversion signal
  conversion_probability: number;
  conversion_probability_pct: number;
  confidence_level: 'LOW' | 'MEDIUM' | 'HIGH';
  explanation_text: string;
  positive_drivers: FeatureDriverDTO[];
  negative_drivers: FeatureDriverDTO[];

  // Part 16 propensity scores (keyed by target_id)
  propensity_scores: {
    LEAD_RESPONSE_PROPENSITY_V1?: PropensityScoreDTO;
    APPOINTMENT_PROPENSITY_V1?: PropensityScoreDTO;
    SITE_VISIT_PROPENSITY_V1?: PropensityScoreDTO;
    OPPORTUNITY_STALL_RISK_V1?: PropensityScoreDTO;
    BOOKING_PROPENSITY_V1?: PropensityScoreDTO;
    LEAD_COLD_RISK_V1?: PropensityScoreDTO;
    [key: string]: PropensityScoreDTO | undefined;
  };

  // Next best actions
  next_best_actions: NextBestActionsDTO;

  // Audit trail
  prediction_id: string;
  model_version_tag: string;
  generated_at: string;
  valid_until: string;
}

// Data Sufficiency Audit
export interface DataSufficiencyGateResultDTO {
  target_id: string;
  eligible_rows: number;
  positive_labels: number;
  negative_labels: number;
  class_balance_ratio: number;
  gate_passed: boolean;
  resolved_method: string;
  resolved_status: string;
  reason: string;
  evaluated_at: string;
}

export interface DataSufficiencyAuditDTO {
  organization_id: string;
  audit_timestamp: string;
  targets: Record<string, DataSufficiencyGateResultDTO>;
  summary: {
    total_targets: number;
    gate_passed: number;
    gate_failed: number;
    insufficient_data: number;
  };
}

// Target Definitions Catalog
export interface PredictionTargetDefinitionDTO {
  target_id: string;
  name: string;
  definition: string;
  positive_outcome: string;
  negative_outcome: string;
  unknown_outcome: string;
  lookahead_window_days: number;
  anchor_event: string;
  eligibility_criteria: string;
  exclusion_criteria: string;
  min_eligible_rows: number;
  min_positive_labels: number;
  method: string;
  version: string;
  status: string;
  reason: string;
}

// Propensity target IDs (constants)
export const PROPENSITY_TARGETS = {
  LEAD_RESPONSE: 'LEAD_RESPONSE_PROPENSITY_V1',
  APPOINTMENT: 'APPOINTMENT_PROPENSITY_V1',
  SITE_VISIT: 'SITE_VISIT_PROPENSITY_V1',
  STALL_RISK: 'OPPORTUNITY_STALL_RISK_V1',
  BOOKING: 'BOOKING_PROPENSITY_V1',
  COLD_RISK: 'LEAD_COLD_RISK_V1',
} as const;

// Priority colors for UI
export const PRIORITY_COLORS: Record<string, string> = {
  URGENT: 'text-red-700 bg-red-50 border-red-200',
  HIGH: 'text-orange-700 bg-orange-50 border-orange-200',
  MEDIUM: 'text-yellow-700 bg-yellow-50 border-yellow-200',
  LOW: 'text-gray-600 bg-gray-50 border-gray-200',
};

// Confidence colors for UI
export const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH: 'text-emerald-700',
  MEDIUM: 'text-yellow-700',
  LOW: 'text-gray-500',
};
