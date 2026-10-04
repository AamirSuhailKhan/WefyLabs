'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2, Clock, AlertCircle, Zap, Phone, MessageSquare,
  RefreshCw, ChevronRight, Bell, BarChart2,
  TrendingUp, X, Sparkles, ArrowRight
} from 'lucide-react';
import { api } from '@/lib/api-client';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FollowUpSummary {
  total_leads?: number;
  today_tasks?: number;
  overdue_count?: number;
  pending_approval?: number;
  dispatched_today?: number;
  response_rate_pct?: number;
  top_priority_leads?: PriorityLead[];
}

interface PriorityLead {
  lead_id: string;
  lead_name: string;
  phone: string;
  score: string;
  pipeline_stage: string;
  next_action: string;
  action_reason: string;
  priority_score: number;
  days_since_contact: number;
  fatigue_score: number;
  is_suppressed: boolean;
}

interface FollowUpExecution {
  id: string;
  lead_id: string;
  lead_name?: string;
  channel: string;
  message_draft?: string;
  status: string;
  scheduled_at?: string;
  created_at: string;
}

interface DailyBriefing {
  date?: string;
  total_leads?: number;
  hot_leads?: number;
  overdue_followups?: number;
  today_scheduled?: number;
  pending_approval_count?: number;
  top_actions?: string[];
  response_rate?: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function scorePillCls(score: string) {
  const map: Record<string, string> = {
    hot: 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]',
    warm: 'bg-[#EDE9FE] text-[#7C3AED] border-[#DDD6FE]',
    cold: 'bg-[#DBEAFE] text-[#1D4ED8] border-[#BFDBFE]',
    pending: 'bg-[#F5F0EB] text-[#6B6B6B] border-[#D4D0C8]',
  };
  return map[(score || 'pending').toLowerCase()] || map.pending;
}

function channelIcon(channel: string) {
  const c = (channel || '').toLowerCase();
  if (c.includes('whatsapp') || c.includes('wa')) return '💬';
  if (c.includes('email')) return '✉️';
  if (c.includes('sms')) return '📱';
  if (c.includes('call') || c.includes('phone')) return '📞';
  return '📨';
}

function timeAgo(iso?: string) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ─── Stat Tile ────────────────────────────────────────────────────────────────

function StatTile({
  label, value, sub, accent, pulse
}: {
  label: string; value: number | string; sub?: string; accent: string; pulse?: boolean;
}) {
  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-4 flex flex-col gap-1">
      <div className={`text-[26px] font-extrabold font-mono ${accent} flex items-center gap-2`}>
        {value}
        {pulse && <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />}
      </div>
      <div className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]">{label}</div>
      {sub && <div className="text-[10px] text-[#9B9B9B]">{sub}</div>}
    </div>
  );
}

// ─── Priority Lead Card ───────────────────────────────────────────────────────

function PriorityLeadCard({
  lead, onEvaluate, onOpenLead
}: {
  lead: PriorityLead;
  onEvaluate: (id: string) => void;
  onOpenLead?: (id: string) => void;
}) {
  const urgency =
    lead.priority_score >= 0.8 ? 'border-red-300 bg-red-50/30' :
    lead.priority_score >= 0.5 ? 'border-amber-200 bg-amber-50/20' :
    'border-[#D4D0C8] bg-[#FAF7F2]';

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`border rounded-xl p-4 space-y-2.5 ${urgency}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              className="text-[13px] font-bold text-[#1A1A1A] truncate hover:text-[#0D9488] transition-colors"
              onClick={() => onOpenLead?.(lead.lead_id)}
            >
              {lead.lead_name || 'Lead'}
            </button>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${scorePillCls(lead.score)}`}>
              {(lead.score || 'PENDING').toUpperCase()}
            </span>
            {lead.is_suppressed && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 border border-gray-200">
                SUPPRESSED
              </span>
            )}
          </div>
          <div className="text-[11px] text-[#6B6B6B] font-mono mt-0.5">
            {lead.phone} · {(lead.pipeline_stage || 'new').replace(/_/g, ' ').toUpperCase()}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[11px] font-bold text-[#0D9488]">
            Priority {Math.round((lead.priority_score || 0) * 100)}%
          </div>
          <div className="text-[10px] text-[#9B9B9B]">
            {lead.days_since_contact > 0 ? `${lead.days_since_contact}d silent` : 'Active'}
          </div>
        </div>
      </div>

      {lead.next_action && (
        <div className="flex items-start gap-2 p-2.5 bg-white/80 rounded-lg border border-[#E2E8F0]">
          <Sparkles className="w-3.5 h-3.5 text-[#7C3AED] mt-0.5 shrink-0" />
          <div className="min-w-0">
            <span className="text-[11px] font-bold text-[#7C3AED] block">
              {lead.next_action.replace(/_/g, ' ')}
            </span>
            {lead.action_reason && (
              <span className="text-[10px] text-[#64748B] leading-snug">{lead.action_reason}</span>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 pt-0.5">
        <a
          href={`tel:${lead.phone}`}
          className="flex items-center gap-1 px-2.5 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-[11px] font-bold transition-all"
        >
          <Phone className="w-3 h-3" /> Call
        </a>
        <a
          href={`https://wa.me/${lead.phone.replace(/\D/g, '')}`}
          target="_blank" rel="noreferrer"
          className="flex items-center gap-1 px-2.5 py-1.5 bg-green-500 hover:bg-green-600 text-white rounded-lg text-[11px] font-bold transition-all"
        >
          <MessageSquare className="w-3 h-3" /> WhatsApp
        </a>
        <button
          onClick={() => onEvaluate(lead.lead_id)}
          className="flex items-center gap-1 px-2.5 py-1.5 bg-[#EDE9FE] hover:bg-[#DDD6FE] text-[#7C3AED] rounded-lg text-[11px] font-bold transition-all border border-[#DDD6FE]"
        >
          <Zap className="w-3 h-3" /> Evaluate
        </button>
        {onOpenLead && (
          <button
            onClick={() => onOpenLead(lead.lead_id)}
            className="ml-auto flex items-center gap-1 text-[11px] text-[#64748B] hover:text-[#0D9488] font-semibold transition-colors"
          >
            Open <ChevronRight className="w-3 h-3" />
          </button>
        )}
      </div>
    </motion.div>
  );
}

// ─── Approval Queue Card ──────────────────────────────────────────────────────

function ApprovalQueueCard({
  item, onApprove, onCancel
}: {
  item: FollowUpExecution;
  onApprove: (id: string) => void;
  onCancel: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-[#FFFBEB] border border-[#FDE68A] rounded-xl p-4 space-y-2"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-[#D97706]" />
          <span className="text-[12px] font-bold text-[#92400E]">Pending Approval</span>
          <span className="text-[10px] text-[#B45309]">
            {channelIcon(item.channel)} {(item.channel || 'WHATSAPP').toUpperCase()}
          </span>
        </div>
        <span className="text-[10px] text-[#9B9B9B] font-mono">{timeAgo(item.created_at)}</span>
      </div>

      {item.lead_name && (
        <div className="text-[12px] font-semibold text-[#1A1A1A]">→ {item.lead_name}</div>
      )}

      {item.message_draft && (
        <div className="space-y-1">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[10px] text-[#D97706] font-bold hover:underline"
          >
            {expanded ? '▲ Hide message' : '▼ View draft'}
          </button>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="p-3 bg-white border border-[#FDE68A] rounded-lg text-[11px] text-[#1A1A1A] leading-relaxed whitespace-pre-wrap">
                  {item.message_draft}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() => onApprove(item.id)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-[11px] font-bold transition-all"
        >
          <CheckCircle2 className="w-3.5 h-3.5" /> Approve &amp; Send
        </button>
        <button
          onClick={() => onCancel(item.id)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-[#FEE2E2] text-[#B91C1C] border border-[#FECACA] rounded-lg text-[11px] font-bold transition-all"
        >
          <X className="w-3.5 h-3.5" /> Cancel
        </button>
      </div>
    </motion.div>
  );
}

// ─── Main Export ──────────────────────────────────────────────────────────────

interface Props {
  onOpenLead?: (id: string) => void;
}

export default function FollowUpWorkQueueView({ onOpenLead }: Props) {
  const [summary, setSummary] = useState<FollowUpSummary | null>(null);
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [approvalQueue, setApprovalQueue] = useState<FollowUpExecution[]>([]);
  const [analytics, setAnalytics] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'queue' | 'approvals' | 'analytics'>('queue');
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, briefRes, analyticsRes] = await Promise.allSettled([
        api.followups.getDashboardSummary(),
        api.followups.getDailyBriefing(),
        api.followups.getAnalytics(),
      ]);
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value as any);
      if (briefRes.status === 'fulfilled') setBriefing(briefRes.value as any);
      if (analyticsRes.status === 'fulfilled') setAnalytics(analyticsRes.value);
      setApprovalQueue([]); // populated via per-lead status lookups in future
    } catch {
      // fail-silent — view degrades gracefully
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleEvaluate = async (leadId: string) => {
    setEvaluating(leadId);
    try {
      await api.followups.evaluateLead(leadId);
      showToast('Lead evaluated — AI next action computed');
      await loadData();
    } catch {
      showToast('Evaluation failed — lead may have no recent conversation data', false);
    } finally {
      setEvaluating(null);
    }
  };

  const handleApprove = async (execId: string) => {
    setApproving(execId);
    try {
      await api.followups.approveExecution(execId);
      await api.followups.dispatchExecution(execId);
      setApprovalQueue(q => q.filter(i => i.id !== execId));
      showToast('Message approved and dispatched ✅');
    } catch {
      showToast('Approve failed — check channel configuration', false);
    } finally {
      setApproving(null);
    }
  };

  const handleCancel = async (execId: string) => {
    try {
      await api.followups.cancelExecution(execId);
      setApprovalQueue(q => q.filter(i => i.id !== execId));
      showToast('Message cancelled');
    } catch {
      showToast('Cancel failed', false);
    }
  };

  const priorityLeads: PriorityLead[] = summary?.top_priority_leads || [];

  const TABS = [
    { id: 'queue' as const,     label: 'Priority Queue',    icon: <Zap className="w-3.5 h-3.5" />,         badge: priorityLeads.length },
    { id: 'approvals' as const, label: 'Pending Approval',  icon: <Bell className="w-3.5 h-3.5" />,        badge: approvalQueue.length },
    { id: 'analytics' as const, label: 'Analytics',         icon: <BarChart2 className="w-3.5 h-3.5" />,   badge: 0 },
  ];

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <RefreshCw className="w-8 h-8 text-[#0D9488] animate-spin" />
        <p className="text-[13px] text-[#6B6B6B] font-semibold">Loading follow-up work queue...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 relative">

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={`fixed top-20 right-4 z-50 px-4 py-3 rounded-xl border shadow-lg text-[12px] font-bold flex items-center gap-2 ${
              toast.ok
                ? 'bg-[#DCFCE7] border-[#86EFAC] text-[#15803D]'
                : 'bg-[#FEE2E2] border-[#FECACA] text-[#B91C1C]'
            }`}
          >
            {toast.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            {toast.msg}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Daily Briefing Banner */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-r from-[#0D9488]/8 via-[#0D9488]/4 to-transparent border border-[#0D9488]/20 rounded-2xl p-5"
      >
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2 h-2 rounded-full bg-[#0D9488] animate-pulse" />
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#0D9488]">
                Daily Revenue Briefing
              </span>
              <span className="text-[10px] text-[#6B6B6B] font-mono">
                {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' })}
              </span>
            </div>

            {briefing?.top_actions && briefing.top_actions.length > 0 ? (
              <div className="space-y-1">
                {briefing.top_actions.slice(0, 3).map((action, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12px] text-[#1A1A1A]">
                    <ArrowRight className="w-3 h-3 text-[#0D9488] shrink-0" />
                    <span>{action}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-[#1A1A1A] font-semibold">
                {briefing?.hot_leads ?? 0} hot leads ·{' '}
                {briefing?.overdue_followups ?? summary?.overdue_count ?? 0} overdue ·{' '}
                {briefing?.today_scheduled ?? summary?.today_tasks ?? 0} scheduled today
              </p>
            )}
          </div>
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-[11px] font-bold transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </motion.div>

      {/* Stat Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatTile label="Total Leads"     value={summary?.total_leads ?? briefing?.total_leads ?? 0}         accent="text-[#1A1A1A]" />
        <StatTile label="Today's Tasks"   value={summary?.today_tasks ?? briefing?.today_scheduled ?? 0}     accent="text-[#1D4ED8]" sub="scheduled" />
        <StatTile label="Overdue"         value={summary?.overdue_count ?? briefing?.overdue_followups ?? 0} accent="text-[#DC2626]" pulse={(summary?.overdue_count ?? 0) > 0} />
        <StatTile label="Pending Approval" value={summary?.pending_approval ?? approvalQueue.length}         accent="text-[#D97706]" pulse={(summary?.pending_approval ?? 0) > 0} />
        <StatTile label="Sent Today"      value={summary?.dispatched_today ?? 0}                             accent="text-[#0D9488]" />
        <StatTile label="Response Rate"   value={`${Math.round(summary?.response_rate_pct ?? (analytics?.response_rate_pct as number) ?? 0)}%`} accent="text-[#7C3AED]" sub="of sent msgs" />
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-1 bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl w-fit">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all ${
              activeTab === tab.id
                ? 'bg-[#1A1A1A] text-white shadow-sm'
                : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.badge > 0 && (
              <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-extrabold ${
                activeTab === tab.id ? 'bg-white text-[#1A1A1A]' : 'bg-[#D4D0C8] text-[#4A4A4A]'
              }`}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">

        {activeTab === 'queue' && (
          <motion.div
            key="queue"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-3"
          >
            {priorityLeads.length === 0 ? (
              <div className="text-center py-20 space-y-3">
                <CheckCircle2 className="w-12 h-12 text-[#0D9488] mx-auto opacity-30" />
                <p className="text-[15px] font-bold text-[#1A1A1A]">All caught up!</p>
                <p className="text-[12px] text-[#6B6B6B] max-w-xs mx-auto">
                  No priority leads in your follow-up queue right now. The AI engine will populate this when leads need action.
                </p>
                <button
                  onClick={loadData}
                  className="mt-2 px-4 py-2 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-[12px] font-bold"
                >
                  Refresh Queue
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <h3 className="text-[12px] font-extrabold uppercase tracking-widest text-[#6B6B6B] flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-500 fill-amber-400" />
                    Priority Action Queue ({priorityLeads.length})
                  </h3>
                  <button
                    onClick={loadData}
                    className="text-[11px] text-[#0D9488] font-bold hover:underline flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" /> Refresh
                  </button>
                </div>
                <div className="space-y-2.5">
                  {priorityLeads.map(lead => (
                    <div key={lead.lead_id} className="relative">
                      {evaluating === lead.lead_id && (
                        <div className="absolute inset-0 bg-white/80 rounded-xl flex items-center justify-center z-10">
                          <RefreshCw className="w-5 h-5 text-[#7C3AED] animate-spin" />
                        </div>
                      )}
                      <PriorityLeadCard
                        lead={lead}
                        onEvaluate={handleEvaluate}
                        onOpenLead={onOpenLead}
                      />
                    </div>
                  ))}
                </div>
              </>
            )}
          </motion.div>
        )}

        {activeTab === 'approvals' && (
          <motion.div
            key="approvals"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-3"
          >
            <h3 className="text-[12px] font-extrabold uppercase tracking-widest text-[#6B6B6B] flex items-center gap-2">
              <Bell className="w-4 h-4 text-[#D97706]" />
              Messages Pending Human Approval
            </h3>

            {approvalQueue.length === 0 ? (
              <div className="text-center py-20 space-y-3">
                <CheckCircle2 className="w-12 h-12 text-[#0D9488] mx-auto opacity-30" />
                <p className="text-[15px] font-bold text-[#1A1A1A]">Approval queue is empty</p>
                <p className="text-[12px] text-[#6B6B6B] max-w-sm mx-auto">
                  The AI is operating autonomously. Messages will appear here when the autonomy policy requires human review before sending.
                </p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {approvalQueue.map(item => (
                  <div key={item.id} className="relative">
                    {approving === item.id && (
                      <div className="absolute inset-0 bg-white/80 rounded-xl flex items-center justify-center z-10">
                        <RefreshCw className="w-5 h-5 text-[#0D9488] animate-spin" />
                      </div>
                    )}
                    <ApprovalQueueCard
                      item={item}
                      onApprove={handleApprove}
                      onCancel={handleCancel}
                    />
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {activeTab === 'analytics' && (
          <motion.div
            key="analytics"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-4"
          >
            <h3 className="text-[12px] font-extrabold uppercase tracking-widest text-[#6B6B6B] flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-[#7C3AED]" />
              Follow-Up Performance Analytics
            </h3>

            {analytics ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Delivery */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-[#0D9488]" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#6B6B6B]">Delivery</span>
                  </div>
                  <div className="space-y-2">
                    {([
                      ['Total Evaluated', analytics.total_evaluations],
                      ['Dispatched',      analytics.total_dispatched],
                      ['Suppressed',      analytics.total_suppressed],
                      ['Delivery Rate',   `${analytics.delivery_rate_pct ?? 0}%`],
                    ] as [string, unknown][]).map(([label, val]) => (
                      <div key={label} className="flex justify-between items-center text-[12px]">
                        <span className="text-[#6B6B6B]">{label}</span>
                        <span className="font-bold text-[#1A1A1A] font-mono">{String(val ?? 0)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Engagement */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-[#7C3AED]" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#6B6B6B]">Engagement</span>
                  </div>
                  <div className="flex justify-between items-center text-[12px]">
                    <span className="text-[#6B6B6B]">Response Rate</span>
                    <span className="font-bold text-[#1A1A1A] font-mono">{String(analytics.response_rate_pct ?? 0)}%</span>
                  </div>
                  {Boolean(analytics.channel_distribution && typeof analytics.channel_distribution === 'object') && (
                    <div className="pt-2 border-t border-[#E2E8F0] space-y-1.5">
                      <span className="text-[10px] font-bold uppercase text-[#9B9B9B]">Channel Mix</span>
                      {Object.entries(analytics.channel_distribution as Record<string, number>).map(([ch, cnt]) => (
                        <div key={ch} className="flex justify-between items-center text-[11px]">
                          <span className="text-[#6B6B6B]">{channelIcon(ch)} {ch}</span>
                          <span className="font-bold font-mono text-[#1A1A1A]">{cnt}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Suppression */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-[#D97706]" />
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#6B6B6B]">Suppression Reasons</span>
                  </div>
                  {analytics.top_suppression_reasons && typeof analytics.top_suppression_reasons === 'object' ? (
                    <div className="space-y-1.5">
                      {Object.entries(analytics.top_suppression_reasons as Record<string, number>).map(([reason, cnt]) => (
                        <div key={reason} className="flex justify-between items-center text-[11px]">
                          <span className="text-[#6B6B6B]">{reason.replace(/_/g, ' ')}</span>
                          <span className="font-bold font-mono text-[#1A1A1A]">{cnt}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[11px] text-[#9B9B9B]">No suppression events yet.</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-[#9B9B9B] text-[12px]">
                Analytics data unavailable — will populate as the follow-up engine runs.
              </div>
            )}
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
}
