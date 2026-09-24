'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Users, Target, Calendar, CheckSquare, Activity, DollarSign, 
  Search, Plus, AlertCircle, ArrowUpRight, TrendingUp, Clock, Filter
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { CRMDashboardMetrics, CRMSearchResultItem } from '@/types/crm';

export default function CRMDashboardPage() {
  const [metrics, setMetrics] = useState<CRMDashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<CRMSearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    async function loadMetrics() {
      try {
        const data = await api.crm.getDashboard();
        setMetrics(data);
      } catch (err) {
        console.error('Failed to load CRM dashboard metrics', err);
      } finally {
        setLoading(false);
      }
    }
    loadMetrics();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await api.crm.search(searchQuery);
      setSearchResults(res.results);
    } catch (err) {
      console.error('Search failed', err);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0F766E] bg-[#CCFBF1] px-2.5 py-1 rounded-full">
                Native Real-Estate CRM
              </span>
              <span className="text-xs text-[#6B7280]">
                Zero External CRM Dependencies
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-[#111827] mt-2">
              CRM Operations Cockpit
            </h1>
            <p className="text-sm text-[#4B5563] mt-1">
              Canonical workspace for customer identity, lead progression, pipeline execution, and revenue realization.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/crm/leads"
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#0F766E] text-white text-sm font-semibold rounded-lg hover:bg-[#0D655E] transition shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Manage Leads
            </Link>
            <Link
              href="/dashboard/crm/pipeline"
              className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-[#E5E7EB] text-[#374151] text-sm font-semibold rounded-lg hover:bg-[#F3F4F6] transition shadow-sm"
            >
              <Target className="w-4 h-4 text-[#0F766E]" />
              Pipeline Kanban
            </Link>
          </div>
        </div>

        {/* Global Universal Search Bar */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl p-4 shadow-sm mb-8">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-3 w-4 h-4 text-[#9CA3AF]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Universal Search across Customers, Leads, Deals, Tasks, Properties..."
                className="w-full pl-10 pr-4 py-2 bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg text-sm text-[#111827] placeholder-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#0F766E] focus:bg-white"
              />
            </div>
            <button
              type="submit"
              disabled={isSearching}
              className="px-5 py-2 bg-[#111827] text-white text-sm font-semibold rounded-lg hover:bg-[#1F2937] transition disabled:opacity-50"
            >
              {isSearching ? 'Searching...' : 'Search CRM'}
            </button>
          </form>

          {/* Search Results Dropdown/Box */}
          {searchResults.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[#F3F4F6]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-[#6B7280]">
                  Found {searchResults.length} Results for &quot;{searchQuery}&quot;
                </span>
                <button
                  onClick={() => setSearchResults([])}
                  className="text-xs text-[#6B7280] hover:text-[#111827]"
                >
                  Clear
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {searchResults.map((item) => (
                  <Link
                    key={`${item.entity_type}_${item.id}`}
                    href={item.deep_link}
                    className="p-3 bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg hover:border-[#0F766E] transition block"
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-bold text-[#0F766E] uppercase tracking-wide">
                        {item.entity_type}
                      </span>
                      {item.status && (
                        <span className="bg-[#E5E7EB] text-[#374151] px-1.5 py-0.5 rounded text-[10px]">
                          {item.status}
                        </span>
                      )}
                    </div>
                    <div className="font-semibold text-sm text-[#111827] truncate">
                      {item.title}
                    </div>
                    {item.subtitle && (
                      <div className="text-xs text-[#6B7280] truncate mt-0.5">
                        {item.subtitle}
                      </div>
                    )}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Operational Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm">
            <div className="flex items-center justify-between text-[#6B7280]">
              <span className="text-xs font-semibold uppercase tracking-wider">My Open Leads</span>
              <Users className="w-4 h-4 text-[#0F766E]" />
            </div>
            <div className="text-2xl font-bold text-[#111827] mt-2">
              {loading ? '—' : metrics?.my_open_leads ?? 0}
            </div>
            <div className="text-xs text-[#059669] mt-1 flex items-center gap-1">
              <span>{metrics?.new_leads_today ?? 0} new today</span>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm">
            <div className="flex items-center justify-between text-[#6B7280]">
              <span className="text-xs font-semibold uppercase tracking-wider">Active Pipeline</span>
              <DollarSign className="w-4 h-4 text-[#2563EB]" />
            </div>
            <div className="text-2xl font-bold text-[#111827] mt-2">
              {loading ? '—' : `${metrics?.pipeline_currency ?? 'AED'} ${(metrics?.pipeline_total_value ?? 0).toLocaleString()}`}
            </div>
            <div className="text-xs text-[#4B5563] mt-1">
              {metrics?.active_opportunities_count ?? 0} active deals
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm">
            <div className="flex items-center justify-between text-[#6B7280]">
              <span className="text-xs font-semibold uppercase tracking-wider">Today&apos;s Agenda</span>
              <Calendar className="w-4 h-4 text-[#D97706]" />
            </div>
            <div className="text-2xl font-bold text-[#111827] mt-2">
              {loading ? '—' : metrics?.todays_appointments_count ?? 0}
            </div>
            <div className="text-xs text-[#4B5563] mt-1">
              {metrics?.upcoming_site_visits_count ?? 0} site visits upcoming
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm">
            <div className="flex items-center justify-between text-[#6B7280]">
              <span className="text-xs font-semibold uppercase tracking-wider">Tasks Overdue</span>
              <CheckSquare className="w-4 h-4 text-[#DC2626]" />
            </div>
            <div className="text-2xl font-bold text-[#111827] mt-2">
              {loading ? '—' : metrics?.overdue_tasks_count ?? 0}
            </div>
            <div className="text-xs text-[#6B7280] mt-1">
              Requires immediate action
            </div>
          </div>
        </div>

        {/* Primary CRM Module Nav Cards */}
        <h2 className="text-lg font-bold text-[#111827] mb-4">CRM Workspaces</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <Link
            href="/dashboard/crm/customers"
            className="group p-6 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#0F766E] hover:shadow-md transition"
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-[#CCFBF1] flex items-center justify-center text-[#0F766E]">
                <Users className="w-5 h-5" />
              </div>
              <ArrowUpRight className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#0F766E] transition" />
            </div>
            <h3 className="text-base font-bold text-[#111827] mt-4">Customer 360</h3>
            <p className="text-xs text-[#6B7280] mt-1 leading-relaxed">
              Complete buyer profiles, structured preferences, qualification facts, property shortlist, and unified journey.
            </p>
          </Link>

          <Link
            href="/dashboard/crm/leads"
            className="group p-6 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#0F766E] hover:shadow-md transition"
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-[#EFF6FF] flex items-center justify-center text-[#2563EB]">
                <Filter className="w-5 h-5" />
              </div>
              <ArrowUpRight className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#2563EB] transition" />
            </div>
            <h3 className="text-base font-bold text-[#111827] mt-4">Lead Operator Table</h3>
            <p className="text-xs text-[#6B7280] mt-1 leading-relaxed">
              Multi-filtered operator grid with saved views, SLA monitors, controlled stage progression, and bulk actions.
            </p>
          </Link>

          <Link
            href="/dashboard/crm/pipeline"
            className="group p-6 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#0F766E] hover:shadow-md transition"
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-[#FDF2F8] flex items-center justify-center text-[#DB2777]">
                <Target className="w-5 h-5" />
              </div>
              <ArrowUpRight className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#DB2777] transition" />
            </div>
            <h3 className="text-base font-bold text-[#111827] mt-4">Sales Pipeline Kanban</h3>
            <p className="text-xs text-[#6B7280] mt-1 leading-relaxed">
              Visual deal progression from inquiry to booking, velocity metrics, stagnation tracking, and stage totals.
            </p>
          </Link>

          <Link
            href="/dashboard/crm/tasks"
            className="group p-6 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#0F766E] hover:shadow-md transition"
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-[#FEF3C7] flex items-center justify-center text-[#D97706]">
                <CheckSquare className="w-5 h-5" />
              </div>
              <ArrowUpRight className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#D97706] transition" />
            </div>
            <h3 className="text-base font-bold text-[#111827] mt-4">Task Management</h3>
            <p className="text-xs text-[#6B7280] mt-1 leading-relaxed">
              Follow-up calls, proposal deliveries, and team workload queues categorized by Due Today, Overdue, and Completed.
            </p>
          </Link>

          <Link
            href="/dashboard/crm/activities"
            className="group p-6 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#0F766E] hover:shadow-md transition"
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-[#F3E8FF] flex items-center justify-center text-[#7E22CE]">
                <Activity className="w-5 h-5" />
              </div>
              <ArrowUpRight className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#7E22CE] transition" />
            </div>
            <h3 className="text-base font-bold text-[#111827] mt-4">Activity Audit Feed</h3>
            <p className="text-xs text-[#6B7280] mt-1 leading-relaxed">
              Chronological log of customer touchpoints, calls, emails, site visits, and system lifecycle updates.
            </p>
          </Link>

          <Link
            href="/dashboard/revenue-intelligence"
            className="group p-6 bg-white border border-[#E5E7EB] rounded-xl hover:border-[#0F766E] hover:shadow-md transition"
          >
            <div className="flex items-center justify-between">
              <div className="w-10 h-10 rounded-lg bg-[#ECFDF5] flex items-center justify-center text-[#059669]">
                <TrendingUp className="w-5 h-5" />
              </div>
              <ArrowUpRight className="w-4 h-4 text-[#9CA3AF] group-hover:text-[#059669] transition" />
            </div>
            <h3 className="text-base font-bold text-[#111827] mt-4">Revenue Intelligence</h3>
            <p className="text-xs text-[#6B7280] mt-1 leading-relaxed">
              Funnel leakage detection, source attribution, outcome tracking, and AI revenue optimization feedback loops.
            </p>
          </Link>
        </div>
      </main>
    </div>
  );
}
