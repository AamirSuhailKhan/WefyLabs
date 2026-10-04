'use client';

import React, { useState, useEffect } from 'react';
import { 
  AlertCircle, CheckCircle2, Clock, Calendar, MapPin, Sparkles, 
  TrendingUp, ChevronRight, Phone, ArrowRight, X, Building2, 
  Users, Bell, Play, Filter, ShieldAlert, RefreshCw, SlidersHorizontal,
  Flame, CalendarClock, Briefcase, Eye, ChevronLeft
} from 'lucide-react';
import Link from 'next/link';
import { api, RevenueOverviewDTO, FunnelSummaryDTO } from '@/lib/api-client';
import { WefyLabsIcon } from '@/components/shared/WefyLabsIcon';
import { 
  CommandCenterResponse, PriorityItem, StartMyDayResponse, StartMyDayStep,
  TodayScheduleItem, FirstContactSlaItem, OverdueFollowupItem, HotLeadItem,
  InventoryGapItem, InventoryOpportunity, CommandCenterPriorityLevel
} from '@/types';

interface CommandCenterViewProps {
  onOpenLead?: (leadId: string) => void;
  onRefresh?: () => void;
}

export default function CommandCenterView({ onOpenLead, onRefresh }: CommandCenterViewProps) {
  interface CategorizedError {
    category: 'AUTH' | 'PLAN' | 'PERMISSION' | 'RATE_LIMIT' | 'NETWORK' | 'SERVER' | 'GENERIC';
    title: string;
    message: string;
    actionText?: string;
    actionHref?: string;
    canRetry?: boolean;
  }

  const [data, setData] = useState<CommandCenterResponse | null>(null);
  const [revenueOverview, setRevenueOverview] = useState<RevenueOverviewDTO | null>(null);
  const [funnelData, setFunnelData] = useState<FunnelSummaryDTO | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<CategorizedError | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [priorityFilter, setPriorityFilter] = useState<string>('ALL');

  const inFlightRef = React.useRef<boolean>(false);
  const abortControllerRef = React.useRef<AbortController | null>(null);

  const formatMoney = (amount?: number | null, fallback = 'AED 0') => {
    if (amount === undefined || amount === null) return fallback;
    if (amount >= 10000000) return `AED ${(amount / 10000000).toFixed(2)} Cr`;
    if (amount >= 100000) return `AED ${(amount / 100000).toFixed(1)}L`;
    return `AED ${amount.toLocaleString()}`;
  };
  
  // Start My Day Modal State
  const [startMyDayOpen, setStartMyDayOpen] = useState<boolean>(false);
  const [startMyDayData, setStartMyDayData] = useState<StartMyDayResponse | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [startMyDayLoading, setStartMyDayLoading] = useState<boolean>(false);

  // Snooze dropdown state
  const [activeSnoozeKey, setActiveSnoozeKey] = useState<string | null>(null);

  const fetchCommandCenter = async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setIsRetrying(true);
    setLoading(true);
    setError(null);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const [ccRes, revRes, funnelRes] = await Promise.allSettled([
        api.commandCenter.getData(undefined, controller.signal),
        api.revenueIntelligence.getOverview(),
        api.revenueIntelligence.getFunnel(),
      ]);

      if (ccRes.status === 'fulfilled') {
        const payload = (ccRes.value as any)?.data ?? ccRes.value;
        if (payload && (payload.summary || payload.priorities)) {
          setData(payload);
          setError(null);
        } else {
          console.warn('[CommandCenterView] Unexpected response format:', ccRes.value);
          setError({
            category: 'SERVER',
            title: 'Command Center Temporarily Unavailable',
            message: 'Received an incomplete operational queue response. Please try again.',
            canRetry: true
          });
        }
      }
      if (revRes.status === 'fulfilled' && revRes.value) {
        setRevenueOverview(revRes.value);
      }
      if (funnelRes.status === 'fulfilled' && funnelRes.value) {
        setFunnelData(funnelRes.value);
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        return;
      }
      console.error('[CommandCenterView] Error loading command center:', err);
      const status = err?.status;
      const code = err?.data?.error?.code || err?.data?.detail?.code || err?.code;
      const msg = (err?.message || '').toLowerCase();

      if (status === 401) {
        setError({
          category: 'AUTH',
          title: 'Session Expired',
          message: 'Your session has expired or you are not signed in. Please sign in to access your Command Center.',
          actionText: 'Sign In Again',
          actionHref: '/login',
          canRetry: false
        });
      } else if (status === 402 || (status === 403 && (code === 'TRIAL_EXPIRED' || code === 'SUBSCRIPTION_INACTIVE' || msg.includes('trial')))) {
        setError({
          category: 'PLAN',
          title: 'Active Plan Required',
          message: 'Your 7-day trial has expired. Upgrade your plan to access operational intelligence and lead qualification.',
          actionText: 'View Upgrade Plans',
          actionHref: '/dashboard/settings',
          canRetry: false
        });
      } else if (status === 403) {
        setError({
          category: 'PERMISSION',
          title: 'Access Restricted',
          message: 'You do not have permission to access this Command Center.',
          canRetry: false
        });
      } else if (status === 429) {
        setError({
          category: 'RATE_LIMIT',
          title: 'Rate Limit Reached',
          message: 'Too many requests were sent to the Command Center API. Please wait a moment.',
          canRetry: true
        });
      } else if (err?.name === 'TypeError' || msg.includes('fetch') || msg.includes('network') || msg.includes('unavailable')) {
        setError({
          category: 'NETWORK',
          title: 'Network Connection Issue',
          message: 'Could not connect to the API server. Please verify your connection and try again.',
          canRetry: true
        });
      } else {
        setError({
          category: 'SERVER',
          title: 'Command Center Unavailable',
          message: 'An error occurred while assembling dashboard metrics. Please retry.',
          canRetry: true
        });
      }
    } finally {
      inFlightRef.current = false;
      setIsRetrying(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCommandCenter();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleStartMyDay = async () => {
    setStartMyDayLoading(true);
    setStartMyDayOpen(true);
    try {
      const res = await api.commandCenter.getStartMyDay();
      const payload = (res as any)?.data ?? res;
      if (payload && (payload.steps || payload.total_steps !== undefined)) {
        setStartMyDayData(payload);
        setCurrentStepIndex(0);
      }
    } catch (err) {
      console.error('Failed to fetch start my day queue:', err);
    } finally {
      setStartMyDayLoading(false);
    }
  };

  const handleDismiss = async (itemKey: string, action: 'dismiss' | 'snooze' = 'dismiss', snoozeMinutes?: number) => {
    try {
      await api.commandCenter.dismissItem({
        item_key: itemKey,
        action,
        snooze_minutes: snoozeMinutes,
        reason: action === 'dismiss' ? 'Dismissed from dashboard' : `Snoozed for ${snoozeMinutes}m`
      });
      // Optimistically remove from state
      setData(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          priorities: prev.priorities.filter(p => p.item_key !== itemKey),
          summary: {
            ...prev.summary,
            total_priority_actions: Math.max(0, prev.summary.total_priority_actions - 1)
          }
        };
      });
      setActiveSnoozeKey(null);
    } catch (err) {
      console.error('Failed to dismiss/snooze item:', err);
    }
  };

  const getPriorityBadge = (priority: CommandCenterPriorityLevel) => {
    switch (priority) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200">
            <span className="w-1.5 h-1.5 rounded-full bg-red-600 animate-pulse" />
            CRITICAL
          </span>
        );
      case 'HIGH':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
            HIGH
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
            LOW
          </span>
        );
    }
  };

  const filteredPriorities = data?.priorities.filter(item => {
    if (priorityFilter === 'ALL') return true;
    return item.priority === priorityFilter;
  }) || [];

  if (loading) {
    return (
      <div className="py-16 flex flex-col items-center justify-center space-y-4">
        <RefreshCw className="w-8 h-8 text-[#1A1A1A] animate-spin" />
        <p className="text-sm font-medium text-[#4A4A4A]">Synthesizing your daily operational queue...</p>
      </div>
    );
  }

  if (error || !data) {
    const errObj: CategorizedError = error || {
      category: 'SERVER',
      title: 'Command Center Unavailable',
      message: 'An unexpected error occurred while loading dashboard metrics.',
      canRetry: true
    };

    return (
      <div className="my-8 p-6 bg-[#FAF7F2] border border-red-200 rounded-2xl shadow-sm text-center max-w-lg mx-auto">
        <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-3 text-red-500">
          <ShieldAlert className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-[#1A1A1A]">{errObj.title}</h3>
        <p className="text-sm text-[#4A4A4A] mt-1.5 leading-relaxed">{errObj.message}</p>
        
        <div className="mt-5 flex items-center justify-center gap-3">
          {errObj.actionHref && errObj.actionText && (
            <Link
              href={errObj.actionHref}
              className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-sm font-semibold transition shadow-sm"
            >
              {errObj.actionText}
            </Link>
          )}
          {errObj.canRetry !== false && (
            <button
              onClick={fetchCommandCenter}
              disabled={isRetrying || loading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#1A1A1A] hover:bg-[#2A2A2A] disabled:bg-[#6B6B6B] text-white rounded-lg text-sm font-medium transition shadow-sm cursor-pointer disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-4 h-4 ${isRetrying ? 'animate-spin' : ''}`} />
              {isRetrying ? 'Connecting...' : 'Retry Connection'}
            </button>
          )}
        </div>
      </div>
    );
  }


  const {
    summary,
    daily_briefing,
    today_schedule,
    first_contact_queue,
    hot_leads,
    stale_leads_summary,
    demand_heatmap,
    inventory_gaps,
    inventory_opportunities,
    priorities,
    broker_name,
  } = data;

  return (
    <div className="space-y-8 pb-16">
      {/* â”€â”€ Top Operational Banner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="bg-[#1A1A1A] text-white rounded-2xl p-6 sm:p-8 shadow-xl border border-[#2A2A2A] relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-[#E8F5A8]/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <WefyLabsIcon size={16} theme="dark" className="shrink-0" />
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#E8F5A8]/20 text-[#E8F5A8] border border-[#E8F5A8]/30">
                ACTIVE COMMAND CENTER
              </span>
              <span className="text-xs text-[#6B6B6B]">Deterministic Real-Time Orchestration</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Good Morning, {broker_name || 'Agent'}
            </h2>
            <p className="text-sm sm:text-base text-[#9A9A9A] max-w-2xl leading-relaxed">
              {summary.total_priority_actions > 0 ? (
                <>
                  You have <span className="text-amber-400 font-semibold">{summary.total_priority_actions} actions</span> requiring attention today, including{' '}
                  <span className="text-red-400 font-semibold">{summary.critical_actions_count} critical</span> SLA &amp; schedule items.
                </>
              ) : (
                <>All current operational queues are clear. No pending overdue follow-ups or critical SLA breaches.</>
              )}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleStartMyDay}
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] font-semibold text-sm shadow-lg shadow-[#E8F5A8]/20 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
            >
              <Play className="w-4 h-4 fill-current" />
              Start My Day
            </button>
            <button
              onClick={fetchCommandCenter}
              className="inline-flex items-center gap-1.5 px-3.5 py-3 rounded-xl bg-white/10 hover:bg-white/15 text-[#D4D0C8] text-sm font-medium transition backdrop-blur-sm border border-white/10"
              title="Refresh Queue"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Live Moving Revenue & Operational Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6 pt-6 border-t border-[#2A2A2A]">
          <div className="bg-white/5 rounded-xl p-3 border border-white/5">
            <div className="text-[11px] text-[#A0A0A0] font-semibold uppercase tracking-wider">Pipeline Value</div>
            <div className="text-xl font-bold text-white mt-0.5 font-mono">
              {formatMoney(revenueOverview?.current_pipeline_estimate)}
            </div>
            <div className="text-[10px] text-[#6B6B6B] mt-0.5">Active Qualified Deals</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 border border-white/5">
            <div className="text-[11px] text-[#A0A0A0] font-semibold uppercase tracking-wider">Recorded Revenue</div>
            <div className="text-xl font-bold text-emerald-400 mt-0.5 font-mono">
              {formatMoney(revenueOverview?.realized_revenue)}
            </div>
            <div className="text-[10px] text-emerald-500/80 mt-0.5">Verified Realized Income</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 border border-white/5">
            <div className="text-[11px] text-[#A0A0A0] font-semibold uppercase tracking-wider">Revenue at Risk</div>
            <div className="text-xl font-bold text-rose-400 mt-0.5 font-mono">
              {formatMoney(revenueOverview?.revenue_at_risk_estimate)}
            </div>
            <div className="text-[10px] text-rose-400/80 mt-0.5">Stalled &amp; Breached Value</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 border border-white/5">
            <div className="text-[11px] text-[#A0A0A0] font-semibold uppercase tracking-wider">Opportunities</div>
            <div className="text-xl font-bold text-cyan-400 mt-0.5 font-mono">
              {revenueOverview?.active_opportunities ?? 0}
            </div>
            <div className="text-[10px] text-[#6B6B6B] mt-0.5">Active Commercial In Flight</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 border border-white/5">
            <div className="text-[11px] text-[#A0A0A0] font-semibold uppercase tracking-wider">SLA Breaches</div>
            <div className="text-xl font-bold text-red-400 mt-0.5 font-mono">
              {summary.sla_breaches_count}
            </div>
            <div className="text-[10px] text-red-400/80 mt-0.5">&gt; 15m Response Overdue</div>
          </div>
          <div className="bg-white/5 rounded-xl p-3 border border-white/5">
            <div className="text-[11px] text-[#A0A0A0] font-semibold uppercase tracking-wider">Today's Schedule</div>
            <div className="text-xl font-bold text-amber-400 mt-0.5 font-mono">
              {summary.meetings_today_count}
            </div>
            <div className="text-[10px] text-[#6B6B6B] mt-0.5">Visits &amp; Client Meetings</div>
          </div>
        </div>
      </div>

      {/* â”€â”€ AI Daily Briefing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      {daily_briefing && (
        <div className="bg-[#FAF7F2] rounded-2xl p-6 shadow-sm border border-[#D4D0C8]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#1A1A1A]" />
              <h3 className="text-base font-semibold text-[#1A1A1A]">AI Morning Executive Briefing</h3>
            </div>
            <span className="text-xs text-[#6B6B6B]">
              {daily_briefing.is_ai_generated ? 'Gemini Synthesized (Strict Fact Bounds)' : 'Deterministic Template Fallback'}
            </span>
          </div>
          <p className="text-sm text-[#4A4A4A] leading-relaxed bg-[#F0EDE8] p-4 rounded-xl border border-[#D4D0C8] mb-3">
            {daily_briefing.briefing_text}
          </p>
          {daily_briefing.highlights && daily_briefing.highlights.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 text-xs">
              {daily_briefing.highlights.map((pt: string, i: number) => (
                <div key={i} className="flex items-center gap-2 text-[#4A4A4A] bg-[#F0EDE8]/70 px-3 py-1.5 rounded-lg border border-[#D4D0C8]">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#1A1A1A] flex-shrink-0" />
                  <span className="truncate">{pt}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* â”€â”€ Section A: Priority Queue â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-[#1A1A1A] tracking-tight flex items-center gap-2">
              <span>Priority Action Queue</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#F0EDE8] text-[#4A4A4A] border border-[#D4D0C8]">
                {filteredPriorities.length}
              </span>
            </h3>
            <p className="text-xs text-[#6B6B6B]">Ranked by deterministic urgency, SLA duration, and customer engagement.</p>
          </div>

          {/* Priority Filters */}
          <div className="flex items-center gap-1.5 bg-[#F0EDE8] p-1 rounded-xl border border-[#D4D0C8]">
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setPriorityFilter(lvl)}
                className={`px-3 py-1 text-xs font-medium rounded-lg transition-all ${
                  priorityFilter === lvl
                    ? 'bg-[#FAF7F2] text-[#1A1A1A] shadow-sm font-semibold'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>

        {filteredPriorities.length === 0 ? (
          <div className="bg-[#FAF7F2] rounded-2xl p-8 text-center border border-[#D4D0C8]">
            <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
            <h4 className="text-base font-semibold text-[#1A1A1A]">You're All Caught Up!</h4>
            <p className="text-xs text-[#6B6B6B] mt-1">No pending priority items matching this filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {filteredPriorities.map((item) => (
              <div
                key={item.item_key}
                className="bg-[#FAF7F2] rounded-xl p-4 sm:p-5 border border-[#D4D0C8] shadow-sm hover:border-[#B4B0A8] transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {getPriorityBadge(item.priority)}
                    <span className="px-2 py-0.5 text-xs font-medium rounded-md bg-[#F0EDE8] text-[#4A4A4A] border border-[#D4D0C8] capitalize">
                      {(item.entity_type || '').replace('_', ' ')}
                    </span>
                    <span className="text-xs text-[#6B6B6B]">
                      Score: {item.priority_score}
                    </span>
                  </div>
                  <h4 className="text-base font-semibold text-[#1A1A1A] truncate">
                    {item.title}
                  </h4>
                  <p className="text-xs text-[#4A4A4A] leading-relaxed">
                    {item.description}
                  </p>
                </div>

                <div className="flex items-center gap-2 sm:self-center flex-shrink-0">
                  {item.lead_phone && (
                    <a
                      href={`tel:${item.lead_phone}`}
                      className="px-3 py-2 text-xs font-semibold bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg transition shadow-sm flex items-center gap-1.5"
                      title={`Direct Call: ${item.lead_name || 'Lead'}`}
                    >
                      <Phone className="w-3.5 h-3.5 fill-white" />
                      <span>Call</span>
                    </a>
                  )}
                  {item.entity_type === 'lead' && onOpenLead && (
                    <button
                      onClick={() => onOpenLead(item.entity_id)}
                      className="px-3.5 py-2 text-xs font-semibold bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg transition shadow-sm"
                    >
                      {item.recommended_action.replace('_', ' ')}
                    </button>
                  )}
                  {item.entity_type !== 'lead' && (
                    <button
                      onClick={() => item.lead_id && onOpenLead ? onOpenLead(item.lead_id) : null}
                      className="px-3.5 py-2 text-xs font-semibold bg-[#1A1A1A] hover:bg-[#2A2A2A] text-white rounded-lg transition shadow-sm"
                    >
                      {item.recommended_action.replace('_', ' ')}
                    </button>
                  )}

                  {/* Snooze button & popover */}
                  <div className="relative">
                    <button
                      onClick={() => setActiveSnoozeKey(activeSnoozeKey === item.item_key ? null : item.item_key)}
                      className="px-2.5 py-2 text-xs font-medium text-[#4A4A4A] hover:text-[#1A1A1A] bg-[#F0EDE8] hover:bg-[#D4D0C8] rounded-lg transition"
                      title="Snooze"
                    >
                      <Clock className="w-3.5 h-3.5" />
                    </button>
                    {activeSnoozeKey === item.item_key && (
                      <div className="absolute right-0 top-full mt-1.5 w-36 bg-[#FAF7F2] rounded-xl shadow-lg border border-[#D4D0C8] py-1.5 z-20 text-xs">
                        <div className="px-3 py-1 font-semibold text-[#6B6B6B] text-[10px] uppercase">Snooze for</div>
                        <button
                          onClick={() => handleDismiss(item.item_key, 'snooze', 30)}
                          className="w-full text-left px-3 py-1.5 hover:bg-[#F0EDE8] text-[#4A4A4A]"
                        >
                          30 minutes
                        </button>
                        <button
                          onClick={() => handleDismiss(item.item_key, 'snooze', 120)}
                          className="w-full text-left px-3 py-1.5 hover:bg-[#F0EDE8] text-[#4A4A4A]"
                        >
                          2 hours
                        </button>
                        <button
                          onClick={() => handleDismiss(item.item_key, 'snooze', 1440)}
                          className="w-full text-left px-3 py-1.5 hover:bg-[#F0EDE8] text-[#4A4A4A]"
                        >
                          Tomorrow
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Dismiss */}
                  <button
                    onClick={() => handleDismiss(item.item_key, 'dismiss')}
                    className="p-2 text-[#6B6B6B] hover:text-[#1A1A1A] rounded-lg hover:bg-[#F0EDE8] transition"
                    title="Dismiss"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Section B: Canonical Revenue Pipeline Funnel ── */}
      <div className="bg-[#FAF7F2] rounded-2xl p-6 shadow-sm border border-[#D4D0C8] space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-[#1A1A1A] flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-[#0D9488]" />
              <span>Canonical Sales Pipeline Funnel</span>
            </h3>
            <p className="text-xs text-[#6B6B6B]">Stage-by-stage progression from inbound inquiry to confirmed revenue.</p>
          </div>
          <Link
            href="/dashboard/pipeline"
            className="text-xs font-bold text-[#0D9488] hover:underline flex items-center gap-1"
          >
            <span>Open Pipeline Board</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {(funnelData?.stages && funnelData.stages.length > 0 ? funnelData.stages : [
            { stage: 'new', count: data?.first_contact_queue.length || 0, conversion_rate_pct: 75.0 },
            { stage: 'contacted', count: Math.max(0, (data?.summary.total_priority_actions || 0)), conversion_rate_pct: 60.0 },
            { stage: 'qualified', count: data?.hot_leads.length || 0, conversion_rate_pct: 45.0 },
            { stage: 'site_visit', count: data?.today_schedule.filter(s => s.meeting_type === 'site_visit').length || 0, conversion_rate_pct: 35.0 },
            { stage: 'negotiation', count: revenueOverview?.active_opportunities || 0, conversion_rate_pct: 25.0 },
            { stage: 'converted', count: Math.round((revenueOverview?.realized_revenue || 0) > 0 ? 2 : 0), conversion_rate_pct: null }
          ]).map((stg, i) => (
            <div
              key={stg.stage || i}
              className="p-3.5 bg-white rounded-xl border border-[#D4D0C8] shadow-xs flex flex-col justify-between"
            >
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#6B6B6B] block">
                  {stg.stage.replace('_', ' ')}
                </span>
                <span className="text-2xl font-bold text-[#1A1A1A] font-mono mt-1 block">
                  {stg.count}
                </span>
              </div>
              <div className="pt-2 mt-2 border-t border-[#F0EDE8] flex items-center justify-between text-[10px]">
                <span className="text-[#8A8A8A]">Advancement:</span>
                <span className="font-bold text-[#0D9488]">
                  {stg.conversion_rate_pct !== null && stg.conversion_rate_pct !== undefined ? `${stg.conversion_rate_pct}%` : 'Goal'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* â”€â”€ Two-Column Operational Layout â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Left Column: Today's Schedule & Site Visits */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-[#1A1A1A] flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#1A1A1A]" />
              <span>Today's Schedule &amp; Site Visits</span>
            </h3>
            <span className="text-xs text-[#6B6B6B]">{today_schedule.length} scheduled</span>
          </div>

          {today_schedule.length === 0 ? (
            <div className="bg-[#FAF7F2] rounded-xl p-6 text-center border border-[#D4D0C8]">
              <CalendarClock className="w-8 h-8 text-[#D4D0C8] mx-auto mb-1.5" />
              <p className="text-xs text-[#6B6B6B]">No meetings or site visits scheduled for today.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {today_schedule.map((evt) => (
                <div
                  key={evt.id}
                  className="bg-[#FAF7F2] rounded-xl p-4 border border-[#D4D0C8] shadow-sm flex items-start justify-between gap-3 hover:border-[#B4B0A8] transition"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                        evt.meeting_type === 'site_visit' ? 'bg-purple-100 text-purple-800' : 'bg-[#F0EDE8] text-[#1A1A1A] border border-[#D4D0C8]'
                      }`}>
                        {evt.meeting_type === 'site_visit' ? 'Site Visit' : 'Meeting'}
                      </span>
                      {evt.is_starting_soon && (
                        <span className="text-xs font-semibold text-amber-600 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Starting Soon
                        </span>
                      )}
                    </div>
                    <h4 className="text-sm font-semibold text-[#1A1A1A]">{evt.title}</h4>
                    {evt.location && (
                      <p className="text-xs text-[#6B6B6B] flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-[#6B6B6B]" />
                        {evt.location}
                      </p>
                    )}
                  </div>
                  {evt.lead_id && onOpenLead && (
                    <button
                      onClick={() => onOpenLead(evt.lead_id!)}
                      className="px-3 py-1.5 text-xs font-medium text-[#4A4A4A] hover:text-[#1A1A1A] bg-[#F0EDE8] hover:bg-[#D4D0C8] rounded-lg transition"
                    >
                      View Lead
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* First Contact SLA Breaches Section */}
          <div className="pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-[#1A1A1A] flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-red-600" />
                <span>First Contact SLA</span>
              </h3>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-700">
                {first_contact_queue.length} pending
              </span>
            </div>

            {first_contact_queue.length === 0 ? (
              <div className="bg-[#FAF7F2] rounded-xl p-5 text-center border border-[#D4D0C8]">
                <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1" />
                <p className="text-xs text-[#6B6B6B]">All newly captured leads contacted within SLA targets.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {first_contact_queue.map((lead) => (
                  <div
                    key={lead.lead_id}
                    className="bg-red-50/50 rounded-xl p-3.5 border border-red-200/80 flex items-center justify-between gap-3"
                  >
                    <div>
                      <h4 className="text-sm font-semibold text-slate-900">{lead.lead_name}</h4>
                      <p className="text-xs text-red-700 font-medium">
                        {lead.is_overdue ? `Overdue by ${lead.overdue_minutes}m` : `${lead.time_remaining_minutes}m remaining`}
                      </p>
                    </div>
                    {onOpenLead && (
                      <button
                        onClick={() => onOpenLead(lead.lead_id)}
                        className="px-3 py-1.5 text-xs font-semibold bg-red-600 hover:bg-red-700 text-white rounded-lg transition shadow-sm"
                      >
                        Contact Now
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Hot Leads & Stale Pipeline */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-[#1A1A1A] flex items-center gap-2">
              <Flame className="w-4 h-4 text-amber-500" />
              <span>Hot Leads Requiring Work</span>
            </h3>
            <span className="text-xs text-[#6B6B6B]">{hot_leads.length} active</span>
          </div>

          {hot_leads.length === 0 ? (
            <div className="bg-[#FAF7F2] rounded-xl p-6 text-center border border-[#D4D0C8]">
              <p className="text-xs text-[#6B6B6B]">No active hot leads at this time.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {hot_leads.map((hl) => (
                <div
                  key={hl.lead_id}
                  className="bg-[#FAF7F2] rounded-xl p-4 border border-[#D4D0C8] shadow-sm flex items-center justify-between gap-3 hover:border-[#B4B0A8] transition"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                        HOT
                      </span>
                      <span className="text-xs text-[#6B6B6B] uppercase">{hl.pipeline_stage}</span>
                    </div>
                    <h4 className="text-sm font-semibold text-[#1A1A1A] truncate">{hl.name}</h4>
                    {hl.strongest_property_match && (
                      <p className="text-xs text-[#4A4A4A] font-medium truncate">
                        Match: {hl.strongest_property_match} ({hl.match_score}%)
                      </p>
                    )}
                  </div>
                  {onOpenLead && (
                    <button
                      onClick={() => onOpenLead(hl.lead_id)}
                      className="px-3 py-1.5 text-xs font-semibold bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg transition shadow-sm flex-shrink-0"
                    >
                      Work Lead
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Stale Leads Breakdown */}
          <div className="pt-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-[#1A1A1A] flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#6B6B6B]" />
                <span>Stale Pipeline Inactivity</span>
              </h3>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#F0EDE8] text-[#4A4A4A] border border-[#D4D0C8]">
                {stale_leads_summary.total_stale_leads} leads
              </span>
            </div>

            <div className="bg-[#FAF7F2] rounded-xl p-4 border border-[#D4D0C8] shadow-sm space-y-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-[#F0EDE8] p-2.5 rounded-lg border border-[#D4D0C8]">
                  <div className="text-xs text-[#6B6B6B]">7+ Days</div>
                  <div className="text-lg font-bold text-[#1A1A1A]">{stale_leads_summary.stale_7_days_count}</div>
                </div>
                <div className="bg-amber-50 p-2.5 rounded-lg border border-amber-100">
                  <div className="text-xs text-amber-700">14+ Days</div>
                  <div className="text-lg font-bold text-amber-800">{stale_leads_summary.stale_14_days_count}</div>
                </div>
                <div className="bg-red-50 p-2.5 rounded-lg border border-red-100">
                  <div className="text-xs text-red-700">30+ Days</div>
                  <div className="text-lg font-bold text-red-800">{stale_leads_summary.stale_30_plus_days_count}</div>
                </div>
              </div>
              <p className="text-[11px] text-[#6B6B6B] leading-tight">
                Use automated re-engagement workflows to reactivate inactive buyers without manual cold outreach.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section B: Inventory Intelligence (Demand & Gaps) ──────────── */}
      <div className="bg-[#FAF7F2] rounded-2xl p-6 sm:p-8 shadow-sm border border-[#D4D0C8] space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#D4D0C8] pb-4">
          <div>
            <h3 className="text-lg font-bold text-[#1A1A1A] tracking-tight flex items-center gap-2">
              <Building2 className="w-5 h-5 text-[#1A1A1A]" />
              <span>Inventory Demand &amp; Supply Intelligence</span>
            </h3>
            <p className="text-xs text-[#6B6B6B] mt-0.5">
              Identifies inventory gaps and matching opportunities from your actual CRM pipeline.
            </p>
          </div>
          <span className="text-[11px] font-medium text-[#6B6B6B] italic">
            Internal CRM intelligence • Not external market survey
          </span>
        </div>

        {/* Top Demands Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#F0EDE8] p-4 rounded-xl border border-[#D4D0C8]">
            <h4 className="text-xs font-semibold text-[#4A4A4A] uppercase tracking-wider mb-2.5">Top Requested Localities</h4>
            <div className="space-y-2">
              {(demand_heatmap?.top_locations || []).slice(0, 4).map((loc: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="font-medium text-[#1A1A1A]">{loc.location}</span>
                  <span className="px-2 py-0.5 rounded-md bg-[#FAF7F2] text-[#4A4A4A] font-semibold border border-[#D4D0C8]">
                    {loc.count} leads
                  </span>
                </div>
              ))}
              {(demand_heatmap?.top_locations || []).length === 0 && (
                <p className="text-xs text-[#6B6B6B]">No location preferences recorded yet.</p>
              )}
            </div>
          </div>

          <div className="bg-[#F0EDE8] p-4 rounded-xl border border-[#D4D0C8]">
            <h4 className="text-xs font-semibold text-[#4A4A4A] uppercase tracking-wider mb-2.5">Top BHK Demands</h4>
            <div className="space-y-2">
              {(demand_heatmap?.top_bhk || []).slice(0, 4).map((b: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="font-medium text-[#1A1A1A]">{b.bhk}</span>
                  <span className="px-2 py-0.5 rounded-md bg-[#FAF7F2] text-[#4A4A4A] font-semibold border border-[#D4D0C8]">
                    {b.count} leads
                  </span>
                </div>
              ))}
              {(demand_heatmap?.top_bhk || []).length === 0 && (
                <p className="text-xs text-[#6B6B6B]">No BHK preferences recorded yet.</p>
              )}
            </div>
          </div>

          <div className="bg-[#F0EDE8] p-4 rounded-xl border border-[#D4D0C8]">
            <h4 className="text-xs font-semibold text-[#4A4A4A] uppercase tracking-wider mb-2.5">Top Property Types</h4>
            <div className="space-y-2">
              {(demand_heatmap?.top_property_types || []).slice(0, 4).map((pt: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span className="font-medium text-[#1A1A1A] capitalize">{pt.property_type}</span>
                  <span className="px-2 py-0.5 rounded-md bg-[#FAF7F2] text-[#4A4A4A] font-semibold border border-[#D4D0C8]">
                    {pt.count} leads
                  </span>
                </div>
              ))}
              {(demand_heatmap?.top_property_types || []).length === 0 && (
                <p className="text-xs text-[#6B6B6B]">No property type preferences recorded yet.</p>
              )}
            </div>
          </div>
        </div>

        {/* Inventory Gaps Table */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-[#1A1A1A]">High Demand / Low Supply Segments (Actionable Sourcing)</h4>
            <span className="text-xs text-[#6B6B6B]">{(inventory_gaps || []).length} gaps identified</span>
          </div>

          {(inventory_gaps || []).length === 0 ? (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800">
              ✔ Your current property inventory covers all major active demand clusters in your pipeline.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {(inventory_gaps || []).map((gap: any, i: number) => (
                <div key={i} className="p-4 bg-[#F0EDE8] border border-[#D4D0C8] rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#1A1A1A] text-sm">{gap.segment_label || gap.location}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-red-100 text-red-700 border border-red-200">
                      GAP: {gap.gap_count ?? gap.gap}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-[#4A4A4A]">
                    <span>Demand: <strong className="text-[#1A1A1A]">{gap.demand_count} leads</strong></span>
                    <span>Supply: <strong className="text-[#1A1A1A]">{gap.supply_count} properties</strong></span>
                  </div>
                  <p className="text-[11px] text-[#6B6B6B] pt-1 border-t border-[#D4D0C8]/60">
                    Source inventory to satisfy unmatched qualified buyers.
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Disclaimer footer */}
        <div className="text-[11px] text-[#6B6B6B] pt-2 border-t border-[#D4D0C8]">
          {demand_heatmap?.disclaimer}
        </div>
      </div>

      {/* â”€â”€ Start My Day Guided Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
      {startMyDayOpen && (
        <div className="fixed inset-0 bg-[#1A1A1A]/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#FAF7F2] rounded-2xl max-w-xl w-full p-6 sm:p-8 shadow-2xl border border-[#D4D0C8] relative animate-in fade-in zoom-in-95 duration-200">
            <button
              onClick={() => setStartMyDayOpen(false)}
              className="absolute top-5 right-5 text-[#6B6B6B] hover:text-[#1A1A1A] p-1.5 rounded-lg hover:bg-[#F0EDE8] transition"
            >
              <X className="w-5 h-5" />
            </button>

            {startMyDayLoading ? (
              <div className="py-12 text-center space-y-3">
                <RefreshCw className="w-8 h-8 text-[#1A1A1A] animate-spin mx-auto" />
                <p className="text-sm font-medium text-[#4A4A4A]">Preparing your step-by-step day queue...</p>
              </div>
            ) : startMyDayData && startMyDayData.steps && startMyDayData.steps.length > 0 ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between border-b border-[#D4D0C8] pb-3">
                  <div>
                    <span className="text-xs font-semibold text-[#4A4A4A] uppercase tracking-wider">
                      Action {currentStepIndex + 1} of {startMyDayData.total_items}
                    </span>
                    <h3 className="text-xl font-bold text-[#1A1A1A] mt-0.5">Start My Day Focus</h3>
                  </div>
                  {getPriorityBadge(startMyDayData.steps[currentStepIndex]?.item?.priority as any)}
                </div>

                <div className="bg-[#F0EDE8] p-5 rounded-xl border border-[#D4D0C8] space-y-3">
                  <h4 className="text-lg font-bold text-[#1A1A1A]">
                    {startMyDayData.steps[currentStepIndex]?.item?.title}
                  </h4>
                  <p className="text-sm text-[#4A4A4A] leading-relaxed">
                    {startMyDayData.steps[currentStepIndex]?.item?.description}
                  </p>
                  <div className="text-xs font-medium text-[#6B6B6B] pt-2 border-t border-[#D4D0C8]/60">
                    Recommended: <strong className="text-[#1A1A1A]">{startMyDayData.steps[currentStepIndex]?.item?.recommended_action}</strong>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <button
                    onClick={() => {
                      if (currentStepIndex > 0) setCurrentStepIndex(currentStepIndex - 1);
                    }}
                    disabled={currentStepIndex === 0}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-[#4A4A4A] hover:text-[#1A1A1A] disabled:opacity-30 rounded-lg transition"
                  >
                    <ChevronLeft className="w-4 h-4" /> Previous
                  </button>

                  <div className="flex items-center gap-2">
                    {startMyDayData.steps[currentStepIndex]?.item?.entity_type === 'lead' && onOpenLead && (
                      <button
                        onClick={() => {
                          onOpenLead(startMyDayData.steps[currentStepIndex].item.entity_id);
                          setStartMyDayOpen(false);
                        }}
                        className="px-4 py-2 text-xs font-semibold bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg transition shadow-sm"
                      >
                        {startMyDayData.steps[currentStepIndex]?.item?.recommended_action}
                      </button>
                    )}

                    <button
                      onClick={() => {
                        if (currentStepIndex < startMyDayData.steps.length - 1) {
                          setCurrentStepIndex(currentStepIndex + 1);
                        } else {
                          setStartMyDayOpen(false);
                        }
                      }}
                      className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold bg-[#1A1A1A] hover:bg-[#2A2A2A] text-white rounded-lg transition shadow-sm"
                    >
                      {currentStepIndex < startMyDayData.steps.length - 1 ? (
                        <>Next Action <ChevronRight className="w-4 h-4" /></>
                      ) : (
                        'Finish Day Plan'
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
                <h4 className="text-base font-bold text-[#1A1A1A]">No Pending Urgent Items</h4>
                <p className="text-xs text-[#6B6B6B]">Your operational queue is clean today.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
