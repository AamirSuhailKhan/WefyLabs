'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles, Search, CheckCircle2, AlertTriangle, ArrowRight,
  TrendingUp, Users, Building2, Layers, Filter, RefreshCw,
  Eye, Check, ShieldCheck, Clock, ArrowUpRight, ChevronRight,
  DollarSign, MapPin, BedDouble, Maximize2
} from 'lucide-react';
import { formatCurrencyINR } from '@/lib/utils';
import { api } from '@/lib/api-client';
import { PageContainer, PageHeader, Card, CardHeader, CardTitle, CardDescription, CardContent, Button } from '@/components/ui';

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
    <PageContainer maxWidth="xl">
      {/* Header */}
      <PageHeader
        title="AI Lead ↔ Property Matching"
        description="Deterministic hard constraint filtering, 8-dimensional explainable scoring, and dual-direction candidate recommendation. Zero hallucinations."
        badge={
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-emerald-600" /> Grounded Engine
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-blue-50 text-blue-800 border border-blue-200 flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-blue-600" /> Zero Fabrication
            </span>
          </div>
        }
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchDashboardMetrics}
            isLoading={isLoadingDashboard}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh Metrics
          </Button>
        }
      />

      {/* Action feedback alert */}
      {actionSuccessMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center gap-2 shadow-xs">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{actionSuccessMessage}</span>
        </div>
      )}

      {/* Top KPI Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6B6B6B]">Leads Needing Matches</span>
            <Users className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[#1A1A1A]">
              {dashboardData?.leads_needing_matches_count ?? 0}
            </span>
            <span className="text-[10px] text-[#6B6B6B]">Unmatched Hot</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6B6B6B]">Available Properties</span>
            <Building2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[#1A1A1A]">
              {dashboardData?.total_inventory_count ?? 0}
            </span>
            <span className="text-[10px] text-[#6B6B6B]">Active Units</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6B6B6B]">Total Active Leads</span>
            <TrendingUp className="w-4 h-4 text-blue-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[#1A1A1A]">
              {dashboardData?.total_leads_count ?? 0}
            </span>
            <span className="text-[10px] text-[#6B6B6B]">In CRM</span>
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#6B6B6B]">Supply Gaps Detected</span>
            <AlertTriangle className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-[#1A1A1A]">
              {dashboardData?.supply_gaps?.length ?? 0}
            </span>
            <span className="text-[10px] text-[#6B6B6B]">Localities</span>
          </div>
        </div>
      </div>

      {/* Mode Navigation Tabs */}
      <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] w-fit flex-wrap">
        <button
          onClick={() => setActiveTab('lead_to_prop')}
          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
            activeTab === 'lead_to_prop'
              ? 'bg-[#1A1A1A] text-white shadow-xs'
              : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          <span>Lead → Properties</span>
        </button>

        <button
          onClick={() => setActiveTab('prop_to_lead')}
          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
            activeTab === 'prop_to_lead'
              ? 'bg-[#1A1A1A] text-white shadow-xs'
              : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]'
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          <span>Property → Leads (Reverse)</span>
        </button>

        <button
          onClick={() => setActiveTab('supply_gaps')}
          className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
            activeTab === 'supply_gaps'
              ? 'bg-[#1A1A1A] text-white shadow-xs'
              : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Demand vs Supply Gaps</span>
        </button>
      </div>

      {/* TAB 1: Lead → Properties */}
      {activeTab === 'lead_to_prop' && (
        <div className="space-y-6">
          <form onSubmit={handleRunLeadMatch} className="p-5 sm:p-6 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] space-y-4 shadow-xs">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#1A1A1A] font-mono flex items-center gap-2">
                <Search className="w-4 h-4 text-emerald-600" />
                <span>Search & Rank Best Properties for Lead</span>
              </h2>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <input
                  type="text"
                  value={leadIdInput}
                  onChange={(e) => setLeadIdInput(e.target.value)}
                  placeholder="Enter Lead ID (or select an unmatched hot lead below)..."
                  className="w-full px-3.5 py-2.5 text-xs rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] placeholder-[#9CA3AF] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A]"
                />
              </div>

              <div className="flex items-center gap-3 flex-wrap">
                <label className="flex items-center gap-2 text-xs text-[#4A4A4A] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={allowAlternatives}
                    onChange={(e) => setAllowAlternatives(e.target.checked)}
                    className="rounded border-[#D4D0C8] text-[#1A1A1A] focus:ring-0"
                  />
                  <span>Allow Soft Alternatives (+20% budget, nearby)</span>
                </label>

                <Button
                  type="submit"
                  variant="lime"
                  size="sm"
                  disabled={isLoadingLeadMatches || !leadIdInput.trim()}
                  isLoading={isLoadingLeadMatches}
                  leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                >
                  Rank Candidates
                </Button>
              </div>
            </div>

            {/* Unmatched hot leads quick links */}
            {dashboardData?.unmatched_hot_leads?.length > 0 && (
              <div className="pt-3 border-t border-[#E5E1DA]">
                <span className="text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider block mb-2">
                  Quick Pick — Unmatched Hot Leads:
                </span>
                <div className="flex flex-wrap gap-2">
                  {dashboardData.unmatched_hot_leads.map((hl: any) => (
                    <button
                      key={hl.lead_id}
                      type="button"
                      onClick={() => handleRunLeadMatch(undefined, hl.lead_id)}
                      className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-white border border-[#D4D0C8] text-[#1A1A1A] hover:bg-[#E8F5A8] hover:border-[#1A1A1A] transition-all cursor-pointer shadow-2xs"
                    >
                      {hl.name} ({hl.property_type || 'Any'}, ₹{hl.budget ? formatCurrencyINR(hl.budget) : 'Unstated'})
                    </button>
                  ))}
                </div>
              </div>
            )}
          </form>

          {leadMatchError && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
              {leadMatchError}
            </div>
          )}

          {/* Results Display or High-Density Empty State */}
          {!leadMatches && !isLoadingLeadMatches && (
            <div className="p-8 sm:p-10 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs space-y-6">
              <div className="max-w-2xl mx-auto text-center space-y-2">
                <div className="w-12 h-12 rounded-2xl bg-[#E8F5A8] border border-[#D4D0C8] flex items-center justify-center mx-auto text-[#1A1A1A] shadow-xs">
                  <Sparkles className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-[#1A1A1A] font-mono">
                  Autonomous Multi-Factor Matching Pipeline
                </h3>
                <p className="text-xs text-[#6B6B6B] font-sans leading-relaxed">
                  Select a lead from the quick pick bar above or enter a Lead ID to execute deterministic scoring across active real estate inventory.
                </p>
              </div>

              {/* Explainable Pipeline Diagram */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-[#E5E1DA]">
                <div className="p-4 rounded-xl bg-white border border-[#D4D0C8] shadow-2xs space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold font-mono text-[#1A1A1A]">
                    <span className="w-5 h-5 rounded-full bg-[#1A1A1A] text-white flex items-center justify-center text-[10px]">1</span>
                    <span>Hard Constraints</span>
                  </div>
                  <p className="text-[11px] text-[#6B6B6B] leading-relaxed">
                    Strictest validation: filters out properties outside buyer budget, incorrect property types, or incompatible locations.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-white border border-[#D4D0C8] shadow-2xs space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold font-mono text-[#1A1A1A]">
                    <span className="w-5 h-5 rounded-full bg-[#1A1A1A] text-white flex items-center justify-center text-[10px]">2</span>
                    <span>8-D Compatibility</span>
                  </div>
                  <p className="text-[11px] text-[#6B6B6B] leading-relaxed">
                    Scores remaining inventory across budget fit, locality radius, layout area, timelines, and amenity preferences.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-white border border-[#D4D0C8] shadow-2xs space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold font-mono text-[#1A1A1A]">
                    <span className="w-5 h-5 rounded-full bg-[#1A1A1A] text-white flex items-center justify-center text-[10px]">3</span>
                    <span>Action Verification</span>
                  </div>
                  <p className="text-[11px] text-[#6B6B6B] leading-relaxed">
                    Brokers review transparent match rationales and shortlist or recommend with automatic task scheduling.
                  </p>
                </div>
              </div>
            </div>
          )}

          {leadMatches && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-[#6B6B6B] flex-wrap gap-2">
                <span>
                  Evaluated <strong className="text-[#1A1A1A]">{leadMatches.total_candidates_retrieved}</strong> inventory properties.
                  Filtered <strong className="text-rose-600">{leadMatches.filtered_candidates_count}</strong> via hard constraints.
                </span>
                <span className="text-[10px] font-mono bg-[#FAF7F2] px-2.5 py-1 rounded-lg border border-[#D4D0C8] text-[#1A1A1A]">
                  Execution: {leadMatches.execution_duration_ms}ms
                </span>
              </div>

              {leadMatches.items.length === 0 ? (
                <div className="p-12 text-center rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
                  <Building2 className="w-8 h-8 text-[#9CA3AF] mx-auto mb-3" />
                  <h3 className="text-sm font-bold text-[#1A1A1A] font-mono">No Matching Properties Found</h3>
                  <p className="text-xs text-[#6B6B6B] mt-1 max-w-md mx-auto">
                    All properties were filtered out by hard constraints. Try enabling &quot;Allow Soft Alternatives&quot; to expand budget and location radius.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {leadMatches.items.map((item: any) => (
                    <div
                      key={item.property_id}
                      className="p-5 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all flex flex-col justify-between shadow-xs"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div>
                            <span className="text-[10px] font-bold font-mono uppercase px-2 py-0.5 rounded bg-white border border-[#D4D0C8] text-[#6B6B6B] mr-2">
                              #{item.rank_position} {item.recommendation_type.replace('_', ' ')}
                            </span>
                            <h3 className="text-sm font-bold text-[#1A1A1A] mt-1 font-mono">{item.title}</h3>
                            <p className="text-xs text-[#6B6B6B] flex items-center gap-1.5 mt-0.5">
                              <MapPin className="w-3 h-3 text-[#9CA3AF]" />
                              <span>{item.locality ? `${item.locality}, ` : ''}{item.city}</span>
                              <span>•</span>
                              <span>{item.bedrooms} BHK</span>
                              <span>•</span>
                              <span>{item.built_up_area_sqft} sq ft</span>
                            </p>
                          </div>

                          <div className="text-right shrink-0">
                            <div className="text-lg font-bold font-mono text-emerald-700">
                              {item.match_score}%
                            </div>
                            <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded uppercase ${
                              item.confidence >= 0.8
                                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                                : item.confidence >= 0.5
                                ? 'bg-amber-50 text-amber-800 border border-amber-200'
                                : 'bg-rose-50 text-rose-800 border border-rose-200'
                            }`}>
                              {item.confidence >= 0.8 ? 'High Conf' : item.confidence >= 0.5 ? 'Med Conf' : 'Low Conf'}
                            </span>
                          </div>
                        </div>

                        <div className="text-base font-bold font-mono text-[#1A1A1A] mb-3">
                          ₹{formatCurrencyINR(item.price)}
                        </div>

                        {/* Reasons list */}
                        <div className="space-y-1 mb-3">
                          {item.why_matches?.slice(0, 3).map((r: string, i: number) => (
                            <div key={i} className="text-[11px] text-emerald-800 flex items-center gap-1.5 font-medium">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600 shrink-0" />
                              <span className="truncate">{r}</span>
                            </div>
                          ))}
                          {item.trade_offs?.slice(0, 2).map((t: string, i: number) => (
                            <div key={i} className="text-[11px] text-amber-800 flex items-center gap-1.5 font-medium">
                              <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                              <span className="truncate">{t}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="pt-3 border-t border-[#E5E1DA] flex items-center justify-between gap-2 mt-2">
                        <button
                          onClick={() => setSelectedItemForModal(item)}
                          className="text-xs font-semibold text-[#6B6B6B] hover:text-[#1A1A1A] transition flex items-center gap-1 cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Why This Match?</span>
                        </button>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleShortlist(item.property_id, leadIdInput)}
                            className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] text-[#1A1A1A] transition cursor-pointer shadow-2xs"
                          >
                            Shortlist
                          </button>
                          <button
                            onClick={() => handleRecommend(item.property_id, leadIdInput)}
                            className="btn-lime px-3 py-1.5 text-xs rounded-xl shadow-2xs cursor-pointer"
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
          <form onSubmit={handleRunPropMatch} className="p-5 sm:p-6 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] space-y-4 shadow-xs">
            <h2 className="text-sm font-bold text-[#1A1A1A] font-mono flex items-center gap-2">
              <Search className="w-4 h-4 text-blue-600" />
              <span>Reverse Match: Find Qualified Buyer Leads for Property</span>
            </h2>

            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1">
                <input
                  type="text"
                  value={propertyIdInput}
                  onChange={(e) => setPropertyIdInput(e.target.value)}
                  placeholder="Enter Property ID..."
                  className="w-full px-3.5 py-2.5 text-xs rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] placeholder-[#9CA3AF] focus:outline-none focus:border-[#1A1A1A]"
                />
              </div>

              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={isLoadingPropMatches || !propertyIdInput.trim()}
                isLoading={isLoadingPropMatches}
                leftIcon={<Sparkles className="w-3.5 h-3.5" />}
              >
                Find Buyers
              </Button>
            </div>

            {/* Quick links to high demand properties */}
            {dashboardData?.high_demand_properties?.length > 0 && (
              <div className="pt-3 border-t border-[#E5E1DA]">
                <span className="text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider block mb-2">
                  Quick Pick — Active Properties:
                </span>
                <div className="flex flex-wrap gap-2">
                  {dashboardData.high_demand_properties.map((p: any) => (
                    <button
                      key={p.property_id}
                      type="button"
                      onClick={() => handleRunPropMatch(undefined, p.property_id)}
                      className="px-2.5 py-1 text-[11px] font-medium rounded-lg bg-white border border-[#D4D0C8] text-[#1A1A1A] hover:bg-[#F0EDE8] hover:border-[#1A1A1A] transition-all cursor-pointer shadow-2xs"
                    >
                      {p.property_title} (₹{formatCurrencyINR(p.price)})
                    </button>
                  ))}
                </div>
              </div>
            )}
          </form>

          {propMatchError && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
              {propMatchError}
            </div>
          )}

          {/* Leads Table */}
          {propertyMatches.length > 0 && (
            <div className="rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] overflow-hidden shadow-xs">
              <div className="px-6 py-4 border-b border-[#E5E1DA] flex items-center justify-between">
                <h3 className="text-xs font-bold text-[#1A1A1A] font-mono uppercase tracking-wider">
                  Top {propertyMatches.length} Compatible Buyer Leads
                </h3>
                <span className="text-[10px] font-mono text-[#6B6B6B]">Strictly Tenant Scoped</span>
              </div>

              <div className="divide-y divide-[#E5E1DA]">
                {propertyMatches.map((leadItem: any) => (
                  <div key={leadItem.lead_id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-[#F5F0EB] transition">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-[#1A1A1A] font-mono">{leadItem.name}</h4>
                        <span className={`text-[10px] font-bold font-mono uppercase px-2 py-0.5 rounded ${
                          leadItem.lead_tier === 'hot'
                            ? 'bg-rose-50 text-rose-800 border border-rose-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}>
                          {leadItem.lead_tier}
                        </span>
                      </div>
                      <p className="text-xs text-[#6B6B6B] mt-0.5">{leadItem.phone} • {leadItem.notes}</p>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {leadItem.reasons?.map((r: string, idx: number) => (
                          <span key={idx} className="text-[10px] text-emerald-800 flex items-center gap-1 font-medium">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> {r}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      <div className="text-right">
                        <div className="text-base font-bold font-mono text-blue-700">{leadItem.match_score}%</div>
                        <span className="text-[10px] text-[#6B6B6B]">Compatibility</span>
                      </div>

                      <button
                        onClick={() => handleRecommend(propertyIdInput, leadItem.lead_id)}
                        className="btn-lime px-3 py-1.5 text-xs rounded-xl shadow-2xs cursor-pointer"
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
          <div className="p-6 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
            <h2 className="text-sm font-bold text-[#1A1A1A] font-mono mb-1 flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber-600" />
              <span>High Demand vs Low Inventory Localities</span>
            </h2>
            <p className="text-xs text-[#6B6B6B] mb-6 max-w-xl">
              Real-time analysis of active buyer lead preferences compared against active property listings.
            </p>

            {(!dashboardData?.supply_gaps || dashboardData.supply_gaps.length === 0) ? (
              <p className="text-xs text-[#6B6B6B] py-8 text-center font-mono">No acute supply gaps detected in your active inventory.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase text-[10px]">
                      <th className="pb-3">Locality</th>
                      <th className="pb-3">Active Buyer Demand</th>
                      <th className="pb-3">Available Properties</th>
                      <th className="pb-3">Inventory Gap</th>
                      <th className="pb-3">Severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E1DA]">
                    {dashboardData.supply_gaps.map((gap: any, i: number) => (
                      <tr key={i} className="hover:bg-[#F5F0EB]">
                        <td className="py-3 font-bold text-[#1A1A1A] font-mono">{gap.locality}</td>
                        <td className="py-3 text-[#4A4A4A]">{gap.active_leads_demand} Leads</td>
                        <td className="py-3 text-[#4A4A4A]">{gap.available_inventory} Units</td>
                        <td className="py-3 font-bold text-rose-700 font-mono">+{gap.gap} Units Needed</td>
                        <td className="py-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                            gap.severity === 'HIGH' ? 'bg-rose-50 text-rose-800 border border-rose-200' : 'bg-amber-50 text-amber-800 border border-amber-200'
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
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="max-w-lg w-full rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] p-6 space-y-4 shadow-2xl animate-in fade-in-50 zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-[#E5E1DA] pb-3">
              <h3 className="text-sm font-bold text-[#1A1A1A] font-mono flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-emerald-600" />
                <span>Why This Property Matches ({selectedItemForModal.match_score}%)</span>
              </h3>
              <button
                onClick={() => setSelectedItemForModal(null)}
                className="text-[#6B6B6B] hover:text-[#1A1A1A] p-1 rounded-lg cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <h4 className="font-bold text-[#1A1A1A] font-mono">{selectedItemForModal.title}</h4>
                <p className="text-[#6B6B6B]">
                  {selectedItemForModal.locality}, {selectedItemForModal.city} • ₹{formatCurrencyINR(selectedItemForModal.price)}
                </p>
              </div>

              {/* Granular Component Scores */}
              {selectedItemForModal.score_breakdown && (
                <div className="p-3.5 rounded-xl bg-white border border-[#D4D0C8] space-y-2">
                  <span className="text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider block">
                    Component Breakdown:
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div>Budget Fit: <strong className="font-mono text-[#1A1A1A]">{selectedItemForModal.score_breakdown.budget_fit}%</strong></div>
                    <div>Location Fit: <strong className="font-mono text-[#1A1A1A]">{selectedItemForModal.score_breakdown.location_fit}%</strong></div>
                    <div>Property Type: <strong className="font-mono text-[#1A1A1A]">{selectedItemForModal.score_breakdown.property_fit}%</strong></div>
                    <div>Bedrooms Fit: <strong className="font-mono text-[#1A1A1A]">{selectedItemForModal.score_breakdown.timeline_fit}%</strong></div>
                    <div>Amenities Fit: <strong className="font-mono text-[#1A1A1A]">{selectedItemForModal.score_breakdown.preference_fit}%</strong></div>
                    <div>Layout Area: <strong className="font-mono text-[#1A1A1A]">{selectedItemForModal.score_breakdown.investment_fit}%</strong></div>
                  </div>
                </div>
              )}

              <div>
                <span className="text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider block mb-1">
                  Grounded Rationale:
                </span>
                <ul className="space-y-1">
                  {selectedItemForModal.why_matches?.map((r: string, idx: number) => (
                    <li key={idx} className="text-emerald-800 flex items-center gap-1.5 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span>{r}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {selectedItemForModal.trade_offs?.length > 0 && (
                <div>
                  <span className="text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider block mb-1">
                    Potential Mismatches / Trade-offs:
                  </span>
                  <ul className="space-y-1">
                    {selectedItemForModal.trade_offs.map((t: string, idx: number) => (
                      <li key={idx} className="text-amber-800 flex items-center gap-1.5 font-medium">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-[#E5E1DA] flex justify-end">
              <button
                onClick={() => setSelectedItemForModal(null)}
                className="px-4 py-2 text-xs font-semibold rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] hover:bg-[#F0EDE8] cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
