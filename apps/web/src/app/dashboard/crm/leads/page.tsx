'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Users, Filter, Search, ArrowLeft, ArrowUpRight, CheckSquare, 
  MoreHorizontal, Plus, RefreshCw, AlertCircle
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { LeadCRMListItem } from '@/types/crm';

export default function CRMLeadsOperatorPage() {
  const [leads, setLeads] = useState<LeadCRMListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  
  // Filter state
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState('');
  const [scoreFilter, setScoreFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');

  // Bulk operation state
  const [bulkAction, setBulkAction] = useState('');
  const [bulkStage, setBulkStage] = useState('contacted');
  const [isExecutingBulk, setIsExecutingBulk] = useState(false);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const res = await api.crm.getLeads({
        search: search || undefined,
        stage: stageFilter || undefined,
        score: scoreFilter || undefined,
        source: sourceFilter || undefined,
        limit: 50
      });
      setLeads(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to load CRM leads', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [stageFilter, scoreFilter, sourceFilter]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchLeads();
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === leads.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(leads.map((l) => l.id));
    }
  };

  const toggleSelectOne = (id: string) => {
    if (selectedIds.includes(id)) {
      setSelectedIds(selectedIds.filter((item) => item !== id));
    } else {
      setSelectedIds([...selectedIds, id]);
    }
  };

  const handleStageChange = async (leadId: string, newStage: string) => {
    try {
      await api.crm.updateLeadStage(leadId, { new_stage: newStage });
      await fetchLeads();
    } catch (err) {
      console.error('Stage transition failed', err);
    }
  };

  const handleBulkExecute = async () => {
    if (selectedIds.length === 0 || !bulkAction) return;
    setIsExecutingBulk(true);
    try {
      await api.crm.bulkLeads({
        operation: bulkAction,
        lead_ids: selectedIds,
        params: bulkAction === 'change_stage' ? { stage: bulkStage } : {}
      });
      setSelectedIds([]);
      setBulkAction('');
      await fetchLeads();
    } catch (err) {
      console.error('Bulk operation failed', err);
    } finally {
      setIsExecutingBulk(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 mb-4 text-xs text-[#6B7280]">
          <Link href="/dashboard/crm" className="hover:text-[#111827] flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            CRM Operations
          </Link>
          <span>/</span>
          <span className="text-[#111827] font-semibold">Lead Operator Table</span>
        </div>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">Lead Operator Table</h1>
            <p className="text-xs text-[#4B5563] mt-1">
              Active commercial workspace for lead triage, assignment, stage transitions, and bulk updates.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchLeads()}
              className="p-2 border border-[#E5E7EB] bg-white rounded-lg hover:bg-[#F3F4F6] text-[#374151] transition"
              title="Refresh leads"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <Link
              href="/dashboard/pipeline"
              className="px-4 py-2 border border-[#D1D5DB] bg-white text-xs font-semibold rounded-lg hover:bg-[#F3F4F6] transition text-[#374151]"
            >
              Pipeline View
            </Link>
          </div>
        </div>

        {/* Filters Toolbar */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-4 shadow-sm mb-6 flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-[#9CA3AF]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search name, phone, email..."
                className="w-full pl-9 pr-4 py-1.5 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
              />
            </div>
          </form>

          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="py-1.5 px-3 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E] text-[#374151]"
          >
            <option value="">All Stages</option>
            <option value="new">New</option>
            <option value="contacted">Contacted</option>
            <option value="qualified">Qualified</option>
            <option value="matched">Matched</option>
            <option value="appointment">Appointment</option>
            <option value="site_visit">Site Visit</option>
            <option value="opportunity">Opportunity</option>
            <option value="negotiation">Negotiation</option>
            <option value="won">Closed Won</option>
            <option value="lost">Closed Lost</option>
          </select>

          <select
            value={scoreFilter}
            onChange={(e) => setScoreFilter(e.target.value)}
            className="py-1.5 px-3 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E] text-[#374151]"
          >
            <option value="">All Scores</option>
            <option value="hot">Hot</option>
            <option value="warm">Warm</option>
            <option value="cold">Cold</option>
          </select>

          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="py-1.5 px-3 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E] text-[#374151]"
          >
            <option value="">All Sources</option>
            <option value="manual">Manual</option>
            <option value="meta">Meta Ads</option>
            <option value="google">Google Ads</option>
            <option value="website">Website Form</option>
            <option value="portal">Customer Portal</option>
          </select>

          <span className="text-xs text-[#6B7280]">
            Total: <strong>{total}</strong> leads
          </span>
        </div>

        {/* Floating Bulk Operations Toolbar */}
        {selectedIds.length > 0 && (
          <div className="bg-[#111827] text-white p-3.5 rounded-xl mb-4 flex items-center justify-between shadow-lg text-xs">
            <div className="flex items-center gap-2">
              <span className="font-bold bg-[#0F766E] px-2 py-0.5 rounded text-[11px]">
                {selectedIds.length} Selected
              </span>
              <span>Bulk Operation:</span>
              <select
                value={bulkAction}
                onChange={(e) => setBulkAction(e.target.value)}
                className="bg-[#1F2937] text-white border border-[#374151] rounded px-2.5 py-1"
              >
                <option value="">Select Action...</option>
                <option value="change_stage">Change Pipeline Stage</option>
                <option value="change_priority">Mark Priority</option>
                <option value="create_task">Create Follow-Up Task</option>
              </select>

              {bulkAction === 'change_stage' && (
                <select
                  value={bulkStage}
                  onChange={(e) => setBulkStage(e.target.value)}
                  className="bg-[#1F2937] text-white border border-[#374151] rounded px-2.5 py-1 ml-1"
                >
                  <option value="contacted">Contacted</option>
                  <option value="qualified">Qualified</option>
                  <option value="negotiation">Negotiation</option>
                  <option value="won">Closed Won</option>
                  <option value="lost">Closed Lost</option>
                </select>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleBulkExecute}
                disabled={isExecutingBulk || !bulkAction}
                className="px-4 py-1.5 bg-[#0F766E] hover:bg-[#0D655E] text-white font-semibold rounded disabled:opacity-50 transition"
              >
                {isExecutingBulk ? 'Executing...' : 'Apply to Selected'}
              </button>
              <button
                onClick={() => setSelectedIds([])}
                className="px-3 py-1.5 bg-[#374151] hover:bg-[#4B5563] text-[#D1D5DB] rounded transition"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Operator Table */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#4B5563]">
              <thead className="bg-[#F9FAFB] border-b border-[#E5E7EB] text-[#6B7280] font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-3 w-8">
                    <input
                      type="checkbox"
                      checked={leads.length > 0 && selectedIds.length === leads.length}
                      onChange={toggleSelectAll}
                      className="rounded border-[#D1D5DB] text-[#0F766E] focus:ring-[#0F766E]"
                    />
                  </th>
                  <th className="py-3 px-3">Lead / Customer</th>
                  <th className="py-3 px-3">Stage</th>
                  <th className="py-3 px-3">Temperature</th>
                  <th className="py-3 px-3">Source</th>
                  <th className="py-3 px-3">Budget</th>
                  <th className="py-3 px-3">Assigned Owner</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3F4F6]">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="text-center py-12 text-[#9CA3AF]">
                      Loading operator leads...
                    </td>
                  </tr>
                ) : leads.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-12 text-[#6B7280]">
                      No leads match the specified filter criteria.
                    </td>
                  </tr>
                ) : (
                  leads.map((l) => (
                    <tr key={l.id} className="hover:bg-[#F9FAFB] transition">
                      <td className="py-3.5 px-3">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(l.id)}
                          onChange={() => toggleSelectOne(l.id)}
                          className="rounded border-[#D1D5DB] text-[#0F766E] focus:ring-[#0F766E]"
                        />
                      </td>
                      <td className="py-3.5 px-3 font-semibold text-[#111827]">
                        <Link
                          href={`/dashboard/crm/customers/${l.id}`}
                          className="hover:text-[#0F766E] flex items-center gap-1"
                        >
                          {l.name || 'Unnamed Client'}
                          <ArrowUpRight className="w-3 h-3 text-[#9CA3AF]" />
                        </Link>
                        <span className="text-[11px] text-[#6B7280] font-normal block mt-0.5">
                          {l.phone}
                        </span>
                      </td>
                      <td className="py-3.5 px-3">
                        <select
                          value={l.pipeline_stage}
                          onChange={(e) => handleStageChange(l.id, e.target.value)}
                          className="py-1 px-2 text-xs bg-white border border-[#E5E7EB] rounded font-semibold text-[#0369A1] focus:ring-1 focus:ring-[#0F766E]"
                        >
                          <option value="new">New</option>
                          <option value="contacted">Contacted</option>
                          <option value="qualified">Qualified</option>
                          <option value="matched">Matched</option>
                          <option value="appointment">Appointment</option>
                          <option value="site_visit">Site Visit</option>
                          <option value="opportunity">Opportunity</option>
                          <option value="negotiation">Negotiation</option>
                          <option value="won">Won</option>
                          <option value="lost">Lost</option>
                        </select>
                      </td>
                      <td className="py-3.5 px-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          l.score === 'hot'
                            ? 'bg-[#FEE2E2] text-[#B91C1C]'
                            : l.score === 'warm'
                            ? 'bg-[#FEF3C7] text-[#B45309]'
                            : 'bg-[#F3F4F6] text-[#4B5563]'
                        }`}>
                          {l.score}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-[#374151] capitalize">
                        {l.source}
                      </td>
                      <td className="py-3.5 px-3 font-medium text-[#111827]">
                        {l.budget_max
                          ? `${l.budget_currency} ${l.budget_max.toLocaleString()}`
                          : '—'}
                      </td>
                      <td className="py-3.5 px-3 text-[#4B5563]">
                        {l.owner_name || 'Agent'}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <Link
                          href={`/dashboard/crm/customers/${l.id}`}
                          className="px-2.5 py-1 bg-white border border-[#D1D5DB] rounded text-xs font-semibold text-[#111827] hover:bg-[#F3F4F6] transition inline-block"
                        >
                          Customer 360
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
