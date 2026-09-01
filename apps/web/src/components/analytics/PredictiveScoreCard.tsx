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
  conversionProbability,
  churnRisk,
  estimatedLtv,
  bestFollowupWindow,
  attributions,
}: Props) {
  const { region } = useRegion();

  const hasData = conversionProbability !== undefined && conversionProbability !== null;

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-purple-600 fill-purple-200" />
          <span>Conversion Propensity Intelligence</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          Propensity Engine v1.0
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Conversion Prop</span>
          <span className="text-base font-extrabold font-mono text-emerald-700">
            {hasData ? `${conversionProbability}%` : '--'}
          </span>
        </div>

        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Churn Risk</span>
          <span className="text-base font-extrabold font-mono text-amber-700">
            {churnRisk !== undefined && churnRisk !== null ? `${churnRisk}%` : '--'}
          </span>
        </div>

        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Estimated LTV</span>
          <span className="text-base font-extrabold font-mono text-[#1A1A1A]">
            {estimatedLtv ? formatCurrency(estimatedLtv, region) : '--'}
          </span>
        </div>
      </div>

      {/* Recommended Follow-up Window */}
      {bestFollowupWindow && (
        <div className="bg-purple-50 border border-purple-200 p-2.5 rounded-xl flex items-center gap-2">
          <Clock className="w-4 h-4 text-purple-700 shrink-0" />
          <div className="text-xs text-purple-950 font-sans">
            <strong className="font-mono text-purple-900 block">Optimal Contact Window:</strong>
            <span>{bestFollowupWindow}</span>
          </div>
        </div>
      )}

      {/* Feature Attribution Explanation (Explaining WHY) */}
      <div className="space-y-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <HelpCircle className="w-3.5 h-3.5 text-gray-500" />
          <span>Feature Attributions (Why this score?)</span>
        </div>

        {attributions && attributions.length > 0 ? (
          <div className="space-y-1.5">
            {attributions.map((attr, i) => (
              <div key={i} className="bg-white p-2.5 rounded-xl border border-[#D4D0C8] text-xs font-sans space-y-0.5">
                <div className="flex items-center justify-between font-mono font-bold text-[#1A1A1A]">
                  <span>{attr.feature}</span>
                  <span className={attr.impact >= 0 ? 'text-emerald-700' : 'text-rose-600'}>
                    {attr.impact >= 0 ? `+${attr.impact}%` : `${attr.impact}%`}
                  </span>
                </div>
                <p className="text-[11px] text-gray-600">{attr.explanation}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white p-3 rounded-xl border border-[#D4D0C8] text-xs text-gray-500 text-center font-mono">
            {hasData ? 'No significant attribution factors.' : 'Insufficient data to compute attributions.'}
          </div>
        )}
      </div>
    </div>
  );
}
