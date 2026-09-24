/**
 * Part 16 — Prediction API Client
 * =================================
 * Type-safe API client for all prediction endpoints.
 * Handles auth headers, error parsing, and response typing.
 */

import type {
  LeadIntelligenceSurfaceDTO,
  DataSufficiencyAuditDTO,
  PropensityScoreDTO,
  NextBestActionsDTO,
  PredictionTargetDefinitionDTO,
} from '@/types/predictive';

const BASE = '/api/v1/predictions';

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`[Predictions API] ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ─── Part 16 Endpoints ────────────────────────────────────────────────────────

/**
 * GET /api/v1/predictions/leads/{lead_id}/intelligence
 * Returns the full CRM prediction surface (conversion + propensity + NBA).
 */
export async function getLeadIntelligence(
  leadId: string,
  forceRefresh = false
): Promise<LeadIntelligenceSurfaceDTO> {
  const qs = forceRefresh ? '?force_refresh=true' : '';
  return apiGet<LeadIntelligenceSurfaceDTO>(`/leads/${leadId}/intelligence${qs}`);
}

/**
 * GET /api/v1/predictions/audit/data-sufficiency
 * Returns the mandatory Part 16 data gate audit report for all targets.
 */
export async function getDataSufficiencyAudit(): Promise<DataSufficiencyAuditDTO> {
  return apiGet<DataSufficiencyAuditDTO>('/audit/data-sufficiency');
}

/**
 * GET /api/v1/predictions/targets
 * Returns the registered prediction target catalog.
 */
export async function getPredictionTargets(): Promise<{
  total_targets: number;
  targets: PredictionTargetDefinitionDTO[];
}> {
  return apiGet('/targets');
}

/**
 * GET /api/v1/predictions/leads/{lead_id}/propensity/{target_id}
 * Returns a single propensity score for a lead.
 */
export async function getLeadPropensity(
  leadId: string,
  targetId: string
): Promise<PropensityScoreDTO> {
  return apiGet<PropensityScoreDTO>(`/leads/${leadId}/propensity/${targetId}`);
}

/**
 * GET /api/v1/predictions/leads/{lead_id}/next-best-actions
 * Returns ranked NBA for a lead.
 */
export async function getNextBestActions(leadId: string): Promise<NextBestActionsDTO> {
  return apiGet<NextBestActionsDTO>(`/leads/${leadId}/next-best-actions`);
}

// ─── Legacy / Existing Endpoints (unchanged signatures) ──────────────────────

export async function getLeadConversionPrediction(leadId: string, forceRefresh = false) {
  const qs = forceRefresh ? '?force_refresh=true' : '';
  return apiGet(`/leads/${leadId}${qs}`);
}

export async function getRevenueForecast(horizon = '30_DAYS', currency = 'AED') {
  return apiGet(`/revenue?horizon=${horizon}&currency=${currency}`);
}

export async function getDriftReport(modelVersion = 'v1.0.0') {
  return apiGet(`/drift?model_version=${modelVersion}`);
}
