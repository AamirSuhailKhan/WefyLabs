'use client';

import React, { useState } from 'react';
import { DealRiskCard } from '@/components/deals/DealRiskCard';
import { Briefcase, CheckCircle2, AlertTriangle, Clock, ArrowRight, DollarSign, FileText } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function DealsPage() {
  const { region } = useRegion();
  const [selectedStageFilter, setSelectedStageFilter] = useState<string>('all');

  const stages = [
    'lead', 'qualified', 'property_visit', 'offer', 'negotiation',
    'booking', 'documents', 'loan', 'legal', 'registration',
    'closing', 'commission', 'after_sales'
  ];

  const deals = [
    {
      id: '1',
      deal_name: 'DLF Marina Gate Penthouse Purchase',
      agreed_price: 2850000,
      currency: 'AED',
      current_stage: 'booking',
      commission_percentage: 2.0,
      estimated_commission_amount: 57000,
      lead_name: 'Rahul Sharma',
      property_title: 'Luxury 3BHK Penthouse in Marina Gate',
      risk_level: 'medium' as const,
      closing_probability_pct: 78.5,
      missing_documents: ['Reservation Form Signed'],
      recommended_action: 'Request signed Reservation Form from Rahul Sharma to proceed to Booking.'
    },
    {
      id: '2',
      deal_name: 'Downtown Heights 2BHK Villa Sale',
      agreed_price: 3100000,
      currency: 'AED',
      current_stage: 'loan',
      commission_percentage: 2.5,
      estimated_commission_amount: 77500,
      lead_name: 'Tariq Al-Mansoor',
      property_title: 'Modern 2BHK Apartment in Downtown Heights',
      risk_level: 'low' as const,
      closing_probability_pct: 91.0,
      missing_documents: [],
      recommended_action: 'Awaiting final bank disbursement cheque.'
    }
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Enterprise Transaction Management</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Manage 13-stage customer journey, payment schedules, legal milestone checklists, and AI Deal Risk.
          </p>
        </div>

        <button className="btn-lime px-4 py-2 text-xs flex items-center gap-1.5 self-start sm:self-auto">
          <Briefcase className="w-4 h-4" />
          <span>New Transaction Deal</span>
        </button>
      </div>

      {/* 13-Stage Journey Stepper */}
      <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-3 rounded-2xl overflow-x-auto shadow-xs">
        <div className="flex items-center gap-2 min-w-max">
          {stages.map((stg, idx) => (
            <button
              key={stg}
              onClick={() => setSelectedStageFilter(stg)}
              className={`px-3 py-1.5 text-[11px] font-mono font-bold rounded-xl capitalize transition-colors flex items-center gap-1.5 ${
                selectedStageFilter === stg
                  ? 'bg-[#1A1A1A] text-white shadow-xs'
                  : 'bg-white text-gray-700 border border-[#D4D0C8] hover:bg-gray-100'
              }`}
            >
              <span className="w-4 h-4 rounded-full bg-[#E8F5A8] text-[#1A1A1A] flex items-center justify-center text-[10px] font-extrabold">
                {idx + 1}
              </span>
              <span>{stg.replace('_', ' ')}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Deal Pipeline Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {deals.map((deal) => (
          <div key={deal.id} className="bg-white border border-[#D4D0C8] rounded-2xl p-5 shadow-xs space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase bg-indigo-100 text-indigo-900 px-2 py-0.5 rounded font-bold">
                  Stage: {deal.current_stage.replace('_', ' ')}
                </span>
                <h3 className="text-base font-bold font-mono text-[#1A1A1A] mt-1">{deal.deal_name}</h3>
                <p className="text-xs text-gray-500 font-sans">Buyer: {deal.lead_name} • {deal.property_title}</p>
              </div>

              <div className="text-right">
                <span className="text-sm font-extrabold font-mono text-[#1A1A1A] block">
                  {formatCurrency(deal.agreed_price, region)}
                </span>
                <span className="text-[10px] font-mono text-emerald-700 font-bold">
                  Est. Comm: {formatCurrency(deal.estimated_commission_amount, region)} ({deal.commission_percentage}%)
                </span>
              </div>
            </div>

            {/* AI Risk Card */}
            <DealRiskCard
              dealName={deal.deal_name}
              stage={deal.current_stage}
              closingProbability={deal.closing_probability_pct}
              riskLevel={deal.risk_level}
              missingDocs={deal.missing_documents}
              recommendedAction={deal.recommended_action}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
