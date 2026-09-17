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
    <div className="glass-panel p-5 rounded-2xl border border-dark-border space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-dark-border pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Best Property Matches
              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-mono font-bold ${
                confidence === 'HIGH' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                confidence === 'LOW' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                'bg-blue-500/10 text-blue-400 border-blue-500/30'
              }`}>
                {confidence} CONFIDENCE
              </span>
            </h3>
            <p className="text-[11px] text-slate-400">Explainable matching from live verified inventory</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchMatches}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors disabled:opacity-50"
            title="Refresh Matches"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <Link
            href="/dashboard/matching"
            className="text-[11px] font-bold text-emerald-400 hover:underline flex items-center gap-1"
          >
            <span>View All</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {confidence === 'LOW' && (
        <div className="p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-start gap-2 text-amber-300 text-[11px]">
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
                ? 'bg-emerald-500 text-slate-950'
                : 'bg-dark-card border border-dark-border text-slate-400 hover:text-white'
            }`}
          >
            {type === 'all' ? 'All Types' : type.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-8 text-slate-400 space-y-2">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-emerald-400" />
          <p className="text-xs font-bold">Evaluating live property candidates...</p>
        </div>
      ) : error ? (
        <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs rounded-xl">
          {error}
        </div>
      ) : matches.length === 0 ? (
        <div className="text-center py-8 text-slate-400 font-mono text-xs space-y-2">
          <Building2 className="w-8 h-8 mx-auto text-slate-600" />
          <p className="font-bold text-slate-300">No strong matches found</p>
          <p className="text-[11px] text-slate-500">
            No properties currently satisfy all hard constraints.
          </p>
          <Link
            href="/dashboard/matching"
            className="inline-block mt-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs font-bold transition-all"
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
                className="bg-dark-card/60 border border-dark-border rounded-xl p-3.5 space-y-3 hover:border-emerald-500/30 transition-all"
              >
                {/* Title & Score */}
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/5 text-slate-400">
                        {item.property_code}
                      </span>
                      <h4 className="text-xs font-bold text-white truncate">{item.property_title}</h4>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
                      <span>{item.bedrooms ? `${item.bedrooms} BHK` : 'N/A'}</span>
                      <span>•</span>
                      <span>{item.locality || 'Unknown'}</span>
                      <span>•</span>
                      <span className="font-bold text-emerald-400">{formatCurrencyINR(item.price)}</span>
                    </p>
                  </div>

                  <div className="flex flex-col items-end shrink-0">
                    <div className={`px-2 py-0.5 rounded-full border text-xs font-extrabold font-mono ${getScoreBadgeColor(score)}`}>
                      {Math.round(score)}% MATCH
                    </div>
                    <button
                      onClick={() => setExpandedMatchId(isExpanded ? null : item.property_id)}
                      className="text-[10px] text-slate-400 hover:text-emerald-400 flex items-center gap-0.5 mt-1"
                    >
                      <span>{isExpanded ? 'Hide' : 'Why?'}</span>
                      {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                  </div>
                </div>

                {/* Reasons Preview */}
                {item.reasons && item.reasons.length > 0 && !isExpanded && (
                  <div className="text-[11px] text-slate-300 space-y-1">
                    {item.reasons.slice(0, 2).map((r: string, idx: number) => (
                      <div key={idx} className="flex items-center gap-1.5 text-emerald-400">
                        <CheckCircle2 className="w-3 h-3 shrink-0" />
                        <span className="truncate text-slate-300">{r}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Score Breakdown (Expanded) */}
                {isExpanded && (
                  <div className="pt-2 border-t border-dark-border/60 space-y-2 text-xs">
                    <div className="font-bold text-slate-300 text-[11px]">Component Score Breakdown:</div>
                    <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
                      {Object.entries(item.score_breakdown || {}).map(([key, val]: [string, any]) => (
                        <div key={key} className="flex items-center justify-between p-1.5 bg-black/20 rounded border border-white/5">
                          <span className="capitalize text-slate-400">{key.replace('_', ' ')}</span>
                          <span className="font-bold text-white">{Math.round(val)}%</span>
                        </div>
                      ))}
                    </div>

                    {item.reasons && item.reasons.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">Matched Factors:</div>
                        {item.reasons.map((r: string, idx: number) => (
                          <div key={idx} className="flex items-start gap-1.5 text-emerald-400 text-[11px]">
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span className="text-slate-200">{r}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {item.mismatches && item.mismatches.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider">Potential Caveats:</div>
                        {item.mismatches.map((m: string, idx: number) => (
                          <div key={idx} className="flex items-start gap-1.5 text-amber-400 text-[11px]">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span className="text-slate-300">{m}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-1 border-t border-dark-border/40">
                  <button
                    onClick={() => handleShortlist(item.property_id)}
                    disabled={actionLoading === item.property_id}
                    className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all disabled:opacity-50"
                  >
                    <Bookmark className="w-3 h-3" />
                    <span>Shortlist</span>
                  </button>
                  <button
                    onClick={() => handleRecommend(item.property_id)}
                    disabled={actionLoading === item.property_id}
                    className="px-3 py-1 bg-emerald-500 hover:bg-emerald-400 text-slate-950 rounded-lg text-[11px] font-extrabold flex items-center gap-1 transition-all shadow-xs disabled:opacity-50"
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
