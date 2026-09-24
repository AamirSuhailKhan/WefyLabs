'use client';

import { use, useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Users, ArrowLeft, Phone, Mail, MapPin, Calendar, Clock, 
  Target, CheckSquare, MessageSquare, Activity, ShieldCheck, 
  Sparkles, DollarSign, Home, Plus
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { Customer360Response } from '@/types/crm';
import { LeadIntelligencePanel } from '@/components/analytics/LeadIntelligencePanel';

export default function Customer360Page({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const customerId = resolvedParams.id;

  const [customer, setCustomer] = useState<Customer360Response | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'properties' | 'timeline' | 'tasks' | 'deals'>('overview');
  const [noteContent, setNoteContent] = useState('');
  const [taskTitle, setTaskTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchCustomer = async () => {
    setLoading(true);
    try {
      const data = await api.crm.getCustomer360(customerId);
      setCustomer(data);
    } catch (err) {
      console.error('Failed to load customer 360', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomer();
  }, [customerId]);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim() || !customer) return;
    setIsSubmitting(true);
    try {
      await api.crm.createNote({
        lead_id: customer.customer_id,
        content: noteContent
      });
      setNoteContent('');
      await fetchCustomer();
    } catch (err) {
      console.error('Failed to add note', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskTitle.trim() || !customer) return;
    setIsSubmitting(true);
    try {
      await api.crm.createTask({
        title: taskTitle,
        lead_id: customer.customer_id,
        priority: 'normal'
      });
      setTaskTitle('');
      await fetchCustomer();
    } catch (err) {
      console.error('Failed to add task', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
        <DashboardNav />
        <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-32 pb-16 text-center text-[#6B7280]">
          Loading Customer 360 Workspace...
        </main>
      </div>
    );
  }

  if (!customer) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
        <DashboardNav />
        <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-32 pb-16 text-center">
          <p className="text-[#DC2626] font-semibold">Customer record not found or access denied.</p>
          <Link href="/dashboard/crm/customers" className="text-xs text-[#0F766E] underline mt-2 block">
            Return to Customer Directory
          </Link>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 mb-4 text-xs text-[#6B7280]">
          <Link href="/dashboard/crm" className="hover:text-[#111827]">
            CRM Operations
          </Link>
          <span>/</span>
          <Link href="/dashboard/crm/customers" className="hover:text-[#111827]">
            Customers
          </Link>
          <span>/</span>
          <span className="text-[#111827] font-semibold">{customer.name || customer.primary_phone}</span>
        </div>

        {/* Customer Header Card */}
        <div className="bg-white border border-[#E5E7EB] rounded-2xl p-6 shadow-sm mb-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-extrabold text-[#111827]">
                  {customer.name || 'Unnamed Client'}
                </h1>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${
                  customer.temperature === 'hot'
                    ? 'bg-[#FEE2E2] text-[#B91C1C]'
                    : customer.temperature === 'warm'
                    ? 'bg-[#FEF3C7] text-[#B45309]'
                    : 'bg-[#F3F4F6] text-[#4B5563]'
                }`}>
                  {customer.temperature} Lead
                </span>
                <span className="bg-[#E0F2FE] text-[#0369A1] px-2.5 py-0.5 rounded-full text-xs font-bold uppercase">
                  Stage: {customer.pipeline_stage}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-[#4B5563]">
                <span className="flex items-center gap-1.5 font-medium">
                  <Phone className="w-3.5 h-3.5 text-[#0F766E]" />
                  {customer.primary_phone}
                </span>
                {customer.primary_email && (
                  <span className="flex items-center gap-1.5 font-medium">
                    <Mail className="w-3.5 h-3.5 text-[#0F766E]" />
                    {customer.primary_email}
                  </span>
                )}
                <span className="text-[#9CA3AF]">|</span>
                <span>Owner: <strong>{customer.owner_name || 'Assigned Agent'}</strong></span>
                <span>Source: <strong>{customer.source}</strong></span>
                <span>SLA: <strong className="text-[#059669]">{customer.sla_state}</strong></span>
              </div>
            </div>

            {/* Next Best Action Widget */}
            {customer.next_best_action && (
              <div className="bg-[#F0FDF4] border border-[#BBF7D0] p-3.5 rounded-xl max-w-md">
                <div className="flex items-center gap-1.5 text-xs font-bold text-[#15803D]">
                  <Sparkles className="w-4 h-4 text-[#16A34A]" />
                  AI Recommended Next Action
                </div>
                <p className="text-xs text-[#166534] mt-1 font-medium">
                  {customer.next_best_action}
                </p>
              </div>
            )}
          </div>

          {/* Revenue Journey Progress Ribbon */}
          <div className="mt-6 pt-6 border-t border-[#F3F4F6]">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#6B7280] block mb-3">
              Customer Revenue Journey
            </span>
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 text-center text-xs">
              <div className="p-2 rounded-lg bg-[#F9FAFB] border border-[#E5E7EB]">
                <span className="text-[10px] text-[#6B7280] block">Inquiry</span>
                <span className="font-bold text-[#111827]">
                  {new Date(customer.revenue_journey.first_seen_at).toLocaleDateString()}
                </span>
              </div>
              <div className={`p-2 rounded-lg border ${
                customer.revenue_journey.qualified_at ? 'bg-[#ECFDF5] border-[#A7F3D0] text-[#065F46]' : 'bg-[#F9FAFB] border-[#E5E7EB] text-[#9CA3AF]'
              }`}>
                <span className="text-[10px] block">Qualified</span>
                <span className="font-bold">
                  {customer.revenue_journey.qualified_at ? 'Completed' : 'Pending'}
                </span>
              </div>
              <div className={`p-2 rounded-lg border ${
                customer.property_matches.length > 0 ? 'bg-[#ECFDF5] border-[#A7F3D0] text-[#065F46]' : 'bg-[#F9FAFB] border-[#E5E7EB] text-[#9CA3AF]'
              }`}>
                <span className="text-[10px] block">Matches</span>
                <span className="font-bold">
                  {customer.property_matches.length} Props
                </span>
              </div>
              <div className={`p-2 rounded-lg border ${
                customer.appointments.length > 0 ? 'bg-[#ECFDF5] border-[#A7F3D0] text-[#065F46]' : 'bg-[#F9FAFB] border-[#E5E7EB] text-[#9CA3AF]'
              }`}>
                <span className="text-[10px] block">Viewing</span>
                <span className="font-bold">
                  {customer.appointments.length} Booked
                </span>
              </div>
              <div className={`p-2 rounded-lg border ${
                customer.opportunities.length > 0 ? 'bg-[#ECFDF5] border-[#A7F3D0] text-[#065F46]' : 'bg-[#F9FAFB] border-[#E5E7EB] text-[#9CA3AF]'
              }`}>
                <span className="text-[10px] block">Deal State</span>
                <span className="font-bold">
                  {customer.opportunities.length > 0 ? customer.opportunities[0].current_stage : 'None'}
                </span>
              </div>
              <div className={`p-2 rounded-lg border ${
                customer.revenue_journey.recorded_revenue ? 'bg-[#FEF3C7] border-[#FDE68A] text-[#92400E]' : 'bg-[#F9FAFB] border-[#E5E7EB] text-[#9CA3AF]'
              }`}>
                <span className="text-[10px] block">Realized Rev</span>
                <span className="font-bold">
                  {customer.revenue_journey.recorded_revenue
                    ? `${customer.preferences.budget_currency} ${customer.revenue_journey.recorded_revenue.toLocaleString()}`
                    : '—'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex border-b border-[#E5E7EB] mb-6 gap-6 text-sm font-semibold">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-3 transition ${
              activeTab === 'overview'
                ? 'border-b-2 border-[#0F766E] text-[#0F766E]'
                : 'text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Overview &amp; Preferences
          </button>
          <button
            onClick={() => setActiveTab('properties')}
            className={`pb-3 transition ${
              activeTab === 'properties'
                ? 'border-b-2 border-[#0F766E] text-[#0F766E]'
                : 'text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Property Matches ({customer.property_matches.length})
          </button>
          <button
            onClick={() => setActiveTab('timeline')}
            className={`pb-3 transition ${
              activeTab === 'timeline'
                ? 'border-b-2 border-[#0F766E] text-[#0F766E]'
                : 'text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Unified Timeline ({customer.timeline.length})
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`pb-3 transition ${
              activeTab === 'tasks'
                ? 'border-b-2 border-[#0F766E] text-[#0F766E]'
                : 'text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Tasks &amp; Notes ({customer.tasks.length + customer.notes.length})
          </button>
          <button
            onClick={() => setActiveTab('deals')}
            className={`pb-3 transition ${
              activeTab === 'deals'
                ? 'border-b-2 border-[#0F766E] text-[#0F766E]'
                : 'text-[#6B7280] hover:text-[#111827]'
            }`}
          >
            Opportunities ({customer.opportunities.length})
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Preferences Card */}
            <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm">
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider mb-4 flex items-center gap-2">
                <Home className="w-4 h-4 text-[#0F766E]" />
                Buyer Requirements
              </h2>
              <div className="space-y-3 text-xs text-[#374151]">
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Budget Range:</span>
                  <span className="font-semibold text-sm text-[#111827]">
                    {customer.preferences.budget_max
                      ? `${customer.preferences.budget_currency} ${customer.preferences.budget_min?.toLocaleString() ?? 0} – ${customer.preferences.budget_max?.toLocaleString()}`
                      : 'Not specified'}
                  </span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Property Type:</span>
                  <span className="font-semibold text-[#111827]">{customer.preferences.property_type || 'Any'}</span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Transaction Type:</span>
                  <span className="font-semibold text-[#111827] capitalize">{customer.preferences.transaction_type || 'Buy'}</span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Preferred Locations:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {customer.preferences.preferred_locations.length > 0 ? (
                      customer.preferences.preferred_locations.map((loc, i) => (
                        <span key={i} className="bg-[#F3F4F6] text-[#374151] px-2 py-0.5 rounded text-[11px]">
                          {loc}
                        </span>
                      ))
                    ) : (
                      <span className="text-[#9CA3AF]">None listed</span>
                    )}
                  </div>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Purchase Timeline:</span>
                  <span className="font-semibold text-[#111827] capitalize">{customer.preferences.timeline || 'Immediate'}</span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px]">Financing / Loan:</span>
                  <span className="font-semibold text-[#111827] capitalize">{customer.preferences.loan_status || 'Self-funded'}</span>
                </div>
              </div>
            </div>

            {/* Qualification Facts Card */}
            <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm">
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider mb-4 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-[#0F766E]" />
                Qualification Status
              </h2>
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-[#F3F4F6]">
                  <span className="text-[#6B7280]">Status:</span>
                  <span className="font-bold text-[#059669] uppercase">
                    {customer.qualification.status || 'Active'}
                  </span>
                </div>
                <div className="flex items-center justify-between pb-2 border-b border-[#F3F4F6]">
                  <span className="text-[#6B7280]">AI Score Confidence:</span>
                  <span className="font-bold text-[#111827]">
                    {Math.round((customer.qualification.confidence || 0) * 100)}%
                  </span>
                </div>
                <div>
                  <span className="text-[#6B7280] block text-[11px] mb-1">Extracted Facts:</span>
                  {customer.qualification.facts && customer.qualification.facts.length > 0 ? (
                    <div className="space-y-1.5">
                      {customer.qualification.facts.map((f: any, idx: number) => (
                        <div key={idx} className="bg-[#F9FAFB] p-2 rounded border border-[#E5E7EB] text-[11px]">
                          <span className="font-semibold text-[#111827] capitalize">{f.fact_type}: </span>
                          <span className="text-[#4B5563]">{f.value}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[#9CA3AF]">No individual qualification facts parsed yet.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Actions & Notes Card */}
            <div className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm">
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider mb-4 flex items-center gap-2">
                <Plus className="w-4 h-4 text-[#0F766E]" />
                Quick Touchpoint
              </h2>

              <form onSubmit={handleAddNote} className="mb-4">
                <label className="text-[11px] font-semibold text-[#6B7280] block mb-1">
                  Log Internal CRM Note
                </label>
                <textarea
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="Record call summary, client feedback, or objection..."
                  rows={3}
                  className="w-full p-2.5 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                />
                <button
                  type="submit"
                  disabled={isSubmitting || !noteContent.trim()}
                  className="mt-2 w-full py-1.5 bg-[#111827] text-white text-xs font-semibold rounded-lg hover:bg-[#1F2937] transition disabled:opacity-50"
                >
                  Save Note
                </button>
              </form>

              <form onSubmit={handleAddTask}>
                <label className="text-[11px] font-semibold text-[#6B7280] block mb-1">
                  Create Follow-Up Task
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={taskTitle}
                    onChange={(e) => setTaskTitle(e.target.value)}
                    placeholder="e.g. Call client with updated price"
                    className="flex-1 p-2 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E]"
                  />
                  <button
                    type="submit"
                    disabled={isSubmitting || !taskTitle.trim()}
                    className="px-3 py-2 bg-[#0F766E] text-white text-xs font-semibold rounded-lg hover:bg-[#0D655E] transition disabled:opacity-50"
                  >
                    Add
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Part 16 — Predictive Intelligence Panel */}
          <div className="mt-4">
            <LeadIntelligencePanel
              leadId={customerId}
              className="shadow-sm"
            />
          </div>
          </>
        )}

        {/* Tab Content: Property Matches */}
        {activeTab === 'properties' && (
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-bold text-[#111827] mb-4">Recommended &amp; Matched Properties</h2>
            {customer.property_matches.length === 0 ? (
              <p className="text-xs text-[#6B7280] py-6 text-center">
                No matching properties recorded yet. Run matching engine from Lead Intelligence.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {customer.property_matches.map((p, i) => (
                  <div key={i} className="p-4 border border-[#E5E7EB] rounded-lg bg-[#F9FAFB]">
                    <div className="flex items-center justify-between text-xs mb-2">
                      <span className="font-bold text-[#111827]">Property ID: {p.property_id}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#CCFBF1] text-[#0F766E]">
                        {p.match_score}% Match
                      </span>
                    </div>
                    <p className="text-xs text-[#4B5563]">
                      Interest Level: <strong className="capitalize">{p.interest_level}</strong>
                    </p>
                    {p.notes && <p className="text-xs text-[#6B7280] mt-1">{p.notes}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab Content: Unified Timeline */}
        {activeTab === 'timeline' && (
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-bold text-[#111827] mb-4">Unified Activity &amp; Event Timeline</h2>
            {customer.timeline.length === 0 ? (
              <p className="text-xs text-[#6B7280] py-6 text-center">
                No timeline events recorded yet.
              </p>
            ) : (
              <div className="relative border-l-2 border-[#E5E7EB] ml-3 pl-6 space-y-6">
                {customer.timeline.map((event) => (
                  <div key={event.id} className="relative">
                    <div className="absolute -left-[31px] top-0.5 w-3.5 h-3.5 rounded-full bg-[#0F766E] border-2 border-white shadow-sm" />
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-[#111827]">{event.title}</span>
                      <span className="text-[11px] text-[#9CA3AF]">
                        {new Date(event.timestamp).toLocaleString()}
                      </span>
                    </div>
                    {event.description && (
                      <p className="text-xs text-[#4B5563] mt-1">{event.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-[#6B7280]">
                      <span className="px-1.5 py-0.5 bg-[#F3F4F6] rounded uppercase font-semibold">
                        Actor: {event.actor_type}
                      </span>
                      {event.channel && (
                        <span className="px-1.5 py-0.5 bg-[#EFF6FF] text-[#2563EB] rounded uppercase font-semibold">
                          {event.channel}
                        </span>
                      )}
                      <span>Source: {event.source}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab Content: Tasks & Notes */}
        {activeTab === 'tasks' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider mb-4">
                Assigned CRM Tasks ({customer.tasks.length})
              </h2>
              {customer.tasks.length === 0 ? (
                <p className="text-xs text-[#6B7280]">No tasks assigned.</p>
              ) : (
                <div className="space-y-2">
                  {customer.tasks.map((t) => (
                    <div key={t.id} className="p-3 bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg text-xs">
                      <div className="flex items-center justify-between font-semibold text-[#111827]">
                        <span>{t.title}</span>
                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase ${
                          t.status === 'completed' ? 'bg-[#D1FAE5] text-[#065F46]' : 'bg-[#FEF3C7] text-[#92400E]'
                        }`}>
                          {t.status}
                        </span>
                      </div>
                      {t.description && <p className="text-[#4B5563] mt-1">{t.description}</p>}
                      {t.due_at && (
                        <p className="text-[11px] text-[#6B7280] mt-1">
                          Due: {new Date(t.due_at).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
              <h2 className="text-sm font-bold text-[#111827] uppercase tracking-wider mb-4">
                Internal Notes ({customer.notes.length})
              </h2>
              {customer.notes.length === 0 ? (
                <p className="text-xs text-[#6B7280]">No notes added.</p>
              ) : (
                <div className="space-y-2">
                  {customer.notes.map((n) => (
                    <div key={n.id} className="p-3 bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg text-xs">
                      <p className="text-[#111827]">{n.content}</p>
                      <span className="text-[10px] text-[#9CA3AF] mt-1.5 block">
                        {new Date(n.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab Content: Opportunities & Deals */}
        {activeTab === 'deals' && (
          <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm">
            <h2 className="text-base font-bold text-[#111827] mb-4">Commercial Deals &amp; Opportunities</h2>
            {customer.opportunities.length === 0 ? (
              <p className="text-xs text-[#6B7280] py-6 text-center">
                No active deals created for this client yet.
              </p>
            ) : (
              <div className="space-y-3">
                {customer.opportunities.map((d) => (
                  <div key={d.id} className="p-4 border border-[#E5E7EB] rounded-xl bg-[#F9FAFB] flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-sm text-[#111827]">{d.deal_name}</h3>
                      <p className="text-xs text-[#6B7280] mt-0.5">
                        Stage: <strong className="uppercase">{d.current_stage}</strong> | Closing Prob: {d.closing_probability_pct}%
                      </p>
                    </div>
                    <div className="text-right">
                      <span className="text-base font-extrabold text-[#111827]">
                        {d.currency} {d.agreed_price.toLocaleString()}
                      </span>
                      <span className="text-xs text-[#059669] block">
                        Est. Commission: {d.currency} {d.estimated_commission_amount.toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
