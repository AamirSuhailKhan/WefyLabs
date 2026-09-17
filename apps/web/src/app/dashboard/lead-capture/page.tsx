'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { 
  Radio, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ArrowUpRight, 
  RefreshCw, 
  Plus, 
  Globe, 
  Webhook, 
  Share2, 
  FileSpreadsheet, 
  Sparkles,
  Play,
  ShieldCheck
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import LeadCaptureNav from '@/components/lead-capture/LeadCaptureNav';
import { api } from '@/lib/api-client';

interface DashboardMetrics {
  total_captured: number;
  today: number;
  this_week: number;
  this_month: number;
  by_status: Record<string, number>;
  by_channel: Record<string, number>;
  sources: Array<{
    id: string;
    name: string;
    channel: string;
    provider?: string;
    status: string;
    is_active: boolean;
    health: string;
    total_events: number;
    webhook_token?: string;
    created_at?: string;
  }>;
  healthy_sources_count: number;
  attention_needed_count: number;
}

export default function LeadCaptureDashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [testingSourceId, setTestingSourceId] = useState<string | null>(null);
  const [testSuccessMessage, setTestSuccessMessage] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [mRes, eRes] = await Promise.all([
        api.leadCapture.getMetrics().catch(() => null),
        api.leadCapture.listEvents({ limit: 8 }).catch(() => ({ items: [] })),
      ]);
      if (mRes) setMetrics(mRes);
      if (eRes?.items) setRecentEvents(eRes.items);
    } catch (err) {
      console.error('Failed to load lead capture metrics', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleRunTestLead = async (sourceId: string, sourceName: string) => {
    setTestingSourceId(sourceId);
    setTestSuccessMessage(null);
    try {
      const res = await api.leadCapture.sendTestLead(sourceId);
      setTestSuccessMessage(`Test lead "${res.lead_name}" (${res.lead_phone}) created and assigned!`);
      fetchDashboardData();
      setTimeout(() => setTestSuccessMessage(null), 6000);
    } catch (err: any) {
      alert(`Test submission failed: ${err.message || err}`);
    } finally {
      setTestingSourceId(null);
    }
  };

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'HEALTHY':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Healthy
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            Warning
          </span>
        );
      case 'FAILING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3 text-rose-600" />
            Failing
          </span>
        );
      case 'CONFIGURATION_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Radio className="w-3 h-3 text-blue-600" />
            Config Required
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-700 border border-gray-200">
            Disabled
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'processed':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800">Processed</span>;
      case 'duplicate':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-purple-100 text-purple-800">Duplicate</span>;
      case 'failed':
      case 'rejected':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-100 text-rose-800">Failed</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800">{status}</span>;
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-gray-900 pb-16">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto pt-20 px-4 sm:px-6">
        {/* Hub Title Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 border-b border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-gray-900 text-white">
                Part 26
              </span>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-gray-900">
                Lead Capture Hub
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-gray-500">
              Universal multi-source ingestion: website forms, embeddable widgets, REST APIs, webhooks, and CSV imports.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchDashboardData}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 transition shadow-sm"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <Link
              href="/dashboard/lead-capture/sources"
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800 transition shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              New Lead Source
            </Link>
          </div>
        </div>

        {/* Lead Capture Sub Navigation */}
        <div className="my-4 rounded-xl overflow-hidden border border-gray-200 shadow-sm">
          <LeadCaptureNav />
        </div>

        {/* Test Mode Notification Toast */}
        {testSuccessMessage && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between text-emerald-800 text-xs font-semibold animate-in fade-in">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>{testSuccessMessage}</span>
            </div>
            <Link href="/dashboard/leads" className="underline font-bold hover:text-emerald-950">
              View in CRM Leads →
            </Link>
          </div>
        )}

        {/* Top Metric Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="p-5 rounded-2xl bg-white border border-gray-200/80 shadow-sm">
            <div className="flex items-center justify-between text-xs text-gray-500 font-medium mb-2">
              <span>Total Captured</span>
              <Globe className="w-4 h-4 text-gray-400" />
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold text-gray-900">
              {metrics?.total_captured ?? 0}
            </div>
            <div className="mt-2 text-[11px] text-gray-500 flex items-center gap-1">
              <span className="font-semibold text-emerald-600">+{metrics?.today ?? 0}</span> today
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-gray-200/80 shadow-sm">
            <div className="flex items-center justify-between text-xs text-gray-500 font-medium mb-2">
              <span>Past 7 Days</span>
              <Sparkles className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold text-gray-900">
              {metrics?.this_week ?? 0}
            </div>
            <div className="mt-2 text-[11px] text-gray-500">
              Leads ingested this week
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-gray-200/80 shadow-sm">
            <div className="flex items-center justify-between text-xs text-gray-500 font-medium mb-2">
              <span>Source Health</span>
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold text-emerald-600">
              {metrics?.healthy_sources_count ?? 0} / {metrics?.sources?.length ?? 0}
            </div>
            <div className="mt-2 text-[11px] text-gray-500">
              Active healthy channels
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-gray-200/80 shadow-sm">
            <div className="flex items-center justify-between text-xs text-gray-500 font-medium mb-2">
              <span>Duplicates Prevented</span>
              <CheckCircle2 className="w-4 h-4 text-purple-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-extrabold text-purple-700">
              {metrics?.by_status?.['duplicate'] ?? 0}
            </div>
            <div className="mt-2 text-[11px] text-gray-500">
              Deduplicated & re-attributed
            </div>
          </div>
        </div>

        {/* Ingestion Channels Performance Overview */}
        <div className="mb-6 bg-white rounded-2xl border border-gray-200/80 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-bold text-gray-900">Ingestion Channel Performance</h2>
              <p className="text-xs text-gray-500">Verified capture channels routing into your canonical CRM pipeline.</p>
            </div>
            <Link
              href="/dashboard/lead-capture/forms"
              className="text-xs font-semibold text-gray-700 hover:text-gray-900 inline-flex items-center gap-1"
            >
              Form Builder <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-gray-100 bg-[#FAFAFA] flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-gray-700">Website Forms</span>
                  <Globe className="w-4 h-4 text-blue-500" />
                </div>
                <div className="text-xl font-bold text-gray-900 mb-1">
                  {metrics?.by_channel?.['WEBSITE'] ?? 0} leads
                </div>
                <p className="text-[11px] text-gray-500">Public embeddable capture forms & widget submissions.</p>
              </div>
              <div className="mt-4 pt-3 border-t border-gray-200/60 flex items-center justify-between">
                <span className="text-[10px] font-bold text-emerald-600">LIVE</span>
                <Link href="/dashboard/lead-capture/forms" className="text-[11px] font-semibold text-gray-900 hover:underline">
                  Embed Code →
                </Link>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-gray-100 bg-[#FAFAFA] flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-gray-700">Generic Webhooks</span>
                  <Webhook className="w-4 h-4 text-purple-500" />
                </div>
                <div className="text-xl font-bold text-gray-900 mb-1">
                  {metrics?.by_channel?.['WEBHOOK'] ?? 0} leads
                </div>
                <p className="text-[11px] text-gray-500">Inbound HTTP webhooks with cryptographic HMAC verification.</p>
              </div>
              <div className="mt-4 pt-3 border-t border-gray-200/60 flex items-center justify-between">
                <span className="text-[10px] font-bold text-emerald-600">LIVE</span>
                <Link href="/dashboard/lead-capture/sources" className="text-[11px] font-semibold text-gray-900 hover:underline">
                  Webhook URL →
                </Link>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-gray-100 bg-[#FAFAFA] flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-gray-700">Meta / Google Ads</span>
                  <Share2 className="w-4 h-4 text-indigo-500" />
                </div>
                <div className="text-xl font-bold text-gray-900 mb-1">
                  {(metrics?.by_channel?.['META'] ?? 0) + (metrics?.by_channel?.['GOOGLE'] ?? 0)} leads
                </div>
                <p className="text-[11px] text-gray-500">Facebook Lead Ads & Google Lead Form adapters.</p>
              </div>
              <div className="mt-4 pt-3 border-t border-gray-200/60 flex items-center justify-between">
                <span className="text-[10px] font-bold text-blue-600">ADAPTER READY</span>
                <Link href="/dashboard/lead-capture/sources" className="text-[11px] font-semibold text-gray-900 hover:underline">
                  Configure →
                </Link>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-gray-100 bg-[#FAFAFA] flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-gray-700">CSV / Excel Imports</span>
                  <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
                </div>
                <div className="text-xl font-bold text-gray-900 mb-1">
                  {metrics?.by_channel?.['CSV'] ?? metrics?.by_channel?.['IMPORT'] ?? 0} leads
                </div>
                <p className="text-[11px] text-gray-500">Bulk batch import with column auto-mapping and dedup check.</p>
              </div>
              <div className="mt-4 pt-3 border-t border-gray-200/60 flex items-center justify-between">
                <span className="text-[10px] font-bold text-emerald-600">LIVE</span>
                <Link href="/dashboard/lead-capture/import" className="text-[11px] font-semibold text-gray-900 hover:underline">
                  Upload CSV →
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Lead Sources Health Table */}
        <div className="mb-6 bg-white rounded-2xl border border-gray-200/80 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-gray-900">Configured Lead Sources</h2>
              <p className="text-xs text-gray-500">Manage sources, test ingestion paths, and copy embed credentials.</p>
            </div>
            <Link
              href="/dashboard/lead-capture/sources"
              className="text-xs font-semibold text-gray-900 hover:underline"
            >
              View All Sources ({metrics?.sources?.length ?? 0}) →
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAFAFA] border-b border-gray-200 text-gray-500 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-5 font-semibold">Source Name</th>
                  <th className="py-3 px-5 font-semibold">Channel</th>
                  <th className="py-3 px-5 font-semibold">Health Status</th>
                  <th className="py-3 px-5 font-semibold text-right">Captured Events</th>
                  <th className="py-3 px-5 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {metrics?.sources && metrics.sources.length > 0 ? (
                  metrics.sources.slice(0, 6).map((s) => (
                    <tr key={s.id} className="hover:bg-gray-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-bold text-gray-900">
                        {s.name}
                      </td>
                      <td className="py-3.5 px-5 text-gray-600 font-medium">
                        {s.channel}
                      </td>
                      <td className="py-3.5 px-5">
                        {getHealthBadge(s.health)}
                      </td>
                      <td className="py-3.5 px-5 text-right font-semibold text-gray-900">
                        {s.total_events}
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => handleRunTestLead(s.id, s.name)}
                          disabled={testingSourceId === s.id}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded font-semibold text-[11px] transition"
                        >
                          <Play className={`w-3 h-3 ${testingSourceId === s.id ? 'animate-spin' : ''}`} />
                          {testingSourceId === s.id ? 'Simulating...' : 'Send Test Lead'}
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-gray-500">
                      No lead sources configured yet. Click "New Lead Source" to create your first ingestion channel.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Real-time Ingestion Activity Stream */}
        <div className="bg-white rounded-2xl border border-gray-200/80 shadow-sm overflow-hidden">
          <div className="p-5 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-gray-900">Recent Ingestion Activity</h2>
              <p className="text-xs text-gray-500">Live provenance feed of inbound lead signals.</p>
            </div>
            <Link
              href="/dashboard/lead-capture/events"
              className="text-xs font-semibold text-gray-900 hover:underline"
            >
              Full Ingestion Log & DLQ →
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#FAFAFA] border-b border-gray-200 text-gray-500 uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-5 font-semibold">Event ID</th>
                  <th className="py-3 px-5 font-semibold">Source</th>
                  <th className="py-3 px-5 font-semibold">Channel</th>
                  <th className="py-3 px-5 font-semibold">Status</th>
                  <th className="py-3 px-5 font-semibold text-right">Received At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentEvents && recentEvents.length > 0 ? (
                  recentEvents.map((ev) => (
                    <tr key={ev.id} className="hover:bg-gray-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-mono text-[11px] text-gray-600">
                        {ev.id.slice(0, 12)}...
                      </td>
                      <td className="py-3.5 px-5 font-semibold text-gray-900">
                        {ev.source_name || 'Direct'}
                      </td>
                      <td className="py-3.5 px-5 text-gray-600 font-medium">
                        {ev.channel}
                      </td>
                      <td className="py-3.5 px-5">
                        {getStatusBadge(ev.status)}
                      </td>
                      <td className="py-3.5 px-5 text-right text-gray-500 font-mono text-[11px]">
                        {ev.received_at ? new Date(ev.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Just now'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-gray-500">
                      No ingestion activity recorded yet. Submissions from website forms and webhooks will appear here in real-time.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
