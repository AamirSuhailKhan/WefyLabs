'use client';

/**
 * Part 16 — Lead Intelligence Panel
 * ====================================
 * Comprehensive predictive intelligence panel for the Native CRM Lead 360 view.
 * Displays:
 *   - Conversion probability gauge with confidence level
 *   - 6 propensity scores (response, appointment, site visit, stall, cold risk, booking)
 *   - Top next-best-action with CTA button
 *   - Full ranked action list
 *   - SHAP positive/negative feature drivers
 *   - Prediction metadata (version, generated_at, valid_until)
 *
 * Calls: GET /api/v1/predictions/leads/{lead_id}/intelligence
 * Fails gracefully — shows skeleton loader → degraded state → full data
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2,
  Clock, Zap, Phone, MessageSquare, Mail, Calendar, Target,
  ArrowRight, RefreshCw, Info, BarChart3, Shield, Flame,
  ChevronDown, ChevronUp, Activity, Star, Award,
} from 'lucide-react';
import type {
  LeadIntelligenceSurfaceDTO, PropensityScoreDTO, ScoredActionDTO,
  NextBestActionsDTO, PROPENSITY_TARGETS,
} from '@/types/predictive';

// ─── API Client ───────────────────────────────────────────────────────────────

async function fetchLeadIntelligence(
  leadId: string,
  forceRefresh = false
): Promise<LeadIntelligenceSurfaceDTO> {
  const res = await fetch(
    `/api/v1/predictions/leads/${leadId}/intelligence${forceRefresh ? '?force_refresh=true' : ''}`,
    {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    }
  );
  if (!res.ok) throw new Error(`Intelligence fetch failed: ${res.status}`);
  return res.json();
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function probabilityGradient(prob: number): string {
  if (prob >= 0.70) return 'from-emerald-500 to-green-600';
  if (prob >= 0.45) return 'from-yellow-400 to-amber-500';
  if (prob >= 0.25) return 'from-orange-400 to-red-500';
  return 'from-rose-500 to-red-700';
}

function probabilityTextColor(prob: number): string {
  if (prob >= 0.70) return 'text-emerald-700';
  if (prob >= 0.45) return 'text-amber-700';
  return 'text-rose-700';
}

function confidenceBadge(level: string): string {
  switch (level) {
    case 'HIGH': return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    case 'MEDIUM': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    default: return 'bg-gray-100 text-gray-600 border-gray-300';
  }
}

function priorityStyle(priority: string) {
  switch (priority) {
    case 'URGENT': return { bg: 'bg-red-50 border-red-200', text: 'text-red-700', badge: 'bg-red-100 text-red-800' };
    case 'HIGH': return { bg: 'bg-orange-50 border-orange-200', text: 'text-orange-700', badge: 'bg-orange-100 text-orange-800' };
    case 'MEDIUM': return { bg: 'bg-yellow-50 border-yellow-200', text: 'text-yellow-700', badge: 'bg-yellow-100 text-yellow-800' };
    default: return { bg: 'bg-gray-50 border-gray-200', text: 'text-gray-600', badge: 'bg-gray-100 text-gray-700' };
  }
}

function actionIcon(actionType: string) {
  if (actionType.includes('CALL')) return <Phone className="w-4 h-4" />;
  if (actionType.includes('WHATSAPP')) return <MessageSquare className="w-4 h-4" />;
  if (actionType.includes('EMAIL')) return <Mail className="w-4 h-4" />;
  if (actionType.includes('VIEWING') || actionType.includes('SCHEDULE')) return <Calendar className="w-4 h-4" />;
  if (actionType.includes('AI')) return <Sparkles className="w-4 h-4" />;
  return <Zap className="w-4 h-4" />;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ConversionGauge({ probability, pct, confidence }: {
  probability: number; pct: number; confidence: string;
}) {
  const r = 44;
  const circ = 2 * Math.PI * r;
  const offset = circ - (probability * circ);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-28 h-28">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#E5E7EB" strokeWidth="10" />
          <circle
            cx="50" cy="50" r={r} fill="none"
            strokeWidth="10" strokeLinecap="round"
            stroke={probability >= 0.70 ? '#10B981' : probability >= 0.45 ? '#F59E0B' : '#EF4444'}
            strokeDasharray={circ}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 1.2s ease-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-extrabold font-mono ${probabilityTextColor(probability)}`}>
            {Math.round(pct)}%
          </span>
          <span className="text-[9px] font-mono text-gray-500 uppercase tracking-wide">Conversion</span>
        </div>
      </div>
      <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${confidenceBadge(confidence)}`}>
        {confidence} CONFIDENCE
      </span>
    </div>
  );
}

function PropensityBadge({ score, label, isRisk = false }: {
  score: PropensityScoreDTO; label: string; isRisk?: boolean;
}) {
  const pct = score.probability_pct;
  const isHigh = pct >= 60;
  const isMid = pct >= 35;

  const color = isRisk
    ? (isHigh ? 'text-red-700' : isMid ? 'text-orange-600' : 'text-gray-500')
    : (isHigh ? 'text-emerald-700' : isMid ? 'text-yellow-700' : 'text-gray-500');

  const bg = isRisk
    ? (isHigh ? 'bg-red-50 border-red-200' : isMid ? 'bg-orange-50 border-orange-200' : 'bg-gray-50 border-gray-200')
    : (isHigh ? 'bg-emerald-50 border-emerald-200' : isMid ? 'bg-yellow-50 border-yellow-200' : 'bg-gray-50 border-gray-200');

  return (
    <div className={`p-3 rounded-xl border ${bg} space-y-1`}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono font-bold text-gray-500 uppercase">{label}</span>
        <span className={`text-sm font-extrabold font-mono ${color}`}>{Math.round(pct)}%</span>
      </div>
      <div className="w-full h-1.5 bg-white rounded-full overflow-hidden border border-gray-200">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${
            isRisk
              ? (isHigh ? 'bg-red-500' : isMid ? 'bg-orange-400' : 'bg-gray-300')
              : (isHigh ? 'bg-emerald-500' : isMid ? 'bg-yellow-400' : 'bg-gray-300')
          }`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono text-gray-400">{score.method.replace('_', ' ')}</span>
        <span className={`text-[9px] font-mono ${score.confidence === 'HIGH' ? 'text-emerald-600' : score.confidence === 'MEDIUM' ? 'text-yellow-600' : 'text-gray-400'}`}>
          {score.confidence}
        </span>
      </div>
    </div>
  );
}

function ActionCard({ action, primary = false }: { action: ScoredActionDTO; primary?: boolean }) {
  const style = priorityStyle(action.priority);
  return (
    <div className={`p-3 rounded-xl border ${style.bg} ${primary ? 'ring-2 ring-offset-1 ring-purple-300' : ''} space-y-2`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={style.text}>{actionIcon(action.action_type)}</span>
          <span className="text-sm font-bold font-mono text-gray-900">{action.cta_label}</span>
        </div>
        <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-full ${style.badge}`}>
          {action.priority}
        </span>
      </div>
      <p className="text-[11px] text-gray-600 font-sans leading-relaxed">{action.rationale}</p>
      <div className="flex items-center gap-1.5 text-[10px] text-purple-700">
        <TrendingUp className="w-3 h-3" />
        <span className="font-sans">{action.estimated_impact}</span>
      </div>
      <div className="flex items-center gap-1 text-[10px] text-gray-400 font-mono">
        <Activity className="w-3 h-3" />
        <span>Score: {Math.round(action.utility_score * 100)}%</span>
      </div>
    </div>
  );
}

function FeatureDriver({ feature, impact, description, positive }: {
  feature: string; impact: number; description: string; positive: boolean;
}) {
  return (
    <div className={`p-2.5 rounded-xl border text-xs font-sans ${
      positive ? 'bg-emerald-50 border-emerald-200' : 'bg-rose-50 border-rose-200'
    }`}>
      <div className="flex items-center justify-between font-mono font-bold mb-0.5">
        <span className="text-gray-900">{feature}</span>
        <span className={positive ? 'text-emerald-700' : 'text-rose-700'}>
          {positive ? `+${Math.abs(impact * 100).toFixed(0)}%` : `-${Math.abs(impact * 100).toFixed(0)}%`}
        </span>
      </div>
      <p className="text-gray-600 text-[11px]">{description}</p>
    </div>
  );
}

// ─── Loading Skeleton ─────────────────────────────────────────────────────────

function PredictionSkeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-4 bg-gray-200 rounded w-48" />
      <div className="flex justify-center">
        <div className="w-28 h-28 bg-gray-200 rounded-full" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-200 rounded-xl" />
        ))}
      </div>
      <div className="h-24 bg-gray-200 rounded-xl" />
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface LeadIntelligencePanelProps {
  leadId: string;
  className?: string;
}

export function LeadIntelligencePanel({ leadId, className = '' }: LeadIntelligencePanelProps) {
  const [data, setData] = useState<LeadIntelligenceSurfaceDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllActions, setShowAllActions] = useState(false);
  const [showDrivers, setShowDrivers] = useState(false);

  const loadIntelligence = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const result = await fetchLeadIntelligence(leadId, refresh);
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load prediction intelligence');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadIntelligence();
  }, [leadId]);

  if (loading) return (
    <div className={`bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 ${className}`}>
      <PredictionSkeleton />
    </div>
  );

  if (error && !data) return (
    <div className={`bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 ${className}`}>
      <div className="flex items-center gap-2 text-amber-700 text-xs font-mono">
        <AlertTriangle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
        <button
          onClick={() => loadIntelligence()}
          className="ml-auto text-purple-600 hover:text-purple-800 font-bold underline"
        >
          Retry
        </button>
      </div>
    </div>
  );

  if (!data) return null;

  const { propensity_scores: ps, next_best_actions: nba } = data;
  const topAction = nba?.top_action;
  const otherActions = (nba?.ranked_actions ?? []).slice(1);
  const stall = ps?.OPPORTUNITY_STALL_RISK_V1;
  const cold = ps?.LEAD_COLD_RISK_V1;
  const isHighRisk = (stall?.probability ?? 0) >= 0.60 || (cold?.probability ?? 0) >= 0.60;

  return (
    <div className={`bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-4 shadow-sm ${className}`}>

      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-purple-600 fill-purple-200" />
          <span>Predictive Intelligence</span>
          {isHighRisk && (
            <span className="flex items-center gap-1 text-[9px] bg-red-100 text-red-700 border border-red-200 px-2 py-0.5 rounded-full ml-1">
              <AlertTriangle className="w-3 h-3" />
              HIGH RISK
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
            {data.model_version_tag}
          </span>
          <button
            onClick={() => loadIntelligence(true)}
            disabled={refreshing}
            className="text-gray-400 hover:text-purple-600 transition-colors"
            title="Refresh predictions"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Conversion Gauge + Summary */}
      <div className="flex gap-4 items-start">
        <ConversionGauge
          probability={data.conversion_probability}
          pct={data.conversion_probability_pct}
          confidence={data.confidence_level}
        />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] text-gray-700 font-sans leading-relaxed line-clamp-4">
            {data.explanation_text}
          </p>
          <div className="flex items-center gap-1 mt-2 text-[9px] text-gray-400 font-mono">
            <Clock className="w-3 h-3" />
            <span>Valid until {new Date(data.valid_until).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
          </div>
        </div>
      </div>

      {/* Propensity Scores Grid */}
      <div>
        <div className="text-[10px] font-mono font-bold text-gray-500 uppercase mb-2 flex items-center gap-1">
          <BarChart3 className="w-3 h-3" />
          Propensity Signals
        </div>
        <div className="grid grid-cols-2 gap-2">
          {ps?.LEAD_RESPONSE_PROPENSITY_V1 && (
            <PropensityBadge score={ps.LEAD_RESPONSE_PROPENSITY_V1} label="Response" />
          )}
          {ps?.APPOINTMENT_PROPENSITY_V1 && (
            <PropensityBadge score={ps.APPOINTMENT_PROPENSITY_V1} label="Appointment" />
          )}
          {ps?.SITE_VISIT_PROPENSITY_V1 && (
            <PropensityBadge score={ps.SITE_VISIT_PROPENSITY_V1} label="Site Visit" />
          )}
          {ps?.BOOKING_PROPENSITY_V1 && (
            <PropensityBadge score={ps.BOOKING_PROPENSITY_V1} label="Booking (30d)" />
          )}
          {ps?.OPPORTUNITY_STALL_RISK_V1 && (
            <PropensityBadge score={ps.OPPORTUNITY_STALL_RISK_V1} label="Stall Risk" isRisk />
          )}
          {ps?.LEAD_COLD_RISK_V1 && (
            <PropensityBadge score={ps.LEAD_COLD_RISK_V1} label="Cold Risk" isRisk />
          )}
        </div>
      </div>

      {/* NBA Summary */}
      {nba && nba.action_count > 0 && (
        <div>
          <div className="text-[10px] font-mono font-bold text-gray-500 uppercase mb-2 flex items-center gap-1">
            <Target className="w-3 h-3" />
            Next Best Actions
          </div>

          {/* Reasoning summary */}
          {nba.reasoning_summary && (
            <p className="text-[11px] text-gray-600 font-sans mb-2 leading-relaxed bg-purple-50 border border-purple-100 rounded-lg p-2">
              {nba.reasoning_summary}
            </p>
          )}

          {/* Top action */}
          {topAction && <ActionCard action={topAction} primary />}

          {/* More actions toggle */}
          {otherActions.length > 0 && (
            <>
              <button
                onClick={() => setShowAllActions(v => !v)}
                className="w-full mt-2 flex items-center justify-center gap-1 text-[11px] font-mono text-purple-600 hover:text-purple-800 transition-colors"
              >
                {showAllActions ? (
                  <><ChevronUp className="w-3.5 h-3.5" /> Hide {otherActions.length} more actions</>
                ) : (
                  <><ChevronDown className="w-3.5 h-3.5" /> {otherActions.length} more actions</>
                )}
              </button>

              {showAllActions && (
                <div className="mt-2 space-y-2">
                  {otherActions.map((action, i) => (
                    <ActionCard key={i} action={action} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Feature Drivers Toggle */}
      {(data.positive_drivers.length > 0 || data.negative_drivers.length > 0) && (
        <div>
          <button
            onClick={() => setShowDrivers(v => !v)}
            className="w-full flex items-center justify-between text-[10px] font-mono font-bold text-gray-500 uppercase hover:text-gray-700 transition-colors"
          >
            <span className="flex items-center gap-1">
              <Info className="w-3 h-3" />
              Why this score? (Feature Drivers)
            </span>
            {showDrivers ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          {showDrivers && (
            <div className="mt-2 space-y-1.5">
              {data.positive_drivers.slice(0, 3).map((d, i) => (
                <FeatureDriver key={i} {...d} positive />
              ))}
              {data.negative_drivers.slice(0, 3).map((d, i) => (
                <FeatureDriver key={i} {...d} positive={false} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Prediction metadata footer */}
      <div className="border-t border-[#EAE7E1] pt-2 flex items-center gap-2 text-[9px] font-mono text-gray-400">
        <Shield className="w-3 h-3" />
        <span>ID: {data.prediction_id.slice(0, 8)}…</span>
        <span className="ml-auto">
          {new Date(data.generated_at).toLocaleString('en-US', {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
          })}
        </span>
      </div>
    </div>
  );
}

export default LeadIntelligencePanel;
