'use client';

import React from 'react';
import { CheckCircle2, Clock, FileText, Landmark, Key, ShieldCheck } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

interface Props {
  propertyTitle?: string;
  agreedPrice?: number;
  currentStage?: string;
  completionPercentage?: number;
  estimatedRegistrationDate?: string;
}

export function CustomerTimelineTracker({
  propertyTitle = 'Luxury 3BHK Penthouse in Marina Gate 1',
  agreedPrice = 2850000,
  currentStage = 'Bank Loan Pre-Approval',
  completionPercentage = 75,
  estimatedRegistrationDate = 'Aug 15, 2026'
}: Props) {
  const { region } = useRegion();

  const steps = [
    { label: 'Booking Token Paid', icon: CheckCircle2, completed: true },
    { label: 'Document KYC Verified', icon: FileText, completed: true },
    { label: 'Bank Loan Pre-Approved', icon: Landmark, completed: true },
    { label: 'Legal Title Deed NOC', icon: ShieldCheck, completed: false, active: true },
    { label: 'DLD Transfer & Keys', icon: Key, completed: false }
  ];

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-6 space-y-5 shadow-xs">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#EAE7E1] pb-4">
        <div>
          <span className="text-[10px] font-mono uppercase bg-emerald-100 text-emerald-900 px-2 py-0.5 rounded font-bold">
            Active Property Purchase
          </span>
          <h2 className="text-base font-bold font-mono text-[#1A1A1A] mt-1">{propertyTitle}</h2>
          <p className="text-xs text-gray-500 font-sans">Estimated Key Handover: {estimatedRegistrationDate}</p>
        </div>

        <div className="text-right">
          <span className="text-sm font-extrabold font-mono text-[#1A1A1A] block">
            {formatCurrency(agreedPrice, region)}
          </span>
          <span className="text-xs font-mono font-bold text-emerald-700">
            {completionPercentage}% Overall Complete
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="h-3 w-full bg-gray-200 rounded-full overflow-hidden">
          <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${completionPercentage}%` }}></div>
        </div>
        <div className="flex justify-between text-xs font-mono text-gray-600">
          <span>Current Stage: <strong>{currentStage}</strong></span>
          <span>Next: Title Deed Registration</span>
        </div>
      </div>

      {/* Timeline Steps Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 pt-2">
        {steps.map((step, idx) => {
          const Icon = step.icon;
          return (
            <div
              key={idx}
              className={`p-3 rounded-2xl border text-center space-y-1.5 transition-colors ${
                step.completed
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
                  : step.active
                  ? 'bg-amber-50 border-amber-300 text-amber-950 shadow-2xs'
                  : 'bg-white border-[#D4D0C8] text-gray-400 opacity-60'
              }`}
            >
              <div className="flex justify-center">
                <Icon className={`w-5 h-5 ${step.completed ? 'text-emerald-600' : step.active ? 'text-amber-600' : 'text-gray-400'}`} />
              </div>
              <span className="text-[11px] font-mono font-bold block leading-tight">{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
