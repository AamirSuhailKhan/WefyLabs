'use client';

import React, { useEffect, useState, useCallback } from 'react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import {
  RevenueOverviewDTO,
  FunnelSummaryDTO,
  LeakageReportDTO,
  ExtendedLeakageItemDTO,
  AttributionReportDTO,
  OutcomeSummaryDTO,
  LearningLoopSummaryDTO,
  DataQualityReportDTO,
  TeamIntelligenceDTO,
  LeadRevenueJourneyDTO
} from '@/lib/api-client';
import {
  RefreshCw,
  TrendingUp,
  AlertOctagon,
  PieChart,
  ShieldCheck,
  Users,
  Activity,
  ArrowRight,
  Database,
  Search,
  CheckCircle2,
  XCircle,
  HelpCircle
} from 'lucide-react';

export default function RevenueIntelligencePage() {
  const [activeTab, setActiveTab] = useState<'funnel' | 'leakage' | 'attribution' | 'outcomes' | 'quality' | 'team'>('funnel');
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [loading, setLoading] = useState<boolean>(true);
  const [recomputing, setRecomputing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Core Data States
  const [overview, setOverview] = useState<RevenueOverviewDTO | null>(null);
  const [funnel, setFunnel] = useState<FunnelSummaryDTO | null>(null);
  const [leakage, setLeakage] = useState<LeakageReportDTO | null>(null);
  const [leakageItems, setLeakageItems] = useState<ExtendedLeakageItemDTO[]>([]);
  const [leakageSeverityFilter, setLeakageSeverityFilter] = useState<string>('ALL');
  const [attribution, setAttribution] = useState<AttributionReportDTO | null>(null);
  const [outcomes, setOutcomes] = useState<OutcomeSummaryDTO | null>(null);
  const [learningLoop, setLearningLoop] = useState<LearningLoopSummaryDTO | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQualityReportDTO | null>(null);
  const [team, setTeam] = useState<TeamIntelligenceDTO | null>(null);

  // Lead Journey Search
  const [searchLeadId, setSearchLeadId] = useState<string>('');
  const [leadJourney, setLeadJourney] = useState<LeadRevenueJourneyDTO | null>(null);
  const [journeyLoading, setJourneyLoading] = useState<boolean>(false);
  const [journeyError, setJourneyError] = useState<string | null>(null);

  const getDateParams = useCallback(() => {
    if (dateRange === 'all') return {};
    const now = new Date();
    const past = new Date();
    if (dateRange === '7d') past.setDate(now.getDate() - 7);
    if (dateRange === '30d') past.setDate(now.getDate() - 30);
    if (dateRange === '90d') past.setDate(now.getDate() - 90);
    return {
      start_date: past.toISOString(),
      end_date: now.toISOString(),
    };
  }, [dateRange]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = getDateParams();
    try {
      const [
        overviewRes,
        funnelRes,
        leakageRes,
        leakageItemsRes,
        attributionRes,
        outcomesRes,
        learningRes,
        qualityRes,
        teamRes,
      ] = await Promise.allSettled([
        api.revenueIntelligence.getOverview(params),
        api.revenueIntelligence.getFunnel(params),
        api.revenueIntelligence.getLeakage(params),
        api.revenueIntelligence.getLeakageItems({ ...params, limit: 50 }),
        api.revenueIntelligence.getAttribution(params),
        api.revenueIntelligence.getOutcomes(params),
        api.revenueIntelligence.getActions(params),
        api.revenueIntelligence.getDataQuality(params),
        api.revenueIntelligence.getTeam(params),
      ]);

      if (overviewRes.status === 'fulfilled') setOverview(overviewRes.value);
      if (funnelRes.status === 'fulfilled') setFunnel(funnelRes.value);
      if (leakageRes.status === 'fulfilled') setLeakage(leakageRes.value);
      if (leakageItemsRes.status === 'fulfilled') setLeakageItems(leakageItemsRes.value);
      if (attributionRes.status === 'fulfilled') setAttribution(attributionRes.value);
      if (outcomesRes.status === 'fulfilled') setOutcomes(outcomesRes.value);
      if (learningRes.status === 'fulfilled') setLearningLoop(learningRes.value);
      if (qualityRes.status === 'fulfilled') setDataQuality(qualityRes.value);
      if (teamRes.status === 'fulfilled') setTeam(teamRes.value);
    } catch (err: any) {
      setError(err?.message || 'Failed to load revenue intelligence data');
    } finally {
      setLoading(false);
    }
  }, [getDateParams]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRecompute = async () => {
    setRecomputing(true);
    try {
      await api.revenueIntelligence.recompute();
      await loadData();
    } catch (err: any) {
      alert(`Recomputation failed: ${err.message}`);
    } finally {
      setRecomputing(false);
    }
  };

  const handleFetchLeadJourney = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchLeadId.trim()) return;
    setJourneyLoading(true);
    setJourneyError(null);
    setLeadJourney(null);
    try {
      const res = await api.revenueIntelligence.getLeadJourney(searchLeadId.trim());
      setLeadJourney(res);
    } catch (err: any) {
      setJourneyError(err?.message || 'Lead journey could not be located');
    } finally {
      setJourneyLoading(false);
    }
  };

  const filteredLeakageItems = leakageItems.filter(item => {
    if (leakageSeverityFilter === 'ALL') return true;
    return item.severity === leakageSeverityFilter;
  });

  const formatCurrency = (val: number | null | undefined) => {
    if (val === null || val === undefined) return 'No Data';
    if (val === 0) return '₹0';
    if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
    if (val >= 100000) return `₹${(val / 100000).toFixed(2)} Lakh`;
    return `₹${val.toLocaleString('en-IN')}`;
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A]">
      <DashboardNav />

      <div className="pt-20 pb-16">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 space-y-6">

          {/* Top Header & Range Selection */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="bg-[#1A1A1A] text-white text-[10px] font-mono uppercase px-2 py-0.5 rounded tracking-wider">
                  INSTITUTIONAL
                </span>
                <span className="text-xs font-mono font-semibold text-[#6B6B6B] uppercase tracking-widest">
                  Enterprise Revenue Analytics
                </span>
              </div>
              <h1
                className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1A1A1A] mt-1"
                style={{ fontFamily: 'JetBrains Mono, Geist Mono, monospace' }}
              >
                REVENUE INTELLIGENCE & FUNNEL ATTRIBUTION
              </h1>
              <p className="text-xs text-[#6B6B6B] mt-1 font-sans">
                Deterministic funnel progression, 15-category leakage radar, source attribution, and verified learning loop.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Date range switcher */}
              <div className="flex items-center bg-white border border-[#D4D0C8] rounded-xl p-1 shadow-sm text-xs font-mono">
                {(['7d', '30d', '90d', 'all'] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setDateRange(r)}
                    className={`px-3 py-1.5 rounded-lg transition-all ${
                      dateRange === r
                        ? 'bg-[#1A1A1A] text-white font-bold'
                        : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                    }`}
                  >
                    {r === 'all' ? 'ALL TIME' : r.toUpperCase()}
                  </button>
                ))}
              </div>

              {/* Recompute button */}
              <button
                onClick={handleRecompute}
                disabled={recomputing}
                className="flex items-center gap-1.5 px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs font-mono font-semibold hover:bg-[#EAE6DF] transition shadow-sm disabled:opacity-50"
                title="Run deterministic analytics engine recomputation"
              >
                <Activity className={`w-3.5 h-3.5 ${recomputing ? 'animate-pulse text-amber-600' : ''}`} />
                <span>{recomputing ? 'Recomputing...' : 'Recompute'}</span>
              </button>

              {/* Refresh button */}
              <button
                onClick={loadData}
                disabled={loading}
                className="p-2 bg-white border border-[#D4D0C8] rounded-xl hover:bg-[#EAE6DF] transition shadow-sm disabled:opacity-50"
                title="Refresh page data"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-teal-600' : ''}`} />
              </button>
            </div>
          </div>

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center justify-between">
              <span>{error}</span>
              <button onClick={loadData} className="underline font-bold ml-4">Retry</button>
            </div>
          )}

          {/* Revenue Overview Stats Banner */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
              <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Realized Revenue</span>
              <div className="text-xl font-bold font-mono text-[#0F766E] mt-1">
                {formatCurrency(overview?.realized_revenue)}
              </div>
              <span className="text-[10px] text-[#6B6B6B] block mt-1">Confirmed transactions</span>
            </div>

            <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
              <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Pipeline Value</span>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mt-1">
                {formatCurrency(overview?.current_pipeline_estimate)}
              </div>
              <span className="text-[10px] text-[#6B6B6B] block mt-1">Qualified+ estimate</span>
            </div>

            <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
              <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Revenue At Risk</span>
              <div className="text-xl font-bold font-mono text-red-600 mt-1">
                {formatCurrency(overview?.revenue_at_risk_estimate)}
              </div>
              <span className="text-[10px] text-[#6B6B6B] block mt-1">Stalled / lost opportunities</span>
            </div>

            <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
              <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Active Opportunities</span>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mt-1">
                {overview?.active_opportunities ?? 0}
              </div>
              <span className="text-[10px] text-[#6B6B6B] block mt-1">In progress deals</span>
            </div>

            <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
              <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Attribution Coverage</span>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mt-1">
                {overview?.attribution_coverage_pct !== null && overview?.attribution_coverage_pct !== undefined
                  ? `${overview.attribution_coverage_pct}%`
                  : 'No Data'}
              </div>
              <span className="text-[10px] text-[#6B6B6B] block mt-1">Leads with known source</span>
            </div>

            <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
              <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Total Leads</span>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mt-1">
                {overview?.total_leads ?? 0}
              </div>
              <span className="text-[10px] text-[#6B6B6B] block mt-1">In selected period</span>
            </div>
          </div>

          {/* Forecasting Transparency Banner */}
          <div className="bg-[#FAF9F5] border border-[#D4D0C8] rounded-xl px-4 py-3 text-xs flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-[#6B6B6B] shrink-0" />
              <span className="font-mono font-bold text-[#1A1A1A]">Forecast Status:</span>
              <span className="bg-[#EAE6DF] px-2 py-0.5 rounded font-mono text-[11px]">
                {overview?.forecast_status || 'FORECAST_NOT_AVAILABLE'}
              </span>
              <span className="text-[#6B6B6B] hidden sm:inline">
                {overview?.forecast_disclaimer || 'Projections rely strictly on deterministic pipeline values.'}
              </span>
            </div>
            <span className="text-[10px] font-mono text-[#6B6B6B] uppercase tracking-wider shrink-0">
              Zero ML Fabrication Rule
            </span>
          </div>

          {/* Navigation Tabs */}
          <div className="flex overflow-x-auto space-x-1 border-b border-[#D4D0C8] pb-px">
            {[
              { id: 'funnel', label: 'Canonical Funnel', icon: TrendingUp },
              { id: 'leakage', label: '15-Category Leakage Radar', icon: AlertOctagon, count: leakage?.total_leakage_events },
              { id: 'attribution', label: 'Source Attribution', icon: PieChart },
              { id: 'outcomes', label: 'Outcomes & Learning Loop', icon: Activity },
              { id: 'quality', label: 'Data Quality Panel', icon: ShieldCheck, score: dataQuality?.data_health_score_pct },
              { id: 'team', label: 'Team & Lead Journeys', icon: Users },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-4 py-3 text-xs font-mono font-bold uppercase tracking-wider border-b-2 transition-all whitespace-nowrap ${
                    isActive
                      ? 'border-[#1A1A1A] text-[#1A1A1A] bg-white/50 rounded-t-lg'
                      : 'border-transparent text-[#6B6B6B] hover:text-[#1A1A1A] hover:border-[#D4D0C8]'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {tab.count !== undefined && (
                    <span className="bg-red-100 text-red-700 text-[10px] px-1.5 py-0.5 rounded-full font-bold">
                      {tab.count}
                    </span>
                  )}
                  {tab.score !== undefined && (
                    <span className="bg-teal-100 text-teal-800 text-[10px] px-1.5 py-0.5 rounded-full font-bold">
                      {tab.score}%
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* TAB 1: CANONICAL FUNNEL */}
          {activeTab === 'funnel' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
                  <div>
                    <h2 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider">
                      Canonical 6-Stage Revenue Funnel
                    </h2>
                    <p className="text-xs text-[#6B6B6B] mt-0.5">
                      Deterministic progression with explicit sample denominators. No inflated synthetic conversion metrics.
                    </p>
                  </div>
                  <div className="text-xs font-mono bg-[#FAF9F5] px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
                    Overall Win Rate:{' '}
                    <span className="font-bold text-[#0F766E]">
                      {funnel?.overall_conversion_rate_pct !== null && funnel?.overall_conversion_rate_pct !== undefined
                        ? `${funnel.overall_conversion_rate_pct}%`
                        : 'No Data'}
                    </span>
                  </div>
                </div>

                {/* Funnel Stage Cards */}
                <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
                  {(funnel?.stages || []).map((stage, idx) => (
                    <div
                      key={stage.stage}
                      className="bg-[#FAF9F5] border border-[#D4D0C8] rounded-xl p-4 flex flex-col justify-between relative group hover:border-[#1A1A1A] transition"
                    >
                      <div>
                        <div className="flex items-center justify-between text-[11px] font-mono text-[#6B6B6B] uppercase mb-1">
                          <span>Stage 0{idx + 1}</span>
                          <span className="font-bold text-[#1A1A1A]">{stage.stage}</span>
                        </div>
                        <div className="text-2xl font-bold font-mono text-[#1A1A1A] my-2">
                          {stage.count}
                        </div>
                      </div>

                      <div className="pt-3 border-t border-[#D4D0C8]/60 mt-2">
                        <span className="text-[10px] font-mono text-[#6B6B6B] block">Advancement Rate:</span>
                        <div className="text-xs font-mono font-bold text-[#0F766E] mt-0.5">
                          {stage.conversion_rate_pct !== null && stage.conversion_rate_pct !== undefined
                            ? `${stage.conversion_rate_pct}%`
                            : 'N/A (0 leads)'}
                        </div>
                      </div>

                      {idx < 5 && (
                        <div className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-6 h-6 bg-white border border-[#D4D0C8] rounded-full items-center justify-center shadow-xs">
                          <ArrowRight className="w-3 h-3 text-[#6B6B6B]" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Leakage stage summary table */}
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <h3 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider mb-4">
                  Stage Dropoff &amp; Staleness Breakdown
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase text-[11px]">
                        <th className="pb-3 font-semibold">Funnel Stage</th>
                        <th className="pb-3 font-semibold">Dropoff / Lost Count</th>
                        <th className="pb-3 font-semibold">Avg Days In Stage</th>
                        <th className="pb-3 font-semibold">Estimated Value Lost</th>
                        <th className="pb-3 font-semibold">Primary Dropoff Reason</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#D4D0C8]/50">
                      {(leakage?.by_stage || []).map((row) => (
                        <tr key={row.stage} className="hover:bg-[#FAF9F5] transition">
                          <td className="py-3 font-mono font-bold uppercase">{row.stage}</td>
                          <td className="py-3 font-mono text-red-700">{row.lost_count}</td>
                          <td className="py-3 font-mono">{row.avg_days_in_stage ? `${row.avg_days_in_stage}d` : '—'}</td>
                          <td className="py-3 font-mono">{formatCurrency(row.total_estimated_value_lost_estimate)}</td>
                          <td className="py-3 text-[#6B6B6B]">{row.top_reason || 'UNSPECIFIED'}</td>
                        </tr>
                      ))}
                      {(!leakage?.by_stage || leakage.by_stage.length === 0) && (
                        <tr>
                          <td colSpan={5} className="py-6 text-center text-[#6B6B6B] font-mono">
                            No stage dropoff data detected for this period.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: 15-CATEGORY LEAKAGE RADAR */}
          {activeTab === 'leakage' && (
            <div className="space-y-6">
              {/* Header & Filter Controls */}
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider flex items-center gap-2">
                      <AlertOctagon className="w-4 h-4 text-red-600" />
                      15-Category Operational Revenue Leakage Radar
                    </h2>
                    <p className="text-xs text-[#6B6B6B] mt-1">
                      Identifies actionable revenue bottlenecks across SLA breaches, follow-up gaps, appointment no-shows, and stalled deals.
                    </p>
                  </div>

                  {/* Severity Filter Tabs */}
                  <div className="flex items-center gap-1 bg-[#FAF9F5] p-1 rounded-xl border border-[#D4D0C8] text-xs font-mono">
                    {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
                      <button
                        key={sev}
                        onClick={() => setLeakageSeverityFilter(sev)}
                        className={`px-3 py-1.5 rounded-lg transition-all ${
                          leakageSeverityFilter === sev
                            ? 'bg-[#1A1A1A] text-white font-bold'
                            : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                        }`}
                      >
                        {sev}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Leakage Metrics Summary Banner */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6 pt-6 border-t border-[#D4D0C8]">
                  <div className="p-3 bg-red-50/60 border border-red-200 rounded-xl">
                    <span className="text-[11px] font-mono text-red-800 uppercase block">Total Leakage Events</span>
                    <div className="text-2xl font-bold font-mono text-red-700 mt-1">
                      {leakage?.total_leakage_events ?? 0}
                    </div>
                  </div>
                  <div className="p-3 bg-amber-50/60 border border-amber-200 rounded-xl">
                    <span className="text-[11px] font-mono text-amber-800 uppercase block">Total Value At Risk</span>
                    <div className="text-2xl font-bold font-mono text-amber-700 mt-1">
                      {formatCurrency(leakage?.total_estimated_value_at_risk_estimate)}
                    </div>
                  </div>
                  <div className="p-3 bg-[#FAF9F5] border border-[#D4D0C8] rounded-xl">
                    <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Configured Staleness SLA</span>
                    <div className="text-2xl font-bold font-mono text-[#1A1A1A] mt-1">
                      {leakage?.staleness_threshold_days ?? 14} days
                    </div>
                  </div>
                </div>
              </div>

              {/* Leakage Items List */}
              <div className="space-y-3">
                {filteredLeakageItems.map((item, idx) => {
                  const isCrit = item.severity === 'CRITICAL';
                  const isHigh = item.severity === 'HIGH';
                  const isMed = item.severity === 'MEDIUM';
                  return (
                    <div
                      key={`${item.leakage_type}-${item.entity_id}-${idx}`}
                      className="bg-white border border-[#D4D0C8] rounded-xl p-4 shadow-sm hover:border-[#1A1A1A] transition flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                    >
                      <div className="space-y-1.5 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase ${
                              isCrit
                                ? 'bg-red-600 text-white'
                                : isHigh
                                ? 'bg-amber-500 text-white'
                                : isMed
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-400 text-white'
                            }`}
                          >
                            {item.severity}
                          </span>
                          <span className="font-mono font-bold text-xs text-[#1A1A1A]">
                            {item.leakage_type}
                          </span>
                          <span className="text-[11px] text-[#6B6B6B] font-mono">
                            {item.entity_type} #{item.entity_id.slice(0, 8)}
                          </span>
                          {item.age_days !== null && item.age_days !== undefined && (
                            <span className="text-[11px] bg-[#FAF9F5] px-2 py-0.5 rounded border border-[#D4D0C8] font-mono">
                              Age: {item.age_days}d
                            </span>
                          )}
                        </div>

                        <div className="text-xs text-[#4A4A4A] font-sans">
                          {item.recommended_next_action}
                        </div>

                        {/* Evidence snippets */}
                        {item.evidence && Object.keys(item.evidence).length > 0 && (
                          <div className="text-[11px] font-mono text-[#6B6B6B] bg-[#FAF9F5] px-2.5 py-1 rounded border border-[#D4D0C8]/60 inline-block">
                            Evidence:{' '}
                            {Object.entries(item.evidence)
                              .map(([k, v]) => `${k}: ${v}`)
                              .join(' | ')}
                          </div>
                        )}
                      </div>

                      <div className="flex md:flex-col items-end justify-between w-full md:w-auto gap-2 shrink-0 border-t md:border-t-0 pt-2 md:pt-0 border-[#D4D0C8]/50">
                        <div className="text-right">
                          <span className="text-[10px] font-mono text-[#6B6B6B] block uppercase">Value At Risk</span>
                          <span className="text-xs font-mono font-bold text-red-600">
                            {formatCurrency(item.estimated_impact_estimate)}
                          </span>
                        </div>
                        <button
                          onClick={() => {
                            if (item.entity_type === 'lead') {
                              window.location.href = `/dashboard/leads?id=${item.entity_id}`;
                            } else {
                              alert(`Action: ${item.recommended_next_action}`);
                            }
                          }}
                          className="px-3 py-1.5 bg-[#1A1A1A] text-white rounded-lg text-xs font-mono hover:bg-[#333] transition"
                        >
                          Resolve Action →
                        </button>
                      </div>
                    </div>
                  );
                })}

                {filteredLeakageItems.length === 0 && (
                  <div className="bg-white border border-[#D4D0C8] rounded-xl p-8 text-center text-[#6B6B6B] font-mono text-xs">
                    No active leakage detected for severity: {leakageSeverityFilter}. Funnel operations healthy!
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: SOURCE ATTRIBUTION */}
          {activeTab === 'attribution' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h2 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider">
                      Source Attribution &amp; Channel Quality
                    </h2>
                    <p className="text-xs text-[#6B6B6B] mt-0.5">
                      Attributed conversion outcomes without causal fabrication. Identifies high-ROI lead channels.
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <div className="bg-[#FAF9F5] px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
                      Top Lead Source:{' '}
                      <span className="font-bold text-[#1A1A1A]">
                        {attribution?.top_source_by_leads || 'UNKNOWN'}
                      </span>
                    </div>
                    <div className="bg-[#FAF9F5] px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
                      Highest Conversion:{' '}
                      <span className="font-bold text-[#0F766E]">
                        {attribution?.top_source_by_conversion || 'UNKNOWN'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Source Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase text-[11px]">
                        <th className="pb-3 font-semibold">Channel / Source</th>
                        <th className="pb-3 font-semibold">Lead Count</th>
                        <th className="pb-3 font-semibold">Converted Count</th>
                        <th className="pb-3 font-semibold">Conversion Rate</th>
                        <th className="pb-3 font-semibold">Attributed Pipeline Value (Estimate)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#D4D0C8]/50">
                      {(attribution?.by_source || []).map((s) => (
                        <tr key={s.source} className="hover:bg-[#FAF9F5] transition">
                          <td className="py-3 font-mono font-bold uppercase">{s.source}</td>
                          <td className="py-3 font-mono">{s.lead_count}</td>
                          <td className="py-3 font-mono text-[#0F766E] font-bold">{s.converted_count}</td>
                          <td className="py-3 font-mono">
                            {s.conversion_rate_pct !== null && s.conversion_rate_pct !== undefined
                              ? `${s.conversion_rate_pct}%`
                              : 'No Data'}
                          </td>
                          <td className="py-3 font-mono">{formatCurrency(s.estimated_revenue_estimate)}</td>
                        </tr>
                      ))}
                      {(!attribution?.by_source || attribution.by_source.length === 0) && (
                        <tr>
                          <td colSpan={5} className="py-6 text-center text-[#6B6B6B] font-mono">
                            No source attribution records found in this window.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: OUTCOMES & LEARNING LOOP */}
          {activeTab === 'outcomes' && (
            <div className="space-y-6">
              {/* Outcomes Summary Header */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
                  <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">True Win Rate</span>
                  <div className="text-2xl font-bold font-mono text-[#0F766E] mt-1">
                    {outcomes?.win_rate_pct !== null && outcomes?.win_rate_pct !== undefined
                      ? `${outcomes.win_rate_pct}%`
                      : 'No Data'}
                  </div>
                  <span className="text-[10px] text-[#6B6B6B] block mt-1">Based on explicit feedback</span>
                </div>

                <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
                  <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Positive Signals</span>
                  <div className="text-2xl font-bold font-mono text-[#1A1A1A] mt-1">
                    {outcomes?.positive_feedback_count ?? 0}
                  </div>
                  <span className="text-[10px] text-[#6B6B6B] block mt-1">Conversions &amp; wins</span>
                </div>

                <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
                  <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Completed Deals</span>
                  <div className="text-2xl font-bold font-mono text-[#1A1A1A] mt-1">
                    {outcomes?.completed_deals ?? 0}
                  </div>
                  <span className="text-[10px] text-[#6B6B6B] block mt-1">Verified deal transactions</span>
                </div>

                <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 shadow-sm">
                  <span className="text-[11px] font-mono text-[#6B6B6B] uppercase block">Avg Score At Win</span>
                  <div className="text-2xl font-bold font-mono text-[#1A1A1A] mt-1">
                    {outcomes?.avg_opportunity_score_at_win !== null && outcomes?.avg_opportunity_score_at_win !== undefined
                      ? outcomes.avg_opportunity_score_at_win.toFixed(1)
                      : 'N/A'}
                  </div>
                  <span className="text-[10px] text-[#6B6B6B] block mt-1">Autopilot priority score</span>
                </div>
              </div>

              {/* Outcome Distribution Grid */}
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <h3 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider mb-4">
                  Outcome Taxonomy Distribution
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
                  {(outcomes?.outcome_distribution || []).map((o) => (
                    <div key={o.outcome} className="bg-[#FAF9F5] border border-[#D4D0C8] rounded-xl p-3 text-center">
                      <span className="text-[10px] font-mono uppercase text-[#6B6B6B] block truncate" title={o.outcome}>
                        {o.outcome}
                      </span>
                      <div className="text-lg font-bold font-mono text-[#1A1A1A] mt-1">
                        {o.count}
                      </div>
                      <span className="text-[10px] font-mono text-[#0F766E] block">
                        {o.pct !== null && o.pct !== undefined ? `${o.pct}%` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Learning Loop Heuristics Table */}
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider">
                      Opportunity Action Effectiveness (Learning Loop)
                    </h3>
                    <p className="text-xs text-[#6B6B6B]">
                      Algorithm: <span className="font-mono font-semibold">{learningLoop?.computation_method}</span> (Heuristic aggregation without unverified ML models)
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase text-[11px]">
                        <th className="pb-3 font-semibold">Opportunity Type</th>
                        <th className="pb-3 font-semibold">Total Evaluated</th>
                        <th className="pb-3 font-semibold">Actioned Count</th>
                        <th className="pb-3 font-semibold">Action Rate</th>
                        <th className="pb-3 font-semibold">Positive Feedback Rate</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#D4D0C8]/50">
                      {(learningLoop?.top_opportunity_types || []).map((t) => (
                        <tr key={t.opportunity_type} className="hover:bg-[#FAF9F5] transition">
                          <td className="py-3 font-mono font-bold uppercase">{t.opportunity_type}</td>
                          <td className="py-3 font-mono">{t.total_count}</td>
                          <td className="py-3 font-mono">{t.actioned_count}</td>
                          <td className="py-3 font-mono">
                            {t.action_rate_pct !== null && t.action_rate_pct !== undefined ? `${t.action_rate_pct}%` : 'N/A'}
                          </td>
                          <td className="py-3 font-mono text-[#0F766E] font-bold">
                            {t.positive_feedback_rate_pct !== null && t.positive_feedback_rate_pct !== undefined
                              ? `${t.positive_feedback_rate_pct}%`
                              : 'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: DATA QUALITY PANEL */}
          {activeTab === 'quality' && (
            <div className="space-y-6">
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                  <div>
                    <h2 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-teal-700" />
                      Revenue Intelligence Data Quality &amp; Completeness Audit
                    </h2>
                    <p className="text-xs text-[#6B6B6B] mt-0.5">
                      Audits underlying entities for missing attribution, missing budgets, missing timestamps, and unrecorded visit outcomes.
                    </p>
                  </div>
                  <div className="text-xs font-mono bg-[#FAF9F5] px-4 py-2 rounded-xl border border-[#D4D0C8] flex items-center gap-3">
                    <span>Overall Data Health Score:</span>
                    <span className="text-base font-bold text-teal-700">
                      {dataQuality?.data_health_score_pct ?? 100}%
                    </span>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase text-[11px]">
                        <th className="pb-3 font-semibold">Audit Metric</th>
                        <th className="pb-3 font-semibold">Severity</th>
                        <th className="pb-3 font-semibold">Missing Records</th>
                        <th className="pb-3 font-semibold">Total Audited</th>
                        <th className="pb-3 font-semibold">Completeness Coverage</th>
                        <th className="pb-3 font-semibold">Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#D4D0C8]/50">
                      {(dataQuality?.issues || []).map((issue) => (
                        <tr key={issue.metric} className="hover:bg-[#FAF9F5] transition">
                          <td className="py-3 font-mono font-bold">{issue.metric}</td>
                          <td className="py-3 font-mono">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                issue.severity === 'CRITICAL'
                                  ? 'bg-red-100 text-red-700'
                                  : issue.severity === 'HIGH'
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-gray-100 text-gray-700'
                              }`}
                            >
                              {issue.severity}
                            </span>
                          </td>
                          <td className="py-3 font-mono text-red-600 font-bold">{issue.missing_count}</td>
                          <td className="py-3 font-mono">{issue.total_count}</td>
                          <td className="py-3 font-mono">
                            {issue.coverage_pct !== null && issue.coverage_pct !== undefined ? (
                              <div className="flex items-center gap-2">
                                <div className="w-16 bg-gray-200 h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className="bg-teal-600 h-full"
                                    style={{ width: `${Math.min(100, Math.max(0, issue.coverage_pct))}%` }}
                                  />
                                </div>
                                <span>{issue.coverage_pct}%</span>
                              </div>
                            ) : (
                              'N/A'
                            )}
                          </td>
                          <td className="py-3 text-[#6B6B6B]">{issue.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: TEAM INTELLIGENCE & LEAD REVENUE JOURNEYS */}
          {activeTab === 'team' && (
            <div className="space-y-6">
              {/* Team Performance Table */}
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <h2 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider mb-2">
                  Team Operational Performance &amp; Funnel Throughput
                </h2>
                <p className="text-xs text-[#6B6B6B] mb-6">
                  Objective operational metrics per agent without subjective ranking labels.
                </p>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase text-[11px]">
                        <th className="pb-3 font-semibold">Agent / Broker</th>
                        <th className="pb-3 font-semibold">Assigned Leads</th>
                        <th className="pb-3 font-semibold">Contacted</th>
                        <th className="pb-3 font-semibold">Qualified</th>
                        <th className="pb-3 font-semibold">Appointments</th>
                        <th className="pb-3 font-semibold">Site Visits</th>
                        <th className="pb-3 font-semibold">Active Opportunities</th>
                        <th className="pb-3 font-semibold">Closed Deals</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#D4D0C8]/50">
                      {(team?.agents || []).map((agent) => (
                        <tr key={agent.broker_id} className="hover:bg-[#FAF9F5] transition">
                          <td className="py-3 font-mono font-bold">
                            {agent.name}
                            <span className="text-[10px] text-[#6B6B6B] block">{agent.email}</span>
                          </td>
                          <td className="py-3 font-mono">{agent.assigned_leads}</td>
                          <td className="py-3 font-mono">{agent.contacted_leads}</td>
                          <td className="py-3 font-mono">{agent.qualified_leads}</td>
                          <td className="py-3 font-mono">{agent.scheduled_appointments}</td>
                          <td className="py-3 font-mono">{agent.completed_site_visits}</td>
                          <td className="py-3 font-mono">{agent.active_opportunities}</td>
                          <td className="py-3 font-mono text-[#0F766E] font-bold">{agent.closed_deals}</td>
                        </tr>
                      ))}
                      {(!team?.agents || team.agents.length === 0) && (
                        <tr>
                          <td colSpan={8} className="py-6 text-center text-[#6B6B6B] font-mono">
                            No team operational records found.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Lead Revenue Journey Inspector */}
              <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                  <div>
                    <h3 className="text-sm font-mono font-bold text-[#1A1A1A] uppercase tracking-wider">
                      Lead Revenue Journey Inspector
                    </h3>
                    <p className="text-xs text-[#6B6B6B] mt-0.5">
                      Reconstruct the unified chronological revenue journey from lead creation through qualification, visits, and deals.
                    </p>
                  </div>
                </div>

                <form onSubmit={handleFetchLeadJourney} className="flex gap-2 max-w-lg mb-6">
                  <input
                    type="text"
                    value={searchLeadId}
                    onChange={(e) => setSearchLeadId(e.target.value)}
                    placeholder="Enter Lead UUID (e.g. 123e4567-e89b-12d3...)"
                    className="flex-1 bg-[#FAF9F5] border border-[#D4D0C8] rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-[#1A1A1A]"
                  />
                  <button
                    type="submit"
                    disabled={journeyLoading || !searchLeadId.trim()}
                    className="px-4 py-2 bg-[#1A1A1A] text-white rounded-xl text-xs font-mono font-bold hover:bg-[#333] transition disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <Search className="w-3.5 h-3.5" />
                    <span>{journeyLoading ? 'Inspecting...' : 'Inspect'}</span>
                  </button>
                </form>

                {journeyError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-mono mb-4">
                    {journeyError}
                  </div>
                )}

                {leadJourney && (
                  <div className="space-y-4 pt-4 border-t border-[#D4D0C8]">
                    <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-[#FAF9F5] rounded-xl border border-[#D4D0C8] text-xs font-mono">
                      <div>
                        <span className="text-[#6B6B6B]">Lead:</span>{' '}
                        <span className="font-bold text-[#1A1A1A]">{leadJourney.lead_name || 'Unnamed Lead'}</span>{' '}
                        <span className="text-[11px] text-[#6B6B6B]">({leadJourney.lead_id})</span>
                      </div>
                      <div className="flex gap-3">
                        <span>Source: <strong className="text-[#1A1A1A]">{leadJourney.source || 'UNKNOWN'}</strong></span>
                        <span>Stage: <strong className="text-[#1A1A1A]">{leadJourney.pipeline_stage}</strong></span>
                        <span>Budget: <strong className="text-[#1A1A1A]">{formatCurrency(leadJourney.budget_max)}</strong></span>
                      </div>
                    </div>

                    {/* Timeline */}
                    <div className="space-y-3 relative pl-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#D4D0C8]">
                      {leadJourney.journey.map((ev, i) => (
                        <div key={ev.event_id || i} className="relative group">
                          <div className="absolute -left-6 top-1.5 w-3.5 h-3.5 bg-white border-2 border-[#1A1A1A] rounded-full" />
                          <div className="bg-[#FAF9F5] border border-[#D4D0C8] rounded-xl p-3 text-xs space-y-1">
                            <div className="flex items-center justify-between text-[11px] font-mono text-[#6B6B6B]">
                              <span>{new Date(ev.occurred_at).toLocaleString()}</span>
                              <span className="bg-[#EAE6DF] px-2 py-0.5 rounded font-bold text-[#1A1A1A]">
                                {ev.actor_type}
                              </span>
                            </div>
                            <div className="font-mono font-bold text-[#1A1A1A]">{ev.title}</div>
                            {ev.description && <div className="text-[#4A4A4A]">{ev.description}</div>}
                          </div>
                        </div>
                      ))}
                      {leadJourney.journey.length === 0 && (
                        <div className="text-xs text-[#6B6B6B] font-mono">No journey events recorded.</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
