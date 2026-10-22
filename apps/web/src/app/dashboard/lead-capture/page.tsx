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
import LeadCaptureNav from '@/components/lead-capture/LeadCaptureNav';
import { api } from '@/lib/api-client';
import { PageContainer, PageHeader, Button } from '@/components/ui';

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
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Healthy
          </span>
        );
      case 'WARNING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            Warning
          </span>
        );
      case 'FAILING':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-800 border border-rose-200">
            <XCircle className="w-3 h-3 text-rose-600" />
            Failing
          </span>
        );
      case 'CONFIGURATION_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
            <Radio className="w-3 h-3 text-blue-600" />
            Config Required
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#FAF7F2] text-[#6B6B6B] border border-[#D4D0C8]">
            Disabled
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'processed':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200">Processed</span>;
      case 'duplicate':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider bg-purple-50 text-purple-800 border border-purple-200">Duplicate</span>;
      case 'failed':
      case 'rejected':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider bg-rose-50 text-rose-800 border border-rose-200">Failed</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-200">{status}</span>;
    }
  };

  return (
    <PageContainer maxWidth="xl">
      {/* Header */}
      <PageHeader
        title="Lead Capture Hub"
        description="Universal multi-source ingestion: website forms, embeddable widgets, REST APIs, webhooks, and CSV imports."
        badge={
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-widest bg-[#1A1A1A] text-white">
            Universal Ingestion
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={fetchDashboardData}
              isLoading={loading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
            <Link href="/dashboard/lead-capture/sources">
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                New Lead Source
              </Button>
            </Link>
          </div>
        }
      />

      {/* Secondary Sub-Navigation */}
      <LeadCaptureNav activeTab="overview" />

      {/* Test Mode Notification Toast */}
      {testSuccessMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between text-emerald-800 text-xs font-semibold shadow-xs">
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
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between text-xs text-[#6B6B6B] font-semibold mb-2">
            <span>Total Captured</span>
            <Globe className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-[#1A1A1A]">
            {metrics?.total_captured ?? 0}
          </div>
          <div className="mt-2 text-[11px] text-[#6B6B6B] flex items-center gap-1">
            <span className="font-semibold text-emerald-700">+{metrics?.today ?? 0}</span> today
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between text-xs text-[#6B6B6B] font-semibold mb-2">
            <span>Past 7 Days</span>
            <Sparkles className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-[#1A1A1A]">
            {metrics?.this_week ?? 0}
          </div>
          <div className="mt-2 text-[11px] text-[#6B6B6B]">
            Leads ingested this week
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between text-xs text-[#6B6B6B] font-semibold mb-2">
            <span>Source Health</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-emerald-700">
            {metrics?.healthy_sources_count ?? 0} / {metrics?.sources?.length ?? 0}
          </div>
          <div className="mt-2 text-[11px] text-[#6B6B6B]">
            Active healthy channels
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs">
          <div className="flex items-center justify-between text-xs text-[#6B6B6B] font-semibold mb-2">
            <span>Duplicates Prevented</span>
            <CheckCircle2 className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-2xl sm:text-3xl font-bold font-mono text-purple-800">
            {metrics?.by_status?.['duplicate'] ?? 0}
          </div>
          <div className="mt-2 text-[11px] text-[#6B6B6B]">
            Deduplicated & re-attributed
          </div>
        </div>
      </div>

      {/* Ingestion Channels Performance Overview */}
      <div className="bg-[#FAF7F2] rounded-2xl border border-[#D4D0C8] shadow-xs p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[#1A1A1A] font-mono">Ingestion Channel Performance</h2>
            <p className="text-xs text-[#6B6B6B]">Verified capture channels routing into your canonical CRM pipeline.</p>
          </div>
          <Link
            href="/dashboard/lead-capture/forms"
            className="text-xs font-semibold text-[#1A1A1A] hover:underline inline-flex items-center gap-1"
          >
            Form Builder <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-[#D4D0C8] bg-white flex flex-col justify-between shadow-2xs">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#1A1A1A] font-mono">Website Forms</span>
                <Globe className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mb-1">
                {metrics?.by_channel?.['WEBSITE'] ?? 0} leads
              </div>
              <p className="text-[11px] text-[#6B6B6B]">Public embeddable capture forms & widget submissions.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-[#E5E1DA] flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold text-emerald-700">LIVE</span>
              <Link href="/dashboard/lead-capture/forms" className="text-[11px] font-semibold text-[#1A1A1A] hover:underline">
                Embed Code →
              </Link>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[#D4D0C8] bg-white flex flex-col justify-between shadow-2xs">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#1A1A1A] font-mono">Generic Webhooks</span>
                <Webhook className="w-4 h-4 text-purple-600" />
              </div>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mb-1">
                {metrics?.by_channel?.['WEBHOOK'] ?? 0} leads
              </div>
              <p className="text-[11px] text-[#6B6B6B]">Inbound HTTP webhooks with cryptographic HMAC verification.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-[#E5E1DA] flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold text-emerald-700">LIVE</span>
              <Link href="/dashboard/lead-capture/sources" className="text-[11px] font-semibold text-[#1A1A1A] hover:underline">
                Webhook URL →
              </Link>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[#D4D0C8] bg-white flex flex-col justify-between shadow-2xs">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#1A1A1A] font-mono">Meta / Google Ads</span>
                <Share2 className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mb-1">
                {(metrics?.by_channel?.['META'] ?? 0) + (metrics?.by_channel?.['GOOGLE'] ?? 0)} leads
              </div>
              <p className="text-[11px] text-[#6B6B6B]">Facebook Lead Ads & Google Lead Form adapters.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-[#E5E1DA] flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold text-blue-700">ADAPTER READY</span>
              <Link href="/dashboard/lead-capture/sources" className="text-[11px] font-semibold text-[#1A1A1A] hover:underline">
                Configure →
              </Link>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-[#D4D0C8] bg-white flex flex-col justify-between shadow-2xs">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#1A1A1A] font-mono">CSV / Excel Imports</span>
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mb-1">
                {metrics?.by_channel?.['CSV'] ?? metrics?.by_channel?.['IMPORT'] ?? 0} leads
              </div>
              <p className="text-[11px] text-[#6B6B6B]">Bulk batch import with column auto-mapping and dedup check.</p>
            </div>
            <div className="mt-4 pt-3 border-t border-[#E5E1DA] flex items-center justify-between">
              <span className="text-[10px] font-mono font-bold text-emerald-700">LIVE</span>
              <Link href="/dashboard/lead-capture/import" className="text-[11px] font-semibold text-[#1A1A1A] hover:underline">
                Upload CSV →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Lead Sources Health Table */}
      <div className="bg-[#FAF7F2] rounded-2xl border border-[#D4D0C8] shadow-xs overflow-hidden">
        <div className="p-5 border-b border-[#E5E1DA] flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[#1A1A1A] font-mono">Configured Lead Sources</h2>
            <p className="text-xs text-[#6B6B6B]">Manage sources, test ingestion paths, and copy embed credentials.</p>
          </div>
          <Link
            href="/dashboard/lead-capture/sources"
            className="text-xs font-semibold text-[#1A1A1A] hover:underline"
          >
            View All Sources ({metrics?.sources?.length ?? 0}) →
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F0EDE8] border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-5 font-semibold">Source Name</th>
                <th className="py-3 px-5 font-semibold">Channel</th>
                <th className="py-3 px-5 font-semibold">Health Status</th>
                <th className="py-3 px-5 font-semibold text-right">Captured Events</th>
                <th className="py-3 px-5 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E1DA]">
              {metrics?.sources && metrics.sources.length > 0 ? (
                metrics.sources.slice(0, 6).map((s) => (
                  <tr key={s.id} className="hover:bg-[#F5F0EB] transition-colors">
                    <td className="py-3.5 px-5 font-bold font-mono text-[#1A1A1A]">
                      {s.name}
                    </td>
                    <td className="py-3.5 px-5 text-[#4A4A4A] font-medium">
                      {s.channel}
                    </td>
                    <td className="py-3.5 px-5">
                      {getHealthBadge(s.health)}
                    </td>
                    <td className="py-3.5 px-5 text-right font-mono font-semibold text-[#1A1A1A]">
                      {s.total_events}
                    </td>
                    <td className="py-3.5 px-5 text-right">
                      <button
                        onClick={() => handleRunTestLead(s.id, s.name)}
                        disabled={testingSourceId === s.id}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-white hover:bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] rounded-lg font-semibold text-[11px] transition cursor-pointer shadow-2xs"
                      >
                        <Play className={`w-3 h-3 ${testingSourceId === s.id ? 'animate-spin' : ''}`} />
                        {testingSourceId === s.id ? 'Simulating...' : 'Send Test Lead'}
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-[#6B6B6B] font-mono">
                    No lead sources configured yet. Click &quot;New Lead Source&quot; to create your first ingestion channel.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Real-time Ingestion Activity Stream */}
      <div className="bg-[#FAF7F2] rounded-2xl border border-[#D4D0C8] shadow-xs overflow-hidden">
        <div className="p-5 border-b border-[#E5E1DA] flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[#1A1A1A] font-mono">Recent Ingestion Activity</h2>
            <p className="text-xs text-[#6B6B6B]">Live provenance feed of inbound lead signals.</p>
          </div>
          <Link
            href="/dashboard/lead-capture/events"
            className="text-xs font-semibold text-[#1A1A1A] hover:underline"
          >
            Full Ingestion Log & DLQ →
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F0EDE8] border-b border-[#D4D0C8] text-[#6B6B6B] font-mono uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-5 font-semibold">Event ID</th>
                <th className="py-3 px-5 font-semibold">Source</th>
                <th className="py-3 px-5 font-semibold">Channel</th>
                <th className="py-3 px-5 font-semibold">Status</th>
                <th className="py-3 px-5 font-semibold text-right">Received At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E1DA]">
              {recentEvents && recentEvents.length > 0 ? (
                recentEvents.map((ev) => (
                  <tr key={ev.id} className="hover:bg-[#F5F0EB] transition-colors">
                    <td className="py-3.5 px-5 font-mono text-[11px] text-[#6B6B6B]">
                      {ev.id.slice(0, 12)}...
                    </td>
                    <td className="py-3.5 px-5 font-semibold text-[#1A1A1A] font-mono">
                      {ev.source_name || 'Direct'}
                    </td>
                    <td className="py-3.5 px-5 text-[#4A4A4A] font-medium">
                      {ev.channel}
                    </td>
                    <td className="py-3.5 px-5">
                      {getStatusBadge(ev.status)}
                    </td>
                    <td className="py-3.5 px-5 text-right text-[#6B6B6B] font-mono text-[11px]">
                      {ev.received_at ? new Date(ev.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Just now'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-[#6B6B6B] font-mono">
                    No ingestion activity recorded yet. Submissions from website forms and webhooks will appear here in real-time.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </PageContainer>
  );
}
