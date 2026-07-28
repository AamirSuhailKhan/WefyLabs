'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Lead } from '@/types';
import { Phone, Clock } from 'lucide-react';

interface KanbanBoardProps {
  leads: Lead[];
  onSelectLead: (leadId: string) => void;
  onUpdateStage: (leadId: string, stageName: string) => void;
}

const STAGE_COLUMNS = [
  { id: 'New',               label: 'NEW',                color: '#0D9488' },
  { id: 'Contacted',         label: 'CONTACTED',          color: '#3B82F6' },
  { id: 'Viewing Scheduled', label: 'VIEWING SCHEDULED',  color: '#F59E0B' },
  { id: 'Negotiating',       label: 'NEGOTIATING',        color: '#EF4444' },
  { id: 'Closed Won',        label: 'CLOSED WON',         color: '#10B981' },
  { id: 'Closed Lost',       label: 'CLOSED LOST',        color: '#6B7280' },
];

function formatBudget(min?: number, max?: number): string {
  if (!min && !max) return 'Budget N/A';
  const fmt = (val: number) => {
    if (val >= 10000000) return `${(val / 10000000).toFixed(1)}Cr`;
    if (val >= 100000)   return `${(val / 100000).toFixed(0)}L`;
    return `${val}`;
  };
  if (min && max) return `₹${fmt(min)}-${fmt(max)}`;
  if (min) return `> ₹${fmt(min)}`;
  return `< ₹${fmt(max!)}`;
}

function ScorePill({ score }: { score?: string }) {
  const s = (score || 'pending').toLowerCase();
  const configs: Record<string, { label: string; cls: string }> = {
    hot:     { label: '🔥 HOT',   cls: 'bg-[#FEF3C7] text-[#B45309]' },
    warm:    { label: '🟡 WARM',  cls: 'bg-[#E0E7FF] text-[#4338CA]' },
    cold:    { label: '❄️ COLD',  cls: 'bg-[#DBEAFE] text-[#1D4ED8]' },
    spam:    { label: '🚫 SPAM',  cls: 'bg-[#FEE2E2] text-[#B91C1C]' },
    pending: { label: '⏳ ...',   cls: 'bg-[#F5F0EB] text-[#6B6B6B]' },
  };
  const c = configs[s] || configs.pending;
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${c.cls}`}>
      {c.label}
    </span>
  );
}

function LoanBadge({ status }: { status?: string }) {
  if (status === 'pre_approved' || status === 'not_needed') {
    return <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#DCFCE7] text-[#15803D] border border-[#BBF7D0]">[Loan: ✅]</span>;
  }
  if (status === 'in_process') {
    return <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#FEF3C7] text-[#B45309] border border-[#FDE68A]">[Loan: ⏳]</span>;
  }
  return <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#F5F0EB] text-[#6B6B6B] border border-[#D4D0C8]">[Loan: ❌]</span>;
}

export default function KanbanBoard({ leads, onSelectLead, onUpdateStage }: KanbanBoardProps) {
  return (
    <div className="w-full overflow-x-auto pb-6 no-scrollbar">
      <div className="flex gap-3 min-w-[1300px]">
        {STAGE_COLUMNS.map((col) => {
          const colLeads = leads.filter((l) => (l.stage_name || 'New') === col.id);

          return (
            <div key={col.id} className="flex-1 flex flex-col">
              {/* Column Header */}
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

              {/* Column Body */}
              <div
                className="bg-[#FAF7F2]/60 border border-[#D4D0C8] rounded-2xl p-2.5 flex-1 min-h-[420px] overflow-y-auto"
                style={{ borderTop: `2.5px solid ${col.color}` }}
              >
                {colLeads.length > 0 ? (
                  <div className="space-y-2.5">
                    {colLeads.map((lead, idx) => {
                      const upcomingTask = lead.tasks?.find(t => t.status === 'pending');

                      return (
                        <motion.div
                          key={lead.id}
                          initial={{ opacity: 0, y: 15 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.35, delay: idx * 0.05, ease: [0.16, 1, 0.3, 1] }}
                          whileHover={{ y: -2 }}
                          onClick={() => onSelectLead(lead.id)}
                          className="bg-white border border-[#D4D0C8] rounded-xl p-3.5 cursor-pointer group transition-all hover:border-[#B0ACA4]"
                        >
                          {/* Name + Score */}
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <h4
                              className="text-[13px] font-semibold text-[#1A1A1A] truncate leading-tight"
                              style={{ fontFamily: 'Inter, sans-serif' }}
                            >
                              {lead.name || 'Unnamed Lead'}
                            </h4>
                            <ScorePill score={lead.score} />
                          </div>

                          {/* Budget */}
                          <div
                            className="text-[13px] font-bold text-[#0D9488] mb-1"
                            style={{ fontFamily: 'JetBrains Mono, monospace' }}
                          >
                            {formatBudget(lead.budget_min, lead.budget_max)}
                          </div>

                          {/* Location */}
                          <div className="text-[12px] text-[#4A4A4A] truncate mb-2.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                            {(lead.preferred_locations || []).join(', ') || 'Bengaluru'}
                          </div>

                          {/* Tags row: Loan + color tags */}
                          <div className="flex items-center flex-wrap gap-1.5 mb-2.5">
                            <LoanBadge status={lead.loan_status} />
                            {lead.tags?.map((t) => (
                              <span
                                key={t.id}
                                className="text-[9px] font-bold px-1.5 py-0.5 rounded border"
                                style={{ backgroundColor: `${t.color}18`, color: t.color, borderColor: `${t.color}30` }}
                              >
                                {t.name}
                              </span>
                            ))}
                          </div>

                          {/* Task Reminder */}
                          {upcomingTask && (
                            <div className="flex items-center gap-1.5 p-2 rounded-lg bg-[#FEF3C7]/60 border border-[#FDE68A] mb-2.5">
                              <Clock className="w-3 h-3 text-[#B45309] shrink-0" />
                              <span className="text-[10px] text-[#B45309] font-semibold truncate">
                                📌 {upcomingTask.title}
                              </span>
                            </div>
                          )}

                          {/* Footer: Stage dropdown + Call */}
                          <div
                            className="flex items-center justify-between pt-2.5 border-t border-[#F0EDE8]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <select
                              value={lead.stage_name || 'New'}
                              onChange={(e) => onUpdateStage(lead.id, e.target.value)}
                              className="text-[10px] bg-[#FAF7F2] border border-[#D4D0C8] rounded-md px-2 py-1 text-[#4A4A4A] font-semibold focus:outline-none focus:border-[#1A1A1A] cursor-pointer"
                              style={{ fontFamily: 'Inter, sans-serif' }}
                            >
                              {STAGE_COLUMNS.map((s) => (
                                <option key={s.id} value={s.id}>{s.id}</option>
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
                    })}
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center">
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
  );
}
