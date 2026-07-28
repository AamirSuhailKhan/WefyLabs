'use client';

import { Sparkles, IndianRupee, MapPin, Building2, Calendar, CreditCard, BrainCircuit, Lightbulb, PhoneCall } from 'lucide-react';
import { LeadDetail } from '@/types';
import ScoreBadge from '@/components/shared/ScoreBadge';
import { formatCurrencyINR, formatTimeline, formatLoanStatus } from '@/lib/utils';

interface ExtractedDataCardProps {
  lead: LeadDetail;
}

export default function ExtractedDataCard({ lead }: ExtractedDataCardProps) {
  const latestScore = lead.latest_score;

  const budgetStr =
    lead.budget_min || lead.budget_max
      ? `${formatCurrencyINR(lead.budget_min)} - ${formatCurrencyINR(lead.budget_max)}`
      : 'Not specified yet';

  const locationsStr = lead.preferred_locations?.length
    ? lead.preferred_locations.join(', ')
    : 'Bengaluru Core';

  return (
    <div className="space-y-4">
      {/* AI Score Header */}
      <div className="glass-panel p-5 rounded-2xl border border-dark-border relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 blur-2xl rounded-full" />
        
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            <h3 className="font-extrabold text-white text-base">GPT-4o Qualification Scorecard</h3>
          </div>
          <ScoreBadge score={lead.score} confidence={lead.score_confidence} showConfidence size="lg" />
        </div>

        {/* Extracted Attributes Grid */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
              <IndianRupee className="w-3.5 h-3.5 text-emerald-400" />
              <span>Budget Range</span>
            </div>
            <p className="text-sm font-extrabold text-white">{budgetStr}</p>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
              <Building2 className="w-3.5 h-3.5 text-blue-400" />
              <span>Type & Intent</span>
            </div>
            <p className="text-sm font-extrabold text-white uppercase">
              {lead.property_type || '2BHK'} • {lead.transaction_type || 'Buy'}
            </p>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
              <Calendar className="w-3.5 h-3.5 text-amber-400" />
              <span>Move-in Timeline</span>
            </div>
            <p className="text-sm font-extrabold text-white">{formatTimeline(lead.timeline)}</p>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
              <CreditCard className="w-3.5 h-3.5 text-indigo-400" />
              <span>Home Loan Status</span>
            </div>
            <p className="text-sm font-extrabold text-white">{formatLoanStatus(lead.loan_status)}</p>
          </div>
        </div>

        {/* Location Badge */}
        <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border mb-4">
          <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
            <MapPin className="w-3.5 h-3.5 text-red-400" />
            <span>Preferred Localities</span>
          </div>
          <p className="text-sm font-bold text-slate-200">{locationsStr}</p>
        </div>

        {/* AI Reasoning */}
        {latestScore?.reasoning && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs mb-4">
            <div className="flex items-center gap-1.5 font-bold text-emerald-400 mb-1">
              <BrainCircuit className="w-4 h-4" />
              <span>AI Scoring Rationale</span>
            </div>
            <p className="text-slate-300 leading-relaxed font-medium">{latestScore.reasoning}</p>
          </div>
        )}

        {/* Call CTA */}
        <a
          href={`tel:${lead.phone}`}
          className="flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-400 hover:from-emerald-400 hover:to-teal-300 text-slate-950 font-extrabold py-3 px-4 rounded-xl text-sm transition-all shadow-lg shadow-emerald-500/25"
        >
          <PhoneCall className="w-4 h-4" />
          <span>Call {lead.name || 'Lead'} Now ({lead.phone})</span>
        </a>
      </div>
    </div>
  );
}
