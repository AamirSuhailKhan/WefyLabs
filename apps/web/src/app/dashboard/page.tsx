'use client';

import { useEffect, useState } from 'react';
import { RefreshCw, Download, LayoutGrid, Table as TableIcon, Zap, Sparkles } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Lead } from '@/types';
import StatsCards from '@/components/dashboard/StatsCards';
import LeadTable from '@/components/dashboard/LeadTable';
import KanbanBoard from '@/components/dashboard/KanbanBoard';
import NewLeadModal from '@/components/dashboard/NewLeadModal';
import LeadDrawer from '@/components/leads/LeadDrawer';
import DashboardNav from '@/components/shared/DashboardNav';
import CommandCenterView from '@/components/dashboard/CommandCenterView';
import RevenueAutopilotView from '@/components/dashboard/RevenueAutopilotView';

export default function DashboardPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'command_center' | 'autopilot' | 'kanban' | 'table'>('command_center');
  const [ccSummary, setCcSummary] = useState<any>(null);
  const [revenueOverview, setRevenueOverview] = useState<any>(null);

  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const [leadsRes, ccRes, revRes] = await Promise.allSettled([
        api.getLeads(),
        api.commandCenter.getData().catch(() => null),
        api.revenueIntelligence.getOverview().catch(() => null)
      ]);

      if (leadsRes.status === 'fulfilled' && leadsRes.value) {
        setLeads(leadsRes.value.items || (leadsRes.value as any).data || []);
      }
      if (ccRes.status === 'fulfilled' && ccRes.value) {
        const payload = (ccRes.value as any)?.data ?? ccRes.value;
        setCcSummary(payload?.summary || null);
      }
      if (revRes.status === 'fulfilled' && revRes.value) {
        setRevenueOverview(revRes.value);
      }
    } catch (e) {
      console.error('Error fetching dashboard data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const handleUpdateStage = async (leadId: string, stageName: string) => {
    try {
      await api.updateLeadStage(leadId, stageName);
      setLeads(prev => prev.map(l => l.id === leadId ? { ...l, stage_name: stageName } : l));
    } catch (e) {
      console.error('Failed to update stage:', e);
    }
  };

  const handleOpenDrawer = (leadId: string) => {
    setSelectedLeadId(leadId);
    setIsDrawerOpen(true);
  };

  const handleExportCSV = () => {
    if (!leads.length) return;
    const headers = ['Name', 'Phone', 'Stage', 'Score', 'Confidence', 'Budget Min', 'Budget Max', 'Type', 'Locations', 'Timeline', 'Status'];
    const rows = leads.map(l => [
      l.name || 'Lead',
      l.phone,
      l.stage_name || 'New',
      l.score,
      `${Math.round(l.score_confidence * 100)}%`,
      l.budget_min || '',
      l.budget_max || '',
      l.property_type || '',
      (l.preferred_locations || []).join('; '),
      l.timeline || '',
      l.status
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `wefylabs_export_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const firstContactBreaches = ccSummary?.first_contact_breaches ?? 0;
  const overdueFollowups = ccSummary?.followup_overdue ?? 0;
  const todayScheduled = ccSummary?.today_scheduled_events ?? 0;
  const hotLeadsCount = ccSummary?.active_hot_leads ?? leads.filter(l => l.score === 'hot').length;
  const revenueAtRisk = revenueOverview?.revenue_at_risk_estimate;

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      {/* Dashboard-specific nav */}
      <DashboardNav onAddLead={() => setIsModalOpen(true)} />

      {/* Content — pushed below fixed 64px nav */}
      <div className="pt-16">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">

          {/* ── Today's Urgent Layer Banner ── */}
          <div className="mt-6 p-4 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-xs">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#0F766E]">
                    Today&apos;s Operational Truth
                  </span>
                  <span className="text-xs text-gray-400 font-mono">
                    {new Date().toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-[#1A1A1A] mt-0.5" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  REVENUE COMMAND COCKPIT
                </h2>
              </div>

              {/* Today Quick Metric Pills */}
              <div className="flex items-center gap-2.5 flex-wrap">
                {firstContactBreaches > 0 ? (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-xs font-bold">
                    <span className="w-2 h-2 rounded-full bg-red-600 animate-pulse" />
                    <span>{firstContactBreaches} SLA Breaches</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span>SLA Clean</span>
                  </div>
                )}

                {overdueFollowups > 0 && (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-semibold">
                    <span>⚠️ {overdueFollowups} Follow-ups Overdue</span>
                  </div>
                )}

                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-semibold">
                  <span>📅 {todayScheduled} Events Today</span>
                </div>

                <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-teal-50 border border-teal-200 text-teal-800 text-xs font-semibold">
                  <span>🔥 {hotLeadsCount} Hot Inquiries</span>
                </div>

                {revenueAtRisk !== undefined && revenueAtRisk !== null && revenueAtRisk > 0 && (
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-bold font-mono">
                    <span>Risk: AED {Number(revenueAtRisk).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Page Header & Controls ── */}
          <div className="py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8]">
            <div>
              <h1
                className="text-[24px] sm:text-[26px] font-bold text-[#1A1A1A] tracking-tight leading-tight"
                style={{ fontFamily: 'JetBrains Mono, monospace' }}
              >
                OPERATIONAL COMMAND CENTER
              </h1>
              <p className="text-[13px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                Prioritized queue, real-time SLA monitors, automated qualification, and deal execution.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* View Toggle */}
              <div className="flex items-center bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl flex-wrap">
                <button
                  onClick={() => setViewMode('command_center')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all ${
                    viewMode === 'command_center'
                      ? 'bg-[#1A1A1A] text-white shadow-sm'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  <Zap className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                  Command Center
                </button>
                <button
                  onClick={() => setViewMode('autopilot')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all ${
                    viewMode === 'autopilot'
                      ? 'bg-[#1A1A1A] text-white shadow-sm'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 text-teal-400 fill-teal-400" />
                  Revenue Autopilot
                </button>
                <button
                  onClick={() => setViewMode('kanban')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all ${
                    viewMode === 'kanban'
                      ? 'bg-[#1A1A1A] text-white shadow-sm'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  Pipeline Board
                </button>
                <button
                  onClick={() => setViewMode('table')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all ${
                    viewMode === 'table'
                      ? 'bg-[#1A1A1A] text-white shadow-sm'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  <TableIcon className="w-3.5 h-3.5" />
                  Leads Table
                </button>
              </div>


              {/* Refresh */}
              <button
                onClick={fetchLeads}
                disabled={loading}
                title="Refresh leads"
                className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg transition-all"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-[#0D9488]' : ''}`} />
              </button>

              {/* Export */}
              <button
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 px-3 py-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg text-[11px] font-bold transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Export Excel</span>
              </button>

              {/* Add Lead — lime CTA */}
              <button
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[11px] font-bold transition-all"
              >
                + Add New Lead
              </button>
            </div>
          </div>

          {/* ── Main View: Revenue Autopilot vs Command Center vs Kanban vs Table ── */}
          <div className="py-6">
            {viewMode === 'autopilot' ? (
              <RevenueAutopilotView
                onOpenLead={handleOpenDrawer}
                onOpenProperty={(propId) => window.open(`/dashboard/properties?id=${propId}`, '_blank')}
              />
            ) : viewMode === 'command_center' ? (
              <CommandCenterView
                onOpenLead={handleOpenDrawer}
                onRefresh={fetchLeads}
              />
            ) : (
              <>
                <div className="mb-6">
                  <StatsCards leads={leads} />
                </div>
                {viewMode === 'kanban' ? (
                  <KanbanBoard
                    leads={leads}
                    onSelectLead={handleOpenDrawer}
                    onUpdateStage={handleUpdateStage}
                  />
                ) : (
                  <LeadTable
                    leads={leads}
                    onRefresh={fetchLeads}
                    onSelectLead={handleOpenDrawer}
                  />
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Lead Detail Drawer */}
      <LeadDrawer
        leadId={selectedLeadId}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onLeadUpdated={fetchLeads}
      />

      {/* Add Lead Modal */}
      <NewLeadModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={fetchLeads}
      />
    </div>
  );
}
