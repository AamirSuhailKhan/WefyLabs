'use client';

import React from 'react';
import { BrokerCoachingWidget } from '@/components/performance/BrokerCoachingWidget';
import { Trophy, TrendingUp, DollarSign, Award, Target, Zap, Clock, UserCheck } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function PerformancePage() {
  const { region } = useRegion();

  const metrics = {
    revenue_closed: 2850000,
    commission_earned: 57000,
    monthly_quota_target: 3000000,
    quota_attainment_pct: 95.0,
    deals_closed_count: 4,
    conversion_rate_pct: 34.8,
    avg_response_time_mins: 4.2,
    avg_deal_size: 712500,
    office_rank: 2,
    regional_rank: 5
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Broker Performance & Quota Dashboard</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Salesforce CRM Analytics metrics. Track revenue, commission earnings, regional rankings, and AI coaching priorities.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="bg-[#E8F5A8] text-[#1A1A1A] text-xs font-mono font-bold px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
            Q3 Quota Attainment: {metrics.quota_attainment_pct}%
          </span>
        </div>
      </div>

      {/* Main KPI Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Revenue Closed (Q3)</span>
          <div className="text-xl font-extrabold font-mono text-[#1A1A1A]">
            {formatCurrency(metrics.revenue_closed, region)}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Quota Target: {formatCurrency(metrics.monthly_quota_target, region)}</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Est. Commission Earned</span>
          <div className="text-xl font-extrabold font-mono text-emerald-700">
            {formatCurrency(metrics.commission_earned, region)}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Avg 2.0% payout per closed deal</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Deals Closed</span>
          <div className="text-xl font-extrabold font-mono text-[#1A1A1A]">
            {metrics.deals_closed_count} Deals
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Avg Deal Size: {formatCurrency(metrics.avg_deal_size, region)}</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Response Velocity</span>
          <div className="text-xl font-extrabold font-mono text-indigo-700">
            {metrics.avg_response_time_mins} mins
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Conversion Rate: {metrics.conversion_rate_pct}%</span>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Quota Progress Visualizer */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-[#1A1A1A]" />
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Quarterly Quota Attainment Progress</h3>
              </div>
              <span className="text-xs font-mono font-extrabold text-emerald-700">{metrics.quota_attainment_pct}%</span>
            </div>

            <div className="space-y-2">
              <div className="h-4 w-full bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${metrics.quota_attainment_pct}%` }}></div>
              </div>
              <div className="flex justify-between text-xs font-mono text-gray-500">
                <span>Current: {formatCurrency(metrics.revenue_closed, region)}</span>
                <span>Target: {formatCurrency(metrics.monthly_quota_target, region)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Broker Coaching & Regional Leaderboard Widget */}
        <div className="lg:col-span-5">
          <BrokerCoachingWidget />
        </div>
      </div>
    </div>
  );
}
