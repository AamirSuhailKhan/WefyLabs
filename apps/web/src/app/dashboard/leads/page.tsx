'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Download, Phone, MessageSquare, Edit3, Plus, X } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { Lead } from '@/types';

const STAGE_COLORS: Record<string, string> = {
  'new': '#0D9488',
  'contacted': '#3B82F6',
  'viewing': '#F59E0B',
  'negotiating': '#EF4444',
  'closed_won': '#10B981',
  'closed_lost': '#6B7280',
};

function ScorePill({ score }: { score: string }) {
  const configs: Record<string, { label: string; cls: string }> = {
    hot: { label: '🔥 Hot', cls: 'bg-[#FEF3C7] text-[#B45309]' },
    warm: { label: '🟡 Warm', cls: 'bg-[#E0E7FF] text-[#4338CA]' },
    cold: { label: '❄️ Cold', cls: 'bg-[#DBEAFE] text-[#1D4ED8]' },
    spam: { label: '🚫 Spam', cls: 'bg-[#FEE2E2] text-[#B91C1C]' },
    pending: { label: '⏳ Pending', cls: 'bg-[#F5F0EB] text-[#6B6B6B]' },
  };
  const c = configs[score?.toLowerCase()] || configs.pending;
  return (
    <span className={`inline-flex items-center text-[11px] font-bold px-2.5 py-1 rounded-full ${c.cls}`}>
      {c.label}
    </span>
  );
}

function SourceBadge({ source }: { source?: string }) {
  const s = (source || 'manual').toLowerCase();
  let label = 'Manual';
  let cls = 'bg-[#F5F0EB] text-[#4A4A4A] border-[#D4D0C8]';

  if (s.includes('web') || s.includes('site') || s.includes('form')) {
    label = '🌐 Website';
    cls = 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]';
  } else if (s.includes('ai') || s.includes('chat') || s.includes('agent')) {
    label = '🤖 AI Chat';
    cls = 'bg-[#F3E8FF] text-[#7E22CE] border-[#E9D5FF]';
  } else if (s.includes('csv') || s.includes('import') || s.includes('batch')) {
    label = '📁 CSV Import';
    cls = 'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]';
  } else if (s.includes('meta') || s.includes('facebook') || s.includes('ad') || s.includes('campaign')) {
    label = '📢 Paid Ad';
    cls = 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]';
  } else if (s.includes('webhook') || s.includes('api')) {
    label = '⚡ API/Webhook';
    cls = 'bg-[#EEF2FF] text-[#4338CA] border-[#C7D2FE]';
  } else if (s.includes('referral')) {
    label = '🤝 Referral';
    cls = 'bg-[#FAE8FF] text-[#86198F] border-[#F5D0FE]';
  } else if (s.includes('email')) {
    label = '✉️ Email';
    cls = 'bg-[#CCFBF1] text-[#0F766E] border-[#99F6E4]';
  }

  return (
    <span
      className={`inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded border ${cls}`}
      style={{ fontFamily: 'JetBrains Mono, monospace' }}
    >
      {label}
    </span>
  );
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [search, setSearch] = useState('');
  const [scoreFilter, setScoreFilter] = useState('all');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New Lead Form State
  const [newLead, setNewLead] = useState({
    name: '',
    phone: '',
    source: 'manual',
    notes: '',
    budget_min: 4000000,
    budget_max: 6000000,
    property_type: '2bhk',
    transaction_type: 'buy',
    preferred_locations: ['Indiranagar'],
    timeline: '1_month',
    loan_status: 'in_process'
  });

  const fetchLeads = async () => {
    try {
      const res = await api.getLeads({
        score: scoreFilter !== 'all' ? scoreFilter : undefined,
        search: search ? search : undefined
      });
      setLeads(res.data || res.items || []);
    } catch (e) {
      console.warn('Failed fetching leads from API', e);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [scoreFilter, search]);

  const totalHot = leads.filter(l => l.score === 'hot').length;
  const totalWarm = leads.filter(l => l.score === 'warm').length;
  const totalCold = leads.filter(l => l.score === 'cold').length;

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLead.phone) return;
    setIsSubmitting(true);
    try {
      const created = await api.createLead(newLead);
      setLeads([created, ...leads]);
      setIsModalOpen(false);
      setNewLead({
        name: '',
        phone: '',
        source: 'manual',
        notes: '',
        budget_min: 4000000,
        budget_max: 6000000,
        property_type: '2bhk',
        transaction_type: 'buy',
        preferred_locations: ['Indiranagar'],
        timeline: '1_month',
        loan_status: 'in_process'
      });
    } catch (err: any) {
      alert(err.message || 'Failed to create lead');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExport = () => {
    const rows = leads.map(l =>
      [l.name || 'N/A', l.phone, l.score, `₹${l.budget_min || 0}-${l.budget_max || 0}`, (l.preferred_locations || []).join(';'), l.pipeline_stage || l.stage_name || 'new', l.source, l.created_at].join(',')
    );
    const csv = 'data:text/csv;charset=utf-8,Name,Phone,Score,Budget,Location,Stage,Source,Created At\n' + rows.join('\n');
    const a = document.createElement('a');
    a.href = encodeURI(csv);
    a.download = `wefylabs_leads_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">

          {/* ── Page Header ── */}
          <div className="py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8]">
            <div>
              <h1
                className="text-[28px] font-bold text-[#1A1A1A] tracking-tight"
                style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
              >
                ALL LEADS
              </h1>
              <p className="text-[14px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                View, filter, and manage every real estate lead in your pipeline.
              </p>
            </div>

            <div className="flex items-center gap-2 flex-wrap w-full sm:w-auto">
              {/* Search */}
              <div className="relative w-full sm:w-auto">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6B6B6B]" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search name, phone..."
                  className="pl-9 pr-4 py-2.5 bg-[#FAF7F2] border border-[#D4D0C8] rounded-lg text-[13px] text-[#1A1A1A] placeholder:text-[#A0A0A0] focus:outline-none focus:border-[#1A1A1A] w-full sm:w-64"
                  style={{ fontFamily: 'Inter, sans-serif' }}
                />
              </div>

              {/* Score filter */}
              <select
                value={scoreFilter}
                onChange={(e) => setScoreFilter(e.target.value)}
                className="px-3 py-2.5 bg-[#FAF7F2] border border-[#D4D0C8] rounded-lg text-[13px] text-[#4A4A4A] focus:outline-none focus:border-[#1A1A1A]"
                style={{ fontFamily: 'Inter, sans-serif' }}
              >
                <option value="all">All Scores</option>
                <option value="hot">🔥 Hot</option>
                <option value="warm">🟡 Warm</option>
                <option value="cold">❄️ Cold</option>
              </select>

              {/* Add New Lead Button */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-[#1A1A1A] hover:bg-[#333333] text-white rounded-lg text-[13px] font-semibold transition-all shadow-sm"
              >
                <Plus className="w-4 h-4" />
                Add New Lead
              </motion.button>

              {/* Export */}
              <motion.button
                whileHover={{ y: -1 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleExport}
                className="flex items-center gap-1.5 px-3 py-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg text-[12px] font-semibold transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                Export CSV
              </motion.button>
            </div>
          </div>

          {/* ── Stats bar ── */}
          <div className="py-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'TOTAL LEADS', value: leads.length, color: '#1A1A1A' },
              { label: 'HOT LEADS', value: totalHot, color: '#B45309' },
              { label: 'WARM LEADS', value: totalWarm, color: '#4338CA' },
              { label: 'COLD LEADS', value: totalCold, color: '#1D4ED8' },
            ].map((stat, idx) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: idx * 0.05 }}
                className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-4 cursor-default"
              >
                <div
                  className="text-[24px] font-extrabold mb-1"
                  style={{ fontFamily: 'JetBrains Mono, monospace', color: stat.color }}
                >
                  {stat.value}
                </div>
                <div className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {stat.label}
                </div>
              </motion.div>
            ))}
          </div>

          {/* ── Leads Table ── */}
          <div className="pb-10">
            <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl overflow-hidden shadow-sm">
              <div className="grid grid-cols-[2fr_1.5fr_1fr_1.5fr_2fr_1.5fr_1fr_auto] bg-[#F5F0EB] border-b border-[#D4D0C8] px-4 py-3 gap-2">
                {['LEAD NAME', 'PHONE', 'SCORE', 'BUDGET', 'LOCATION', 'STAGE', 'SOURCE', 'ACTIONS'].map((col) => (
                  <span key={col} className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    {col}
                  </span>
                ))}
              </div>

              {leads.length === 0 ? (
                <div className="py-12 text-center text-[14px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
                  No leads found. Click "Add New Lead" to create one.
                </div>
              ) : (
                leads.map((lead, i) => (
                  <motion.div
                    key={lead.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25, delay: i * 0.02 }}
                    className={`grid grid-cols-[2fr_1.5fr_1fr_1.5fr_2fr_1.5fr_1fr_auto] px-4 py-4 gap-2 items-center hover:bg-[#F5F0EB]/50 transition-colors border-b border-[#F0EDE8] ${i === leads.length - 1 ? 'border-b-0' : ''}`}
                  >
                    <Link
                      href={`/leads/${lead.id}`}
                      className="text-[14px] font-semibold text-[#1A1A1A] hover:text-[#0D9488] transition-colors truncate"
                      style={{ fontFamily: 'Inter, sans-serif' }}
                    >
                      {lead.name || 'New Lead'}
                    </Link>
                    <span className="text-[13px] text-[#4A4A4A]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {lead.phone}
                    </span>
                    <div>
                      <ScorePill score={lead.score} />
                    </div>
                    <span className="text-[13px] font-bold text-[#0D9488]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {lead.budget_min ? `₹${(lead.budget_min/100000).toFixed(0)}L-${((lead.budget_max||lead.budget_min)/100000).toFixed(0)}L` : 'Unspecified'}
                    </span>
                    <span className="text-[13px] text-[#4A4A4A] truncate" style={{ fontFamily: 'Inter, sans-serif' }}>
                      {(lead.preferred_locations || []).join(', ') || 'Bengaluru'}
                    </span>
                    <span
                      className="text-[11px] font-bold uppercase tracking-wide"
                      style={{ color: STAGE_COLORS[(lead.pipeline_stage || lead.stage_name || 'new').toLowerCase()] || '#6B6B6B', fontFamily: 'JetBrains Mono, monospace' }}
                    >
                      {lead.pipeline_stage || lead.stage_name || 'new'}
                    </span>
                    <div>
                      <SourceBadge source={lead.source} />
                    </div>
                    <div className="flex items-center gap-2">
                      <a href={`tel:${lead.phone}`} title="Call" className="text-[#0D9488] hover:text-[#0F766E] transition-colors">
                        <Phone className="w-4 h-4" />
                      </a>
                      <a href={`https://wa.me/${lead.phone.replace(/\D/g, '')}`} target="_blank" rel="noreferrer" title="WhatsApp" className="text-[#10B981] hover:text-[#059669] transition-colors">
                        <MessageSquare className="w-4 h-4" />
                      </a>
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Add New Lead Modal ── */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl max-w-lg w-full p-6 shadow-2xl relative"
            >
              <div className="flex items-center justify-between pb-4 border-b border-[#D4D0C8] mb-4">
                <h2 className="text-lg font-bold text-[#1A1A1A]">Add New Lead</h2>
                <button onClick={() => setIsModalOpen(false)} className="text-gray-500 hover:text-gray-700">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateLead} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold uppercase text-[#6B6B6B] mb-1">Phone Number *</label>
                  <input
                    type="tel"
                    required
                    value={newLead.phone}
                    onChange={(e) => setNewLead({ ...newLead, phone: e.target.value })}
                    placeholder="+919876543210"
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-lg text-sm focus:outline-none focus:border-[#1A1A1A]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-[#6B6B6B] mb-1">Lead Name</label>
                  <input
                    type="text"
                    value={newLead.name}
                    onChange={(e) => setNewLead({ ...newLead, name: e.target.value })}
                    placeholder="Rajesh Kumar"
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-lg text-sm focus:outline-none focus:border-[#1A1A1A]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold uppercase text-[#6B6B6B] mb-1">Property Type</label>
                    <select
                      value={newLead.property_type}
                      onChange={(e) => setNewLead({ ...newLead, property_type: e.target.value })}
                      className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-lg text-sm focus:outline-none focus:border-[#1A1A1A]"
                    >
                      <option value="1bhk">1BHK</option>
                      <option value="2bhk">2BHK</option>
                      <option value="3bhk">3BHK</option>
                      <option value="villa">Villa</option>
                      <option value="plot">Plot</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-[#6B6B6B] mb-1">Transaction Type</label>
                    <select
                      value={newLead.transaction_type}
                      onChange={(e) => setNewLead({ ...newLead, transaction_type: e.target.value })}
                      className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-lg text-sm focus:outline-none focus:border-[#1A1A1A]"
                    >
                      <option value="buy">Buy</option>
                      <option value="rent">Rent</option>
                      <option value="lease">Lease</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase text-[#6B6B6B] mb-1">Initial Notes</label>
                  <textarea
                    rows={3}
                    value={newLead.notes}
                    onChange={(e) => setNewLead({ ...newLead, notes: e.target.value })}
                    placeholder="Looking for south-facing apartment in Koramangala..."
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-lg text-sm focus:outline-none focus:border-[#1A1A1A]"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t border-[#D4D0C8]">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 text-sm font-semibold rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-2 bg-[#1A1A1A] hover:bg-[#333333] text-white text-sm font-semibold rounded-lg shadow-sm disabled:opacity-50"
                  >
                    {isSubmitting ? 'Saving...' : 'Save Lead'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
