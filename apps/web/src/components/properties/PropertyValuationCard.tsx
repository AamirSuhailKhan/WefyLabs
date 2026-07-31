'use client';

import React from 'react';
import { Sparkles, TrendingUp, AlertTriangle, CheckCircle2, DollarSign, BarChart3 } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

interface ValuationData {
  estimated_market_value: number;
  estimated_price_per_sqft: number;
  is_overpriced: boolean;
  overpriced_percentage: number;
  estimated_annual_roi_yield_pct: number;
  confidence_score: number;
}

interface Props {
  price: number;
  areaSqft: number;
  valuation?: ValuationData;
}

export function PropertyValuationCard({
  price,
  areaSqft,
  valuation = {
    estimated_market_value: 3237500,
    estimated_price_per_sqft: 1750,
    is_overpriced: false,
    overpriced_percentage: -11.9,
    estimated_annual_roi_yield_pct: 7.8,
    confidence_score: 0.94
  }
}: Props) {
  const { region } = useRegion();

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-3 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-emerald-600 fill-emerald-200" />
          <span>AI Automated Valuation Model (AVM)</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          {(valuation.confidence_score * 100).toFixed(0)}% Match Confidence
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">AI Market Valuation</span>
          <span className="text-sm font-bold font-mono text-[#1A1A1A]">
            {formatCurrency(valuation.estimated_market_value, region)}
          </span>
        </div>

        <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
          <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block mb-1">Locality Avg / sqft</span>
          <span className="text-sm font-bold font-mono text-[#1A1A1A]">
            {formatCurrency(valuation.estimated_price_per_sqft, region)}
          </span>
        </div>
      </div>

      {/* Overpriced / Underpriced Tag */}
      <div
        className={`p-2.5 rounded-xl border flex items-center justify-between text-xs font-mono font-bold ${
          valuation.is_overpriced
            ? 'bg-red-50 border-red-200 text-red-900'
            : 'bg-emerald-50 border-emerald-200 text-emerald-900'
        }`}
      >
        <div className="flex items-center gap-1.5">
          {valuation.is_overpriced ? (
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          )}
          <span>
            {valuation.is_overpriced
              ? `Listed ${valuation.overpriced_percentage}% above AVM Benchmark`
              : `Below Market Value by ${Math.abs(valuation.overpriced_percentage)}%`}
          </span>
        </div>
        <span className="text-[10px] uppercase underline">Zestimate Grade</span>
      </div>

      {/* Projected Annual Yield */}
      <div className="flex items-center justify-between bg-white p-2.5 rounded-xl border border-[#D4D0C8] text-xs font-mono">
        <div className="flex items-center gap-1.5 text-gray-700">
          <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
          <span>Projected Net ROI Yield</span>
        </div>
        <span className="font-bold text-[#1A1A1A]">{valuation.estimated_annual_roi_yield_pct}% / year</span>
      </div>
    </div>
  );
}
