'use client';

import { useState, useEffect } from 'react';
import {
  Sparkles,
  Zap,
  Clock,
  ShieldAlert,
  UserCheck,
  Send,
  CheckCircle2,
  AlertCircle,
  PauseCircle,
  PlayCircle,
  MessageSquare,
  Building2,
  RefreshCw,
  Eye,
  FileText
} from 'lucide-react';
import {
  api,
  SalesActionDecisionData,
  FollowUpStateData,
  SalesBriefData
} from '@/lib/api-client';

interface SalesActionCardProps {
  leadId: string;
  leadName?: string;
}

export default function SalesActionCard({ leadId, leadName }: SalesActionCardProps) {
  const [decision, setDecision] = useState<SalesActionDecisionData | null>(null);
  const [followUpState, setFollowUpState] = useState<FollowUpStateData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [executing, setExecuting] = useState<boolean>(false);
  const [customMessage, setCustomMessage] = useState<string>('');
  const [showBriefModal, setShowBriefModal] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchActionAndState = async () => {
    try {
      setLoading(true);
      const [nextDecision, stateData] = await Promise.all([
        api.salesAction.getNextAction(leadId),
        api.salesAction.getFollowUpState(leadId).catch(() => null),
      ]);
      setDecision(nextDecision);
      setFollowUpState(stateData);
      if (nextDecision?.draft_message_body) {
        setCustomMessage(nextDecision.draft_message_body);
      }
    } catch (err: any) {
      console.error('[SalesActionCard] fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (leadId) {
      fetchActionAndState();
    }
  }, [leadId]);

  const handleEvaluate = async () => {
    setEvaluating(true);
    setFeedback(null);
    try {
      const res = await api.salesAction.evaluate(leadId, { force_refresh: true });
      setDecision(res);
      if (res.draft_message_body) setCustomMessage(res.draft_message_body);
      const stateData = await api.salesAction.getFollowUpState(leadId).catch(() => null);
      setFollowUpState(stateData);
      setFeedback({ type: 'success', message: 'Next Best Action recalculated.' });
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Evaluation failed' });
    } finally {
      setEvaluating(false);
    }
  };

  const handleApprove = async () => {
    if (!decision) return;
    setExecuting(true);
    setFeedback(null);
    try {
      const res = await api.salesAction.approve(leadId, decision.action_id, customMessage);
      setDecision(res);
      setFeedback({ type: 'success', message: 'Action approved for automated execution.' });
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Approval failed' });
    } finally {
      setExecuting(false);
    }
  };

  const handleExecute = async () => {
    if (!decision) return;
    setExecuting(true);
    setFeedback(null);
    try {
      const res = await api.salesAction.execute(leadId, decision.action_id, customMessage);
      if (res.status === 'SENT' || res.status === 'COMPLETED') {
        const msgIdPreview = res.provider_message_id ? ` (ID: ${res.provider_message_id.slice(0, 16)}...)` : '';
        setFeedback({
          type: 'success',
          message: `Action dispatched via ${res.provider || res.channel}${msgIdPreview}.`,
        });
      } else if (res.details?.configuration_required) {
        setFeedback({
          type: 'error',
          message: `${res.channel} is not configured: ${res.details?.error || 'Provider credentials required'}.`,
        });
      } else {
        setFeedback({
          type: 'error',
          message: `Delivery failed via ${res.provider || res.channel}: ${res.details?.error || res.status}.`,
        });
      }
      await fetchActionAndState();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Execution failed' });
    } finally {
      setExecuting(false);
    }
  };

  const handleTogglePause = async () => {
    if (!followUpState) return;
    setFeedback(null);
    try {
      if (followUpState.is_paused) {
        const updated = await api.salesAction.resumeFollowUp(leadId);
        setFollowUpState(updated);
        setFeedback({ type: 'success', message: 'Automated follow-up resumed.' });
      } else {
        const updated = await api.salesAction.pauseFollowUp(leadId);
        setFollowUpState(updated);
        setFeedback({ type: 'success', message: 'Automated follow-up paused.' });
      }
      await fetchActionAndState();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Pause/resume failed' });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">APPROVED</span>;
      case 'HUMAN_REVIEW':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30">HUMAN REVIEW</span>;
      case 'BLOCKED':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/20 text-rose-400 border border-rose-500/30">BLOCKED</span>;
      case 'QUEUED':
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-blue-500/20 text-blue-400 border border-blue-500/30">SCHEDULED</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-slate-500/20 text-slate-300 border border-slate-500/30">{status}</span>;
    }
  };

  if (loading) {
    return (
      <div className="glass-panel p-6 rounded-2xl border border-dark-border animate-pulse space-y-4">
        <div className="flex items-center justify-between">
          <div className="h-4 w-40 bg-slate-800 rounded" />
          <div className="h-4 w-20 bg-slate-800 rounded" />
        </div>
        <div className="h-16 bg-slate-800/50 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="glass-panel p-6 rounded-2xl border border-dark-border space-y-5 relative overflow-hidden">
      {/* Top Banner & Title */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Zap className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
              AI Next Best Action
              {decision && getStatusBadge(decision.status)}
            </h3>
            <p className="text-[11px] text-slate-400">
              Deterministic priority engine & compliance guardrails
            </p>
          </div>
        </div>

        <button
          onClick={handleEvaluate}
          disabled={evaluating}
          className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-bold border border-dark-border flex items-center gap-1.5 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${evaluating ? 'animate-spin' : ''}`} />
          <span>Re-Evaluate</span>
        </button>
      </div>

      {/* Notification / Feedback Banner */}
      {feedback && (
        <div
          className={`p-3 rounded-xl text-xs font-semibold flex items-center gap-2 ${
            feedback.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
          }`}
        >
          {feedback.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Main Action Content */}
      {decision ? (
        <div className="space-y-4">
          {/* Action Header Card */}
          <div className="p-4 rounded-xl bg-dark-card/60 border border-dark-border/80 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold tracking-wide uppercase text-emerald-400 font-mono">
                {decision.action_type.replace(/_/g, ' ')}
              </span>
              <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                <span>Priority: <strong className="text-white">{decision.priority.toFixed(0)}/100</strong></span>
                <span>•</span>
                <span>Confidence: <strong className="text-white">{(decision.confidence * 100).toFixed(0)}%</strong></span>
              </div>
            </div>

            <p className="text-xs text-slate-200 leading-relaxed font-medium">
              {decision.reason}
            </p>

            {/* Blocked / Scheduled Warning */}
            {decision.blocked_reason && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-start gap-2">
                <Clock className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-bold">Execution Restricted / Scheduled:</p>
                  <p className="text-[11px] text-amber-400/90 mt-0.5">{decision.blocked_reason}</p>
                </div>
              </div>
            )}

            {/* Properties summary snippet if present */}
            {decision.matched_properties_summary && decision.matched_properties_summary.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-dark-border/60">
                <div className="text-[11px] font-bold text-slate-400 flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Verified Tenant Matches ({decision.matched_properties_count} available):</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {decision.matched_properties_summary.map((prop) => (
                    <div key={prop.property_id} className="p-2 rounded-lg bg-dark-bg/60 border border-dark-border text-[11px]">
                      <div className="font-bold text-white truncate">{prop.title}</div>
                      <div className="text-slate-400">
                        {prop.price.toLocaleString()} {prop.currency} • {prop.bedrooms ? `${prop.bedrooms} BR • ` : ''}{prop.location}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Draft Message Editor */}
          {decision.draft_message_body && (
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-300 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
                  Grounded Phrasing ({decision.recommended_channel}):
                </span>
                <span className="text-[10px] text-slate-400 font-normal">Strict zero-hallucination verified facts</span>
              </label>
              <textarea
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                rows={3}
                className="w-full bg-dark-card border border-dark-border text-xs text-white rounded-xl p-3 focus:outline-none focus:border-emerald-500 transition-all font-sans leading-relaxed"
                placeholder="Draft message content..."
              />
            </div>
          )}

          {/* Sales Brief Trigger (if handoff exists) */}
          {decision.sales_brief && (
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-indigo-300">
                <UserCheck className="w-4 h-4 text-indigo-400" />
                <span>Human Broker Sales Brief Available</span>
              </div>
              <button
                onClick={() => setShowBriefModal(true)}
                className="px-2.5 py-1 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs font-bold transition-all flex items-center gap-1"
              >
                <Eye className="w-3 h-3" />
                <span>View Brief</span>
              </button>
            </div>
          )}

          {/* Action Trigger Buttons */}
          <div className="flex items-center gap-3 pt-2">
            {decision.human_approval_required && decision.status === 'HUMAN_REVIEW' ? (
              <button
                onClick={handleApprove}
                disabled={executing}
                className="flex-1 bg-amber-500 hover:bg-amber-400 text-slate-950 px-4 py-2.5 rounded-xl text-xs font-extrabold transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-1.5 disabled:opacity-50"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Approve Action</span>
              </button>
            ) : decision.status === 'APPROVED' ? (
              <button
                onClick={handleExecute}
                disabled={executing}
                className="flex-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 px-4 py-2.5 rounded-xl text-xs font-extrabold transition-all shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-1.5 disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span>{executing ? 'Executing...' : `Execute (${decision.recommended_channel})`}</span>
              </button>
            ) : null}

            {followUpState && (
              <button
                onClick={handleTogglePause}
                className="px-3.5 py-2.5 rounded-xl bg-dark-card border border-dark-border hover:bg-white/5 text-slate-300 text-xs font-bold transition-all flex items-center gap-1.5"
                title={followUpState.is_paused ? 'Resume automated follow-ups' : 'Pause automated follow-ups'}
              >
                {followUpState.is_paused ? (
                  <>
                    <PlayCircle className="w-4 h-4 text-emerald-400" />
                    <span>Resume Outreach</span>
                  </>
                ) : (
                  <>
                    <PauseCircle className="w-4 h-4 text-amber-400" />
                    <span>Pause Outreach</span>
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-6 text-slate-400 text-xs">
          <p>No active sales action proposal available.</p>
        </div>
      )}

      {/* Follow-Up Fatigue & State Bar */}
      {followUpState && (
        <div className="pt-3 border-t border-dark-border/80 flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-3">
            <span>
              Fatigue Score: <strong className="text-white">{(followUpState.fatigue_score * 100).toFixed(0)}%</strong>
            </span>
            <span>•</span>
            <span>
              Unanswered: <strong className="text-white">{followUpState.consecutive_no_replies}/3</strong>
            </span>
          </div>
          <div>
            Timezone: <strong className="text-white">{decision?.customer_timezone || 'UTC'}</strong>
          </div>
        </div>
      )}

      {/* Sales Brief Modal */}
      {showBriefModal && decision?.sales_brief && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="glass-panel p-6 rounded-2xl border border-dark-border max-w-lg w-full space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                <h4 className="text-sm font-extrabold text-white">Broker Sales Brief</h4>
              </div>
              <button
                onClick={() => setShowBriefModal(false)}
                className="text-slate-400 hover:text-white text-xs font-bold"
              >
                ✕ Close
              </button>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="p-3 rounded-xl bg-dark-card border border-dark-border space-y-1.5">
                <div><strong>Client:</strong> {decision.sales_brief.lead_name}</div>
                <div><strong>Intent:</strong> {decision.sales_brief.lead_intent}</div>
                <div><strong>Budget:</strong> {decision.sales_brief.budget_range}</div>
                <div><strong>Location:</strong> {decision.sales_brief.preferred_location}</div>
                <div><strong>Property Type:</strong> {decision.sales_brief.property_type}</div>
                <div><strong>Timeline:</strong> {decision.sales_brief.timeline}</div>
                <div><strong>Financing:</strong> {decision.sales_brief.financing}</div>
              </div>

              <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300">
                <strong>Escalation Reason:</strong>
                <p className="mt-1">{decision.sales_brief.handoff_reason}</p>
              </div>

              <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
                <strong>Recommended Human Action:</strong>
                <p className="mt-1">{decision.sales_brief.recommended_human_action}</p>
              </div>

              <div className="p-3 rounded-xl bg-dark-card border border-dark-border text-slate-400">
                <strong>Recent Conversation Summary:</strong>
                <p className="mt-1 text-slate-200">{decision.sales_brief.recent_conversation_summary}</p>
              </div>
            </div>

            <button
              onClick={() => setShowBriefModal(false)}
              className="w-full py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white text-xs font-bold transition-all"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
