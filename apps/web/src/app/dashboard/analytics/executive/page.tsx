'use client';

import React from 'react';
import { TableauNLQueryBar } from '@/components/analytics/TableauNLQueryBar';
import { BarChart3, TrendingUp, AlertTriangle, Globe2, DollarSign, Target, PieChart, ShieldAlert } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function ExecutiveAnalyticsPage() {
  const { region } = useRegion();

  const anomalies = [
    {
      id: '1',
      severity: 'critical',
      title: 'Dubai Marina Lead Response Speed Spike',
      description: 'Average WhatsApp response time spiked from 2.1m to 14.5m over the past 48 hours.',
      action: 'Enable automated round-robin re-assignment after 5 mins.'
    },
    {
      id: '2',
      severity: 'info',
      title: 'Palm Jumeirah Villa Demand Surge (+42%)',
      description: 'Google Ads campaign launched Jul 25 generated 38 high-budget leads.',
      action: 'Allocate 2 additional luxury specialist brokers.'
    }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Executive BI & C-Suite Dashboard</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Tableau & Salesforce CRM Analytics engine. Executive summary, automated anomaly alerts, and natural language analytics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="bg-[#E8F5A8] text-[#1A1A1A] text-xs font-mono font-bold px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
            YTD Revenue: {formatCurrency(8450000, region)}
          </span>
        </div>
      </div>

      {/* Natural Language Analytics Query Bar */}
      <TableauNLQueryBar />

      {/* Anomaly Detection Alerts Section */}
      <div className="space-y-3">
        <h3 className="text-xs font-mono font-bold uppercase text-gray-500 flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span>Automated AI Anomaly Detection Alerts ({anomalies.length})</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {anomalies.map((anom) => (
            <div
              key={anom.id}
              className={`p-4 rounded-2xl border space-y-2 shadow-xs ${
                anom.severity === 'critical'
                  ? 'bg-red-50 border-red-200 text-red-950'
                  : 'bg-indigo-50 border-indigo-200 text-indigo-950'
              }`}
            >
              <div className="flex items-center justify-between font-mono font-bold text-xs">
                <span>{anom.title}</span>
                <span className={`text-[9px] uppercase px-2 py-0.5 rounded font-extrabold ${anom.severity === 'critical' ? 'bg-red-200 text-red-900' : 'bg-indigo-200 text-indigo-900'}`}>
                  {anom.severity}
                </span>
              </div>
              <p className="text-xs font-sans opacity-90">{anom.description}</p>
              <div className="text-[11px] font-mono font-bold pt-1 border-t border-black/10">
                👉 Recommended Action: {anom.action}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* C-Suite Core KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Total Pipeline Value</span>
          <div className="text-xl font-extrabold font-mono text-[#1A1A1A]">
            {formatCurrency(18200000, region)}
          </div>
          <span className="text-[10px] text-emerald-700 font-mono font-bold">+18.4% vs last quarter</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Customer Acquisition Cost (CAC)</span>
          <div className="text-xl font-extrabold font-mono text-emerald-700">
            {formatCurrency(420, region)}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Down from $580 (-27.5%)</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Marketing Campaign ROI</span>
          <div className="text-xl font-extrabold font-mono text-indigo-700">
            348% ROI
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Top channel: Google Off-Plan Ads</span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Overall Conversion Rate</span>
          <div className="text-xl font-extrabold font-mono text-[#1A1A1A]">
            34.8%
          </div>
          <span className="text-[10px] text-gray-400 font-mono">Benchmark: 18.2%</span>
        </div>
      </div>
    </div>
  );
}
