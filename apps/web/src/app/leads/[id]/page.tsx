'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, PhoneCall, Sparkles, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api-client';
import { LeadDetail } from '@/types';
import ConversationTimeline from '@/components/leads/ConversationTimeline';
import ExtractedDataCard from '@/components/leads/ExtractedDataCard';
import SalesActionCard from '@/components/leads/SalesActionCard';
import ConversationIntelligencePanel from '@/components/leads/ConversationIntelligencePanel';
import AutonomousSalesTimeline from '@/components/leads/AutonomousSalesTimeline';
import ScoreBadge from '@/components/shared/ScoreBadge';
import LeadPropertyMatchesPanel from '@/components/leads/LeadPropertyMatchesPanel';
import AIConversationTab from '@/components/leads/AIConversationTab';
import { Bot, MessageSquare } from 'lucide-react';

export default function LeadDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const leadId = resolvedParams.id;

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [qualifying, setQualifying] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'ai' | 'whatsapp'>('ai');

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
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-400">
        <RefreshCw className="w-8 h-8 mx-auto animate-spin text-emerald-400 mb-3" />
        <p className="text-xs font-bold">Loading Lead & Conversation History...</p>
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-400">
        <AlertTriangle className="w-10 h-10 mx-auto text-amber-400 mb-3" />
        <h3 className="text-lg font-bold text-white mb-2">Lead Not Found</h3>
        <p className="text-xs text-slate-400 mb-4">{error}</p>
        <Link href="/dashboard" className="text-xs font-bold text-emerald-400 hover:underline">
          ← Back to Broker Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-panel p-6 rounded-2xl border border-dark-border">
        <div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-white mb-2 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Dashboard</span>
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-extrabold text-white">{lead.name || 'WhatsApp Lead'}</h1>
            <ScoreBadge score={lead.score} confidence={lead.score_confidence} showConfidence />
          </div>
          <p className="text-xs text-slate-400 font-mono mt-1">
            Phone: {lead.phone} • Source: <span className="capitalize">{lead.source.replace('_', ' ')}</span>
          </p>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-3">
          {/* Status Dropdown */}
          <select
            value={lead.status}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="bg-dark-card border border-dark-border text-xs font-bold text-white rounded-xl px-3 py-2.5 focus:outline-none focus:border-emerald-500 capitalize"
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
            className="bg-dark-card border border-dark-border hover:bg-white/10 text-emerald-400 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 disabled:opacity-50"
          >
            <Sparkles className={`w-4 h-4 ${qualifying ? 'animate-spin' : ''}`} />
            <span>{qualifying ? 'Scoring...' : 'Re-Qualify AI'}</span>
          </button>

          <a
            href={`tel:${lead.phone}`}
            className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 px-4 py-2.5 rounded-xl text-xs font-extrabold transition-all shadow-lg shadow-emerald-500/20 flex items-center gap-2"
          >
            <PhoneCall className="w-4 h-4" />
            <span>Call Lead</span>
          </a>
        </div>
      </div>

      {/* Dual Panel Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: AI Conversation Tab or WhatsApp Timeline */}
        <div className="lg:col-span-7 space-y-4">
          {/* Tab Selector */}
          <div className="flex items-center gap-2 p-1 bg-slate-900 border border-slate-800 rounded-xl w-fit">
            <button
              onClick={() => setActiveTab('ai')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'ai'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              <span>AI Sales Agent</span>
            </button>
            <button
              onClick={() => setActiveTab('whatsapp')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                activeTab === 'whatsapp'
                  ? 'bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>WhatsApp Timeline</span>
            </button>
          </div>

          {activeTab === 'ai' ? (
            <AIConversationTab
              leadId={lead.id}
              leadName={lead.name}
              leadPhone={lead.phone}
            />
          ) : (
            <ConversationTimeline conversations={lead.conversations} />
          )}
        </div>

        {/* Right: AI Conversation Intelligence, Next Best Action & Extracted Data */}
        <div className="lg:col-span-5 space-y-6">
          <ConversationIntelligencePanel leadId={lead.id} leadName={lead.name || 'Valued Client'} />
          <SalesActionCard leadId={lead.id} leadName={lead.name} />
          {/* Part 21.8 — Autonomous Sales Loop Timeline & Broker Controls */}
          <AutonomousSalesTimeline leadId={lead.id} leadName={lead.name} />
          {/* Part 29 — Explainable AI Property Matches */}
          <LeadPropertyMatchesPanel leadId={lead.id} leadName={lead.name} />
          <ExtractedDataCard lead={lead} />
        </div>
      </div>
    </div>
  );
}
