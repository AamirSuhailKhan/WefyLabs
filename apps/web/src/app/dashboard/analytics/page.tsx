'use client';

import React from 'react';
import { PredictiveScoreCard } from '@/components/analytics/PredictiveScoreCard';
import { TrendingUp, BarChart3, PieChart, Sparkles, DollarSign, Target, Award, ArrowUpRight } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function AnalyticsPage() {
  const { region } = useRegion();

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Predictive Intelligence & Revenue Forecast</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Salesforce Einstein ML models predicting lead conversion %, quarterly revenue, and attribution factors.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="bg-[#E8F5A8] text-[#1A1A1A] text-xs font-mono font-bold px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
            Model Accuracy: 94.8%
          </span>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Projected Revenue (Q3)</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-[#1A1A1A]">
              {formatCurrency(485000, region)}
            </span>
            <span className="text-xs font-mono font-bold text-emerald-700 flex items-center">
              <ArrowUpRight className="w-3.5 h-3.5" /> +14.2%
            </span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Conf. Interval: {formatCurrency(430000, region)} - {formatCurrency(540000, region)}</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Pipeline Health Score</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-emerald-700">91.4 / 100</span>
            <span className="bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded">Optimal</span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Low bottleneck risk across 13 stages</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Avg Lead Conversion %</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-[#1A1A1A]">34.8%</span>
            <span className="text-xs font-mono font-bold text-emerald-700 flex items-center">
              <ArrowUpRight className="w-3.5 h-3.5" /> +5.6%
            </span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">vs Industry Benchmark (18.2%)</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Agent Coaching Index</span>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold font-mono text-indigo-700">94.2 / 100</span>
            <span className="bg-indigo-100 text-indigo-900 text-[10px] font-mono font-bold px-2 py-0.5 rounded">Top Tier</span>
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Based on response velocity & win rates</span>
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
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Quarterly Revenue Trajectory Forecast</h3>
              </div>
              <span className="text-xs font-mono font-bold text-gray-500">Einstein ML Engine</span>
            </div>

            {/* Simulated Chart Bars */}
            <div className="space-y-3 pt-2">
              <div>
                <div className="flex justify-between text-xs font-mono font-bold mb-1">
                  <span>Jul 2026 (Actual)</span>
                  <span>{formatCurrency(145000, region)}</span>
                </div>
                <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-[#1A1A1A] rounded-full" style={{ width: '65%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono font-bold mb-1">
                  <span>Aug 2026 (Projected)</span>
                  <span className="text-emerald-700">{formatCurrency(175000, region)}</span>
                </div>
                <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: '80%' }}></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono font-bold mb-1">
                  <span>Sep 2026 (Projected)</span>
                  <span className="text-emerald-700">{formatCurrency(165000, region)}</span>
                </div>
                <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-400 rounded-full" style={{ width: '74%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Predictive Intelligence Score Card */}
        <div className="lg:col-span-5">
          <PredictiveScoreCard />
        </div>
      </div>
    </div>
  );
}
