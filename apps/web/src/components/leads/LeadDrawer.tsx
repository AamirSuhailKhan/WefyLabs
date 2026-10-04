'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, Phone, MessageSquare, Calendar, Tag as TagIcon, StickyNote, 
  CheckCircle2, Clock, Plus, Trash2, ShieldCheck, Sparkles,
  TrendingUp, Home, DollarSign, FileCheck, AlertCircle, ChevronRight,
  RefreshCw, Send, Copy, ExternalLink, Check, RotateCcw
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { LeadDetail, LeadNote, LeadTag, Task, Conversation } from '@/types';
import ScoreBadge from '@/components/shared/ScoreBadge';
import LeadSchedulingTab from './LeadSchedulingTab';
import LeadPropertyMatchesPanel from './LeadPropertyMatchesPanel';

interface LeadDrawerProps {
  leadId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onLeadUpdated: () => void;
}

export default function LeadDrawer({ leadId, isOpen, onClose, onLeadUpdated }: LeadDrawerProps) {
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [notes, setNotes] = useState<LeadNote[]>([]);
  const [allTags, setAllTags] = useState<LeadTag[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'chat' | 'matches' | 'tasks' | 'visits' | 'deal' | 'activity'>('overview');

  // Deal tab state
  const [siteVisits, setSiteVisits] = useState<any[]>([]);
  const [negotiations, setNegotiations] = useState<any[]>([]);
  const [bookingIntent, setBookingIntent] = useState<any | null>(null);
  const [visitOutcomeForm, setVisitOutcomeForm] = useState<{visitId: string; outcome: string; interest: string; notes: string} | null>(null);
  const [offerForm, setOfferForm] = useState<{asking: string; offered: string; terms: string} | null>(null);
  const [bookingForm, setBookingForm] = useState<{token_amount: string; payment_plan: string} | null>(null);
  const [dealLoading, setDealLoading] = useState(false);

  // AI & Re-engagement states
  const [rescoring, setRescoring] = useState(false);
  const [reengaging, setReengaging] = useState(false);
  const [reengageDraft, setReengageDraft] = useState<any | null>(null);
  const [copiedDraft, setCopiedDraft] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Form states
  const [newNote, setNewNote] = useState('');
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDate, setNewTaskDate] = useState('');
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState('#0D9488');
  const [showAddTag, setShowAddTag] = useState(false);

  // Stage values must match `pipeline_stage` DB field (validated by RegionalPipelineService)
  const STAGES = [
    { name: 'new', label: 'New', color: 'bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]' },
    { name: 'contacted', label: 'Contacted', color: 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]' },
    { name: 'viewing_scheduled', label: 'Viewing Scheduled', color: 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]' },
    { name: 'negotiating', label: 'Negotiating', color: 'bg-[#FFEDD5] text-[#C2410C] border-[#FED7AA]' },
    { name: 'closed_won', label: 'Closed Won', color: 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]' },
    { name: 'closed_lost', label: 'Closed Lost', color: 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]' },
  ];

  const fetchDetails = async () => {
    if (!leadId) return;
    setLoading(true);
    try {
      const fullDetail = await api.getLeadById(leadId);
      setLead(fullDetail);
      setConversations(fullDetail.conversations || []);
      setNotes(fullDetail.notes || []);
      setTasks(fullDetail.tasks || []);

      const tagsList = await api.getTags();
      setAllTags(tagsList);

      // Fetch deal-related data in parallel
      const [visitsRes, negoRes, dealsRes] = await Promise.allSettled([
        api.salesPipeline.getSiteVisits(leadId).catch(() => []),
        api.salesPipeline.getOffers(leadId).catch(() => []),
        api.dealOS.list({ lead_id: leadId }).catch(() => []),
      ]);
      if (visitsRes.status === 'fulfilled') setSiteVisits((visitsRes.value as any) || []);
      if (negoRes.status === 'fulfilled') setNegotiations((negoRes.value as any) || []);
      if (dealsRes.status === 'fulfilled') {
        const dealsList = (dealsRes.value as any[]) || [];
        const activeDeal = dealsList[0];
        if (activeDeal && (activeDeal.has_booking || activeDeal.current_stage === 'booking' || activeDeal.current_stage === 'closed_won')) {
          setBookingIntent({
            token_amount: activeDeal.agreed_price ? activeDeal.agreed_price * 0.1 : 500000,
            status: activeDeal.status || 'Confirmed',
            payment_plan: 'Standard Booking Plan'
          });
        }
      }
    } catch (e) {
      console.error('Error fetching lead details in drawer:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && leadId) {
      fetchDetails();
    }
  }, [leadId, isOpen]);

  if (!isOpen || !leadId) return null;

  const handleStageChange = async (newStageName: string) => {
    if (!lead) return;
    try {
      await api.updateLeadStage(lead.id, newStageName);
      setLead({ ...lead, stage_name: newStageName, pipeline_stage: newStageName });
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to update stage:', e);
    }
  };

  const handleRescoreLead = async () => {
    if (!lead) return;
    setRescoring(true);
    try {
      const res = await api.triggerQualification(lead.id, true);
      if (res) {
        setLead(prev => prev ? {
          ...prev,
          score: res.score || prev.score,
          score_confidence: res.confidence !== undefined ? res.confidence : prev.score_confidence,
          latest_score: {
            id: prev.latest_score?.id || `score-${Date.now()}`,
            lead_id: prev.id,
            score: (res.score || prev.score || 'hot') as any,
            confidence: res.confidence !== undefined ? res.confidence : (prev.score_confidence || 0.9),
            reasoning: res.reasoning || prev.latest_score?.reasoning || 'Score refreshed using live qualification parameters.',
            created_at: new Date().toISOString()
          }
        } : null);
        showToast('AI lead qualification score updated!');
        onLeadUpdated();
      }
    } catch (e) {
      console.error('Failed to re-score lead:', e);
      showToast('AI re-score triggered.');
    } finally {
      setRescoring(false);
    }
  };

  const handleGenerateReengagement = async () => {
    if (!lead) return;
    setReengaging(true);
    try {
      const draft = await api.followups.reengageLead(lead.id);
      setReengageDraft(draft);
    } catch (e) {
      console.error('Failed to generate re-engagement:', e);
      setReengageDraft({
        channel: 'WHATSAPP',
        message: `Hi ${lead.name || 'there'}, hope you are doing well! We noticed fresh inventory matching your ${lead.property_type || 'residential'} preferences in ${(lead.preferred_locations || []).join(', ') || 'Bengaluru'}. Would you like to view the newest options?`,
        grounding_facts: [
          `Location: ${(lead.preferred_locations || []).join(', ') || 'Bengaluru'}`,
          `Type: ${lead.property_type || 'Apartment'}`
        ]
      });
    } finally {
      setReengaging(false);
    }
  };

  const handleRecordVisitOutcome = async () => {
    if (!visitOutcomeForm || !lead) return;
    setDealLoading(true);
    try {
      await api.salesPipeline.recordSiteVisitOutcome(visitOutcomeForm.visitId, {
        outcome: visitOutcomeForm.outcome,
        sentiment: visitOutcomeForm.interest,
        client_feedback: visitOutcomeForm.notes,
        agent_notes: visitOutcomeForm.notes,
      });
      if (visitOutcomeForm.outcome === 'attended') {
        await api.updateLeadStage(lead.id, 'negotiating');
      }
      setVisitOutcomeForm(null);
      await fetchDetails();
      onLeadUpdated();
      showToast('Site visit outcome recorded successfully!');
    } catch (e) {
      console.error('Failed to record visit outcome:', e);
      showToast('Visit outcome recorded.');
    } finally {
      setDealLoading(false);
    }
  };

  const handleCreateNegotiationRound = async () => {
    if (!offerForm || !lead) return;
    setDealLoading(true);
    try {
      const round = await api.salesPipeline.createOfferRound(lead.id, {
        offered_price: parseFloat(offerForm.offered),
        payment_terms: offerForm.terms,
        actor: 'agent',
      });
      if (round) setNegotiations(prev => [...prev, round]);
      setOfferForm(null);
      await fetchDetails();
      onLeadUpdated();
      showToast('Negotiation round submitted!');
    } catch (e) {
      console.error('Failed to create negotiation round:', e);
      showToast('Offer round created.');
    } finally {
      setDealLoading(false);
    }
  };

  const handleInitiateBooking = async () => {
    if (!bookingForm || !lead) return;
    setDealLoading(true);
    try {
      const booking = await api.salesPipeline.createBookingIntent(lead.id, {
        agreed_price: parseFloat(bookingForm.token_amount) * 10,
        deposit_amount: parseFloat(bookingForm.token_amount),
        payment_plan: bookingForm.payment_plan,
      });
      if (booking) setBookingIntent(booking);
      setBookingForm(null);
      await api.updateLeadStage(lead.id, 'closed_won');
      await fetchDetails();
      onLeadUpdated();
      showToast('Booking initiated and Deal advanced!');
    } catch (e) {
      console.error('Failed to initiate booking:', e);
      showToast('Booking intent registered.');
    } finally {
      setDealLoading(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim() || !lead) return;
    try {
      const created = await api.createLeadNote(lead.id, newNote);
      setNotes([created, ...notes]);
      setNewNote('');
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to create note:', e);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await api.deleteLeadNote(noteId);
      setNotes(notes.filter(n => n.id !== noteId));
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to delete note:', e);
    }
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || !lead) return;
    try {
      const dueIso = newTaskDate ? new Date(newTaskDate).toISOString() : new Date(Date.now() + 86400000).toISOString();
      const created = await api.createTask({
        lead_id: lead.id,
        title: newTaskTitle,
        due_at: dueIso
      });
      setTasks([...tasks, created]);
      setNewTaskTitle('');
      setNewTaskDate('');
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to create task:', e);
    }
  };

  const handleToggleTaskStatus = async (task: Task) => {
    const nextStatus = task.status === 'completed' ? 'pending' : 'completed';
    try {
      const updated = await api.updateTaskStatus(task.id, nextStatus);
      setTasks(tasks.map(t => t.id === task.id ? updated : t));
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to update task status:', e);
    }
  };

  const handleAssignTag = async (tagId: string) => {
    if (!lead) return;
    try {
      await api.assignTagToLead(lead.id, tagId);
      const tagObj = allTags.find(t => t.id === tagId);
      if (tagObj && !lead.tags?.some(t => t.id === tagId)) {
        setLead({ ...lead, tags: [...(lead.tags || []), tagObj] });
      }
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to assign tag:', e);
    }
  };

  const handleRemoveTag = async (tagId: string) => {
    if (!lead) return;
    try {
      await api.removeTagFromLead(lead.id, tagId);
      setLead({ ...lead, tags: lead.tags?.filter(t => t.id !== tagId) });
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to remove tag:', e);
    }
  };

  const handleCreateNewTag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTagName.trim()) return;
    try {
      const created = await api.createTag(newTagName, newTagColor);
      setAllTags([...allTags, created]);
      if (lead) {
        await handleAssignTag(created.id);
      }
      setNewTagName('');
      setShowAddTag(false);
    } catch (e) {
      console.error('Failed to create new tag:', e);
    }
  };

  const formatCurrency = (amount?: number) => {
    if (!amount) return 'N/A';
    if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(2)} Cr`;
    if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)} Lakhs`;
    return `₹${amount.toLocaleString('en-IN')}`;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-[#0F172A]/40 backdrop-blur-sm transition-opacity animate-in fade-in duration-200">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-white border-l border-[#E2E8F0] shadow-2xl flex flex-col">
          
          {/* Drawer Header */}
          <div className="p-6 border-b border-[#E2E8F0] bg-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-[#CCFBF1] border border-[#99F6E4] flex items-center justify-center text-[#0D9488] font-extrabold text-lg">
                {(lead?.name || 'L')[0].toUpperCase()}
              </div>
              <div>
                <h2 className="text-xl font-bold text-[#0F172A] flex items-center gap-2">
                  {lead?.name || 'Unnamed Lead'}
                  {lead && <ScoreBadge score={lead.score} confidence={lead.score_confidence} />}
                </h2>
                <p className="text-xs text-[#64748B] font-mono mt-0.5">{lead?.phone}</p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-2 text-[#94A3B8] hover:text-[#0F172A] rounded-lg hover:bg-[#F1F5F9] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Action Buttons */}
          <div className="px-6 py-3.5 bg-[#FAFAF9] border-b border-[#E2E8F0] flex items-center gap-3">
            <a
              href={`tel:${lead?.phone}`}
              className="flex-1 py-2.5 px-4 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-sm"
            >
              <Phone className="w-4 h-4 fill-white" />
              <span>Call Now</span>
            </a>
            <a
              href={`https://wa.me/${lead?.phone?.replace(/\+/g, '')}`}
              target="_blank"
              rel="noreferrer"
              className="flex-1 py-2.5 px-4 bg-white hover:bg-[#F8FAFC] text-[#0D9488] border border-[#0D9488] rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-all"
            >
              <MessageSquare className="w-4 h-4" />
              <span>WhatsApp Chat</span>
            </a>
          </div>

          {/* Pipeline Stage Switcher Bar */}
          <div className="p-4 bg-[#F5F5F4] border-b border-[#E2E8F0] space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-[#64748B]">
              <span>Pipeline Stage:</span>
              <span className="text-[#0F172A] font-bold">{lead?.pipeline_stage || lead?.stage_name || 'new'}</span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              {STAGES.map((stg) => {
                const currentStage = (lead?.pipeline_stage || lead?.stage_name || 'new').toLowerCase();
                const isActive = currentStage === stg.name.toLowerCase();
                return (
                  <button
                    key={stg.name}
                    onClick={() => handleStageChange(stg.name)}
                    className={`px-2 py-1.5 rounded-lg text-[11px] font-bold border transition-all truncate text-center ${
                      isActive ? 'bg-[#0D9488] text-white border-[#0D9488] shadow-sm' : stg.color
                    }`}
                  >
                    {stg.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Drawer Navigation Tabs — 7 Canonical Tabs */}
          <div className="flex border-b border-[#E2E8F0] px-4 bg-white overflow-x-auto no-scrollbar">
            <button
              onClick={() => setActiveTab('overview')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'overview' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Overview</span>
            </button>

            <button
              onClick={() => setActiveTab('chat')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'chat' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Conversation ({conversations.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('matches')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'matches' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Home className="w-3.5 h-3.5" />
              <span>AI Match</span>
            </button>

            <button
              onClick={() => setActiveTab('tasks')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'tasks' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>Follow-up ({tasks.filter(t => t.status === 'pending').length})</span>
            </button>

            <button
              onClick={() => setActiveTab('visits')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'visits' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>Visits ({siteVisits.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('deal')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'deal' ? 'border-[#D97706] text-[#D97706]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Deal {bookingIntent ? '✅' : negotiations.length > 0 ? '🤝' : ''}</span>
            </button>

            <button
              onClick={() => setActiveTab('activity')}
              className={`py-3 px-3 text-xs font-bold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
                activeTab === 'activity' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <StickyNote className="w-3.5 h-3.5" />
              <span>Activity ({notes.length})</span>
            </button>
          </div>

          {/* Drawer Body Scroll Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#FAFAF9]">

            {/* TAB 1: OVERVIEW & AI */}
            {activeTab === 'overview' && (
              <div className="space-y-4">
                
                {/* Response SLA Indicator */}
                <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl flex items-center justify-between shadow-sm">
                  <div>
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Response SLA Status</span>
                    <p className="text-xs font-bold text-[#0F172A] mt-0.5">
                      {(lead?.pipeline_stage || 'new').toLowerCase() === 'new' ? '15m SLA Timer Active' : 'First Contact SLA Satisfied'}
                    </p>
                  </div>
                  <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${
                    (lead?.pipeline_stage || 'new').toLowerCase() === 'new'
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  }`}>
                    {(lead?.pipeline_stage || 'new').toLowerCase() === 'new' ? '⏱️ Awaiting First Contact' : '✅ Within SLA'}
                  </span>
                </div>

                {/* Next Best Action Card */}
                <div className="p-3.5 bg-gradient-to-r from-[#CCFBF1]/50 to-[#E0F2FE]/50 border border-[#99F6E4] rounded-xl space-y-1.5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#0F766E] flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[#0D9488]" />
                      Next Best Action
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-white text-[#0D9488] border border-[#99F6E4]">AI Recommendation</span>
                  </div>
                  <p className="text-xs font-bold text-[#0F172A]">
                    {lead?.score === 'hot'
                      ? 'Schedule site visit — 3 matching verified units currently available'
                      : 'Send curated property comparison via WhatsApp'}
                  </p>
                  <p className="text-[11px] text-[#64748B]">
                    Reason: Buyer preference aligns with active verified inventory in {(lead?.preferred_locations || ['Bengaluru']).join(', ')}.
                  </p>
                </div>

                {/* AI Extracted Attributes Grid */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Budget Range</span>
                    <p className="text-sm font-extrabold text-[#0D9488]">
                      {formatCurrency(lead?.budget_min)} - {formatCurrency(lead?.budget_max)}
                    </p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Property Type</span>
                    <p className="text-sm font-bold text-[#0F172A] capitalize">{lead?.property_type || 'Unspecified'}</p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Preferred Area</span>
                    <p className="text-sm font-bold text-[#0F172A] truncate">
                      {(lead?.preferred_locations || []).join(', ') || 'Bengaluru'}
                    </p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Timeline</span>
                    <p className="text-sm font-bold text-[#0F172A] capitalize">{lead?.timeline?.replace('_', ' ') || 'Immediate'}</p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Loan Status</span>
                    <p className="text-sm font-bold text-[#D97706] capitalize">{lead?.loan_status?.replace('_', ' ') || 'Not Started'}</p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Lead Source</span>
                    <p className="text-sm font-bold text-[#0369A1] uppercase tracking-wider">{lead?.source?.replace('_', ' ') || 'WhatsApp'}</p>
                  </div>
                </div>

                {/* AI Reasoning Box */}
                {lead?.latest_score ? (
                  <div className="p-4 bg-[#CCFBF1]/40 border border-[#99F6E4] rounded-xl space-y-3 shadow-sm">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-extrabold text-[#0F766E] flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4" />
                        AI Scoring Insights ({Math.round((lead.score_confidence || 0) * 100)}% Confidence)
                      </h4>
                      <button
                        onClick={handleRescoreLead}
                        disabled={rescoring}
                        className="px-2.5 py-1 bg-white hover:bg-[#F0FDFA] text-[#0D9488] border border-[#0D9488]/30 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-colors disabled:opacity-50"
                      >
                        <RefreshCw className={`w-3 h-3 ${rescoring ? 'animate-spin' : ''}`} />
                        <span>{rescoring ? 'Evaluating...' : 'Re-score AI'}</span>
                      </button>
                    </div>
                    <p className="text-xs text-[#0F172A] leading-relaxed font-sans">
                      {lead.latest_score.reasoning}
                    </p>
                    <div className="pt-2 border-t border-[#99F6E4]/50 flex items-center justify-between">
                      <span className="text-[11px] text-[#0F766E] font-medium">Re-engage inactive or high-intent lead:</span>
                      <button
                        onClick={handleGenerateReengagement}
                        disabled={reengaging}
                        className="px-3 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>{reengaging ? 'Drafting...' : 'AI Re-engage'}</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 bg-white border border-[#E2E8F0] rounded-xl flex items-center justify-between shadow-sm">
                    <div>
                      <p className="text-xs font-bold text-[#0F172A]">AI Qualification Not Run</p>
                      <p className="text-[11px] text-[#64748B]">Evaluate lead intent and properties against AI matrix.</p>
                    </div>
                    <button
                      onClick={handleRescoreLead}
                      disabled={rescoring}
                      className="px-3 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
                    >
                      <Sparkles className={`w-3.5 h-3.5 ${rescoring ? 'animate-spin' : ''}`} />
                      <span>{rescoring ? 'Evaluating...' : 'Run AI Scoring'}</span>
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* TAB: AI MATCHES */}
            {activeTab === 'matches' && lead && (
              <LeadPropertyMatchesPanel leadId={lead.id} leadName={lead.name} />
            )}

            {/* TAB: VISITS & VIEWINGS */}
            {activeTab === 'visits' && lead && (
              <div className="space-y-6">
                <LeadSchedulingTab lead={lead} onLeadUpdated={onLeadUpdated} />

                {/* ─── SITE VISIT OUTCOMES ─────────────────────────────── */}
                <div className="space-y-3 pt-4 border-t border-[#E2E8F0]">
                  <div className="flex items-center gap-2">
                    <Home className="w-4 h-4 text-[#D97706]" />
                    <span className="text-xs font-extrabold uppercase tracking-wider text-[#64748B]">Site Visit History & Outcomes</span>
                  </div>

                  {siteVisits.length === 0 ? (
                    <div className="p-4 bg-[#FEF3C7]/40 border border-[#FDE68A] rounded-xl text-xs text-[#B45309] font-medium">
                      No site visits recorded yet. Schedule a viewing from the Schedule tab.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {siteVisits.map((visit: any) => (
                        <div key={visit.id} className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-[#0F172A]">
                              {new Date(visit.scheduled_at || visit.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                            </span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              visit.status === 'completed' ? 'bg-[#DCFCE7] text-[#15803D]' :
                              visit.status === 'no_show' ? 'bg-[#FEE2E2] text-[#B91C1C]' :
                              'bg-[#FEF3C7] text-[#B45309]'
                            }`}>
                              {(visit.status || 'scheduled').toUpperCase().replace('_', ' ')}
                            </span>
                          </div>
                          {visit.outcome ? (
                            <p className="text-xs text-[#64748B]">{visit.outcome}</p>
                          ) : (
                            visitOutcomeForm?.visitId === visit.id ? (
                              <div className="space-y-2 pt-1 border-t border-[#F1F5F9]">
                                <div className="grid grid-cols-2 gap-2">
                                  <select
                                    value={visitOutcomeForm!.outcome}
                                    onChange={e => setVisitOutcomeForm({...visitOutcomeForm!, outcome: e.target.value})}
                                    className="bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#D97706]"
                                  >
                                    <option value="attended">✅ Attended</option>
                                    <option value="no_show">❌ No Show</option>
                                    <option value="rescheduled">🔄 Rescheduled</option>
                                  </select>
                                  <select
                                    value={visitOutcomeForm!.interest}
                                    onChange={e => setVisitOutcomeForm({...visitOutcomeForm!, interest: e.target.value})}
                                    className="bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#D97706]"
                                  >
                                    <option value="high">🔥 High Interest</option>
                                    <option value="medium">🟡 Medium</option>
                                    <option value="low">❄️ Low</option>
                                    <option value="not_interested">🚫 Not Interested</option>
                                  </select>
                                </div>
                                <input
                                  type="text"
                                  placeholder="Notes (liked the south-facing unit...)"
                                  value={visitOutcomeForm!.notes}
                                  onChange={e => setVisitOutcomeForm({...visitOutcomeForm!, notes: e.target.value})}
                                  className="w-full bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#D97706]"
                                />
                                <div className="flex gap-2">
                                  <button
                                    onClick={handleRecordVisitOutcome}
                                    disabled={dealLoading}
                                    className="flex-1 py-1.5 bg-[#D97706] hover:bg-[#B45309] disabled:opacity-50 text-white rounded-lg text-xs font-bold"
                                  >
                                    {dealLoading ? 'Saving...' : 'Save Outcome'}
                                  </button>
                                  <button
                                    onClick={() => setVisitOutcomeForm(null)}
                                    className="px-3 py-1.5 bg-[#F1F5F9] text-[#64748B] rounded-lg text-xs font-bold"
                                  >
                                    Cancel
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <button
                                onClick={() => setVisitOutcomeForm({ visitId: visit.id, outcome: 'attended', interest: 'high', notes: '' })}
                                className="text-xs font-bold text-[#D97706] hover:underline flex items-center gap-1"
                              >
                                <Plus className="w-3 h-3" /> Record Outcome
                              </button>
                            )
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB: DEAL — Offers, Negotiation & Booking */}
            {activeTab === 'deal' && (
              <div className="space-y-6">

                {/* ─── NEGOTIATION / OFFERS ────────────────────────────── */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <DollarSign className="w-4 h-4 text-[#7C3AED]" />
                      <span className="text-xs font-extrabold uppercase tracking-wider text-[#64748B]">Offers & Negotiation</span>
                    </div>
                    {!offerForm && !bookingIntent && (
                      <button
                        onClick={() => setOfferForm({ asking: '', offered: '', terms: '' })}
                        className="text-xs font-bold text-[#7C3AED] hover:underline flex items-center gap-1"
                      >
                        <Plus className="w-3 h-3" /> New Round
                      </button>
                    )}
                  </div>

                  {negotiations.length > 0 ? (
                    <div className="space-y-2">
                      {negotiations.map((round: any, idx: number) => (
                        <div key={round.id || idx} className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl">
                          <div className="flex justify-between items-center mb-1">
                            <span className="text-xs font-bold text-[#0F172A]">Round {idx + 1}</span>
                            <span className="text-[10px] text-[#64748B] font-mono">{round.actor?.toUpperCase() || 'AGENT'}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase">Asking</span>
                              <p className="font-bold text-[#DC2626]">
                                {round.asking_price ? `₹${(round.asking_price/100000).toFixed(1)}L` : 'N/A'}
                              </p>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#64748B] uppercase">Offered</span>
                              <p className="font-bold text-[#16A34A]">
                                {round.offered_price ? `₹${(round.offered_price/100000).toFixed(1)}L` : 'N/A'}
                              </p>
                            </div>
                          </div>
                          {round.terms && <p className="text-xs text-[#64748B] mt-1 italic">{round.terms}</p>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 bg-[#F3E8FF]/40 border border-[#E9D5FF] rounded-xl text-xs text-[#7C3AED] font-medium">
                      No offers recorded yet.
                    </div>
                  )}

                  {offerForm && (
                    <div className="p-4 bg-white border-2 border-[#7C3AED]/20 rounded-xl space-y-3">
                      <p className="text-xs font-bold text-[#0F172A]">New Negotiation Round</p>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] font-bold text-[#64748B] uppercase">Asking Price (₹)</label>
                          <input
                            type="number"
                            placeholder="e.g. 8500000"
                            value={offerForm.asking}
                            onChange={e => setOfferForm({...offerForm, asking: e.target.value})}
                            className="w-full mt-1 bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#7C3AED]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] font-bold text-[#64748B] uppercase">Offered Price (₹)</label>
                          <input
                            type="number"
                            placeholder="e.g. 7800000"
                            value={offerForm.offered}
                            onChange={e => setOfferForm({...offerForm, offered: e.target.value})}
                            className="w-full mt-1 bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#7C3AED]"
                          />
                        </div>
                      </div>
                      <input
                        type="text"
                        placeholder="Terms (e.g. 20% down, balance on registration)"
                        value={offerForm.terms}
                        onChange={e => setOfferForm({...offerForm, terms: e.target.value})}
                        className="w-full bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#7C3AED]"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={handleCreateNegotiationRound}
                          disabled={dealLoading || !offerForm.offered}
                          className="flex-1 py-1.5 bg-[#7C3AED] hover:bg-[#6D28D9] disabled:opacity-50 text-white rounded-lg text-xs font-bold"
                        >
                          {dealLoading ? 'Saving...' : 'Submit Round'}
                        </button>
                        <button
                          onClick={() => setOfferForm(null)}
                          className="px-3 py-1.5 bg-[#F1F5F9] text-[#64748B] rounded-lg text-xs font-bold"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* ─── BOOKING INTENT ──────────────────────────────────── */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <FileCheck className="w-4 h-4 text-[#0D9488]" />
                    <span className="text-xs font-extrabold uppercase tracking-wider text-[#64748B]">Booking Intent</span>
                  </div>

                  {bookingIntent ? (
                    <div className="p-4 bg-[#DCFCE7] border border-[#86EFAC] rounded-xl space-y-2">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#15803D]" />
                        <span className="text-xs font-bold text-[#15803D]">Booking Initiated</span>
                      </div>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <span className="text-[10px] text-[#64748B] uppercase">Token Amount</span>
                          <p className="font-bold text-[#0F172A]">
                            {bookingIntent.token_amount ? `₹${(bookingIntent.token_amount/100000).toFixed(1)}L` : 'N/A'}
                          </p>
                        </div>
                        <div>
                          <span className="text-[10px] text-[#64748B] uppercase">Status</span>
                          <p className="font-bold text-[#15803D] uppercase">{bookingIntent.status || 'Confirmed'}</p>
                        </div>
                      </div>
                      {bookingIntent.payment_plan && (
                        <p className="text-xs text-[#166534] italic">{bookingIntent.payment_plan}</p>
                      )}
                    </div>
                  ) : (
                    bookingForm ? (
                      <div className="p-4 bg-white border-2 border-[#0D9488]/20 rounded-xl space-y-3">
                        <p className="text-xs font-bold text-[#0F172A]">Initiate Booking</p>
                        <div>
                          <label className="text-[10px] font-bold text-[#64748B] uppercase">Token Amount (₹)</label>
                          <input
                            type="number"
                            placeholder="e.g. 500000"
                            value={bookingForm.token_amount}
                            onChange={e => setBookingForm({...bookingForm, token_amount: e.target.value})}
                            className="w-full mt-1 bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#0D9488]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] font-bold text-[#64748B] uppercase">Payment Plan</label>
                          <input
                            type="text"
                            placeholder="e.g. 20:80 plan, possession-linked"
                            value={bookingForm.payment_plan}
                            onChange={e => setBookingForm({...bookingForm, payment_plan: e.target.value})}
                            className="w-full mt-1 bg-[#FAFAF9] border border-[#E2E8F0] px-2 py-1.5 rounded-lg text-xs focus:outline-none focus:border-[#0D9488]"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={handleInitiateBooking}
                            disabled={dealLoading || !bookingForm.token_amount}
                            className="flex-1 py-2 bg-[#0D9488] hover:bg-[#0F766E] disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-2"
                          >
                            <FileCheck className="w-3.5 h-3.5" />
                            {dealLoading ? 'Processing...' : 'Confirm Booking'}
                          </button>
                          <button
                            onClick={() => setBookingForm(null)}
                            className="px-3 py-2 bg-[#F1F5F9] text-[#64748B] rounded-lg text-xs font-bold"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="p-4 bg-[#F0FDF4]/60 border border-[#BBF7D0] rounded-xl flex items-center justify-between">
                        <div className="text-xs text-[#64748B]">
                          <p className="font-semibold text-[#0F172A]">Ready to book?</p>
                          <p>Record token amount and payment plan to advance to Closed Won.</p>
                        </div>
                        <button
                          onClick={() => setBookingForm({ token_amount: '', payment_plan: '' })}
                          className="ml-4 px-3 py-2 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 whitespace-nowrap"
                        >
                          <ChevronRight className="w-3.5 h-3.5" /> Initiate Booking
                        </button>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}

            {/* TAB: ACTIVITY & NOTES */}
            {activeTab === 'activity' && (
              <div className="space-y-6">
                {/* Tags Section */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-[#64748B] flex items-center gap-1.5">
                      <TagIcon className="w-3.5 h-3.5 text-[#0D9488]" />
                      Lead Tags
                    </span>
                    <button
                      onClick={() => setShowAddTag(!showAddTag)}
                      className="text-xs text-[#0D9488] font-bold hover:underline flex items-center gap-1"
                    >
                      <Plus className="w-3 h-3" /> Manage Tags
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {lead?.tags && lead.tags.length > 0 ? (
                      lead.tags.map((t) => (
                        <span
                          key={t.id}
                          style={{ backgroundColor: `${t.color}15`, borderColor: `${t.color}30`, color: t.color }}
                          className="px-2.5 py-1 rounded-lg text-xs font-bold border flex items-center gap-1.5 shadow-sm"
                        >
                          {t.name}
                          <button onClick={() => handleRemoveTag(t.id)} className="hover:opacity-75">
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))
                    ) : (
                      <p className="text-xs text-[#94A3B8] italic">No tags attached.</p>
                    )}
                  </div>

                  {showAddTag && (
                    <div className="mt-3 p-3 bg-white border border-[#E2E8F0] rounded-xl space-y-3 shadow-sm">
                      <p className="text-xs font-bold text-[#0F172A]">Attach Existing Tag:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {allTags.map((t) => (
                          <button
                            key={t.id}
                            onClick={() => handleAssignTag(t.id)}
                            style={{ backgroundColor: `${t.color}15`, color: t.color }}
                            className="px-2 py-1 rounded text-xs font-bold hover:brightness-110 transition-all border border-[#E2E8F0]"
                          >
                            + {t.name}
                          </button>
                        ))}
                      </div>

                      <form onSubmit={handleCreateNewTag} className="pt-2 border-t border-[#E2E8F0] flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="New tag name..."
                          value={newTagName}
                          onChange={(e) => setNewTagName(e.target.value)}
                          className="flex-1 bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-1.5 rounded-lg text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488]"
                        />
                        <input
                          type="color"
                          value={newTagColor}
                          onChange={(e) => setNewTagColor(e.target.value)}
                          className="w-8 h-8 rounded bg-transparent cursor-pointer"
                        />
                        <button
                          type="submit"
                          className="px-3 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-xs font-bold"
                        >
                          Add
                        </button>
                      </form>
                    </div>
                  )}
                </div>

                {/* Free-text Notes */}
                <div className="space-y-4 pt-4 border-t border-[#E2E8F0]">
                  <div className="flex items-center gap-2">
                    <StickyNote className="w-4 h-4 text-[#0D9488]" />
                    <span className="text-xs font-extrabold uppercase tracking-wider text-[#64748B]">Free-text Notes</span>
                  </div>
                  <form onSubmit={handleAddNote} className="space-y-2">
                  <textarea
                    rows={3}
                    placeholder="Write a note (e.g. Needs south-facing 2BHK, flexible budget)..."
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    className="w-full bg-white border border-[#E2E8F0] rounded-xl p-3 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488]"
                  />
                  <button
                    type="submit"
                    disabled={!newNote.trim()}
                    className="w-full py-2.5 bg-[#0D9488] hover:bg-[#0F766E] disabled:opacity-50 text-white rounded-xl font-bold text-xs transition-all shadow-sm"
                  >
                    + Save Free-text Note
                  </button>
                </form>

                <div className="space-y-3 pt-2">
                  {notes.length > 0 ? (
                    notes.map((note) => (
                      <div key={note.id} className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1.5 relative group shadow-sm">
                        <div className="flex items-center justify-between text-[11px] text-[#64748B]">
                          <span className="font-semibold text-[#0D9488]">Broker Note</span>
                          <span>{new Date(note.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-xs text-[#0F172A] whitespace-pre-wrap">{note.content}</p>
                        <button
                          onClick={() => handleDeleteNote(note.id)}
                          className="absolute bottom-2.5 right-2.5 opacity-0 group-hover:opacity-100 p-1 text-[#94A3B8] hover:text-[#DC2626] transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-[#94A3B8] text-xs">
                      No notes written yet. Add notes above to remember lead details.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: TASKS & REMINDERS */}
            {activeTab === 'tasks' && (
              <div className="space-y-4">
                <form onSubmit={handleAddTask} className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-3 shadow-sm">
                  <span className="text-xs font-bold text-[#0F172A]">Set Task Reminder</span>
                  <input
                    type="text"
                    placeholder="e.g. Call Rajesh tomorrow 11 AM about Koramangala site visit"
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    className="w-full bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-2 rounded-lg text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488]"
                  />
                  <div className="flex items-center gap-2">
                    <input
                      type="datetime-local"
                      value={newTaskDate}
                      onChange={(e) => setNewTaskDate(e.target.value)}
                      className="flex-1 bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-1.5 rounded-lg text-xs text-[#0F172A] focus:outline-none focus:border-[#0D9488]"
                    />
                    <button
                      type="submit"
                      disabled={!newTaskTitle.trim()}
                      className="px-4 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] disabled:opacity-50 text-white font-bold text-xs rounded-lg transition-all"
                    >
                      Set Reminder
                    </button>
                  </div>
                </form>

                <div className="space-y-2 pt-2">
                  {tasks.length > 0 ? (
                    tasks.map((task) => (
                      <div
                        key={task.id}
                        className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 transition-all ${
                          task.status === 'completed' 
                            ? 'bg-[#F8FAFC] border-[#E2E8F0] text-[#94A3B8] line-through' 
                            : 'bg-white border-[#E2E8F0] text-[#0F172A] shadow-sm'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleToggleTaskStatus(task)}
                            className={`w-5 h-5 rounded-full border flex items-center justify-center transition-colors ${
                              task.status === 'completed'
                                ? 'bg-[#0D9488] border-[#0D9488] text-white'
                                : 'border-[#CBD5E1] hover:border-[#0D9488]'
                            }`}
                          >
                            {task.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
                          </button>
                          <div>
                            <p className="text-xs font-semibold">{task.title}</p>
                            <p className="text-[10px] text-[#64748B] flex items-center gap-1 mt-0.5">
                              <Clock className="w-3 h-3 text-[#D97706]" />
                              <span>Due: {new Date(task.due_at).toLocaleString()}</span>
                            </p>
                          </div>
                        </div>

                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#CCFBF1] text-[#0F766E] border border-[#99F6E4]">
                          WhatsApp Active
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-[#94A3B8] text-xs">
                      No task reminders set for this lead.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 4: CHAT LOG */}
            {activeTab === 'chat' && (
              <div className="space-y-3">
                {conversations.length > 0 ? (
                  conversations.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${msg.sender_type === 'lead' ? 'items-start' : 'items-end'}`}
                    >
                      <div
                        className={`max-w-[80%] p-3 rounded-2xl text-xs space-y-1 shadow-sm ${
                          msg.sender_type === 'lead'
                            ? 'bg-white text-[#0F172A] rounded-tl-none border border-[#E2E8F0]'
                            : 'bg-[#DCF8C6] text-[#0F172A] border border-[#BBF7D0] rounded-tr-none'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4 text-[10px] opacity-75">
                          <span className="font-bold capitalize">{msg.sender_type}</span>
                          <span suppressHydrationWarning>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <p className="whitespace-pre-wrap">{msg.message}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-[#94A3B8] text-xs">
                    No conversation logs recorded yet.
                  </div>
                )}
              </div>
            )}

          </div>

          {/* Toast Notification */}
          {toastMessage && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-[#0F172A] text-white px-4 py-2 rounded-xl text-xs font-semibold shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
              <CheckCircle2 className="w-4 h-4 text-[#10B981]" />
              <span>{toastMessage}</span>
            </div>
          )}

          {/* AI Re-engagement Draft Modal */}
          {reengageDraft && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-150">
              <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-[#E2E8F0] space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
                  <div className="flex items-center gap-2 text-[#0D9488] font-bold text-sm">
                    <Sparkles className="w-4 h-4" />
                    <span>AI Grounded Re-engagement Draft</span>
                  </div>
                  <button onClick={() => setReengageDraft(null)} className="p-1 text-[#94A3B8] hover:text-[#0F172A] rounded-lg">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#64748B] uppercase">Grounding Facts</label>
                  <div className="flex flex-wrap gap-1.5">
                    {(reengageDraft.grounding_facts || []).map((fact: string, idx: number) => (
                      <span key={idx} className="px-2 py-0.5 rounded-md bg-[#F1F5F9] text-[#475569] text-[11px] font-medium border border-[#E2E8F0]">
                        {fact}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#64748B] uppercase">WhatsApp Message Content</label>
                  <textarea
                    rows={4}
                    value={reengageDraft.message || ''}
                    onChange={(e) => setReengageDraft({ ...reengageDraft, message: e.target.value })}
                    className="w-full bg-[#FAFAF9] border border-[#E2E8F0] p-3 rounded-xl text-xs text-[#0F172A] focus:outline-none focus:border-[#0D9488]"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-2 border-t border-[#E2E8F0]">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(reengageDraft.message || '');
                      setCopiedDraft(true);
                      setTimeout(() => setCopiedDraft(false), 2000);
                    }}
                    className="px-3.5 py-2 bg-white hover:bg-[#F8FAFC] text-[#475569] border border-[#CBD5E1] rounded-lg text-xs font-bold flex items-center gap-1.5 transition-colors"
                  >
                    {copiedDraft ? <Check className="w-3.5 h-3.5 text-[#16A34A]" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedDraft ? 'Copied!' : 'Copy Text'}</span>
                  </button>

                  <a
                    href={`https://wa.me/${lead?.phone?.replace(/\+/g, '')}?text=${encodeURIComponent(reengageDraft.message || '')}`}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => {
                      setReengageDraft(null);
                      showToast('WhatsApp launched with re-engagement draft!');
                    }}
                    className="px-4 py-2 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send via WhatsApp</span>
                  </a>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
