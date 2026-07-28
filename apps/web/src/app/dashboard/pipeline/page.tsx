'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Phone, Clock, TableIcon, LayoutGrid, AlertCircle } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { Lead } from '@/types';

const STAGE_COLUMNS = [
  { id: 'new', label: 'NEW', color: '#0D9488' },
  { id: 'contacted', label: 'CONTACTED', color: '#3B82F6' },
  { id: 'viewing', label: 'VIEWING SCHEDULED', color: '#F59E0B' },
  { id: 'negotiating', label: 'NEGOTIATING', color: '#EF4444' },
  { id: 'closed_won', label: 'CLOSED WON', color: '#10B981' },
  { id: 'closed_lost', label: 'CLOSED LOST', color: '#6B7280' },
];

function ScorePill({ score }: { score: string }) {
  const configs: Record<string, { label: string; cls: string }> = {
    hot: { label: '🔥 HOT', cls: 'bg-[#FEF3C7] text-[#B45309]' },
    warm: { label: '🟡 WARM', cls: 'bg-[#E0E7FF] text-[#4338CA]' },
    cold: { label: '❄️ COLD', cls: 'bg-[#DBEAFE] text-[#1D4ED8]' },
    pending: { label: '⏳ ...', cls: 'bg-[#F5F0EB] text-[#6B6B6B]' },
  };
  const c = configs[score?.toLowerCase()] || configs.pending;
  return <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${c.cls}`}>{c.label}</span>;
}

function LeadCard({ lead, onStageChange, index = 0 }: { lead: Lead; onStageChange: (id: string, stage: string) => void; index?: number }) {
  const currentStage = (lead.pipeline_stage || lead.stage_name || 'new').toLowerCase();

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.03 }}
      whileHover={{ y: -2 }}
      className="bg-white border border-[#D4D0C8] rounded-xl p-3.5 mb-2.5 hover:border-[#B0ACA4] transition-all shadow-sm cursor-pointer"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h4 className="text-[13px] font-semibold text-[#1A1A1A] truncate leading-tight" style={{ fontFamily: 'Inter, sans-serif' }}>
          {lead.name || 'New Lead'}
        </h4>
        <ScorePill score={lead.score} />
      </div>

      <div className="text-[13px] font-bold text-[#0D9488] mb-1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
        {lead.budget_min ? `₹${(lead.budget_min/100000).toFixed(0)}L-${((lead.budget_max||lead.budget_min)/100000).toFixed(0)}L` : 'Budget Unspecified'}
      </div>

      <div className="text-[12px] text-[#4A4A4A] truncate mb-2.5" style={{ fontFamily: 'Inter, sans-serif' }}>
        {(lead.preferred_locations || []).join(', ') || 'Bengaluru'}
      </div>

      {lead.notes && lead.notes.length > 0 && (
        <div className="flex items-center gap-1.5 p-2 rounded-lg bg-[#FEF3C7]/60 border border-[#FDE68A] mb-2.5">
          <Clock className="w-3 h-3 text-[#B45309] shrink-0" />
          <span className="text-[10px] text-[#B45309] font-semibold truncate">📌 {lead.notes[0].content}</span>
        </div>
      )}

      <div
        className="flex items-center justify-between pt-2 border-t border-[#F0EDE8]"
        onClick={(e) => e.stopPropagation()}
      >
        <select
          value={currentStage}
          onChange={(e) => onStageChange(lead.id, e.target.value)}
          className="text-[10px] bg-[#FAF7F2] border border-[#D4D0C8] rounded-md px-2 py-1 text-[#4A4A4A] font-semibold focus:outline-none focus:border-[#1A1A1A] cursor-pointer"
        >
          {STAGE_COLUMNS.map((s) => (
            <option key={s.id} value={s.id}>{s.label}</option>
          ))}
        </select>
        <a
          href={`tel:${lead.phone}`}
          className="flex items-center gap-1 text-[11px] font-semibold text-[#0D9488] hover:text-[#0F766E] transition-colors"
        >
          <Phone className="w-3 h-3" />
          Call
        </a>
      </div>
    </motion.div>
  );
}

export default function PipelinePage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchLeads = async () => {
    try {
      const res = await api.getLeads();
      setLeads(res.data || (res as any).items || []);
    } catch (e) {
      console.warn('Failed to load pipeline leads', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const handleStageChange = async (id: string, stage: string) => {
    setLeads((prev) => prev.map((l) => l.id === id ? { ...l, pipeline_stage: stage, stage_name: stage } : l));
    try {
      await api.updateLeadStage(id, stage);
    } catch (err: any) {
      alert(err.message || 'Failed updating stage');
      fetchLeads();
    }
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
                PIPELINE BOARD
              </h1>
              <p className="text-[14px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                Move leads between pipeline stages to keep your real estate deals organized.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl">
                <button className="px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 bg-[#1A1A1A] text-white">
                  <LayoutGrid className="w-3.5 h-3.5" />
                  Pipeline View
                </button>
                <Link
                  href="/dashboard/leads"
                  className="px-3 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 text-[#6B6B6B] hover:text-[#1A1A1A]"
                >
                  <TableIcon className="w-3.5 h-3.5" />
                  Table View
                </Link>
              </div>
            </div>
          </div>

          {/* ── Summary Row ── */}
          <div className="py-4 flex items-center gap-4 overflow-x-auto no-scrollbar">
            {STAGE_COLUMNS.map((col) => {
              const count = leads.filter(l => (l.pipeline_stage || l.stage_name || 'new').toLowerCase() === col.id).length;
              return (
                <div key={col.id} className="flex items-center gap-2 shrink-0">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: col.color }} />
                  <span className="text-[11px] font-bold text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    {col.label}: <span className="text-[#1A1A1A]">{count}</span>
                  </span>
                </div>
              );
            })}
          </div>

          {/* ── Kanban Board ── */}
          <div className="pb-10 overflow-x-auto no-scrollbar">
            <div className="flex gap-3 min-w-[1300px]">
              {STAGE_COLUMNS.map((col) => {
                const colLeads = leads.filter(l => (l.pipeline_stage || l.stage_name || 'new').toLowerCase() === col.id);
                return (
                  <div key={col.id} className="flex-1 flex flex-col">
                    <div className="flex items-center justify-between mb-2.5 px-0.5">
                      <span
                        className="text-[11px] font-extrabold tracking-wider"
                        style={{ color: col.color, fontFamily: 'JetBrains Mono, monospace' }}
                      >
                        {col.label}
                      </span>
                      <span
                        className="text-[11px] font-bold text-[#6B6B6B] bg-[#FAF7F2] border border-[#D4D0C8] px-2 py-0.5 rounded-full"
                        style={{ fontFamily: 'JetBrains Mono, monospace' }}
                      >
                        {colLeads.length}
                      </span>
                    </div>

                    <div
                      className="bg-[#FAF7F2]/60 border border-[#D4D0C8] rounded-2xl p-2.5 flex-1 min-h-[420px] overflow-y-auto shadow-inner"
                      style={{ borderTop: `3px solid ${col.color}` }}
                    >
                      {colLeads.length > 0 ? (
                        colLeads.map((lead, idx) => (
                          <LeadCard key={lead.id} lead={lead} onStageChange={handleStageChange} index={idx} />
                        ))
                      ) : (
                        <div className="h-full flex items-center justify-center py-12">
                          <p className="text-[12px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
                            No leads
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
