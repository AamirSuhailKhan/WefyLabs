'use client';

import { useState } from 'react';
import { Search, PhoneCall, ChevronRight, MapPin, Calendar, Building2 } from 'lucide-react';
import { Lead } from '@/types';
import ScoreBadge from '@/components/shared/ScoreBadge';
import { formatCurrencyINR, formatTimeline } from '@/lib/utils';

interface LeadTableProps {
  leads: Lead[];
  onRefresh?: () => void;
  onSelectLead?: (leadId: string) => void;
}

export default function LeadTable({ leads, onSelectLead }: LeadTableProps) {
  const [selectedScore, setSelectedScore] = useState<string>('all');
  const [selectedSource, setSelectedSource] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredLeads = leads.filter((lead) => {
    const matchesScore =
      selectedScore === 'all' || lead.score?.toLowerCase() === selectedScore.toLowerCase();
    const matchesSource =
      selectedSource === 'all' || lead.source?.toLowerCase() === selectedSource.toLowerCase();
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch =
      !searchQuery ||
      lead.name?.toLowerCase().includes(searchLower) ||
      lead.phone.includes(searchQuery);
    return matchesScore && matchesSource && matchesSearch;
  });

  const getStageBadge = (stageName: string = 'New') => {
    switch (stageName) {
      case 'Contacted': return 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]';
      case 'Viewing Scheduled': return 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]';
      case 'Negotiating': return 'bg-[#FFEDD5] text-[#C2410C] border-[#FED7AA]';
      case 'Closed Won': return 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]';
      case 'Closed Lost': return 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]';
      default: return 'bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]';
    }
  };

  return (
    <div className="bg-white rounded-xl border border-[#E2E8F0] overflow-hidden shadow-sm">
      {/* Header controls */}
      <div className="p-4 sm:p-6 border-b border-[#E2E8F0] bg-white flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-extrabold text-[#0F172A] flex items-center gap-2">
            Qualifications & Leads List
            <span className="text-xs bg-[#CCFBF1] text-[#0F766E] px-2.5 py-0.5 rounded-full font-bold border border-[#99F6E4]">
              {filteredLeads.length} total
            </span>
          </h2>
          <p className="text-xs text-[#64748B]">Leads captured and scored automatically via WhatsApp & Ads</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Search bar */}
          <div className="relative flex-1 sm:w-56">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
            <input
              type="text"
              placeholder="Search phone or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#FAFAF9] border border-[#E2E8F0] rounded-lg pl-9 pr-4 py-2 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488] focus:ring-1 focus:ring-[#0D9488] transition-colors"
            />
          </div>

          {/* Lead Source Filter */}
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-2 rounded-lg text-xs font-semibold text-[#0F172A] focus:outline-none focus:border-[#0D9488]"
          >
            <option value="all">All Sources</option>
            <option value="whatsapp_forward">WhatsApp Forward</option>
            <option value="facebook">Facebook Ads</option>
            <option value="google">Google Ads</option>
            <option value="referral">Referral</option>
            <option value="walk_in">Walk-in</option>
          </select>

          {/* Score Filters */}
          <div className="flex items-center gap-1 bg-[#F5F5F4] p-1 rounded-lg border border-[#E2E8F0]">
            {['all', 'hot', 'warm', 'cold'].map((scoreKey) => (
              <button
                key={scoreKey}
                onClick={() => setSelectedScore(scoreKey)}
                className={`px-3 py-1.5 rounded-md text-xs font-bold capitalize transition-all ${
                  selectedScore === scoreKey
                    ? 'bg-[#0D9488] text-white shadow-sm'
                    : 'text-[#64748B] hover:text-[#0F172A] hover:bg-white'
                }`}
              >
                {scoreKey}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#FAFAF9] text-[#64748B] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
            <tr>
              <th className="py-3.5 px-4 sm:px-6">Lead & Contact</th>
              <th className="py-3.5 px-4">Stage</th>
              <th className="py-3.5 px-4">AI Score</th>
              <th className="py-3.5 px-4">Budget Range</th>
              <th className="py-3.5 px-4">Type & Locations</th>
              <th className="py-3.5 px-4">Timeline</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#F1F5F9]">
            {filteredLeads.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center py-12 text-[#94A3B8] font-medium">
                  No leads found matching your search criteria.
                </td>
              </tr>
            ) : (
              filteredLeads.map((lead) => {
                const budgetStr =
                  lead.budget_min || lead.budget_max
                    ? `${formatCurrencyINR(lead.budget_min)} - ${formatCurrencyINR(lead.budget_max)}`
                    : 'Not Specified';

                const locationsStr = lead.preferred_locations?.length
                  ? lead.preferred_locations.join(', ')
                  : 'Bengaluru';

                return (
                  <tr
                    key={lead.id}
                    onClick={() => onSelectLead?.(lead.id)}
                    className="hover:bg-[#F8FAFC] cursor-pointer transition-colors group"
                  >
                    {/* Lead info */}
                    <td className="py-4 px-4 sm:px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-[#F1F5F9] border border-[#E2E8F0] flex items-center justify-center text-[#0F172A] font-bold text-sm">
                          {lead.name ? lead.name.charAt(0).toUpperCase() : 'P'}
                        </div>
                        <div>
                          <div className="font-bold text-sm text-[#0F172A] group-hover:text-[#0D9488] transition-colors block">
                            {lead.name || 'WhatsApp Lead'}
                          </div>
                          <div className="text-[#64748B] font-mono text-[11px] flex items-center gap-2">
                            <span>{lead.phone}</span>
                            <span className="text-[10px] uppercase font-bold text-[#0D9488]">({lead.source?.replace('_', ' ') || 'WhatsApp'})</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Pipeline Stage */}
                    <td className="py-4 px-4">
                      <span className={`px-2.5 py-1 rounded-lg text-xs font-extrabold border ${getStageBadge(lead.stage_name)}`}>
                        {lead.stage_name || 'New'}
                      </span>
                    </td>

                    {/* AI Score */}
                    <td className="py-4 px-4">
                      <ScoreBadge
                        score={lead.score}
                        confidence={lead.score_confidence}
                        showConfidence
                        size="sm"
                      />
                    </td>

                    {/* Budget */}
                    <td className="py-4 px-4 font-bold text-[#0D9488] text-sm">
                      {budgetStr}
                    </td>

                    {/* Type & Locations */}
                    <td className="py-4 px-4">
                      <div className="flex items-center gap-1.5 text-[#0F172A] font-semibold mb-1">
                        <Building2 className="w-3.5 h-3.5 text-[#94A3B8]" />
                        <span className="uppercase">{lead.property_type || '2BHK'}</span> •{' '}
                        <span className="capitalize">{lead.transaction_type || 'Buy'}</span>
                      </div>
                      <div className="flex items-center gap-1 text-[#64748B] text-[11px]">
                        <MapPin className="w-3 h-3 text-[#0D9488]" />
                        <span className="truncate max-w-[150px]">{locationsStr}</span>
                      </div>
                    </td>

                    {/* Timeline */}
                    <td className="py-4 px-4 text-[#475569] font-medium">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-[#D97706]" />
                        <span>{formatTimeline(lead.timeline)}</span>
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="py-4 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end gap-2">
                        <a
                          href={`tel:${lead.phone}`}
                          className="flex items-center gap-1.5 bg-[#CCFBF1] text-[#0F766E] border border-[#99F6E4] hover:bg-[#0D9488] hover:text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-sm"
                        >
                          <PhoneCall className="w-3.5 h-3.5" />
                          <span>Call</span>
                        </a>

                        <button
                          onClick={() => onSelectLead?.(lead.id)}
                          className="p-1.5 text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-lg transition-colors"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
