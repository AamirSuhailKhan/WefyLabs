'use client';

import { useEffect, useState } from 'react';
import { RefreshCw, Download, LayoutGrid, Table as TableIcon } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Lead } from '@/types';
import StatsCards from '@/components/dashboard/StatsCards';
import LeadTable from '@/components/dashboard/LeadTable';
import KanbanBoard from '@/components/dashboard/KanbanBoard';
import NewLeadModal from '@/components/dashboard/NewLeadModal';
import LeadDrawer from '@/components/leads/LeadDrawer';
import DashboardNav from '@/components/shared/DashboardNav';

export default function DashboardPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'kanban' | 'table'>('kanban');

  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const data = await api.getLeads();
      setLeads(data.items || []);
    } catch (e) {
      console.error('Error fetching leads:', e);
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
    link.setAttribute('download', `beetlelabs_export_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      {/* Dashboard-specific nav — no announcement banner, no landing CTAs */}
      <DashboardNav onAddLead={() => setIsModalOpen(true)} />

      {/* Content — pushed below fixed 64px nav */}
      <div className="pt-16">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">

          {/* ── Page Header ── */}
          <div className="py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8]">
            <div>
              <h1
                className="text-[26px] sm:text-[28px] font-bold text-[#1A1A1A] tracking-tight leading-tight"
                style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
              >
                BROKER DASHBOARD
              </h1>
              <p className="text-[13px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                Visual pipeline stages, task reminders, free-text notes, color tags &amp; instant qualification.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              {/* View Toggle */}
              <div className="flex items-center bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl">
                <button
                  onClick={() => setViewMode('kanban')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all ${
                    viewMode === 'kanban'
                      ? 'bg-[#1A1A1A] text-white'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  Pipeline
                </button>
                <button
                  onClick={() => setViewMode('table')}
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all ${
                    viewMode === 'table'
                      ? 'bg-[#1A1A1A] text-white'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  <TableIcon className="w-3.5 h-3.5" />
                  Table
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

          {/* ── Stats Cards ── */}
          <div className="py-6">
            <StatsCards leads={leads} />
          </div>

          {/* ── Main View: Kanban vs Table ── */}
          <div className="pb-8">
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
