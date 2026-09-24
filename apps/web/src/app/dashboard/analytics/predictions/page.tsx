'use client';

/**
 * Part 16 — Predictive Intelligence Analytics Page
 * ==================================================
 * Prediction Model Registry, Data Sufficiency Audit, and Target Catalog.
 * Route: /dashboard/analytics/predictions
 */

import React, { useState, useEffect } from 'react';
import {
  Sparkles, BarChart3, Shield, TrendingUp, AlertTriangle, CheckCircle2,
  RefreshCw, Database, Target, Info, ChevronRight, Activity, Clock,
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { PageHeader, Button } from '@/components/ui';
import {
  getDataSufficiencyAudit,
  getPredictionTargets,
} from '@/lib/api/predictions';
import type {
  DataSufficiencyAuditDTO,
  PredictionTargetDefinitionDTO,
  DataSufficiencyGateResultDTO,
} from '@/types/predictive';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(status: string) {
  const map: Record<string, string> = {
    ACTIVE: 'bg-emerald-100 text-emerald-800 border-emerald-300',
    BASELINE: 'bg-blue-100 text-blue-800 border-blue-300',
    SHADOW: 'bg-purple-100 text-purple-800 border-purple-300',
    INSUFFICIENT_DATA: 'bg-gray-100 text-gray-600 border-gray-300',
    ERROR: 'bg-red-100 text-red-800 border-red-300',
    UNAVAILABLE: 'bg-gray-100 text-gray-500 border-gray-200',
  };
  return map[status] || 'bg-gray-100 text-gray-600 border-gray-200';
}

function methodBadge(method: string) {
  const map: Record<string, string> = {
    DETERMINISTIC_HEURISTIC: 'bg-yellow-50 text-yellow-800 border-yellow-200',
    STATISTICAL_BASELINE: 'bg-blue-50 text-blue-800 border-blue-200',
    VALIDATED_ML: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    UNAVAILABLE: 'bg-gray-50 text-gray-600 border-gray-200',
    INSUFFICIENT_DATA: 'bg-gray-50 text-gray-500 border-gray-200',
  };
  return map[method] || 'bg-gray-50 text-gray-600 border-gray-200';
}

// ─── Gate Result Row ──────────────────────────────────────────────────────────

function GateResultRow({ targetId, result }: { targetId: string; result: DataSufficiencyGateResultDTO }) {
  const [expanded, setExpanded] = useState(false);
  const balancePct = result.class_balance_ratio * 100;

  return (
    <div className={`border rounded-xl overflow-hidden transition-all ${result.gate_passed ? 'border-emerald-200' : 'border-gray-200'}`}>
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full p-3 flex items-center gap-3 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="shrink-0">
          {result.gate_passed
            ? <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            : <AlertTriangle className="w-4 h-4 text-amber-500" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-bold text-xs text-gray-900">{targetId}</span>
            <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${methodBadge(result.resolved_method)}`}>
              {result.resolved_method.replace('_', ' ')}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-[10px] font-mono text-gray-500">
            <span>Eligible: <strong>{result.eligible_rows}</strong></span>
            <span>Positives: <strong>{result.positive_labels}</strong></span>
            <span>Balance: <strong className={balancePct >= 10 ? 'text-emerald-600' : balancePct >= 3 ? 'text-yellow-600' : 'text-red-600'}>{balancePct.toFixed(1)}%</strong></span>
          </div>
        </div>
        <ChevronRight className={`w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-100 bg-gray-50/50 space-y-2">
          <div className="grid grid-cols-4 gap-2 text-center">
            {[
              { label: 'Eligible Rows', value: result.eligible_rows, color: 'text-gray-900' },
              { label: 'Positives', value: result.positive_labels, color: 'text-emerald-700' },
              { label: 'Negatives', value: result.negative_labels, color: 'text-rose-700' },
              { label: 'Balance', value: `${balancePct.toFixed(1)}%`, color: balancePct >= 10 ? 'text-emerald-700' : 'text-amber-700' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-white border border-gray-200 rounded-lg p-2">
                <div className={`text-base font-extrabold font-mono ${color}`}>{value}</div>
                <div className="text-[9px] font-mono text-gray-400 uppercase">{label}</div>
              </div>
            ))}
          </div>
          <div className={`text-[11px] font-sans rounded-lg p-2.5 ${result.gate_passed ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-amber-50 text-amber-800 border border-amber-200'}`}>
            {result.reason}
          </div>
          <div className="text-[9px] font-mono text-gray-400">
            Evaluated: {new Date(result.evaluated_at).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Target Definition Card ───────────────────────────────────────────────────

function TargetCard({ target }: { target: PredictionTargetDefinitionDTO }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-[#D4D0C8] rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full p-3.5 flex items-center gap-3 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono font-bold text-xs text-gray-900">{target.name}</span>
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${statusBadge(target.status)}`}>
              {target.status}
            </span>
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${methodBadge(target.method)}`}>
              {target.method.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{target.definition}</p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[9px] font-mono text-gray-400">v{target.version}</div>
          <div className="text-[9px] font-mono text-gray-400">{target.lookahead_window_days}d window</div>
        </div>
        <ChevronRight className={`w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-gray-100 space-y-3">
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div>
              <div className="font-mono font-bold text-emerald-700 mb-1">✓ Positive outcome</div>
              <div className="text-gray-600 font-sans">{target.positive_outcome}</div>
            </div>
            <div>
              <div className="font-mono font-bold text-rose-700 mb-1">✗ Negative outcome</div>
              <div className="text-gray-600 font-sans">{target.negative_outcome}</div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'Min Rows', value: target.min_eligible_rows },
              { label: 'Min Positives', value: target.min_positive_labels },
              { label: 'Lookahead', value: `${target.lookahead_window_days}d` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-gray-50 border border-gray-200 rounded-lg p-2">
                <div className="text-sm font-extrabold font-mono text-gray-900">{value}</div>
                <div className="text-[9px] font-mono text-gray-400 uppercase">{label}</div>
              </div>
            ))}
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-2.5 text-[11px] font-sans text-blue-800">
            <strong className="font-mono">Reason: </strong>{target.reason}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function PredictiveIntelligencePage() {
  const [audit, setAudit] = useState<DataSufficiencyAuditDTO | null>(null);
  const [targets, setTargets] = useState<PredictionTargetDefinitionDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (refresh = false) => {
    if (refresh) setRefreshing(true);
    try {
      const [auditRes, targetsRes] = await Promise.all([
        getDataSufficiencyAudit().catch(() => null),
        getPredictionTargets().catch(() => ({ total_targets: 0, targets: [] })),
      ]);
      setAudit(auditRes);
      setTargets(targetsRes.targets);
    } catch (e) {
      // silent
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const passedCount = audit?.summary.gate_passed ?? 0;
  const failedCount = audit?.summary.gate_failed ?? 0;
  const totalCount = audit?.summary.total_targets ?? 0;

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="PREDICTIVE INTELLIGENCE"
          description="Model registry, data sufficiency validation, statistical baseline heuristics, and propensity target catalog."
          breadcrumbs={[
            { label: 'Intelligence', href: '/dashboard/revenue-intelligence' },
            { label: 'Predictive Models' },
          ]}
          actions={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => loadData(true)}
              disabled={refreshing}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />}
            >
              Refresh Audit
            </Button>
          }
        />

      {/* Summary cards */}
      {audit && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Total Targets', value: totalCount, icon: Target, color: 'text-gray-900' },
            { label: 'Gate Passed', value: passedCount, icon: CheckCircle2, color: 'text-emerald-700' },
            { label: 'Gate Failed', value: failedCount, icon: AlertTriangle, color: 'text-amber-700' },
            { label: 'Insufficient Data', value: audit.summary.insufficient_data, icon: Database, color: 'text-gray-500' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white border border-[#D4D0C8] rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono uppercase text-gray-400 font-bold">{label}</span>
                <Icon className={`w-4 h-4 ${color}`} />
              </div>
              <span className={`text-3xl font-extrabold font-mono ${color}`}>{value}</span>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Data Sufficiency Gate Results */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-purple-600" />
            <h2 className="font-mono font-bold text-sm text-gray-900">Data Sufficiency Gate</h2>
            <span className="text-[9px] font-mono text-gray-500 bg-[#FAF7F2] border border-[#D4D0C8] px-2 py-0.5 rounded-full font-bold">
              AUTOMATED GATE
            </span>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-14 bg-gray-200 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : audit ? (
            <div className="space-y-2">
              {Object.entries(audit.targets).map(([tid, result]) => (
                <GateResultRow key={tid} targetId={tid} result={result} />
              ))}
            </div>
          ) : (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-700 font-sans">
              Data sufficiency audit unavailable. Ensure the API is running.
            </div>
          )}
        </div>

        {/* Prediction Target Catalog */}
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-purple-600" />
            <h2 className="font-mono font-bold text-sm text-gray-900">Prediction Target Catalog</h2>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-16 bg-gray-200 animate-pulse rounded-xl" />
              ))}
            </div>
          ) : targets.length > 0 ? (
            <div className="space-y-2">
              {targets.map(t => <TargetCard key={t.target_id} target={t} />)}
            </div>
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-500 font-sans">
              No prediction targets loaded.
            </div>
          )}
        </div>
      </div>

      {/* Audit timestamp footer */}
      {audit && (
        <div className="flex items-center gap-2 text-[10px] font-mono text-[#6B6B6B] pt-4 border-t border-[#D4D0C8]">
          <Clock className="w-3 h-3" />
          <span>Last automated audit: {new Date(audit.audit_timestamp).toLocaleString()}</span>
        </div>
      )}
      </main>
    </div>
  );
}
