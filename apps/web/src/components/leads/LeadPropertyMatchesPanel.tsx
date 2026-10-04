'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Sparkles, Building2, CheckCircle2, AlertTriangle, ChevronDown,
  ChevronUp, Bookmark, Send, ExternalLink, RefreshCw, Layers, ShieldCheck
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { formatCurrencyINR } from '@/lib/utils';

interface LeadPropertyMatchesPanelProps {
  leadId: string;
  leadName?: string;
}

export default function LeadPropertyMatchesPanel({ leadId, leadName }: LeadPropertyMatchesPanelProps) {
  const [matches, setMatches] = useState<any[]>([]);
  const [confidence, setConfidence] = useState<string>('MEDIUM');
  const [confidenceReason, setConfidenceReason] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedMatchId, setExpandedMatchId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');

  const fetchMatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.matching.getLeadMatches(leadId, {
        limit: 8,
        property_type: filterType !== 'all' ? filterType : undefined
      });
      setMatches(res.matches || []);
      setConfidence(res.confidence || 'MEDIUM');
      setConfidenceReason(res.confidence_reason || '');
    } catch (err: any) {
      setError(err?.message || 'Failed to calculate property matches');
      setMatches([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMatches();
  }, [leadId, filterType]);

  const handleShortlist = async (propertyId: string) => {
    setActionLoading(propertyId);
    try {
      await api.matching.shortlist({
        lead_id: leadId,
        property_id: propertyId,
        notes: `Shortlisted by agent for ${leadName || 'lead'}`
      });
      alert('Property shortlisted successfully!');
      fetchMatches();
    } catch (err: any) {
      alert(err?.message || 'Failed to shortlist');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRecommend = async (propertyId: string) => {
    setActionLoading(propertyId);
    try {
      await api.matching.recommend({
        lead_id: leadId,
        property_id: propertyId,
        notes: `Recommended by agent for ${leadName || 'lead'}`
      });
      alert('Property recommended! Follow-up task created.');
      fetchMatches();
    } catch (err: any) {
      alert(err?.message || 'Failed to recommend');
    } finally {
      setActionLoading(null);
    }
  };

  const getScoreBadgeColor = (score: number) => {
    if (score >= 85) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    if (score >= 70) return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
    if (score >= 50) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  };

  return (
    <div className="bg-white p-5 rounded-2xl border border-[#E2E8F0] shadow-sm space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-[#CCFBF1] text-[#0D9488]">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#0F172A] flex items-center gap-2">
              Best Property Matches
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-mono font-bold ${
                confidence === 'HIGH' ? 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]' :
                confidence === 'LOW' ? 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]' :
                'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]'
              }`}>
                {confidence} CONFIDENCE
              </span>
            </h3>
            <p className="text-[11px] text-[#64748B]">Explainable matching from live verified inventory</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchMatches}
            disabled={loading}
            className="p-1.5 rounded-lg text-[#64748B] hover:text-[#0F172A] hover:bg-[#F1F5F9] transition-colors disabled:opacity-50"
            title="Refresh Matches"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <Link
            href="/dashboard/matching"
            className="text-[11px] font-bold text-[#0D9488] hover:underline flex items-center gap-1"
          >
            <span>View All</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {confidence === 'LOW' && (
        <div className="p-2.5 bg-[#FEF3C7] border border-[#FDE68A] rounded-xl flex items-start gap-2 text-[#B45309] text-[11px]">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Insufficient Requirements: </span>
            {confidenceReason || 'Missing budget or location preferences. Matches are broad recommendations.'}
          </div>
        </div>
      )}

      {/* Filter Chips */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {['all', 'apartment', 'villa', 'independent_house'].map((type) => (
          <button
            key={type}
            onClick={() => setFilterType(type)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold capitalize transition-colors shrink-0 ${
              filterType === type
                ? 'bg-[#0D9488] text-white'
                : 'bg-[#F8FAFC] border border-[#E2E8F0] text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            {type === 'all' ? 'All Types' : type.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-8 text-[#64748B] space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-[#0D9488]" />
          <p className="text-xs font-bold text-[#0F172A]">Evaluating live property candidates...</p>
        </div>
      ) : error ? (
        <div className="p-3 bg-[#FEE2E2] border border-[#FECACA] text-[#B91C1C] text-xs rounded-xl">
          {error}
        </div>
      ) : matches.length === 0 ? (
        <div className="text-center py-8 text-[#64748B] font-mono text-xs space-y-2">
          <Building2 className="w-8 h-8 mx-auto text-[#94A3B8]" />
          <p className="font-bold text-[#0F172A]">No strong matches found</p>
          <p className="text-[11px] text-[#64748B]">
            No properties currently satisfy all hard constraints.
          </p>
          <Link
            href="/dashboard/matching"
            className="inline-block mt-2 px-3 py-1.5 rounded-lg bg-[#CCFBF1] text-[#0D9488] hover:bg-[#99F6E4] text-xs font-bold transition-all"
          >
            Explore Soft Alternatives
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {matches.map((item) => {
            const isExpanded = expandedMatchId === item.property_id;
            const score = item.final_score ?? item.score ?? 0;
            return (
              <div
                key={item.property_id}
                className="bg-[#FAFAF9] border border-[#E2E8F0] rounded-xl p-3.5 space-y-3 hover:border-[#0D9488]/40 transition-all"
              >
                {/* Title & Score */}
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-white text-[#64748B] border border-[#E2E8F0]">
                        {item.property_code}
                      </span>
                      <h4 className="text-xs font-bold text-[#0F172A] truncate">{item.property_title}</h4>
                    </div>
                    <p className="text-[11px] text-[#64748B] mt-1 flex items-center gap-2">
                      <span>{item.bedrooms ? `${item.bedrooms} BHK` : 'N/A'}</span>
                      <span>•</span>
                      <span>{item.locality || 'Unknown'}</span>
                      <span>•</span>
                      <span className="font-bold text-[#0D9488]">{formatCurrencyINR(item.price)}</span>
                    </p>
                  </div>

                  <div className="flex flex-col items-end shrink-0">
                    <div className={`px-2 py-0.5 rounded-full border text-xs font-extrabold font-mono ${getScoreBadgeColor(score)}`}>
                      {Math.round(score)}% MATCH
                    </div>
                    <button
                      onClick={() => setExpandedMatchId(isExpanded ? null : item.property_id)}
                      className="text-[10px] text-[#64748B] hover:text-[#0D9488] flex items-center gap-0.5 mt-1"
                    >
                      <span>{isExpanded ? 'Hide' : 'Why?'}</span>
                      {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                {/* Reasons Preview */}
                {item.reasons && item.reasons.length > 0 && !isExpanded && (
                  <div className="text-[11px] text-[#475569] space-y-1">
                    {item.reasons.slice(0, 2).map((r: string, idx: number) => (
                      <div key={idx} className="flex items-center gap-1.5 text-[#0D9488]">
                        <CheckCircle2 className="w-3 h-3 shrink-0" />
                        <span className="truncate text-[#475569]">{r}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Score Breakdown (Expanded) */}
                {isExpanded && (
                  <div className="pt-2 border-t border-[#E2E8F0] space-y-2 text-xs">
                    <div className="font-bold text-[#0F172A] text-[11px]">Component Score Breakdown:</div>
                    <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
                      {Object.entries(item.score_breakdown || {}).map(([key, val]: [string, any]) => (
                        <div key={key} className="flex items-center justify-between p-1.5 bg-white rounded border border-[#E2E8F0]">
                          <span className="capitalize text-[#64748B]">{key.replace('_', ' ')}</span>
                          <span className="font-bold text-[#0F172A]">{Math.round(val)}%</span>
                        </div>
                      ))}
                    </div>

                    {item.reasons && item.reasons.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <div className="text-[10px] font-bold text-[#0D9488] uppercase tracking-wider">Matched Factors:</div>
                        {item.reasons.map((r: string, idx: number) => (
                          <div key={idx} className="flex items-start gap-1.5 text-[#0D9488] text-[11px]">
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span className="text-[#334155]">{r}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {item.mismatches && item.mismatches.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <div className="text-[10px] font-bold text-[#D97706] uppercase tracking-wider">Potential Caveats:</div>
                        {item.mismatches.map((m: string, idx: number) => (
                          <div key={idx} className="flex items-start gap-1.5 text-[#D97706] text-[11px]">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span className="text-[#475569]">{m}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-1 border-t border-[#E2E8F0]">
                  <button
                    onClick={() => handleShortlist(item.property_id)}
                    disabled={actionLoading === item.property_id}
                    className="px-2.5 py-1 bg-white hover:bg-[#F1F5F9] text-[#475569] border border-[#CBD5E1] rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all disabled:opacity-50"
                  >
                    <Bookmark className="w-3 h-3" />
                    <span>Shortlist</span>
                  </button>
                  <button
                    onClick={() => handleRecommend(item.property_id)}
                    disabled={actionLoading === item.property_id}
                    className="px-3 py-1 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-[11px] font-extrabold flex items-center gap-1 transition-all shadow-xs disabled:opacity-50"
                  >
                    <Send className="w-3 h-3" />
                    <span>Recommend</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
