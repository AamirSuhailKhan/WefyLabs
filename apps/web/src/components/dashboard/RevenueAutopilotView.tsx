'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  Phone,
  Mail,
  Calendar,
  AlertCircle,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Clock,
  Home,
  User,
  ArrowRight,
  RefreshCw,
  Eye,
  SlidersHorizontal,
  ChevronRight,
  X,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Building,
  DollarSign,
  MapPin,
  ExternalLink,
  Layers
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { WefyLabsIcon } from '@/components/shared/WefyLabsIcon';
import {
  ActionQueueItem,
  RevenueOpportunity,
  RevenueBriefing,
  DemandIntelligenceResponse,
  OutreachDraft
} from '@/types';

interface RevenueAutopilotViewProps {
  onOpenLead?: (leadId: string) => void;
  onOpenProperty?: (propertyId: string) => void;
}

export default function RevenueAutopilotView({
  onOpenLead,
  onOpenProperty,
}: RevenueAutopilotViewProps) {
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [queueItems, setQueueItems] = useState<ActionQueueItem[]>([]);
  const [briefing, setBriefing] = useState<RevenueBriefing | null>(null);
  const [demandIntel, setDemandIntel] = useState<DemandIntelligenceResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'critical' | 'matches' | 'visits' | 'stale'>('all');

  // Modal / Drawer states
  const [selectedOpp, setSelectedOpp] = useState<RevenueOpportunity | null>(null);
  const [outreachModalOpen, setOutreachModalOpen] = useState<boolean>(false);
  const [outreachDraft, setOutreachDraft] = useState<OutreachDraft | null>(null);
  const [outreachLoading, setOutreachLoading] = useState<boolean>(false);
  const [emailSubject, setEmailSubject] = useState<string>('');
  const [emailBody, setEmailBody] = useState<string>('');

  const [dismissModalOpen, setDismissModalOpen] = useState<boolean>(false);
  const [dismissReason, setDismissReason] = useState<string>('Not relevant');
  const [dismissOppId, setDismissOppId] = useState<string | null>(null);

  const [feedbackSuccessId, setFeedbackSuccessId] = useState<string | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // P0 Empty State Intelligence Metadata
  const [queueMeta, setQueueMeta] = useState<{
    active_leads_count: number;
    active_properties_count: number;
    completed_today_count: number;
    last_scan_at: string | null;
  }>({
    active_leads_count: 0,
    active_properties_count: 0,
    completed_today_count: 0,
    last_scan_at: null,
  });

  // P2 Execute Confirmation Modal State
  const [confirmModalItem, setConfirmModalItem] = useState<{
    id: string;
    actionType: string;
    leadName: string;
    propertyTitle?: string | null;
  } | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);

  const loadAutopilotData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setErrorMsg(null);

    try {
      const [queueRes, briefRes, demandRes] = await Promise.allSettled([
        api.revenue.getActionQueue(15),
        api.revenue.getBriefing(),
        api.revenue.getDemandIntelligence(),
      ]);

      if (queueRes.status === 'fulfilled') {
        setQueueItems(queueRes.value.items || []);
        setQueueMeta({
          active_leads_count: queueRes.value.active_leads_count ?? 0,
          active_properties_count: queueRes.value.active_properties_count ?? 0,
          completed_today_count: queueRes.value.completed_today_count ?? 0,
          last_scan_at: queueRes.value.last_scan_at ?? null,
        });
      } else if (queueRes.status === 'rejected') {
        const reason = (queueRes as any).reason;
        setErrorMsg(reason?.message || 'Failed to evaluate revenue queue.');
      }
      if (briefRes.status === 'fulfilled') {
        setBriefing(briefRes.value);
      }
      if (demandRes.status === 'fulfilled') {
        setDemandIntel(demandRes.value);
      }
    } catch (err: any) {
      console.error('Failed to load Revenue Autopilot:', err);
      setErrorMsg(err?.message || 'Revenue recommendations are temporarily unavailable.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAutopilotData();
  }, [loadAutopilotData]);

  const handleOpenOutreach = async (oppId: string) => {
    setOutreachLoading(true);
    setOutreachModalOpen(true);
    try {
      const [opp, draft] = await Promise.all([
        api.revenue.getOpportunity(oppId),
        api.revenue.generateOutreach(oppId),
      ]);
      setSelectedOpp(opp);
      setOutreachDraft(draft);
      setEmailSubject(draft.email_draft.subject || '');
      setEmailBody(draft.email_draft.body || '');
    } catch (e: any) {
      console.error('Failed to fetch outreach draft:', e);
    } finally {
      setOutreachLoading(false);
    }
  };

  const handleExecuteAction = async (oppId: string, actionType: string) => {
    try {
      const res = await api.revenue.performAction(oppId, {
        action_type: actionType,
        email_subject: emailSubject,
        email_body: emailBody,
        send_email_now: actionType === 'SEND_EMAIL',
        create_follow_up_task: true,
      });

      setActionSuccessMsg(res.message || `Action '${actionType}' completed.`);
      setTimeout(() => setActionSuccessMsg(null), 4000);
      setOutreachModalOpen(false);

      // Optimistically update queue
      setQueueItems((prev) => prev.filter((item) => item.id !== oppId));
    } catch (err: any) {
      alert(`Action failed: ${err?.message || 'Unknown error'}`);
    }
  };

  const handleConfirmDismiss = async () => {
    if (!dismissOppId) return;
    try {
      await api.revenue.dismissOpportunity(dismissOppId, { reason: dismissReason });
      setQueueItems((prev) => prev.filter((item) => item.id !== dismissOppId));
      setDismissModalOpen(false);
      setDismissOppId(null);
    } catch (err: any) {
      alert(`Failed to dismiss: ${err?.message || 'Unknown error'}`);
    }
  };

  const handleFeedback = async (oppId: string, rating: 'YES' | 'NO') => {
    try {
      await api.revenue.submitFeedback(oppId, { rating });
      setFeedbackSuccessId(oppId);
      setTimeout(() => setFeedbackSuccessId(null), 3000);
    } catch (err: any) {
      console.error('Feedback failed:', err);
    }
  };

  // Filter queue items based on active tab
  const filteredItems = queueItems.filter((item) => {
    if (activeTab === 'critical') return item.urgency === 'CRITICAL' || item.priority === 'CRITICAL';
    if (activeTab === 'matches') return item.opportunity_type.includes('MATCH');
    if (activeTab === 'visits') return item.opportunity_type.includes('SITE_VISIT');
    if (activeTab === 'stale') return item.opportunity_type.includes('STALE') || item.opportunity_type.includes('REACTIVATION');
    return true;
  });

  // P0 — Explicit Empty State Machine
  const getQueueState = (): 'LOADING' | 'ERROR' | 'PLAN_RESTRICTED' | 'NO_LEADS' | 'NO_PROPERTIES' | 'ALL_CAUGHT_UP' | 'NO_OPPORTUNITIES' | 'HAS_OPPORTUNITIES' => {
    if (loading) return 'LOADING';
    if (errorMsg) {
      const lower = errorMsg.toLowerCase();
      if (lower.includes('plan') || lower.includes('upgrade') || lower.includes('trial') || lower.includes('restricted')) {
        return 'PLAN_RESTRICTED';
      }
      return 'ERROR';
    }
    if (queueItems.length > 0) return 'HAS_OPPORTUNITIES';
    if (queueMeta.active_leads_count === 0) return 'NO_LEADS';
    if (queueMeta.active_properties_count === 0) return 'NO_PROPERTIES';
    if (queueMeta.completed_today_count > 0) return 'ALL_CAUGHT_UP';
    return 'NO_OPPORTUNITIES';
  };

  const queueState = getQueueState();

  return (
    <div className="space-y-6">
      {/* ─── Top Autopilot Header & Narrative Briefing ──────────────────── */}
      <div className="bg-[#181B22] border border-[#2D333F] rounded-2xl p-6 text-white shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <WefyLabsIcon size={14} theme="dark" className="shrink-0" />
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider bg-teal-500/20 text-teal-300 border border-teal-500/30 uppercase">
                <Sparkles className="w-3 h-3 text-teal-300 animate-pulse" />
                AI REVENUE AUTOPILOT
              </span>
              <span className="text-[11px] text-gray-400 font-mono">v1 Deterministic Engine</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white font-mono">
              {briefing?.greeting || 'Good day, Sales Agent.'}
            </h2>
            <p className="text-sm text-gray-300 mt-1 max-w-2xl font-sans leading-relaxed">
              {briefing?.headline || 'Continuous intelligence identifying the highest-value real estate sales actions right now.'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => loadAutopilotData(true)}
              disabled={refreshing}
              className="px-3 py-2 rounded-xl bg-[#232732] hover:bg-[#2E3342] text-gray-200 border border-[#373E4F] text-xs font-semibold flex items-center gap-2 transition-all"
              title="Recalculate revenue opportunities"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-teal-400' : ''}`} />
              <span>{refreshing ? 'Recalculating...' : 'Refresh Autopilot'}</span>
            </button>
          </div>
        </div>

        {/* ─── Briefing Counter Metrics Bar ─── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-5 border-t border-[#2D333F]">
          <div className="bg-[#212530] border border-[#303746] rounded-xl p-3">
            <span className="text-[11px] text-gray-400 uppercase font-mono tracking-wider">DO THIS NOW</span>
            <div className="text-2xl font-bold text-white font-mono mt-0.5">{queueItems.length}</div>
            <span className="text-[11px] text-teal-400 font-sans">Priority sales actions</span>
          </div>

          <div className="bg-[#212530] border border-[#303746] rounded-xl p-3">
            <span className="text-[11px] text-red-400 uppercase font-mono tracking-wider">CRITICAL URGENCY</span>
            <div className="text-2xl font-bold text-red-400 font-mono mt-0.5">
              {queueItems.filter((i) => i.urgency === 'CRITICAL' || i.priority === 'CRITICAL').length}
            </div>
            <span className="text-[11px] text-gray-400 font-sans">SLA / Follow-up risk</span>
          </div>

          <div className="bg-[#212530] border border-[#303746] rounded-xl p-3">
            <span className="text-[11px] text-amber-400 uppercase font-mono tracking-wider">HOT BUYER MATCHES</span>
            <div className="text-2xl font-bold text-amber-400 font-mono mt-0.5">
              {queueItems.filter((i) => i.opportunity_type.includes('MATCH')).length}
            </div>
            <span className="text-[11px] text-gray-400 font-sans">High match confidence</span>
          </div>

          <div className="bg-[#212530] border border-[#303746] rounded-xl p-3">
            <span className="text-[11px] text-blue-400 uppercase font-mono tracking-wider">INVENTORY GAPS</span>
            <div className="text-2xl font-bold text-blue-400 font-mono mt-0.5">
              {demandIntel?.top_demand_gaps?.length || 0}
            </div>
            <span className="text-[11px] text-gray-400 font-sans">Supply deficit segments</span>
          </div>
        </div>

        {/* Top Recommendation Highlight */}
        {briefing?.top_recommendation_text && (
          <div className="mt-4 p-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-200 text-xs flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-teal-300 shrink-0" />
            <span>{briefing.top_recommendation_text}</span>
          </div>
        )}
      </div>

      {/* Success Notification Alert */}
      {actionSuccessMsg && (
        <div className="p-4 rounded-xl bg-teal-50 border border-teal-200 text-teal-900 text-sm font-semibold flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-teal-600" />
            <span>{actionSuccessMsg}</span>
          </div>
          <button onClick={() => setActionSuccessMsg(null)} className="text-teal-700 hover:text-teal-900 text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {/* ─── Demand Gap Intelligence Summary Banner (if deficits found) ─── */}
      {demandIntel && demandIntel.top_demand_gaps.length > 0 && (
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-amber-600" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#1A1A1A] font-mono">
                BROKER DEMAND GAP INTELLIGENCE
              </h3>
            </div>
            <span className="text-[11px] text-[#6B6B6B] font-mono">
              {demandIntel.total_active_buyers} active buyers vs {demandIntel.total_available_listings} listings
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {demandIntel.top_demand_gaps.slice(0, 3).map((gap) => (
              <div key={gap.segment_id} className="bg-white border border-[#E5E0D8] rounded-xl p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-xs text-[#1A1A1A]">
                    {gap.bedrooms}BHK in {gap.locality}
                  </span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
                    Deficit: {gap.deficit_count}
                  </span>
                </div>
                <p className="text-[11px] text-[#6B6B6B] leading-tight">
                  {gap.active_buyer_demand_count} buyers waiting • {gap.matching_inventory_count} listings available
                </p>
                <div className="mt-2 text-[11px] font-medium text-teal-700 flex items-center gap-1">
                  <span>→ {gap.recommended_action}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Action Queue Navigation Tabs ───────────────────────────────── */}
      <div className="flex items-center justify-between gap-3 border-b border-[#D4D0C8] pb-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'all'
                ? 'bg-[#1A1A1A] text-white shadow-sm'
                : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
            }`}
          >
            All Actions ({queueItems.length})
          </button>
          <button
            onClick={() => setActiveTab('critical')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
              activeTab === 'critical'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-red-700 hover:bg-red-50'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            Critical Urgency ({queueItems.filter((i) => i.urgency === 'CRITICAL' || i.priority === 'CRITICAL').length})
          </button>
          <button
            onClick={() => setActiveTab('matches')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'matches'
                ? 'bg-[#1A1A1A] text-white shadow-sm'
                : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
            }`}
          >
            Property Matches ({queueItems.filter((i) => i.opportunity_type.includes('MATCH')).length})
          </button>
          <button
            onClick={() => setActiveTab('visits')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'visits'
                ? 'bg-[#1A1A1A] text-white shadow-sm'
                : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
            }`}
          >
            Site Visits ({queueItems.filter((i) => i.opportunity_type.includes('SITE_VISIT')).length})
          </button>
          <button
            onClick={() => setActiveTab('stale')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
              activeTab === 'stale'
                ? 'bg-[#1A1A1A] text-white shadow-sm'
                : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
            }`}
          >
            Reactivations ({queueItems.filter((i) => i.opportunity_type.includes('STALE') || i.opportunity_type.includes('REACTIVATION')).length})
          </button>
        </div>

        <span className="text-[11px] text-[#6B6B6B] font-mono">
          Showing {filteredItems.length} of {queueItems.length} actions
        </span>
      </div>

      {/* ─── Main Action Queue ("DO THIS NOW") State Machine ─────────── */}
      {queueState === 'LOADING' ? (
        <div className="py-20 text-center text-[#6B6B6B] space-y-3 bg-white rounded-2xl border border-[#D4D0C8]">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-teal-600" />
          <p className="text-sm font-semibold">Evaluating active leads and inventory opportunities...</p>
        </div>
      ) : queueState === 'ERROR' ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-red-200 space-y-3 shadow-xs">
          <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">Revenue Autopilot Unavailable</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto">
            {errorMsg || 'Something went wrong while loading recommendations.'}
          </p>
          <button
            onClick={() => loadAutopilotData(true)}
            className="px-4 py-2 rounded-xl bg-[#1A1A1A] text-white text-xs font-bold hover:bg-black transition-all inline-flex items-center gap-2 mx-auto"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        </div>
      ) : queueState === 'PLAN_RESTRICTED' ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-amber-200 space-y-3 shadow-xs">
          <AlertCircle className="w-10 h-10 text-amber-500 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">Plan Upgrade Required</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto">
            AI Revenue Autopilot requires an active Growth or Enterprise plan.
          </p>
          <Link
            href="/dashboard/pricing"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1A1A1A] text-white text-xs font-bold hover:bg-black transition-all mx-auto"
          >
            <span>View Subscription Plans</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : queueState === 'NO_LEADS' ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-[#D4D0C8] space-y-3 shadow-xs">
          <User className="w-10 h-10 text-teal-600 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">Add Your First Lead</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto leading-relaxed">
            Revenue Autopilot needs active buyers to identify revenue opportunities. Once you add a lead, we'll match them against your inventory.
          </p>
          <div className="pt-2 flex items-center justify-center gap-2">
            <Link
              href="/dashboard/leads"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold transition-all shadow-sm"
            >
              <User className="w-3.5 h-3.5 text-teal-400" />
              <span>Add Lead</span>
            </Link>
          </div>
        </div>
      ) : queueState === 'NO_PROPERTIES' ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-[#D4D0C8] space-y-3 shadow-xs">
          <Building className="w-10 h-10 text-teal-600 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">Add Your First Property</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto leading-relaxed">
            Revenue Autopilot needs inventory to find buyer/property opportunities. Add listings so our engine can generate high-probability matches.
          </p>
          <div className="pt-2 flex items-center justify-center gap-2">
            <Link
              href="/dashboard/properties"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold transition-all shadow-sm"
            >
              <Home className="w-3.5 h-3.5 text-amber-400" />
              <span>Add Property</span>
            </Link>
          </div>
        </div>
      ) : queueState === 'ALL_CAUGHT_UP' ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-teal-200 space-y-3 shadow-xs bg-gradient-to-b from-teal-50/30 to-white">
          <CheckCircle2 className="w-10 h-10 text-teal-600 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">You're All Caught Up</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto">
            <strong className="text-teal-800">{queueMeta.completed_today_count} opportunities</strong> handled today. All priority actions have been completed or dismissed.
          </p>
          <button
            onClick={() => loadAutopilotData(true)}
            className="px-4 py-2 rounded-xl bg-[#1A1A1A] text-white text-xs font-bold hover:bg-black transition-all inline-flex items-center gap-2 mx-auto"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Trigger Fresh Scan</span>
          </button>
        </div>
      ) : queueState === 'NO_OPPORTUNITIES' ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-[#D4D0C8] space-y-3 shadow-xs">
          <Clock className="w-10 h-10 text-teal-600 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">No Priority Opportunities Right Now</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto leading-relaxed">
            Your active leads and inventory are being monitored continuously. New price updates, buyer engagements, and viewing outcomes will trigger instant recommendations.
          </p>
          <div className="inline-flex items-center gap-3 bg-[#FAF7F2] border border-[#E5E0D8] rounded-xl px-4 py-2 text-xs font-mono text-gray-700 mx-auto">
            <span>Active leads: <strong>{queueMeta.active_leads_count}</strong></span>
            <span className="text-gray-300">•</span>
            <span>Active properties: <strong>{queueMeta.active_properties_count}</strong></span>
            {queueMeta.last_scan_at && (
              <>
                <span className="text-gray-300">•</span>
                <span>Last scan: <strong>{new Date(queueMeta.last_scan_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong></span>
              </>
            )}
          </div>
          <div className="pt-2">
            <button
              onClick={() => loadAutopilotData(true)}
              className="px-4 py-2 rounded-xl bg-[#1A1A1A] text-white text-xs font-bold hover:bg-black transition-all inline-flex items-center gap-2 mx-auto"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Trigger Fresh Scan</span>
            </button>
          </div>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="py-16 px-4 text-center bg-white rounded-2xl border border-[#D4D0C8] space-y-3">
          <CheckCircle2 className="w-10 h-10 text-gray-400 mx-auto" />
          <h3 className="text-base font-bold text-[#1A1A1A] font-mono">No {activeTab.toUpperCase()} Actions</h3>
          <p className="text-xs text-[#6B6B6B] max-w-md mx-auto">
            There are no actions matching the "{activeTab}" filter.
          </p>
          <button
            onClick={() => setActiveTab('all')}
            className="px-4 py-2 rounded-xl bg-[#1A1A1A] text-white text-xs font-bold hover:bg-black transition-all"
          >
            View All Actions ({queueItems.length})
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredItems.map((item, index) => {
            const isCritical = item.urgency === 'CRITICAL' || item.priority === 'CRITICAL';
            const isHigh = item.priority === 'HIGH' || item.urgency === 'HIGH';

            return (
              <div
                key={item.id}
                className={`bg-white border rounded-2xl p-5 sm:p-6 transition-all hover:shadow-md ${
                  isCritical
                    ? 'border-red-300 shadow-sm shadow-red-100'
                    : isHigh
                    ? 'border-amber-300'
                    : 'border-[#D4D0C8]'
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-[#F0EDE8]">
                  {/* Left: Lead and Action Title */}
                  <div>
                    <div className="flex items-center gap-2 flex-wrap mb-1.5">
                      <span className="text-xs font-mono font-bold text-gray-500">
                        #{index + 1}
                      </span>
                      {isCritical ? (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700 border border-red-200">
                          🔥 CRITICAL ACTION
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                          ⚡ HIGH VALUE
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-gray-100 text-gray-700">
                        OPP SCORE: {item.opportunity_score.toFixed(0)}
                      </span>
                      {item.match_score > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-teal-100 text-teal-800">
                          MATCH: {item.match_score.toFixed(0)}%
                        </span>
                      )}
                      <span className="text-[11px] text-gray-400 font-mono">
                        {item.opportunity_type.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <h3 className="text-lg font-bold text-[#1A1A1A] font-mono flex items-center gap-2">
                      <span>{item.recommended_action.replace(/_/g, ' ')} → {item.lead_name}</span>
                      <span className="text-xs font-normal text-gray-500 font-sans">
                        ({item.lead_phone})
                      </span>
                    </h3>
                  </div>

                  {/* Right: Primary Call to Action Buttons */}
                  <div className="flex items-center gap-2 flex-wrap shrink-0">
                    <button
                      onClick={() => handleOpenOutreach(item.id)}
                      className="px-3 py-2 rounded-xl bg-[#FAF7F2] hover:bg-[#F0EDE8] border border-[#D4D0C8] text-[#1A1A1A] text-xs font-bold flex items-center gap-1.5 transition-all"
                    >
                      <Eye className="w-3.5 h-3.5 text-[#6B6B6B]" />
                      <span>Outreach Brief</span>
                    </button>

                    <button
                      onClick={() => setConfirmModalItem({
                        id: item.id,
                        actionType: item.recommended_action,
                        leadName: item.lead_name,
                        propertyTitle: item.property_title
                      })}
                      className="px-4 py-2 rounded-xl bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold flex items-center gap-2 transition-all shadow-sm"
                    >
                      {item.recommended_action.includes('CALL') ? (
                        <Phone className="w-3.5 h-3.5 text-teal-400" />
                      ) : item.recommended_action.includes('EMAIL') ? (
                        <Mail className="w-3.5 h-3.5 text-blue-400" />
                      ) : (
                        <Calendar className="w-3.5 h-3.5 text-amber-400" />
                      )}
                      <span>Execute {item.recommended_action.replace(/_/g, ' ')}</span>
                    </button>

                    <button
                      onClick={() => {
                        setDismissOppId(item.id);
                        setDismissModalOpen(true);
                      }}
                      className="p-2 rounded-xl hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-all"
                      title="Dismiss opportunity"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* ─── Grounded "WHY" Explainability Grid ─── */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-xs">
                  {/* Box 1: Why Now & Action Objective */}
                  <div className="p-3.5 rounded-xl bg-[#FAF7F2] border border-[#E5E0D8] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-[11px] text-[#6B6B6B] uppercase tracking-wider">
                        WHY NOW?
                      </span>
                      <Clock className="w-3.5 h-3.5 text-gray-400" />
                    </div>
                    <p className="text-[#1A1A1A] leading-relaxed font-sans font-medium">
                      {item.why_now}
                    </p>

                    {item.risk_of_inactivity && (
                      <div className="pt-2 border-t border-[#E5E0D8] text-[11px] text-red-700 flex items-start gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-red-600" />
                        <span><strong>Risk if ignored:</strong> {item.risk_of_inactivity}</span>
                      </div>
                    )}
                  </div>

                  {/* Box 2: Recommended Property & Grounded Spec */}
                  <div className="p-3.5 rounded-xl bg-[#FAF7F2] border border-[#E5E0D8] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-[11px] text-[#6B6B6B] uppercase tracking-wider">
                        RECOMMENDED INVENTORY
                      </span>
                      {item.property_id && onOpenProperty && (
                        <button
                          onClick={() => onOpenProperty(item.property_id!)}
                          className="text-[11px] font-bold text-teal-700 hover:underline flex items-center gap-1"
                        >
                          View Listing <ExternalLink className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    {item.property_title ? (
                      <div>
                        <div className="font-bold text-[#1A1A1A] text-sm">
                          {item.property_title}
                        </div>
                        <div className="text-[11px] text-gray-600 mt-0.5 flex items-center gap-3">
                          <span>₹{(item.property_price || 0).toLocaleString()}</span>
                          <span>•</span>
                          <span>{item.property_bedrooms} BHK</span>
                          <span>•</span>
                          <span>{item.property_locality || 'Prime Locality'}</span>
                        </div>
                        {item.why_property && (
                          <div className="mt-2 text-[11px] text-[#4A4A4A] font-sans">
                            ✓ {item.why_property}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-gray-500 italic">
                        Portfolio recommendation: Curate available listings from preferred locality.
                      </p>
                    )}
                  </div>
                </div>

                {/* ─── Evidence Signals & Provenance Pills ─── */}
                <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-[#F0EDE8] flex-wrap text-xs">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] font-bold font-mono text-gray-400 uppercase">Signals:</span>
                    {item.positive_signals.slice(0, 3).map((sig, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                        {sig}
                      </span>
                    ))}
                    {item.negative_signals.slice(0, 1).map((neg, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-200">
                        {neg}
                      </span>
                    ))}
                  </div>

                  {/* Feedback Loop */}
                  <div className="flex items-center gap-2 text-[11px] text-gray-500">
                    <span>Helpful?</span>
                    <button
                      onClick={() => handleFeedback(item.id, 'YES')}
                      className={`p-1 rounded hover:bg-gray-100 ${feedbackSuccessId === item.id ? 'text-teal-600 font-bold' : ''}`}
                      title="Mark recommendation as helpful"
                    >
                      <ThumbsUp className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleFeedback(item.id, 'NO')}
                      className="p-1 rounded hover:bg-gray-100"
                      title="Mark as not helpful"
                    >
                      <ThumbsDown className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ─── Outreach Brief & Grounded Draft Modal ──────────────────────── */}
      {outreachModalOpen && selectedOpp && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D8]">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-800 uppercase">
                    Grounded Sales Outreach
                  </span>
                  {/* P1 — Outreach Provenance Badge */}
                  {outreachDraft?.is_ai_generated ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono bg-purple-100 text-purple-800 border border-purple-200">
                      <Sparkles className="w-3 h-3 text-purple-600" />
                      AI Generated · Gemini
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono bg-amber-100 text-amber-800 border border-amber-200">
                      📋 Deterministic Fallback
                    </span>
                  )}
                </div>
                <h3 className="text-lg font-bold font-mono text-[#1A1A1A] mt-1">
                  Call Brief &amp; Email Draft → {selectedOpp.lead_name}
                </h3>
              </div>
              <button
                onClick={() => setOutreachModalOpen(false)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {outreachLoading ? (
              <div className="py-12 text-center text-gray-500">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-teal-600 mb-2" />
                <span>Loading grounded outreach brief...</span>
              </div>
            ) : (
              <div className="space-y-5">
                {/* 1. Call Briefing Card */}
                <div className="bg-[#FAF7F2] border border-[#E5E0D8] rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-gray-500 uppercase">
                      PHONE CALL BRIEFING
                    </span>
                    <span className="text-xs font-bold text-teal-700 font-mono">
                      {selectedOpp.lead_phone}
                    </span>
                  </div>

                  <div>
                    <span className="text-[11px] font-bold text-gray-700 uppercase">Call Objective:</span>
                    <p className="text-xs text-gray-900 font-medium mt-0.5">
                      {selectedOpp.call_brief?.objective || 'Introduce curated matching property'}
                    </p>
                  </div>

                  <div>
                    <span className="text-[11px] font-bold text-gray-700 uppercase">Suggested Opening Line:</span>
                    <p className="text-xs text-teal-900 bg-teal-50 border border-teal-200 p-2.5 rounded-lg mt-0.5 font-medium italic">
                      "{selectedOpp.call_brief?.suggested_opening || 'Hello, I have a property update matching your criteria.'}"
                    </p>
                  </div>

                  {selectedOpp.call_brief?.potential_objection && (
                    <div className="text-[11px] text-amber-800 bg-amber-50 border border-amber-200 p-2 rounded-lg">
                      <strong>Potential objection:</strong> {selectedOpp.call_brief.potential_objection}
                    </div>
                  )}
                </div>

                {/* 2. Email Draft Card */}
                <div className="bg-white border border-[#D4D0C8] rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-gray-500 uppercase">
                      EDITABLE EMAIL DRAFT
                    </span>
                    <span className="text-[10px] text-gray-400 font-mono">
                      Human approval required
                    </span>
                  </div>

                  <div>
                    <label className="text-[11px] font-bold text-gray-700">Subject</label>
                    <input
                      type="text"
                      value={emailSubject}
                      onChange={(e) => setEmailSubject(e.target.value)}
                      className="w-full mt-1 px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none focus:border-teal-600"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-bold text-gray-700">Message Body</label>
                    <textarea
                      rows={6}
                      value={emailBody}
                      onChange={(e) => setEmailBody(e.target.value)}
                      className="w-full mt-1 px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none focus:border-teal-600 font-sans leading-relaxed"
                    />
                  </div>
                </div>

                {/* 3. Action Decision Buttons */}
                <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E5E0D8]">
                  <button
                    onClick={() => setOutreachModalOpen(false)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-100"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => handleExecuteAction(selectedOpp.id, 'CALL_LEAD')}
                    className="px-4 py-2 rounded-xl bg-[#FAF7F2] hover:bg-[#F0EDE8] border border-[#D4D0C8] text-xs font-bold text-[#1A1A1A] flex items-center gap-1.5"
                  >
                    <Phone className="w-3.5 h-3.5 text-teal-600" />
                    Log Call &amp; Complete
                  </button>
                  <button
                    onClick={() => handleExecuteAction(selectedOpp.id, 'SEND_EMAIL')}
                    className="px-4 py-2 rounded-xl bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold flex items-center gap-1.5"
                  >
                    <Mail className="w-3.5 h-3.5 text-blue-400" />
                    Approve &amp; Send Email
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Dismiss Reason Modal ───────────────────────────────────────── */}
      {dismissModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-[#1A1A1A] font-mono">
              Dismiss Revenue Opportunity
            </h3>
            <p className="text-xs text-[#6B6B6B]">
              Please select a reason so the Autopilot engine can refine future action rankings.
            </p>

            <div className="space-y-2">
              {[
                'Not relevant',
                'Already contacted externally',
                'Wrong property fit',
                'Lead unavailable / unreachable',
                'Duplicate opportunity',
                'Other reason',
              ].map((r) => (
                <label key={r} className="flex items-center gap-2 p-2.5 rounded-lg border border-[#E5E0D8] hover:bg-[#FAF7F2] cursor-pointer text-xs">
                  <input
                    type="radio"
                    name="dismiss_reason"
                    checked={dismissReason === r}
                    onChange={() => setDismissReason(r)}
                    className="text-teal-600"
                  />
                  <span>{r}</span>
                </label>
              ))}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E5E0D8]">
              <button
                onClick={() => setDismissModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDismiss}
                className="px-4 py-2 rounded-xl bg-red-600 hover:bg-red-700 text-white text-xs font-bold"
              >
                Confirm Dismissal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── P2 Execute Confirmation Modal ──────────────────────────────── */}
      {confirmModalItem && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#ECE8E1] pb-3">
              <h3 className="text-base font-bold text-[#1A1A1A] font-mono flex items-center gap-2">
                <AlertCircle className="w-5 h-5 text-teal-600" />
                Execute this action?
              </h3>
              <button
                onClick={() => setConfirmModalItem(null)}
                disabled={isExecuting}
                className="p-1 rounded-lg text-gray-400 hover:text-black"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-[#FAF7F2] border border-[#E5E0D8] rounded-xl p-3.5 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="font-bold text-gray-500 font-mono uppercase">Lead:</span>
                <span className="font-bold text-gray-900">{confirmModalItem.leadName}</span>
              </div>
              {confirmModalItem.propertyTitle && (
                <div className="flex justify-between">
                  <span className="font-bold text-gray-500 font-mono uppercase">Property:</span>
                  <span className="font-medium text-gray-900 text-right truncate max-w-[200px]">{confirmModalItem.propertyTitle}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="font-bold text-gray-500 font-mono uppercase">Action:</span>
                <span className="font-bold text-teal-800 font-mono bg-teal-50 px-2 py-0.5 rounded border border-teal-200">
                  {confirmModalItem.actionType.replace(/_/g, ' ')}
                </span>
              </div>
            </div>

            <p className="text-xs text-[#6B6B6B]">
              This will create or update the corresponding CRM task, log an audit entry, and advance the revenue opportunity status.
            </p>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E5E0D8]">
              <button
                type="button"
                disabled={isExecuting}
                onClick={() => setConfirmModalItem(null)}
                className="px-4 py-2 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-100 transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isExecuting}
                onClick={async () => {
                  setIsExecuting(true);
                  try {
                    await handleExecuteAction(confirmModalItem.id, confirmModalItem.actionType);
                    setConfirmModalItem(null);
                  } finally {
                    setIsExecuting(false);
                  }
                }}
                className="px-4 py-2 rounded-xl bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold font-mono transition-all flex items-center gap-2"
              >
                {isExecuting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Confirming...</span>
                  </>
                ) : (
                  <span>Confirm Action</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
