'use client';

import React, { useEffect, useState } from 'react';
import { PredictiveScoreCard } from '@/components/analytics/PredictiveScoreCard';
import { BarChart3, ArrowUpRight, RefreshCw } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';
import { api } from '@/lib/api-client';
import { Lead } from '@/types';

export default function AnalyticsPage() {
  const { region } = useRegion();
  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState<{
    quarter: string;
    projected_revenue: number;
    confidence_interval: { lower_bound: number; upper_bound: number };
    pipeline_health_score: number;
    deals_count: number;
    calculation_basis: string;
  } | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [leadIntel, setLeadIntel] = useState<{
    conversion_probability_pct: number;
    churn_risk_pct: number;
    estimated_lifetime_value: number;
    best_followup_window: string;
    feature_attributions: Array<{ feature: string; impact: number; explanation: string }>;
  } | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [dashRes, leadsRes] = await Promise.allSettled([
        api.predictive.getDashboard(),
        api.getLeads(),
      ]);

      if (dashRes.status === 'fulfilled') {
        setDashboardData(dashRes.value);
      }

      if (leadsRes.status === 'fulfilled' && leadsRes.value.items) {
        const fetchedLeads = leadsRes.value.items;
        setLeads(fetchedLeads);
        if (fetchedLeads.length > 0) {
          try {
            const intel = await api.predictive.getLeadIntelligence(fetchedLeads[0].id);
            setLeadIntel(intel);
          } catch {
            // No intel for lead
          }
        }
      }
    } catch (e) {
      console.error('Failed to load predictive analytics data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const totalLeads = leads.length;
  const qualifiedLeads = leads.filter((l) => l.status === 'qualified' || l.status === 'converted').length;
  const avgConversionPct = totalLeads > 0 ? Math.round((qualifiedLeads / totalLeads) * 100) : 0;
  const projectedRev = dashboardData?.projected_revenue || 0;
  const lowerBound = dashboardData?.confidence_interval?.lower_bound || 0;
  const upperBound = dashboardData?.confidence_interval?.upper_bound || 0;
  const healthScore = dashboardData?.pipeline_health_score || 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Conversion Propensity & Revenue Forecast</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Feature-weighted conversion propensity models, genuine pipeline forecasts, and real attribution factors.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2 bg-white border border-[#D4D0C8] rounded-xl hover:bg-[#F0EDE8] transition-colors"
            title="Refresh analytics"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#1A1A1A] ${loading ? 'animate-spin' : ''}`} />
          </button>
          <span className="bg-[#E8F5A8] text-[#1A1A1A] text-xs font-mono font-bold px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
            Propensity Engine v1.0
          </span>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">
            Projected Revenue ({dashboardData?.quarter || 'Current'})
          </span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-[#1A1A1A]">
              {projectedRev > 0 ? formatCurrency(projectedRev, region) : '₹0'}
            </span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {projectedRev > 0
              ? `Conf. Interval: ${formatCurrency(lowerBound, region)} - ${formatCurrency(upperBound, region)}`
              : 'Insufficient pipeline data'}
          </span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Pipeline Health Score</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-emerald-700">
              {healthScore > 0 ? `${healthScore} / 100` : '--'}
            </span>
            {healthScore > 0 && (
              <span className="bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded">
                Active
              </span>
            )}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {dashboardData?.deals_count ? `${dashboardData.deals_count} active deal transactions` : 'No active deal transactions'}
          </span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Lead Qualification %</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-[#1A1A1A]">
              {totalLeads > 0 ? `${avgConversionPct}%` : '--'}
            </span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {totalLeads > 0 ? `${qualifiedLeads} of ${totalLeads} leads qualified` : 'No leads registered yet'}
          </span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Total Active Leads</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-indigo-700">{totalLeads}</span>
            <span className="bg-indigo-100 text-indigo-900 text-[10px] font-mono font-bold px-2 py-0.5 rounded">
              Verified
            </span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Real-time database records</span>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Revenue Forecast & Pipeline Breakdown */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-[#1A1A1A]" />
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Pipeline Trajectory</h3>
              </div>
              <span className="text-xs font-mono font-bold text-gray-500">Real CRM Metrics</span>
            </div>

            <div className="space-y-3 pt-2">
              {projectedRev > 0 ? (
                <div>
                  <div className="flex justify-between text-xs font-mono font-bold mb-1">
                    <span>{dashboardData?.quarter || 'Quarterly Forecast'}</span>
                    <span className="text-emerald-700">{formatCurrency(projectedRev, region)}</span>
                  </div>
                  <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full" style={{ width: '100%' }}></div>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center text-xs font-mono text-gray-500">
                  Insufficient deal or budget data to generate pipeline projection.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Predictive Intelligence Score Card */}
        <div className="lg:col-span-5">
          <PredictiveScoreCard
            conversionProbability={leadIntel?.conversion_probability_pct}
            churnRisk={leadIntel?.churn_risk_pct}
            estimatedLtv={leadIntel?.estimated_lifetime_value}
            bestFollowupWindow={leadIntel?.best_followup_window}
            attributions={leadIntel?.feature_attributions}
          />
        </div>
      </div>
    </div>
  );
}
