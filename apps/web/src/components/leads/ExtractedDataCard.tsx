'use client';

import { useState, useEffect } from 'react';
import { 
  Sparkles, DollarSign, MapPin, Building2, Calendar, CreditCard, 
  BrainCircuit, Lightbulb, PhoneCall, RefreshCw, CheckCircle2, 
  AlertCircle, HelpCircle, ShieldCheck, Home, ChevronDown, ChevronUp,
  TrendingUp, Award, ExternalLink, Check, AlertTriangle
} from 'lucide-react';
import { LeadDetail } from '@/types';
import ScoreBadge from '@/components/shared/ScoreBadge';
import { api } from '@/lib/api-client';

interface ExtractedDataCardProps {
  lead: LeadDetail;
}

export default function ExtractedDataCard({ lead }: ExtractedDataCardProps) {
  const [intel, setIntel] = useState<any | null>(null);
  const [recommendations, setRecommendations] = useState<any | null>(null);
  const [qualState, setQualState] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [expandedRecId, setExpandedRecId] = useState<string | null>(null);
  const [error, setError] = useState<string>('');

  const fetchIntelligenceAndRecommendations = async (force: boolean = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      if (force) {
        const [intelRes, recRes, qualRes] = await Promise.allSettled([
          api.prospectIntelligence.refresh(lead.id),
          api.recommendations.refresh(lead.id),
          api.qualification.startConversation(lead.id, 'webchat', true)
        ]);
        if (intelRes.status === 'fulfilled') setIntel(intelRes.value);
        if (recRes.status === 'fulfilled') setRecommendations(recRes.value);
        if (qualRes.status === 'fulfilled') setQualState(qualRes.value);
      } else {
        const [intelRes, recRes, qualRes] = await Promise.allSettled([
          api.prospectIntelligence.getProfile(lead.id),
          api.recommendations.getRecommendations(lead.id, 5),
          api.qualification.getConversationState(lead.id)
        ]);
        if (intelRes.status === 'fulfilled') setIntel(intelRes.value);
        if (recRes.status === 'fulfilled') setRecommendations(recRes.value);
        if (qualRes.status === 'fulfilled') setQualState(qualRes.value);
      }
    } catch (e: any) {
      setError(e.message || 'AI intelligence analysis unavailable');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (lead?.id) {
      fetchIntelligenceAndRecommendations(false);
    }
  }, [lead?.id]);

  const req = intel?.property_requirements || {};
  const budget = intel?.budget || {};
  const brief = intel?.sales_brief || {};
  const recItems = recommendations?.items || [];
  const missing = intel?.missing_information || [];
  const questions = intel?.next_best_questions || [];
  const confidences = intel?.confidences || {};

  const budgetDisplay = budget.budget_min || budget.budget_max
    ? `${budget.budget_min ? budget.budget_min.toLocaleString() : 'Any'} - ${budget.budget_max ? budget.budget_max.toLocaleString() : 'Open'} ${budget.currency || ''}`
    : (lead.budget_min || lead.budget_max ? `${lead.budget_min?.toLocaleString() || ''} - ${lead.budget_max?.toLocaleString() || ''}` : 'Not specified');

  const getRecTypeBadge = (type: string) => {
    switch (type) {
      case 'BEST_OVERALL':
        return <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">BEST OVERALL</span>;
      case 'BEST_VALUE':
        return <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-blue-500/20 text-blue-300 border border-blue-500/30">BEST VALUE</span>;
      case 'BEST_LOCATION':
        return <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-purple-500/20 text-purple-300 border border-purple-500/30">BEST LOCATION</span>;
      case 'BEST_INVESTMENT':
        return <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-amber-500/20 text-amber-300 border border-amber-500/30">TOP ROI</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-extrabold bg-slate-500/20 text-slate-300 border border-slate-500/30">ALTERNATIVE</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* 0. AI Lead Qualification & Conversation Engine (Part 21.4) */}
      <div className="glass-panel p-5 rounded-2xl border border-dark-border relative overflow-hidden bg-gradient-to-b from-dark-card/90 to-dark-bg/95">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-teal-400" />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-extrabold text-white text-base">AI Lead Qualification</h3>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border ${
                  qualState?.qualification_state === 'QUALIFIED'
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    : qualState?.qualification_state === 'PARTIALLY_QUALIFIED'
                    ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                    : qualState?.qualification_state === 'NEEDS_HUMAN_REVIEW' || qualState?.human_handoff
                    ? 'bg-red-500/20 text-red-300 border-red-500/30'
                    : qualState?.qualification_state === 'NURTURE'
                    ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                    : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                }`}>
                  {qualState?.qualification_state?.replace(/_/g, ' ') || 'COLLECTING INFORMATION'}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono mt-0.5">Policy: Deterministic Engine v1.0 • Provenance Verified</p>
            </div>
          </div>
          <button
            onClick={() => fetchIntelligenceAndRecommendations(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-dark-card border border-dark-border text-xs text-slate-300 hover:text-white hover:border-slate-500 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-teal-400' : ''}`} />
            <span>{refreshing ? 'Evaluating...' : 'Re-evaluate'}</span>
          </button>
        </div>

        {/* Human Handoff Banner */}
        {qualState?.human_handoff && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl mb-4 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-bold text-red-300">Human Advisor Intervention Required</p>
              <p className="text-[11px] text-slate-300 mt-0.5">{qualState.handoff_reason || 'Contradictory evidence or customer requested agent handoff.'}</p>
            </div>
          </div>
        )}

        {/* Completeness & Confidence Score Bars */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span>Requirement Completeness</span>
              <span className="font-extrabold text-teal-400 font-mono">
                {Math.round((qualState?.completeness_score ?? 0.5) * 100)}%
              </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div 
                className="bg-teal-500 h-full rounded-full transition-all duration-500" 
                style={{ width: `${Math.round((qualState?.completeness_score ?? 0.5) * 100)}%` }} 
              />
            </div>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span>Evidence Confidence</span>
              <span className="font-extrabold text-emerald-400 font-mono">
                {Math.round((qualState?.confidence_score ?? 0.85) * 100)}%
              </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div 
                className="bg-emerald-500 h-full rounded-full transition-all duration-500" 
                style={{ width: `${Math.round((qualState?.confidence_score ?? 0.85) * 100)}%` }} 
              />
            </div>
          </div>
        </div>

        {/* Next Best Qualification Question */}
        {qualState?.current_question && !qualState?.human_handoff && (
          <div className="p-3.5 bg-teal-500/10 border border-teal-500/20 rounded-xl mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-black uppercase tracking-wider text-teal-400 flex items-center gap-1">
                <BrainCircuit className="w-3.5 h-3.5" /> Next Best Question ({qualState.current_question_field})
              </span>
              <a
                href={`https://wa.me/${lead?.phone?.replace(/\+/g, '')}?text=${encodeURIComponent(qualState.current_question)}`}
                target="_blank"
                rel="noreferrer"
                className="px-2.5 py-1 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-extrabold text-[10px] transition-colors flex items-center gap-1"
              >
                <span>Ask Customer</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
            <p className="text-xs text-slate-200 font-medium italic">"{qualState.current_question}"</p>
          </div>
        )}

        {/* Missing Fields Checklist */}
        {qualState?.missing_required_fields?.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-slate-400 font-bold mr-1">Missing Info:</span>
            {qualState.missing_required_fields.map((f: string, idx: number) => (
              <span key={idx} className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20">
                • {f.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 1. Grounded Sales Intelligence Brief */}
      <div className="glass-panel p-5 rounded-2xl border border-dark-border relative overflow-hidden">
        <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 blur-2xl rounded-full" />
        
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="font-extrabold text-white text-base">AI Prospect Intelligence</h3>
              <p className="text-[10px] text-slate-400 font-mono">Model: {intel?.model_version || 'v1.0-real-estate-prospect'}</p>
            </div>
          </div>
          <button
            onClick={() => fetchIntelligenceAndRecommendations(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-dark-card border border-dark-border text-xs text-slate-300 hover:text-white hover:border-slate-500 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
            <span>{refreshing ? 'Analyzing...' : 'Re-analyze'}</span>
          </button>
        </div>

        {brief.headline && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl mb-4">
            <p className="text-xs font-black text-emerald-400 tracking-wide">{brief.headline}</p>
            <p className="text-xs text-slate-300 mt-1 font-medium">{brief.intent_summary}</p>
          </div>
        )}

        {/* Structured Attributes Grid */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <div className="flex items-center gap-1.5">
                <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                <span>Budget</span>
              </div>
              {confidences.budget_confidence > 0 && (
                <span className="text-[10px] font-mono text-emerald-400">{Math.round(confidences.budget_confidence * 100)}%</span>
              )}
            </div>
            <p className="text-sm font-extrabold text-white">{budgetDisplay}</p>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <div className="flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-blue-400" />
                <span>Type & Intent</span>
              </div>
              {confidences.intent_confidence > 0 && (
                <span className="text-[10px] font-mono text-blue-400">{Math.round(confidences.intent_confidence * 100)}%</span>
              )}
            </div>
            <p className="text-sm font-extrabold text-white uppercase">
              {req.bedrooms ? `${req.bedrooms} BHK ` : ''}{req.property_type || lead.property_type || 'Property'} • {intel?.transaction_intent || lead.transaction_type || 'Inquire'}
            </p>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-amber-400" />
                <span>Timeline</span>
              </div>
              {confidences.timeline_confidence > 0 && (
                <span className="text-[10px] font-mono text-amber-400">{Math.round(confidences.timeline_confidence * 100)}%</span>
              )}
            </div>
            <p className="text-sm font-extrabold text-white">{intel?.timeline || lead.timeline || 'Unknown'}</p>
          </div>

          <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <div className="flex items-center gap-1.5">
                <CreditCard className="w-3.5 h-3.5 text-indigo-400" />
                <span>Financing</span>
              </div>
              {confidences.financing_confidence > 0 && (
                <span className="text-[10px] font-mono text-indigo-400">{Math.round(confidences.financing_confidence * 100)}%</span>
              )}
            </div>
            <p className="text-sm font-extrabold text-white">{intel?.financing || 'Unknown'}</p>
          </div>
        </div>

        {/* Location & Preferred Areas */}
        <div className="bg-dark-card/80 p-3 rounded-xl border border-dark-border mb-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <div className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-red-400" />
              <span>Location / Preferred Communities</span>
            </div>
            {confidences.location_confidence > 0 && (
              <span className="text-[10px] font-mono text-red-400">{Math.round(confidences.location_confidence * 100)}%</span>
            )}
          </div>
          <p className="text-sm font-bold text-slate-200">
            {req.location || (req.preferred_areas?.length ? req.preferred_areas.join(', ') : (lead.preferred_locations?.join(', ') || 'Not specified'))}
          </p>
        </div>

        {/* Recommended Next Action */}
        {intel?.next_best_action && intel.next_best_action !== 'NO_ACTION' && (
          <div className="p-3.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-xs mb-4">
            <div className="flex items-center gap-1.5 font-bold text-blue-400 mb-1">
              <Lightbulb className="w-4 h-4" />
              <span>Recommended Next Action ({intel.next_best_action})</span>
            </div>
            <p className="text-slate-200 font-medium">{intel.next_best_action_reason || brief.recommended_action}</p>
          </div>
        )}

        {/* Missing Information & Highest Value Next Best Questions */}
        {questions.length > 0 && (
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs mb-4">
            <div className="flex items-center gap-1.5 font-bold text-amber-400 mb-2">
              <HelpCircle className="w-4 h-4" />
              <span>Next Best Qualification Question</span>
            </div>
            <p className="text-slate-200 font-semibold italic mb-1">"{questions[0].question}"</p>
            <p className="text-[10px] text-slate-400">Rationale: {questions[0].business_rationale}</p>
          </div>
        )}

        {/* 2. PART 21.3 — AI PROPERTY MATCHING & RECOMMENDATIONS */}
        <div className="p-4 rounded-xl bg-purple-500/10 border border-purple-500/20 mb-4">
          <div className="flex items-center justify-between font-bold text-purple-400 mb-3">
            <div className="flex items-center gap-2">
              <Home className="w-4 h-4 text-purple-400" />
              <span className="text-sm font-extrabold text-white">AI Property Matches ({recItems.length})</span>
            </div>
            <span className="text-[10px] bg-purple-500/20 px-2.5 py-0.5 rounded-full text-purple-300 font-semibold">
              Verified Tenant Inventory
            </span>
          </div>

          {recItems.length > 0 ? (
            <div className="space-y-3">
              {recItems.map((item: any) => {
                const isExpanded = expandedRecId === item.property_id;
                const coverage = item.requirement_coverage || { matched: [], unmet: [], unknown: [] };
                return (
                  <div
                    key={item.property_id}
                    className="p-3.5 rounded-xl bg-dark-card border border-dark-border text-xs transition-all hover:border-purple-500/40 shadow-sm"
                  >
                    {/* Header: Title, Type Badge, Price, Match Score */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          {getRecTypeBadge(item.recommendation_type)}
                          <h4 className="font-extrabold text-white text-sm">{item.title}</h4>
                        </div>
                        <p className="text-slate-400 text-xs flex items-center gap-2">
                          <span>{item.bedrooms} BHK</span>
                          <span>•</span>
                          <span>{item.locality || item.city || 'Dubai'}</span>
                          {item.built_up_area_sqft > 0 && (
                            <>
                              <span>•</span>
                              <span>{Math.round(item.built_up_area_sqft).toLocaleString()} sqft</span>
                            </>
                          )}
                        </p>
                      </div>

                      <div className="text-right">
                        <div className="px-2.5 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 font-extrabold text-sm mb-1 inline-block">
                          {Math.round(item.match_score)}% MATCH
                        </div>
                        <p className="text-white font-extrabold text-xs">
                          {item.price ? `${item.price.toLocaleString()} ${item.currency}` : 'Price on Request'}
                        </p>
                      </div>
                    </div>

                    {/* Matched Highlights List */}
                    <div className="mt-2.5 space-y-1">
                      {coverage.matched.slice(0, 3).map((m: string, idx: number) => (
                        <div key={idx} className="flex items-center gap-1.5 text-[11px] text-emerald-300">
                          <Check className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                          <span>{m}</span>
                        </div>
                      ))}
                    </div>

                    {/* Expand/Collapse Toggle */}
                    <button
                      onClick={() => setExpandedRecId(isExpanded ? null : item.property_id)}
                      className="mt-3 flex items-center justify-between w-full pt-2 border-t border-dark-border text-[11px] font-bold text-slate-400 hover:text-purple-300 transition-colors"
                    >
                      <span>{isExpanded ? 'Hide Match Factors & Rationale' : 'View Full Compatibility & Rationale'}</span>
                      {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>

                    {/* Expandable Breakdown Drawer */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-dark-border space-y-3 animate-in fade-in duration-150">
                        {/* Score Component Breakdown Bar Grid */}
                        <div className="grid grid-cols-4 gap-1.5 p-2.5 rounded-lg bg-dark-bg/60 border border-dark-border text-[10px]">
                          <div>
                            <span className="text-slate-400">Budget</span>
                            <p className="font-extrabold text-white">{Math.round(item.score_breakdown?.budget_fit || 0)}%</p>
                          </div>
                          <div>
                            <span className="text-slate-400">Location</span>
                            <p className="font-extrabold text-white">{Math.round(item.score_breakdown?.location_fit || 0)}%</p>
                          </div>
                          <div>
                            <span className="text-slate-400">Specs</span>
                            <p className="font-extrabold text-white">{Math.round(item.score_breakdown?.property_fit || 0)}%</p>
                          </div>
                          <div>
                            <span className="text-slate-400">Amenities</span>
                            <p className="font-extrabold text-white">{Math.round(item.score_breakdown?.preference_fit || 0)}%</p>
                          </div>
                        </div>

                        {/* Trade-offs & Unmet Criteria */}
                        {coverage.unmet.length > 0 && (
                          <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 space-y-1">
                            <div className="flex items-center gap-1 font-bold text-amber-400">
                              <AlertTriangle className="w-3 h-3" />
                              <span>Trade-offs & Considerations:</span>
                            </div>
                            {coverage.unmet.map((u: string, idx: number) => (
                              <p key={idx} className="pl-4 text-[10px] text-slate-300">• {u}</p>
                            ))}
                          </div>
                        )}

                        {/* Unknown Factors */}
                        {coverage.unknown.length > 0 && (
                          <div className="p-2 rounded bg-blue-500/10 border border-blue-500/20 text-[11px] text-blue-300 space-y-1">
                            <div className="flex items-center gap-1 font-bold text-blue-400">
                              <HelpCircle className="w-3 h-3" />
                              <span>Unknown / Requires Confirmation:</span>
                            </div>
                            {coverage.unknown.map((un: string, idx: number) => (
                              <p key={idx} className="pl-4 text-[10px] text-slate-300">• {un}</p>
                            ))}
                          </div>
                        )}

                        {/* Sales Agent Talking Points */}
                        {item.agent_talking_points?.length > 0 && (
                          <div className="p-2.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[11px]">
                            <p className="font-bold text-emerald-400 mb-1">Agent Guidance:</p>
                            <p className="text-slate-200">{item.agent_talking_points[0]}</p>
                          </div>
                        )}

                        {/* Next Action Action Button */}
                        <div className="flex items-center justify-between pt-1">
                          <span className="text-[11px] text-slate-400">
                            Suggested: <strong className="text-white">{item.suggested_next_action}</strong>
                          </span>
                          <a
                            href={`https://wa.me/${lead?.phone?.replace(/\+/g, '')}?text=Hi%20${encodeURIComponent(lead.name || '')},%20I%20have%20found%20a%20property%20matching%20your%20requirements:%20${encodeURIComponent(item.title)}`}
                            target="_blank"
                            rel="noreferrer"
                            className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-extrabold text-[11px] transition-colors flex items-center gap-1.5 shadow-sm"
                          >
                            <span>Send Details</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-6 text-center text-slate-400 text-xs border border-dashed border-dark-border rounded-xl">
              <Home className="w-8 h-8 mx-auto mb-2 text-slate-500 opacity-60" />
              <p className="font-bold text-slate-300">No Verified Properties Currently Match</p>
              <p className="text-[10px] text-slate-400 mt-1">
                Zero properties in your verified inventory satisfy this prospect's hard constraints.
              </p>
            </div>
          )}
        </div>

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
