'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Zap,
  Shield,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  PauseCircle,
  PlayCircle,
  UserCheck,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Bot,
  User,
  MessageSquare,
  Building2,
  Calendar,
  ThumbsUp,
  ThumbsDown,
  Inbox,
  Eye,
  Info
} from 'lucide-react';
import { api } from '@/lib/api-client';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface TimelineEntry {
  audit_id: string;
  event_type: string;
  action_type?: string;
  automation_permission?: string;
  lifecycle_state_before?: string;
  lifecycle_state_after?: string;
  guard_passed: boolean;
  blocking_guard?: string;
  blocking_reason?: string;
  provider_status?: string;
  decision_reason: string;
  occurred_at: string;
  actor_type: string;
}

interface AutomationState {
  lead_id: string;
  is_paused: boolean;
  is_broker_takeover: boolean;
  current_lifecycle_state: string;
  daily_action_count: number;
  consecutive_failures: number;
  pending_action_type?: string;
  pending_since?: string;
  last_event_type?: string;
  last_event_at?: string;
}

interface ExplainabilityDetail {
  audit_id: string;
  event_type: string;
  action_type?: string;
  automation_permission?: string;
  qualification_state: string;
  qualification_completeness: number;
  matched_properties_count: number;
  buying_signal_level: string;
  guard_results: Array<{
    guard_name: string;
    passed: boolean;
    reason?: string;
    details?: Record<string, unknown>;
  }>;
  provider_status?: string;
  decision_reason: string;
  lifecycle_state_before?: string;
  lifecycle_state_after?: string;
  occurred_at: string;
}

interface Props {
  leadId: string;
  leadName?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper utilities
// ─────────────────────────────────────────────────────────────────────────────

function formatEventType(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const GUARD_LABEL: Record<string, string> = {
  CONSENT: 'Consent',
  QUIET_HOURS: 'Quiet Hours',
  FATIGUE: 'Fatigue',
  HUMAN_APPROVAL: 'Human Approval',
  LOOP_PROTECTION: 'Loop Protection',
  LEAD_LIFECYCLE: 'Lifecycle',
  AUTOMATION_POLICY: 'Policy',
};

const STATE_COLORS: Record<string, string> = {
  NEW: 'bg-slate-500',
  CONTACTING: 'bg-sky-500',
  ENGAGING: 'bg-violet-500',
  QUALIFYING: 'bg-amber-500',
  QUALIFIED: 'bg-emerald-500',
  PROPERTY_MATCHED: 'bg-teal-500',
  VIEWING_PENDING: 'bg-orange-500',
  VIEWING_SCHEDULED: 'bg-blue-500',
  VIEWING_COMPLETED: 'bg-indigo-500',
  NEGOTIATION: 'bg-yellow-500',
  BOOKING: 'bg-green-500',
  CONVERTED: 'bg-emerald-600',
  DORMANT: 'bg-slate-400',
  LOST: 'bg-red-500',
  OPTED_OUT: 'bg-red-600',
  HUMAN_HANDOFF: 'bg-purple-500',
};

const ACTOR_ICON: Record<string, JSX.Element> = {
  SYSTEM: <Bot className="w-3 h-3" />,
  AI: <Zap className="w-3 h-3" />,
  BROKER: <User className="w-3 h-3" />,
  CUSTOMER: <MessageSquare className="w-3 h-3" />,
  SCHEDULER: <Clock className="w-3 h-3" />,
};

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LifecycleBadge({ state }: { state?: string }) {
  if (!state) return null;
  const colorClass = STATE_COLORS[state] ?? 'bg-slate-400';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold text-white ${colorClass}`}>
      {formatEventType(state)}
    </span>
  );
}

function GuardChip({ name, passed }: { name: string; passed: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${
        passed
          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
          : 'bg-red-500/20 text-red-300 border border-red-500/30'
      }`}
    >
      {passed ? <CheckCircle2 className="w-2.5 h-2.5" /> : <XCircle className="w-2.5 h-2.5" />}
      {GUARD_LABEL[name] ?? name}
    </span>
  );
}

function ExplainabilityPanel({
  detail,
  onClose
}: {
  detail: ExplainabilityDetail;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl bg-[#111827] border border-white/10 shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between p-5 bg-[#111827]/90 backdrop-blur-sm border-b border-white/10">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-semibold text-white">Why did BeetleLabs do this?</span>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Event + Action */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-xl p-3">
              <p className="text-[10px] uppercase text-white/40 mb-1">Trigger Event</p>
              <p className="text-sm font-semibold text-white">{formatEventType(detail.event_type)}</p>
            </div>
            <div className="bg-white/5 rounded-xl p-3">
              <p className="text-[10px] uppercase text-white/40 mb-1">Action Taken</p>
              <p className="text-sm font-semibold text-violet-300">
                {detail.action_type ? formatEventType(detail.action_type) : 'No action'}
              </p>
            </div>
          </div>

          {/* Lifecycle transition */}
          {(detail.lifecycle_state_before || detail.lifecycle_state_after) && (
            <div className="flex items-center gap-3">
              <LifecycleBadge state={detail.lifecycle_state_before} />
              <ArrowRight className="w-4 h-4 text-white/30" />
              <LifecycleBadge state={detail.lifecycle_state_after} />
            </div>
          )}

          {/* Intelligence context */}
          <div>
            <p className="text-[10px] uppercase text-white/40 mb-2">Intelligence Context</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-lg p-3">
                <p className="text-[10px] text-white/40">Qualification State</p>
                <p className="text-xs font-semibold text-white">{detail.qualification_state}</p>
                <div className="mt-1 h-1 rounded-full bg-white/10 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-violet-500"
                    style={{ width: `${Math.round(detail.qualification_completeness * 100)}%` }}
                  />
                </div>
                <p className="text-[10px] text-white/40 mt-0.5">
                  {Math.round(detail.qualification_completeness * 100)}% complete
                </p>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <p className="text-[10px] text-white/40">Property Matches</p>
                <p className="text-2xl font-bold text-teal-400">{detail.matched_properties_count}</p>
              </div>
              <div className="bg-white/5 rounded-lg p-3 col-span-2">
                <p className="text-[10px] text-white/40">Buying Signal</p>
                <p className="text-xs font-semibold text-amber-300">{detail.buying_signal_level}</p>
              </div>
            </div>
          </div>

          {/* Guard chain */}
          <div>
            <p className="text-[10px] uppercase text-white/40 mb-2">Guard Chain Results</p>
            <div className="space-y-1.5">
              {detail.guard_results.map((g, i) => (
                <div
                  key={i}
                  className={`flex items-start gap-2 p-2 rounded-lg ${
                    g.passed ? 'bg-emerald-500/10' : 'bg-red-500/10'
                  }`}
                >
                  {g.passed
                    ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />
                    : <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />}
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-white">{GUARD_LABEL[g.guard_name] ?? g.guard_name}</p>
                    {g.reason && <p className="text-[11px] text-white/50 mt-0.5 truncate">{g.reason}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Decision rationale */}
          <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl p-3">
            <p className="text-[10px] uppercase text-violet-300 mb-1">Decision Rationale</p>
            <p className="text-sm text-white/80 leading-relaxed">{detail.decision_reason || '—'}</p>
          </div>

          <p className="text-[10px] text-white/30 text-right">
            {new Date(detail.occurred_at).toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export default function AutonomousSalesTimeline({ leadId, leadName }: Props) {
  const [automationState, setAutomationState] = useState<AutomationState | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [explainDetail, setExplainDetail] = useState<ExplainabilityDetail | null>(null);
  const [loadingState, setLoadingState] = useState(true);
  const [loadingTimeline, setLoadingTimeline] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const loadAll = useCallback(async () => {
    setLoadingState(true);
    setLoadingTimeline(true);
    try {
      const [stateRes, timelineRes] = await Promise.allSettled([
        fetch(`/api/v1/autonomous-loop/leads/${leadId}/state`, { credentials: 'include' }),
        fetch(`/api/v1/autonomous-loop/leads/${leadId}/timeline?limit=30`, { credentials: 'include' }),
      ]);
      if (stateRes.status === 'fulfilled' && stateRes.value.ok) {
        const json = await stateRes.value.json();
        setAutomationState(json.data ?? json);
      }
      if (timelineRes.status === 'fulfilled' && timelineRes.value.ok) {
        const json = await timelineRes.value.json();
        setTimeline(Array.isArray(json.data) ? json.data : []);
      }
    } catch (err) {
      console.error('[AutonomousSalesTimeline] load error:', err);
    } finally {
      setLoadingState(false);
      setLoadingTimeline(false);
    }
  }, [leadId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleBrokerAction = async (
    action: 'pause' | 'resume' | 'handoff',
    extra?: Record<string, string>
  ) => {
    setActionLoading(action);
    try {
      const body = action === 'resume' ? {} : { reason: extra?.reason ?? `Broker ${action}` };
      const res = await fetch(`/api/v1/autonomous-loop/leads/${leadId}/${action}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setFeedback({ type: 'success', msg: `Lead automation ${action} successful.` });
      await loadAll();
    } catch (err: any) {
      setFeedback({ type: 'error', msg: err.message || `Failed to ${action} automation.` });
    } finally {
      setActionLoading(null);
      setTimeout(() => setFeedback(null), 3000);
    }
  };

  const handleApprove = async (actionId: string) => {
    setActionLoading(`approve_${actionId}`);
    try {
      const res = await fetch(`/api/v1/autonomous-loop/leads/${leadId}/approve/${actionId}`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) throw new Error(await res.text());
      setFeedback({ type: 'success', msg: 'Action approved and dispatched.' });
      await loadAll();
    } catch (err: any) {
      setFeedback({ type: 'error', msg: err.message || 'Approval failed.' });
    } finally {
      setActionLoading(null);
      setTimeout(() => setFeedback(null), 3000);
    }
  };

  const handleExplain = async (auditId: string) => {
    try {
      const res = await fetch(`/api/v1/autonomous-loop/leads/${leadId}/explain/${auditId}`, {
        credentials: 'include',
      });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setExplainDetail(json.data ?? json);
    } catch (err: any) {
      setFeedback({ type: 'error', msg: 'Could not load explanation.' });
      setTimeout(() => setFeedback(null), 3000);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (loadingState && loadingTimeline) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-24 rounded-2xl bg-white/5" />
        <div className="h-48 rounded-2xl bg-white/5" />
      </div>
    );
  }

  const state = automationState;

  return (
    <div className="space-y-5">
      {/* Feedback toast */}
      {feedback && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-xl shadow-xl text-sm font-medium ${
            feedback.type === 'success'
              ? 'bg-emerald-500 text-white'
              : 'bg-red-500 text-white'
          }`}
        >
          {feedback.type === 'success'
            ? <CheckCircle2 className="w-4 h-4" />
            : <AlertCircle className="w-4 h-4" />}
          {feedback.msg}
        </div>
      )}

      {/* Automation State Panel */}
      {state && (
        <div className="rounded-2xl bg-[#0f172a] border border-white/10 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-violet-500/20">
                <Activity className="w-4 h-4 text-violet-400" />
              </div>
              <span className="text-sm font-semibold text-white">Autonomous Sales Loop</span>
            </div>
            <button
              onClick={loadAll}
              disabled={loadingState}
              className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/5 transition-all"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingState ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* State metrics */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-[10px] text-white/40 mb-1">Lifecycle State</p>
              <LifecycleBadge state={state.current_lifecycle_state} />
            </div>
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-[10px] text-white/40 mb-1">Actions Today</p>
              <p className="text-xl font-bold text-white">{state.daily_action_count}</p>
            </div>
            <div className="bg-white/5 rounded-xl p-3 text-center">
              <p className="text-[10px] text-white/40 mb-1">Failures</p>
              <p className={`text-xl font-bold ${state.consecutive_failures > 2 ? 'text-red-400' : 'text-white'}`}>
                {state.consecutive_failures}
              </p>
            </div>
          </div>

          {/* Status badges */}
          <div className="flex flex-wrap gap-2 mb-4">
            {state.is_paused && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-semibold">
                <PauseCircle className="w-3 h-3" /> Paused
              </span>
            )}
            {state.is_broker_takeover && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-purple-500/20 border border-purple-500/30 text-purple-300 text-xs font-semibold">
                <UserCheck className="w-3 h-3" /> Broker Takeover
              </span>
            )}
            {!state.is_paused && !state.is_broker_takeover && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs font-semibold">
                <Zap className="w-3 h-3" /> Active
              </span>
            )}
          </div>

          {/* Pending approval notice */}
          {state.pending_action_type && (
            <div className="mb-4 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-amber-300">Pending Approval</p>
                <p className="text-[11px] text-white/60 mt-0.5">
                  {formatEventType(state.pending_action_type)} — waiting since{' '}
                  {state.pending_since ? relativeTime(state.pending_since) : 'unknown'}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  id={`approve-pending-${leadId}`}
                  onClick={() => handleApprove('pending')}
                  disabled={actionLoading === 'approve_pending'}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-semibold transition-all"
                >
                  <ThumbsUp className="w-3 h-3" /> Approve
                </button>
              </div>
            </div>
          )}

          {/* Broker controls */}
          <div className="flex flex-wrap gap-2">
            {state.is_paused ? (
              <button
                id={`resume-automation-${leadId}`}
                onClick={() => handleBrokerAction('resume')}
                disabled={actionLoading === 'resume'}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-semibold transition-all disabled:opacity-50"
              >
                <PlayCircle className="w-3.5 h-3.5" />
                {actionLoading === 'resume' ? 'Resuming…' : 'Resume Automation'}
              </button>
            ) : (
              <button
                id={`pause-automation-${leadId}`}
                onClick={() => handleBrokerAction('pause', { reason: 'Broker manually paused.' })}
                disabled={actionLoading === 'pause'}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-white text-xs font-semibold transition-all disabled:opacity-50"
              >
                <PauseCircle className="w-3.5 h-3.5" />
                {actionLoading === 'pause' ? 'Pausing…' : 'Pause Automation'}
              </button>
            )}
            {!state.is_broker_takeover && (
              <button
                id={`broker-takeover-${leadId}`}
                onClick={() => handleBrokerAction('handoff', { reason: 'Broker requested direct control.' })}
                disabled={actionLoading === 'handoff'}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
              >
                <UserCheck className="w-3.5 h-3.5" />
                {actionLoading === 'handoff' ? 'Activating…' : 'Take Over'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="rounded-2xl bg-[#0f172a] border border-white/10 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-sky-500/20">
              <Clock className="w-4 h-4 text-sky-400" />
            </div>
            <span className="text-sm font-semibold text-white">Autonomous Sales Timeline</span>
          </div>
          <span className="text-xs text-white/30">{timeline.length} events</span>
        </div>

        {loadingTimeline ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-5 h-5 text-white/20 animate-spin" />
          </div>
        ) : timeline.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <Inbox className="w-8 h-8 text-white/10" />
            <p className="text-sm text-white/30">No events yet — the loop will activate on the next trigger.</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {timeline.map((entry) => {
              const isExpanded = expandedIds.has(entry.audit_id);
              const stateChanged = entry.lifecycle_state_before !== entry.lifecycle_state_after &&
                entry.lifecycle_state_after;

              return (
                <div key={entry.audit_id} className="px-5 py-3.5 hover:bg-white/[0.02] transition-colors">
                  {/* Row header */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5 min-w-0">
                      {/* Actor icon */}
                      <div className="mt-0.5 p-1 rounded-md bg-white/5 text-white/40 shrink-0">
                        {ACTOR_ICON[entry.actor_type] ?? <Bot className="w-3 h-3" />}
                      </div>

                      <div className="min-w-0 flex-1">
                        {/* Event type + action */}
                        <div className="flex flex-wrap items-center gap-1.5">
                          <p className="text-xs font-semibold text-white truncate">
                            {formatEventType(entry.event_type)}
                          </p>
                          {entry.action_type && (
                            <>
                              <ArrowRight className="w-3 h-3 text-white/20 shrink-0" />
                              <span className="text-xs text-violet-400 font-medium">
                                {formatEventType(entry.action_type)}
                              </span>
                            </>
                          )}
                        </div>

                        {/* Guard chips (max 4) */}
                        {!entry.guard_passed && entry.blocking_guard && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            <GuardChip name={entry.blocking_guard} passed={false} />
                          </div>
                        )}

                        {/* State transition */}
                        {stateChanged && (
                          <div className="flex items-center gap-1.5 mt-1">
                            <LifecycleBadge state={entry.lifecycle_state_before} />
                            <ArrowRight className="w-3 h-3 text-white/20" />
                            <LifecycleBadge state={entry.lifecycle_state_after} />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right side */}
                    <div className="flex items-center gap-2 shrink-0">
                      {/* Status icon */}
                      {entry.guard_passed ? (
                        entry.provider_status ? (
                          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                            entry.provider_status.includes('FAIL') || entry.provider_status.includes('ERROR')
                              ? 'bg-red-500/20 text-red-300'
                              : 'bg-emerald-500/20 text-emerald-300'
                          }`}>
                            {entry.provider_status}
                          </span>
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500/60" />
                        )
                      ) : (
                        <Shield className="w-3.5 h-3.5 text-amber-400/60" />
                      )}

                      <span className="text-[10px] text-white/30 whitespace-nowrap">
                        {relativeTime(entry.occurred_at)}
                      </span>

                      {/* Explain button */}
                      <button
                        onClick={() => handleExplain(entry.audit_id)}
                        className="p-1 rounded text-white/20 hover:text-violet-400 hover:bg-violet-500/10 transition-all"
                        title="Why did this happen?"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>

                      {/* Expand toggle */}
                      <button
                        onClick={() => toggleExpand(entry.audit_id)}
                        className="p-1 rounded text-white/20 hover:text-white/60 hover:bg-white/5 transition-all"
                      >
                        {isExpanded
                          ? <ChevronUp className="w-3.5 h-3.5" />
                          : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="mt-3 pl-7 space-y-2">
                      <div className="bg-white/5 rounded-xl p-3">
                        <p className="text-[10px] uppercase text-white/30 mb-1">Decision Reason</p>
                        <p className="text-xs text-white/70 leading-relaxed">
                          {entry.decision_reason || '—'}
                        </p>
                      </div>
                      {entry.blocking_reason && (
                        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-3">
                          <p className="text-[10px] uppercase text-amber-300 mb-1">Blocked By {GUARD_LABEL[entry.blocking_guard ?? ''] ?? entry.blocking_guard}</p>
                          <p className="text-xs text-white/70">{entry.blocking_reason}</p>
                        </div>
                      )}
                      <button
                        onClick={() => handleExplain(entry.audit_id)}
                        className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition-colors"
                      >
                        <Info className="w-3 h-3" /> Full Explainability Report
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Explainability modal */}
      {explainDetail && (
        <ExplainabilityPanel
          detail={explainDetail}
          onClose={() => setExplainDetail(null)}
        />
      )}
    </div>
  );
}
