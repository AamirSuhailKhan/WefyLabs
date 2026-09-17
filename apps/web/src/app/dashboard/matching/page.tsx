'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles, Search, CheckCircle2, AlertTriangle, ArrowRight,
  TrendingUp, Users, Building2, Layers, Filter, RefreshCw,
  Sliders, Eye, Bookmark, Share2, Calendar, ThumbsUp, ShieldCheck
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { formatCurrencyINR } from '@/lib/utils';
import { api } from '@/lib/api-client';

export default function MatchingDashboardPage() {
  const [activeTab, setActiveTab] = useState<'lead_to_prop' | 'prop_to_lead' | 'supply_gaps'>('lead_to_prop');
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(true);

  // Tab 1: Lead → Property Matching
  const [leadIdInput, setLeadIdInput] = useState('');
  const [allowAlternatives, setAllowAlternatives] = useState(false);
  const [leadMatches, setLeadMatches] = useState<any>(null);
  const [isLoadingLeadMatches, setIsLoadingLeadMatches] = useState(false);
  const [leadMatchError, setLeadMatchError] = useState<string | null>(null);

  // Tab 2: Property → Leads Reverse Matching
  const [propertyIdInput, setPropertyIdInput] = useState('');
  const [propertyMatches, setPropertyMatches] = useState<any[]>([]);
  const [isLoadingPropMatches, setIsLoadingPropMatches] = useState(false);
  const [propMatchError, setPropMatchError] = useState<string | null>(null);

  // Score breakdown modal
  const [selectedItemForModal, setSelectedItemForModal] = useState<any>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  const fetchDashboardMetrics = async () => {
    setIsLoadingDashboard(true);
    try {
      const data = await api.matching.getDashboard();
      setDashboardData(data);
    } catch (err: any) {
      console.warn('Could not load matching dashboard metrics', err);
    } finally {
      setIsLoadingDashboard(false);
    }
  };

  useEffect(() => {
    fetchDashboardMetrics();
  }, []);

  const handleRunLeadMatch = async (e?: React.FormEvent, customLeadId?: string) => {
    if (e) e.preventDefault();
    const targetLeadId = customLeadId || leadIdInput.trim();
    if (!targetLeadId) return;

    if (customLeadId) {
      setLeadIdInput(customLeadId);
      setActiveTab('lead_to_prop');
    }

    setIsLoadingLeadMatches(true);
    setLeadMatchError(null);
    try {
      const res = await api.matching.getLeadMatches(targetLeadId, 5, allowAlternatives);
      setLeadMatches(res);
    } catch (err: any) {
      setLeadMatchError(err?.message || 'Failed to retrieve matches for lead');
      setLeadMatches(null);
    } finally {
      setIsLoadingLeadMatches(false);
    }
  };

  const handleRunPropMatch = async (e?: React.FormEvent, customPropId?: string) => {
    if (e) e.preventDefault();
    const targetPropId = customPropId || propertyIdInput.trim();
    if (!targetPropId) return;

    if (customPropId) {
      setPropertyIdInput(targetPropId);
      setActiveTab('prop_to_lead');
    }

    setIsLoadingPropMatches(true);
    setPropMatchError(null);
    try {
      const res = await api.matching.getPropertyLeadMatches(targetPropId, 10);
      setPropertyMatches(res || []);
    } catch (err: any) {
      setPropMatchError(err?.message || 'Failed to retrieve matching buyer leads');
      setPropertyMatches([]);
    } finally {
      setIsLoadingPropMatches(false);
    }
  };

  const handleShortlist = async (propId: string, leadId: string) => {
    try {
      await api.matching.shortlistMatch({
        lead_id: leadId,
        property_id: propId,
        notes: 'Shortlisted from AI Matching Workspace',
        interest_level: 'high'
      });
      setActionSuccessMessage('Property successfully shortlisted for lead!');
      setTimeout(() => setActionSuccessMessage(null), 4000);
      fetchDashboardMetrics();
    } catch (err: any) {
      alert(err?.message || 'Could not shortlist property');
    }
  };

  const handleRecommend = async (propId: string, leadId: string) => {
    try {
      await api.matching.recommendMatch({
        lead_id: leadId,
        property_id: propId,
        notes: 'Recommended via AI Matching Engine',
        create_followup_task: true
      });
      setActionSuccessMessage('Recommendation recorded! Follow-up task scheduled.');
      setTimeout(() => setActionSuccessMessage(null), 4000);
      fetchDashboardMetrics();
    } catch (err: any) {
      alert(err?.message || 'Could not record recommendation');
    }
  };

  return (
    <div className="min-h-screen bg-dark-bg text-slate-100 flex flex-col">
      <DashboardNav />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <Sparkles className="w-3 h-3" /> Part 29 Native Engine
              </span>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Zero Fabrication
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
              AI Lead ↔ Property Matching
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl">
              Deterministic hard constraint filtering, 8-dimensional explainable scoring, and dual-direction candidate recommendation.
            </p>
          </div>

          <button
            onClick={fetchDashboardMetrics}
            disabled={isLoadingDashboard}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-dark-card border border-dark-border text-slate-300 hover:text-white hover:border-slate-600 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingDashboard ? 'animate-spin' : ''}`} />
            <span>Refresh Analytics</span>
          </button>
        </div>

        {/* Action feedback alert */}
        {actionSuccessMessage && (
          <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{actionSuccessMessage}</span>
          </div>
        )}

        {/* Top KPI Summary Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-dark-card border border-dark-border">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Leads Needing Matches</span>
              <Users className="w-4 h-4 text-amber-400" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-black text-amber-400">
                {dashboardData?.leads_needing_matches_count ?? 0}
              </span>
              <span className="text-[10px] text-slate-500">Unmatched Hot Leads</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-dark-card border border-dark-border">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Available Properties</span>
              <Building2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-black text-emerald-400">
                {dashboardData?.total_inventory_count ?? 0}
              </span>
              <span className="text-[10px] text-slate-500">Active Inventory</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-dark-card border border-dark-border">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Total Active Leads</span>
              <TrendingUp className="w-4 h-4 text-blue-400" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-black text-blue-400">
                {dashboardData?.total_leads_count ?? 0}
              </span>
              <span className="text-[10px] text-slate-500">In Tenant CRM</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-dark-card border border-dark-border">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Supply Gaps Detected</span>
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-black text-rose-400">
                {dashboardData?.supply_gaps?.length ?? 0}
              </span>
              <span className="text-[10px] text-slate-500">High Demand Localities</span>
            </div>
          </div>
        </div>

        {/* Mode Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-dark-border pb-2">
          <button
            onClick={() => setActiveTab('lead_to_prop')}
            className={`px-4 py-2 text-xs font-bold rounded-lg transition flex items-center gap-2 ${
              activeTab === 'lead_to_prop'
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Lead → Properties</span>
          </button>

          <button
            onClick={() => setActiveTab('prop_to_lead')}
            className={`px-4 py-2 text-xs font-bold rounded-lg transition flex items-center gap-2 ${
              activeTab === 'prop_to_lead'
                ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Building2 className="w-3.5 h-3.5" />
            <span>Property → Leads (Reverse)</span>
          </button>

          <button
            onClick={() => setActiveTab('supply_gaps')}
            className={`px-4 py-2 text-xs font-bold rounded-lg transition flex items-center gap-2 ${
              activeTab === 'supply_gaps'
                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Demand vs Inventory Supply Gaps</span>
          </button>
        </div>

        {/* TAB 1: Lead → Properties */}
        {activeTab === 'lead_to_prop' && (
          <div className="space-y-6">
            <form onSubmit={handleRunLeadMatch} className="p-6 rounded-2xl bg-dark-card border border-dark-border space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Search className="w-4 h-4 text-emerald-400" />
                Find Best Properties for Lead
              </h2>

              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <input
                    type="text"
                    value={leadIdInput}
                    onChange={(e) => setLeadIdInput(e.target.value)}
                    placeholder="Enter Lead UUID (or select an unmatched hot lead below)..."
                    className="w-full px-3.5 py-2 text-xs rounded-lg bg-dark-bg border border-dark-border text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={allowAlternatives}
                      onChange={(e) => setAllowAlternatives(e.target.checked)}
                      className="rounded bg-dark-bg border-dark-border text-emerald-500 focus:ring-0"
                    />
                    <span>Allow Soft Alternatives (+20% budget, nearby areas)</span>
                  </label>

                  <button
                    type="submit"
                    disabled={isLoadingLeadMatches || !leadIdInput.trim()}
                    className="px-4 py-2 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50 transition flex items-center gap-1.5"
                  >
                    {isLoadingLeadMatches ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>Rank Candidates</span>
                  </button>
                </div>
              </div>

              {/* Unmatched hot leads quick links */}
              {dashboardData?.unmatched_hot_leads?.length > 0 && (
                <div className="pt-2 border-t border-dark-border/50">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                    Quick Pick — Unmatched Hot Leads:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {dashboardData.unmatched_hot_leads.map((hl: any) => (
                      <button
                        key={hl.lead_id}
                        type="button"
                        onClick={() => handleRunLeadMatch(undefined, hl.lead_id)}
                        className="px-2.5 py-1 text-[11px] rounded bg-dark-bg border border-dark-border text-slate-300 hover:text-emerald-400 hover:border-emerald-500/40 transition"
                      >
                        {hl.name} ({hl.property_type || 'Any'}, ₹{hl.budget ? formatCurrencyINR(hl.budget) : 'Unstated'})
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </form>

            {leadMatchError && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                {leadMatchError}
              </div>
            )}

            {/* Results Display */}
            {leadMatches && (
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>
                    Evaluated <strong className="text-white">{leadMatches.total_candidates_retrieved}</strong> inventory properties.
                    Filtered <strong className="text-rose-400">{leadMatches.filtered_candidates_count}</strong> via hard constraints.
                  </span>
                  <span className="text-[10px] bg-dark-card px-2 py-0.5 rounded border border-dark-border">
                    Time: {leadMatches.execution_duration_ms}ms
                  </span>
                </div>

                {leadMatches.items.length === 0 ? (
                  <div className="p-12 text-center rounded-2xl bg-dark-card border border-dark-border">
                    <Building2 className="w-8 h-8 text-slate-600 mx-auto mb-3" />
                    <h3 className="text-sm font-bold text-white">No Matching Properties Found</h3>
                    <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                      All properties were filtered out by hard constraints. Try enabling "Allow Soft Alternatives" to expand budget and location radius.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {leadMatches.items.map((item: any) => (
                      <div
                        key={item.property_id}
                        className="p-5 rounded-2xl bg-dark-card border border-dark-border hover:border-slate-700 transition flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <div>
                              <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-dark-bg border border-dark-border text-slate-400 mr-2">
                                #{item.rank_position} {item.recommendation_type.replace('_', ' ')}
                              </span>
                              <h3 className="text-sm font-bold text-white mt-1">{item.title}</h3>
                              <p className="text-xs text-slate-400">
                                {item.locality ? `${item.locality}, ` : ''}{item.city} • {item.bedrooms} BHK • {item.built_up_area_sqft} sq ft
                              </p>
                            </div>

                            <div className="text-right shrink-0">
                              <div className="text-lg font-black text-emerald-400">
                                {item.match_score}%
                              </div>
                              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase ${
                                item.confidence >= 0.8
                                  ? 'bg-emerald-500/10 text-emerald-400'
                                  : item.confidence >= 0.5
                                  ? 'bg-amber-500/10 text-amber-400'
                                  : 'bg-rose-500/10 text-rose-400'
                              }`}>
                                {item.confidence >= 0.8 ? 'High Conf' : item.confidence >= 0.5 ? 'Med Conf' : 'Low Conf'}
                              </span>
                            </div>
                          </div>

                          <div className="text-base font-extrabold text-white mb-3">
                            ₹{formatCurrencyINR(item.price)}
                          </div>

                          {/* Reasons list */}
                          <div className="space-y-1 mb-3">
                            {item.why_matches?.slice(0, 3).map((r: string, i: number) => (
                              <div key={i} className="text-[11px] text-emerald-400 flex items-center gap-1.5">
                                <CheckCircle2 className="w-3 h-3 shrink-0" />
                                <span className="truncate">{r}</span>
                              </div>
                            ))}
                            {item.trade_offs?.slice(0, 2).map((t: string, i: number) => (
                              <div key={i} className="text-[11px] text-amber-400 flex items-center gap-1.5">
                                <AlertTriangle className="w-3 h-3 shrink-0" />
                                <span className="truncate">{t}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div className="pt-3 border-t border-dark-border flex items-center justify-between gap-2 mt-2">
                          <button
                            onClick={() => setSelectedItemForModal(item)}
                            className="text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>Why This Match?</span>
                          </button>

                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleShortlist(item.property_id, leadIdInput)}
                              className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-dark-bg border border-dark-border hover:border-emerald-500 text-slate-200 hover:text-emerald-400 transition"
                            >
                              Shortlist
                            </button>
                            <button
                              onClick={() => handleRecommend(item.property_id, leadIdInput)}
                              className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition"
                            >
                              Recommend
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Property → Leads (Reverse Matching) */}
        {activeTab === 'prop_to_lead' && (
          <div className="space-y-6">
            <form onSubmit={handleRunPropMatch} className="p-6 rounded-2xl bg-dark-card border border-dark-border space-y-4">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Search className="w-4 h-4 text-blue-400" />
                Reverse Match: Find Qualified Buyer Leads for Property
              </h2>

              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <input
                    type="text"
                    value={propertyIdInput}
                    onChange={(e) => setPropertyIdInput(e.target.value)}
                    placeholder="Enter Property UUID..."
                    className="w-full px-3.5 py-2 text-xs rounded-lg bg-dark-bg border border-dark-border text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoadingPropMatches || !propertyIdInput.trim()}
                  className="px-4 py-2 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition flex items-center gap-1.5"
                >
                  {isLoadingPropMatches ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  <span>Find Buyers</span>
                </button>
              </div>

              {/* Quick links to high demand properties */}
              {dashboardData?.high_demand_properties?.length > 0 && (
                <div className="pt-2 border-t border-dark-border/50">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">
                    Quick Pick — Active Properties:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {dashboardData.high_demand_properties.map((p: any) => (
                      <button
                        key={p.property_id}
                        type="button"
                        onClick={() => handleRunPropMatch(undefined, p.property_id)}
                        className="px-2.5 py-1 text-[11px] rounded bg-dark-bg border border-dark-border text-slate-300 hover:text-blue-400 hover:border-blue-500/40 transition"
                      >
                        {p.property_title} (₹{formatCurrencyINR(p.price)})
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </form>

            {propMatchError && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                {propMatchError}
              </div>
            )}

            {/* Leads Table */}
            {propertyMatches.length > 0 && (
              <div className="rounded-2xl bg-dark-card border border-dark-border overflow-hidden">
                <div className="px-6 py-4 border-b border-dark-border flex items-center justify-between">
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    Top {propertyMatches.length} Compatible Buyer Leads
                  </h3>
                  <span className="text-[10px] text-slate-400">Strictly Tenant Scoped</span>
                </div>

                <div className="divide-y divide-dark-border/60">
                  {propertyMatches.map((leadItem: any) => (
                    <div key={leadItem.lead_id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-dark-bg/40 transition">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-bold text-white">{leadItem.name}</h4>
                          <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded ${
                            leadItem.lead_tier === 'hot'
                              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          }`}>
                            {leadItem.lead_tier}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5">{leadItem.phone} • {leadItem.notes}</p>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {leadItem.reasons?.map((r: string, idx: number) => (
                            <span key={idx} className="text-[10px] text-emerald-400 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> {r}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="flex items-center gap-4 shrink-0">
                        <div className="text-right">
                          <div className="text-base font-black text-blue-400">{leadItem.match_score}%</div>
                          <span className="text-[10px] text-slate-500">Compatibility</span>
                        </div>

                        <button
                          onClick={() => handleRecommend(propertyIdInput, leadItem.lead_id)}
                          className="px-3 py-1.5 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition"
                        >
                          Recommend
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: Demand vs Inventory Supply Gaps */}
        {activeTab === 'supply_gaps' && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-dark-card border border-dark-border">
              <h2 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
                <Layers className="w-4 h-4 text-amber-400" />
                High Demand vs Low Inventory Localities
              </h2>
              <p className="text-xs text-slate-400 mb-6 max-w-xl">
                Real-time analysis of your active lead requirements compared against current available listings.
              </p>

              {(!dashboardData?.supply_gaps || dashboardData.supply_gaps.length === 0) ? (
                <p className="text-xs text-slate-500 py-8 text-center">No acute supply gaps detected in your active inventory.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-dark-border text-slate-400 font-semibold uppercase text-[10px]">
                        <th className="pb-3">Locality</th>
                        <th className="pb-3">Active Buyer Demand</th>
                        <th className="pb-3">Available Properties</th>
                        <th className="pb-3">Inventory Gap</th>
                        <th className="pb-3">Severity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-border/40">
                      {dashboardData.supply_gaps.map((gap: any, i: number) => (
                        <tr key={i} className="hover:bg-dark-bg/30">
                          <td className="py-3 font-bold text-white">{gap.locality}</td>
                          <td className="py-3 text-slate-300">{gap.active_leads_demand} Leads</td>
                          <td className="py-3 text-slate-300">{gap.available_inventory} Units</td>
                          <td className="py-3 font-bold text-rose-400">+{gap.gap} Units Needed</td>
                          <td className="py-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                              gap.severity === 'HIGH' ? 'bg-rose-500/10 text-rose-400' : 'bg-amber-500/10 text-amber-400'
                            }`}>
                              {gap.severity}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Explainability / Score Breakdown Modal */}
        {selectedItemForModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="max-w-lg w-full rounded-2xl bg-dark-card border border-dark-border p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-dark-border pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                  Why This Property Matches ({selectedItemForModal.match_score}%)
                </h3>
                <button
                  onClick={() => setSelectedItemForModal(null)}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <h4 className="font-bold text-white">{selectedItemForModal.title}</h4>
                  <p className="text-slate-400">
                    {selectedItemForModal.locality}, {selectedItemForModal.city} • ₹{formatCurrencyINR(selectedItemForModal.price)}
                  </p>
                </div>

                {/* Granular Component Scores */}
                {selectedItemForModal.score_breakdown && (
                  <div className="p-3.5 rounded-xl bg-dark-bg border border-dark-border space-y-2">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      Component Breakdown:
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div>Budget Fit: <strong className="text-white">{selectedItemForModal.score_breakdown.budget_fit}%</strong></div>
                      <div>Location Fit: <strong className="text-white">{selectedItemForModal.score_breakdown.location_fit}%</strong></div>
                      <div>Property Type: <strong className="text-white">{selectedItemForModal.score_breakdown.property_fit}%</strong></div>
                      <div>Bedrooms Fit: <strong className="text-white">{selectedItemForModal.score_breakdown.timeline_fit}%</strong></div>
                      <div>Amenities Fit: <strong className="text-white">{selectedItemForModal.score_breakdown.preference_fit}%</strong></div>
                      <div>Layout Area: <strong className="text-white">{selectedItemForModal.score_breakdown.investment_fit}%</strong></div>
                    </div>
                  </div>
                )}

                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Grounded Rationale:
                  </span>
                  <ul className="space-y-1">
                    {selectedItemForModal.why_matches?.map((r: string, idx: number) => (
                      <li key={idx} className="text-emerald-400 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {selectedItemForModal.trade_offs?.length > 0 && (
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                      Potential Mismatches / Trade-offs:
                    </span>
                    <ul className="space-y-1">
                      {selectedItemForModal.trade_offs.map((t: string, idx: number) => (
                        <li key={idx} className="text-amber-400 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                          <span>{t}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-dark-border flex justify-end">
                <button
                  onClick={() => setSelectedItemForModal(null)}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-dark-bg border border-dark-border text-white hover:border-slate-600"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
