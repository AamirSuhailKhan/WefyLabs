'use client';

import React from 'react';
import { Sparkles, AlertCircle, FileCheck, ShieldAlert, CheckCircle2, ArrowRight } from 'lucide-react';

interface Props {
  dealName: string;
  stage: string;
  closingProbability: number;
  riskLevel: 'low' | 'medium' | 'high_risk' | 'critical_stalled';
  missingDocs: string[];
  recommendedAction: string;
}

export function DealRiskCard({
  dealName,
  stage,
  closingProbability = 78.5,
  riskLevel = 'medium',
  missingDocs = ['Reservation Form Signed'],
  recommendedAction = 'Request signed Reservation Form from Rahul Sharma to proceed to Booking.'
}: Props) {
  const getRiskBadge = () => {
    switch (riskLevel) {
      case 'low':
        return <span className="bg-emerald-100 text-emerald-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded">Low Risk</span>;
      case 'medium':
        return <span className="bg-amber-100 text-amber-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded">Medium Risk</span>;
      case 'high_risk':
      case 'critical_stalled':
        return <span className="bg-red-100 text-red-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded font-mono">High Stall Risk</span>;
      default:
        return null;
    }
  };

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-3 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-indigo-600 fill-indigo-200" />
          <span>AI Deal Risk & Closing Engine</span>
        </div>
        {getRiskBadge()}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Closing Probability</span>
          <span className="text-sm font-bold font-mono text-emerald-700">
            {closingProbability}%
          </span>
        </div>

        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Current Stage</span>
          <span className="text-sm font-bold font-mono text-[#1A1A1A] capitalize">
            {stage}
          </span>
        </div>
      </div>

      {/* Missing Documents Warning */}
      {missingDocs && missingDocs.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 p-2.5 rounded-xl space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-amber-900">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
            <span>Missing Stage Documents ({missingDocs.length})</span>
          </div>
          <ul className="text-xs text-amber-800 font-sans list-disc list-inside">
            {missingDocs.map((doc, idx) => (
              <li key={idx}>{doc}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommended Next Action */}
      <div className="bg-indigo-50 border border-indigo-200 p-2.5 rounded-xl flex items-center justify-between">
        <div className="text-xs text-indigo-900 font-sans">
          <strong className="font-mono text-indigo-950 block">AI Recommended Next Action:</strong>
          <span>{recommendedAction}</span>
        </div>
        <button className="btn-lime px-3 py-1 text-[11px] shrink-0 ml-2">Execute</button>
      </div>
    </div>
  );
}
