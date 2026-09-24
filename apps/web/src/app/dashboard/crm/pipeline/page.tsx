'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Target, ArrowLeft, ArrowUpRight, DollarSign, AlertCircle, 
  ChevronRight, RefreshCw, User
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { PipelineKanbanResponse, PipelineColumn, PipelineCard } from '@/types/crm';

export default function CRMPipelinePage() {
  const [pipeline, setPipeline] = useState<PipelineKanbanResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPipeline = async () => {
    setLoading(true);
    try {
      const data = await api.crm.getPipeline();
      setPipeline(data);
    } catch (err) {
      console.error('Failed to load CRM pipeline', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPipeline();
  }, []);

  const handleAdvanceStage = async (card: PipelineCard, targetStage: string) => {
    try {
      await api.crm.updateLeadStage(card.lead_id, { new_stage: targetStage });
      await fetchPipeline();
    } catch (err) {
      console.error('Stage transition failed', err);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1700px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 mb-4 text-xs text-[#6B7280]">
          <Link href="/dashboard/crm" className="hover:text-[#111827] flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            CRM Operations
          </Link>
          <span>/</span>
          <span className="text-[#111827] font-semibold">Sales Pipeline Kanban</span>
        </div>

        {/* Header with Pipeline Statistics */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">Sales Pipeline Kanban</h1>
            <p className="text-xs text-[#4B5563] mt-1">
              Visual pipeline from initial inquiry through qualification, site visits, negotiation, and closed revenue.
            </p>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <span className="text-[11px] font-semibold text-[#6B7280] block uppercase tracking-wider">
                Total Pipeline Value
              </span>
              <span className="text-xl font-black text-[#111827]">
                AED {(pipeline?.total_pipeline_value ?? 0).toLocaleString()}
              </span>
            </div>
            <div className="text-right border-l border-[#E5E7EB] pl-6">
              <span className="text-[11px] font-semibold text-[#6B7280] block uppercase tracking-wider">
                Active Deals
              </span>
              <span className="text-xl font-black text-[#0F766E]">
                {pipeline?.total_active_deals ?? 0}
              </span>
            </div>
            <button
              onClick={() => fetchPipeline()}
              className="p-2 border border-[#E5E7EB] bg-white rounded-lg hover:bg-[#F3F4F6] text-[#374151] transition"
              title="Refresh pipeline"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Kanban Board Horizontal Scroll Container */}
        {loading ? (
          <div className="text-center py-20 text-xs text-[#6B7280]">
            Loading sales pipeline board...
          </div>
        ) : (
          <div className="flex gap-4 overflow-x-auto pb-6 scrollbar-thin">
            {pipeline?.columns.map((col) => (
              <div
                key={col.stage_key}
                className="w-80 shrink-0 bg-[#F1F3F5] rounded-xl p-3 border border-[#E2E8F0] flex flex-col max-h-[calc(100vh-220px)]"
              >
                {/* Column Header */}
                <div className="flex items-center justify-between pb-2.5 mb-2 border-b border-[#CBD5E1]">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: col.color }}
                    />
                    <h2 className="text-xs font-bold text-[#1E293B] uppercase tracking-wide">
                      {col.stage_name}
                    </h2>
                    <span className="bg-white text-[#475569] text-[10px] font-bold px-1.5 py-0.5 rounded-full border border-[#CBD5E1]">
                      {col.total_cards}
                    </span>
                  </div>
                  {col.total_pipeline_value > 0 && (
                    <span className="text-[11px] font-bold text-[#0F766E]">
                      AED {col.total_pipeline_value >= 1000000 
                        ? `${(col.total_pipeline_value / 1000000).toFixed(1)}M` 
                        : `${(col.total_pipeline_value / 1000).toFixed(0)}k`}
                    </span>
                  )}
                </div>

                {/* Cards List */}
                <div className="space-y-2.5 overflow-y-auto pr-1 flex-1">
                  {col.cards.length === 0 ? (
                    <div className="py-8 text-center text-[11px] text-[#94A3B8]">
                      No deals in this stage
                    </div>
                  ) : (
                    col.cards.map((card) => (
                      <div
                        key={card.id}
                        className="p-3.5 bg-white rounded-lg border border-[#E2E8F0] shadow-sm hover:border-[#0F766E] hover:shadow transition text-xs"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <Link
                            href={`/dashboard/crm/customers/${card.lead_id}`}
                            className="font-bold text-[#0F172A] hover:text-[#0F766E] flex items-center gap-1"
                          >
                            {card.customer_name || 'Unnamed Client'}
                            <ArrowUpRight className="w-3 h-3 text-[#94A3B8]" />
                          </Link>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                            card.score === 'hot'
                              ? 'bg-[#FEE2E2] text-[#B91C1C]'
                              : card.score === 'warm'
                              ? 'bg-[#FEF3C7] text-[#B45309]'
                              : 'bg-[#F1F5F9] text-[#475569]'
                          }`}>
                            {card.score}
                          </span>
                        </div>

                        <div className="text-[11px] text-[#64748B] space-y-0.5 mb-2">
                          <p>{card.phone}</p>
                          {card.property_interest && (
                            <p className="truncate text-[#334155] font-medium">
                              {card.property_interest}
                            </p>
                          )}
                        </div>

                        {/* Value & Age */}
                        <div className="flex items-center justify-between pt-2 border-t border-[#F1F5F9]">
                          <span className="font-extrabold text-[#0F172A]">
                            {card.deal_value
                              ? `${card.currency} ${card.deal_value.toLocaleString()}`
                              : 'Value not set'}
                          </span>
                          <span className="text-[10px] text-[#94A3B8]">
                            {card.age_days}d in CRM
                          </span>
                        </div>

                        {/* Alerts or Next Action */}
                        {card.has_revenue_alert && (
                          <div className="mt-2 text-[10px] font-semibold text-[#DC2626] bg-[#FEF2F2] p-1 rounded flex items-center gap-1">
                            <AlertCircle className="w-3 h-3" />
                            Revenue Autopilot Alert
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
