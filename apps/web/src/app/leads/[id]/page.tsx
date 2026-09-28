'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  PhoneCall,
  Sparkles,
  RefreshCw,
  AlertTriangle,
  Building,
  Calendar,
  MessageSquare,
  Bot,
  User,
  Zap,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Compass
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { LeadDetail } from '@/types';
import DashboardNav from '@/components/shared/DashboardNav';
import ConversationTimeline from '@/components/leads/ConversationTimeline';
import ExtractedDataCard from '@/components/leads/ExtractedDataCard';
import SalesActionCard from '@/components/leads/SalesActionCard';
import ConversationIntelligencePanel from '@/components/leads/ConversationIntelligencePanel';
import AutonomousSalesTimeline from '@/components/leads/AutonomousSalesTimeline';
import ScoreBadge from '@/components/shared/ScoreBadge';
import LeadPropertyMatchesPanel from '@/components/leads/LeadPropertyMatchesPanel';
import SourceAttributionCard from '@/components/leads/SourceAttributionCard';
import AIConversationTab from '@/components/leads/AIConversationTab';

export default function LeadDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const leadId = resolvedParams.id;

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [qualifying, setQualifying] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'ai' | 'timeline' | 'properties' | 'autonomous'>('ai');

  const fetchLeadDetail = async () => {
    setLoading(true);
    try {
      const data = await api.getLeadById(leadId);
      setLead(data);
    } catch (e: any) {
      setError(e.message || 'Lead not found');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeadDetail();
  }, [leadId]);

  const handleStatusChange = async (newStatus: string) => {
    if (!lead) return;
    try {
      const updated = await api.updateLeadStatus(lead.id, newStatus);
      setLead((prev) => (prev ? { ...prev, status: updated.status } : null));
    } catch (e: any) {
      console.error('Status update failed', e);
    }
  };

  const handleTriggerQualify = async () => {
    if (!lead) return;
    setQualifying(true);
    try {
      await api.triggerQualification(lead.id);
      await fetchLeadDetail();
    } catch (e: any) {
      alert(e.message || 'Qualification trigger failed');
    } finally {
      setQualifying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F0EDE8] flex flex-col">
        <DashboardNav />
        <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
          <RefreshCw className="w-8 h-8 animate-spin text-[#0D9488] mb-3" />
          <p className="text-xs font-mono font-bold text-[#1A1A1A]">Loading Lead Intelligence & Signals...</p>
        </div>
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="min-h-screen bg-[#F0EDE8] flex flex-col">
        <DashboardNav />
        <div className="flex-1 flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
          <AlertTriangle className="w-10 h-10 text-amber-500 mb-3" />
          <h3 className="text-lg font-bold text-[#1A1A1A] mb-1 font-mono">Lead Record Not Found</h3>
          <p className="text-xs text-[#6B6B6B] mb-4">{error || 'The requested customer profile could not be loaded.'}</p>
          <Link
            href="/dashboard"
            className="px-4 py-2 bg-[#1A1A1A] text-white text-xs font-bold rounded-xl transition-all shadow-sm"
          >
            ← Back to Command Center
          </Link>
        </div>
      </div>
    );
  }

  const budgetDisplay = lead.budget_max
    ? `₹${(lead.budget_max / 10000000).toFixed(2)} Cr`
    : lead.budget_min
    ? `₹${(lead.budget_min / 10000000).toFixed(2)} Cr+`
    : 'Flexible Budget';

  const locationDisplay = lead.preferred_locations && lead.preferred_locations.length > 0
    ? lead.preferred_locations.join(', ')
    : 'Prime Corridor';

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] font-sans pb-16">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 space-y-5">
        {/* Breadcrumb & Navigation */}
        <div className="flex items-center justify-between">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-[#6B6B6B] hover:text-[#1A1A1A] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Command Center</span>
            <span className="text-gray-300">/</span>
            <span className="text-[#1A1A1A]">Leads</span>
            <span className="text-gray-300">/</span>
            <span className="truncate max-w-[160px]">{lead.name || lead.phone}</span>
          </Link>

          <div className="flex items-center gap-2">
            <Link
              href={`/dashboard/inbox`}
              className="px-3 py-1.5 bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] rounded-xl text-xs font-bold text-[#1A1A1A] flex items-center gap-1.5 transition-all shadow-xs"
            >
              <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />
              <span>Open in Inbox</span>
            </Link>
            <Link
              href={`/dashboard/calendar`}
              className="px-3 py-1.5 bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] rounded-xl text-xs font-bold text-[#1A1A1A] flex items-center gap-1.5 transition-all shadow-xs"
            >
              <Calendar className="w-3.5 h-3.5 text-[#0D9488]" />
              <span>Schedule Visit</span>
            </Link>
          </div>
        </div>

        {/* Canonical Lead Header (Spec #11 & #12) */}
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-5 sm:p-6 shadow-xs space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold font-mono text-[#1A1A1A]">{lead.name || 'Anonymous Prospect'}</h1>
                <ScoreBadge score={lead.score} confidence={lead.score_confidence} showConfidence />
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#E8F5A8] text-[#1A1A1A] border border-[#D4D0C8] uppercase">
                  {lead.status}
                </span>
              </div>
              <p className="text-xs text-[#6B6B6B] font-mono">
                Phone: <span className="font-bold text-[#1A1A1A]">{lead.phone}</span> • Source:{' '}
                <span className="capitalize font-bold text-[#1A1A1A]">{lead.source.replace('_', ' ')}</span>
              </p>
            </div>

            {/* Header Actions */}
            <div className="flex items-center gap-2 flex-wrap">
              <select
                value={lead.status}
                onChange={(e) => handleStatusChange(e.target.value)}
                className="bg-white border border-[#D4D0C8] text-xs font-bold text-[#1A1A1A] rounded-xl px-3 py-2 focus:outline-none focus:border-[#1A1A1A] capitalize shadow-xs"
              >
                <option value="pending">Status: Pending</option>
                <option value="active">Status: Active</option>
                <option value="qualified">Status: Qualified</option>
                <option value="converted">Status: Converted</option>
                <option value="lost">Status: Lost</option>
                <option value="spam">Status: Spam</option>
              </select>

              <button
                onClick={handleTriggerQualify}
                disabled={qualifying}
                className="bg-white border border-[#D4D0C8] hover:bg-[#FAF7F2] text-[#1A1A1A] px-3 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
              >
                <Sparkles className={`w-3.5 h-3.5 text-amber-500 fill-amber-300 ${qualifying ? 'animate-spin' : ''}`} />
                <span>{qualifying ? 'Scoring...' : 'Re-Qualify AI'}</span>
              </button>

              <a
                href={`tel:${lead.phone}`}
                className="bg-[#1A1A1A] hover:bg-black text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-xs flex items-center gap-1.5"
              >
                <PhoneCall className="w-3.5 h-3.5" />
                <span>Call Lead</span>
              </a>
            </div>
          </div>

          {/* Canonical Deal Parameters Bar (Spec #11 & #12 - No repetition across 6 cards) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-[#EAE7E1] text-xs">
            <div className="p-2.5 bg-white rounded-xl border border-[#D4D0C8]">
              <span className="text-[10px] text-gray-400 font-mono uppercase block">Budget Profile</span>
              <span className="font-bold text-[#1A1A1A] font-mono">{budgetDisplay}</span>
            </div>
            <div className="p-2.5 bg-white rounded-xl border border-[#D4D0C8]">
              <span className="text-[10px] text-gray-400 font-mono uppercase block">Preferred Location</span>
              <span className="font-bold text-[#1A1A1A] truncate block">{locationDisplay}</span>
            </div>
            <div className="p-2.5 bg-white rounded-xl border border-[#D4D0C8]">
              <span className="text-[10px] text-gray-400 font-mono uppercase block">Property Type</span>
              <span className="font-bold text-[#1A1A1A] capitalize">{lead.property_type || 'Residential Apartment'}</span>
            </div>
            <div className="p-2.5 bg-emerald-50 rounded-xl border border-emerald-200">
              <span className="text-[10px] text-emerald-700 font-mono uppercase block font-bold flex items-center gap-1">
                <Zap className="w-3 h-3 fill-emerald-500" /> Next Best Action
              </span>
              <span className="font-bold text-emerald-950 truncate block text-[11px]">
                {lead.latest_score?.reasoning ? 'Review AI Briefing' : 'Schedule walkthrough'}
              </span>
            </div>
          </div>
        </div>

        {/* Main Operating Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left Column: Interactive Multi-Mode Conversation & Matching Stream (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            {/* View Mode Tabs */}
            <div className="flex items-center gap-1 p-1 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl flex-wrap">
              <button
                onClick={() => setActiveTab('ai')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                  activeTab === 'ai'
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                <Bot className="w-3.5 h-3.5" />
                <span>AI Sales Agent</span>
              </button>
              <button
                onClick={() => setActiveTab('timeline')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                  activeTab === 'timeline'
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>WhatsApp History</span>
              </button>
              <button
                onClick={() => setActiveTab('properties')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                  activeTab === 'properties'
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                <Building className="w-3.5 h-3.5" />
                <span>Matched Properties</span>
              </button>
              <button
                onClick={() => setActiveTab('autonomous')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                  activeTab === 'autonomous'
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                <Compass className="w-3.5 h-3.5" />
                <span>Autonomous Loop</span>
              </button>
            </div>

            {/* Tab Contents */}
            {activeTab === 'ai' && (
              <AIConversationTab
                leadId={lead.id}
                leadName={lead.name}
                leadPhone={lead.phone}
              />
            )}

            {activeTab === 'timeline' && (
              <ConversationTimeline conversations={lead.conversations} />
            )}

            {activeTab === 'properties' && (
              <LeadPropertyMatchesPanel leadId={lead.id} leadName={lead.name} />
            )}

            {activeTab === 'autonomous' && (
              <AutonomousSalesTimeline leadId={lead.id} leadName={lead.name} />
            )}
          </div>

          {/* Right Column: Customer Intelligence Rail & Follow-up Execution (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <ConversationIntelligencePanel leadId={lead.id} leadName={lead.name || 'Valued Client'} />
            <SalesActionCard leadId={lead.id} leadName={lead.name} />
            <SourceAttributionCard lead={lead} />
            <ExtractedDataCard lead={lead} />
          </div>
        </div>
      </main>
    </div>
  );
}
