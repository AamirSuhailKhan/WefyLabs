'use client';

import React from 'react';
import { Sparkles, TrendingUp, Clock, AlertCircle, CheckCircle2, HelpCircle, Award } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

interface AttributionFactor {
  feature: string;
  impact: number;
  explanation: string;
}

interface Props {
  conversionProbability?: number;
  churnRisk?: number;
  estimatedLtv?: number;
  bestFollowupWindow?: string;
  attributions?: AttributionFactor[];
}

export function PredictiveScoreCard({
  conversionProbability = 88.5,
  churnRisk = 11.5,
  estimatedLtv = 32500,
  bestFollowupWindow = 'Tomorrow 10:00 AM - 11:30 AM (Peak Engagement)',
  attributions = [
    {
      feature: 'WhatsApp Response Velocity',
      impact: +32.5,
      explanation: 'Lead responded to WhatsApp bot within 2 minutes of inquiry.'
    },
    {
      feature: 'Budget & Locality Match',
      impact: +24.0,
      explanation: 'Lead budget matches ready possession 3BHK inventory in Dubai Marina.'
    },
    {
      feature: 'Pre-Approval Funding',
      impact: +18.5,
      explanation: 'Bank mortgage pre-approval verified.'
    }
  ]
}: Props) {
  const { region } = useRegion();

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-purple-600 fill-purple-200" />
          <span>Salesforce Einstein Predictive Intelligence</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          SHAP Model v2.4
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Conversion Prob</span>
          <span className="text-base font-extrabold font-mono text-emerald-700">
            {conversionProbability}%
          </span>
        </div>

        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Churn Risk</span>
          <span className="text-base font-extrabold font-mono text-amber-700">
            {churnRisk}%
          </span>
        </div>

        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Estimated LTV</span>
          <span className="text-base font-extrabold font-mono text-[#1A1A1A]">
            {formatCurrency(estimatedLtv, region)}
          </span>
        </div>
      </div>

      {/* Recommended Follow-up Window */}
      <div className="bg-purple-50 border border-purple-200 p-2.5 rounded-xl flex items-center gap-2">
        <Clock className="w-4 h-4 text-purple-700 shrink-0" />
        <div className="text-xs text-purple-950 font-sans">
          <strong className="font-mono text-purple-900 block">Optimal Contact Window:</strong>
          <span>{bestFollowupWindow}</span>
        </div>
      </div>

      {/* Feature Attribution Explanation (Explaining WHY) */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <HelpCircle className="w-3.5 h-3.5 text-gray-500" />
          <span>AI Feature Attribution (Why this score?)</span>
        </div>

        <div className="space-y-1.5">
          {attributions.map((attr, i) => (
            <div key={i} className="bg-white p-2.5 rounded-xl border border-[#D4D0C8] text-xs font-sans space-y-0.5">
              <div className="flex items-center justify-between font-mono font-bold text-[#1A1A1A]">
                <span>{attr.feature}</span>
                <span className="text-emerald-700">+{attr.impact}%</span>
              </div>
              <p className="text-[11px] text-gray-600">{attr.explanation}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
