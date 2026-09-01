'use client';

import React, { useEffect, useState } from 'react';
import { TableauNLQueryBar } from '@/components/analytics/TableauNLQueryBar';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';
import { api } from '@/lib/api-client';

export default function ExecutiveAnalyticsPage() {
  const { region } = useRegion();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<{
    revenue_ytd: number;
    pipeline_total_value: number;
    avg_customer_acquisition_cost: number;
    marketing_campaign_roi_pct: number;
    conversion_rate_overall_pct: number;
    anomalies: Array<{
      id: string;
      severity: string;
      metric_name: string;
      description: string;
      root_cause: string;
      action: string;
    }>;
  } | null>(null);

  const fetchSummary = async () => {
    setLoading(true);
    try {
      const data = await api.bi.getExecutiveSummary();
      setSummary(data);
    } catch (e) {
      console.error('Failed to load executive summary:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const anomalies = summary?.anomalies || [];
  const pipelineVal = summary?.pipeline_total_value || 0;
  const revYtd = summary?.revenue_ytd || 0;
  const convRate = summary?.conversion_rate_overall_pct || 0;
  const cac = summary?.avg_customer_acquisition_cost || 0;
  const roi = summary?.marketing_campaign_roi_pct || 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Executive BI & C-Suite Dashboard</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Executive summary, automated anomaly alerts, and natural language analytics powered by live CRM data.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchSummary}
            disabled={loading}
            className="p-2 bg-white border border-[#D4D0C8] rounded-xl hover:bg-[#F0EDE8] transition-colors"
            title="Refresh BI Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#1A1A1A] ${loading ? 'animate-spin' : ''}`} />
          </button>
          <span className="bg-[#E8F5A8] text-[#1A1A1A] text-xs font-mono font-bold px-3 py-1.5 rounded-xl border border-[#D4D0C8]">
            Est. Commission: {revYtd > 0 ? formatCurrency(revYtd, region) : '₹0'}
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

        {anomalies.length > 0 ? (
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
                  <span>{anom.metric_name || anom.description}</span>
                  <span
                    className={`text-[9px] uppercase px-2 py-0.5 rounded font-extrabold ${
                      anom.severity === 'critical' ? 'bg-red-200 text-red-900' : 'bg-indigo-200 text-indigo-900'
                    }`}
                  >
                    {anom.severity}
                  </span>
                </div>
                <p className="text-xs font-sans opacity-90">{anom.description}</p>
                {anom.action && (
                  <div className="text-[11px] font-mono font-bold pt-1 border-t border-black/10">
                    👉 Recommended Action: {anom.action}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white border border-[#D4D0C8] rounded-2xl p-6 text-center text-xs font-mono text-gray-500">
            No pipeline anomalies detected. CRM operating within standard parameters.
          </div>
        )}
      </div>

      {/* C-Suite Core KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Total Pipeline Value</span>
          <div className="text-xl font-extrabold font-mono text-[#1A1A1A]">
            {pipelineVal > 0 ? formatCurrency(pipelineVal, region) : '₹0'}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {pipelineVal > 0 ? 'Active hot & warm pipeline' : 'No active leads'}
          </span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Est. Acquisition Cost</span>
          <div className="text-xl font-extrabold font-mono text-emerald-700">
            {cac > 0 ? formatCurrency(cac, region) : '--'}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {cac > 0 ? 'Estimated CAC per acquisition' : 'Insufficient closed deal data'}
          </span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Campaign ROI Index</span>
          <div className="text-xl font-extrabold font-mono text-indigo-700">
            {roi > 0 ? `${roi}% ROI` : '--'}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {roi > 0 ? 'Calculated from pipeline conversion' : 'No attribution data'}
          </span>
        </div>

        <div className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-1">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Overall Conversion Rate</span>
          <div className="text-xl font-extrabold font-mono text-[#1A1A1A]">
            {convRate > 0 ? `${convRate}%` : '0%'}
          </div>
          <span className="text-[10px] text-gray-400 font-mono">
            {convRate > 0 ? 'Live CRM qualification rate' : 'No leads qualified yet'}
          </span>
        </div>
      </div>
    </div>
  );
}
