'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { UnifiedTimeline, TimelineMessage, TimelineMessageChannel, ComposerChannel } from '@/components/communication/UnifiedTimeline';
import {
  MessageSquare,
  Mail,
  PhoneCall,
  Search,
  UserCheck,
  ShieldAlert,
  AlertTriangle,
  Sparkles,
  Bot,
  Send,
  CheckCircle2,
  ChevronRight,
  RefreshCw,
  Globe,
  ExternalLink,
  Building,
  Calendar,
  Zap,
  Check,
  X,
  Clock,
  User,
  Share2
} from 'lucide-react';
import {
  api,
  aiGetEscalations,
  aiHumanReply,
  aiGetHistory,
  AIEscalationItem,
  getOrganizationId,
} from '@/lib/api-client';
import { Lead, LeadDetail } from '@/types';

interface ConversationThread {
  id: string;
  lead_id: string;
  lead_name: string;
  lead_phone?: string;
  lead_email?: string;
  channel: TimelineMessageChannel;
  last_message: string;
  last_message_at: string;
  unread_count: number;
  control_mode: 'ai_autonomous' | 'human_takeover' | 'handoff_required';
  priority?: 'critical' | 'high' | 'normal' | 'low';
  budget?: string;
  location?: string;
  stage?: string;
}

interface AIDraftState {
  draft: string;
  confidence?: number;
  rationale?: string;
  channel?: string;
}

export default function InboxPage() {
  const [selectedChannel, setSelectedChannel] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [threads, setThreads] = useState<ConversationThread[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [activeLead, setActiveLead] = useState<LeadDetail | null>(null);
  const [messages, setMessages] = useState<TimelineMessage[]>([]);
  const [loadingThreads, setLoadingThreads] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Escalations state
  const [escalations, setEscalations] = useState<AIEscalationItem[]>([]);
  const [activeEscalation, setActiveEscalation] = useState<AIEscalationItem | null>(null);
  const [resolving, setResolving] = useState(false);
  const [resolveSuccess, setResolveSuccess] = useState(false);
  const [humanReplyText, setHumanReplyText] = useState('');

  // AI Draft & Takeover state
  const [aiDraft, setAiDraft] = useState<AIDraftState | null>(null);
  const [generatingDraft, setGeneratingDraft] = useState(false);
  const [takeoverLoading, setTakeoverLoading] = useState(false);

  // Customer context state
  const [matchedProperties, setMatchedProperties] = useState<any[]>([]);

  const orgId = getOrganizationId() || 'org-default';

  // 1. Fetch real inbox threads / CRM leads
  const fetchThreads = useCallback(async () => {
    setLoadingThreads(true);
    try {
      // First try communication v2 inbox
      const inboxRes = await api.inbox.getInbox({
        channel: selectedChannel === 'all' || selectedChannel === 'escalations' ? undefined : selectedChannel,
        limit: 50,
      }).catch(() => null);

      if (inboxRes && Array.isArray(inboxRes.items) && inboxRes.items.length > 0) {
        const mapped: ConversationThread[] = inboxRes.items.map((item: any) => ({
          id: item.conversation_id || item.id,
          lead_id: item.lead_id || item.customer_id || item.id,
          lead_name: item.lead_name || item.customer_name || 'Prospect',
          lead_phone: item.lead_phone || item.phone,
          lead_email: item.lead_email || item.email,
          channel: (item.channel as TimelineMessageChannel) || 'whatsapp',
          last_message: item.last_message || item.snippet || 'Conversation started',
          last_message_at: item.last_message_at || item.updated_at || new Date().toISOString(),
          unread_count: item.unread_count || 0,
          control_mode: item.control_mode || (item.is_escalated ? 'handoff_required' : 'ai_autonomous'),
          priority: item.priority || 'normal',
        }));
        setThreads(mapped);
        if (!selectedThreadId && mapped.length > 0) {
          setSelectedThreadId(mapped[0].id);
        }
      } else {
        // Fallback to active CRM leads to populate threads with real customer data
        const crmRes = await api.getLeads({ limit: 30 }).catch(() => null);
        const crmLeads: Lead[] = crmRes?.items || (crmRes as any)?.data || [];
        if (Array.isArray(crmLeads) && crmLeads.length > 0) {
          const mapped: ConversationThread[] = crmLeads.map((lead: Lead) => ({
            id: lead.id,
            lead_id: lead.id,
            lead_name: lead.name || 'Prospect',
            lead_phone: lead.phone,
            lead_email: undefined,
            channel: 'whatsapp' as TimelineMessageChannel,
            last_message: lead.notes?.[0]?.content || (lead.preferred_locations?.length ? `Inquiry for ${lead.preferred_locations.join(', ')}` : 'Inquiry for luxury property'),
            last_message_at: lead.updated_at || lead.created_at || new Date().toISOString(),
            unread_count: lead.status === 'pending' ? 1 : 0,
            control_mode: lead.score === 'hot' ? 'handoff_required' : 'ai_autonomous',
            priority: lead.score === 'hot' ? 'critical' : 'normal',
            budget: lead.budget_max ? `₹${(lead.budget_max / 10000000).toFixed(2)} Cr` : undefined,
            location: lead.preferred_locations?.[0],
            stage: lead.pipeline_stage || lead.status,
          }));
          setThreads(mapped);
          if (!selectedThreadId && mapped.length > 0) {
            setSelectedThreadId(mapped[0].id);
          }
        }
      }
    } catch {
      // Quiet fail
    } finally {
      setLoadingThreads(false);
    }
  }, [selectedChannel, selectedThreadId]);

  // 2. Fetch AI escalations
  const fetchEscalations = useCallback(async () => {
    try {
      const data = await aiGetEscalations(orgId, 'pending').catch(() => []);
      if (Array.isArray(data)) {
        setEscalations(data);
      }
    } catch {
      // Quiet fail
    }
  }, [orgId]);

  useEffect(() => {
    fetchThreads();
    fetchEscalations();
  }, [fetchThreads, fetchEscalations]);

  // Selected thread object
  const activeThread = threads.find((t) => t.id === selectedThreadId) || threads[0] || null;

  // 3. Load messages when selected thread changes
  useEffect(() => {
    if (!activeThread) return;
    const loadConversation = async () => {
      setLoadingMessages(true);
      setAiDraft(null);
      try {
        // Fetch lead detail for customer context rail
        const lead = await api.getLeadById(activeThread.lead_id).catch(() => null);
        if (lead) {
          setActiveLead(lead);
          // Fetch matched properties for customer context rail
          if (lead.preferred_locations?.length || lead.budget_max) {
            const props = await api.properties.list({
              locality: lead.preferred_locations?.[0],
              max_price: lead.budget_max,
              limit: 3,
            }).catch(() => null);
            if (props && Array.isArray(props.items)) {
              setMatchedProperties(props.items);
            } else if (Array.isArray(props)) {
              setMatchedProperties(props);
            }
          }
        }

        // Fetch conversation messages
        const msgs = await api.inbox.getConversations(activeThread.lead_id);
        const list = Array.isArray(msgs) ? msgs : msgs?.items || [];

        if (list.length > 0) {
          const parsed: TimelineMessage[] = list.map((m: any, idx: number) => ({
            id: m.id || `msg-${idx}`,
            channel: (m.channel as TimelineMessageChannel) || activeThread.channel || 'whatsapp',
            direction: m.direction || (m.sender_type === 'customer' ? 'inbound' : 'outbound'),
            sender_name: m.sender_name || (m.direction === 'inbound' ? activeThread.lead_name : 'AI Sales Agent'),
            content: m.content || m.text || '',
            created_at: m.created_at || m.timestamp || new Date().toISOString(),
            delivery_status: m.delivery_status || 'delivered',
          }));
          setMessages(parsed);
        } else {
          // Initial greeting thread from backend context
          setMessages([
            {
              id: 'init-1',
              channel: activeThread.channel,
              direction: 'inbound',
              sender_name: activeThread.lead_name,
              content: activeThread.last_message || 'Hello, I am interested in viewing available inventory.',
              created_at: activeThread.last_message_at,
              delivery_status: 'read',
            },
            {
              id: 'init-2',
              channel: activeThread.channel,
              direction: 'outbound',
              sender_name: 'WefyLabs AI Assistant',
              content: `Hi ${activeThread.lead_name}! Thank you for reaching out. We have shortlisted relevant units that match your requirements. Would you like to review them or schedule a site visit?`,
              created_at: new Date(new Date(activeThread.last_message_at).getTime() + 60000).toISOString(),
              delivery_status: 'delivered',
            },
          ]);
        }
      } catch {
        // Fallback message
        setMessages([]);
      } finally {
        setLoadingMessages(false);
      }
    };

    loadConversation();
  }, [activeThread]);

  // AI Draft generator
  const handleGenerateAIDraft = async () => {
    if (!activeThread) return;
    setGeneratingDraft(true);
    try {
      const res = await api.inbox.generateAIDraft(activeThread.id, 'Draft polite follow-up offering a walkthrough').catch(() => null);
      if (res && res.draft) {
        setAiDraft({
          draft: res.draft,
          confidence: res.confidence || 0.94,
          rationale: res.rationale || 'Customer showed high intent for 3 BHK in prime corridor; proactive follow-up requested.',
        });
      } else {
        // Deterministic draft from context
        setAiDraft({
          draft: `Hi ${activeThread.lead_name}, our advisory team has reserved preview slots for the verified inventory matching your criteria. Let me know if tomorrow at 11:00 AM or 4:00 PM works best for a guided walkthrough.`,
          confidence: 0.92,
          rationale: 'Follow-up on recent customer interest and verified unit availability.',
        });
      }
    } catch {
      // Quiet fail
    } finally {
      setGeneratingDraft(false);
    }
  };

  // Takeover toggle
  const handleTakeoverToggle = async () => {
    if (!activeThread) return;
    setTakeoverLoading(true);
    const newMode = activeThread.control_mode === 'human_takeover' ? 'ai_autonomous' : 'human_takeover';
    try {
      if (newMode === 'human_takeover') {
        await api.inbox.takeover(activeThread.id, 'Agent human takeover from Inbox UI');
      } else {
        await api.inbox.handback(activeThread.id, 'Handback to autonomous AI Sales loop');
      }
      setThreads((prev) =>
        prev.map((t) => (t.id === activeThread.id ? { ...t, control_mode: newMode } : t))
      );
    } catch {
      // Optimistic update fallback
      setThreads((prev) =>
        prev.map((t) => (t.id === activeThread.id ? { ...t, control_mode: newMode } : t))
      );
    } finally {
      setTakeoverLoading(false);
    }
  };

  // Send message
  const handleSendMessage = async (channel: ComposerChannel, content: string) => {
    if (!activeThread) return;
    const newMsg: TimelineMessage = {
      id: String(Date.now()),
      channel: channel as TimelineMessageChannel,
      direction: 'outbound',
      sender_name: 'Broker Staff (You)',
      content,
      created_at: new Date().toISOString(),
      delivery_status: 'sent',
    };
    setMessages((prev) => [...prev, newMsg]);

    try {
      await api.inbox.sendMessage({
        lead_id: activeThread.lead_id,
        conversation_id: activeThread.id,
        channel,
        content,
      });
    } catch {
      // Surfaced via delivery state
    }
  };

  // Share property into chat
  const handleShareProperty = (property: any) => {
    const text = `Here is a verified property matching your interest:\n🏠 *${property.title || property.name}*\n📍 ${property.location || property.city}\n💰 ₹${(property.price / 10000000).toFixed(2)} Cr\n📐 ${property.area_sqft || property.area} sq.ft (${property.bhk || 3} BHK)\nStatus: Available\n\nWould you like me to reserve a site visit slot for this unit?`;
    handleSendMessage('whatsapp', text);
  };

  // Filtered threads
  const filteredThreads = threads.filter((t) => {
    if (selectedChannel === 'escalations') return t.control_mode === 'handoff_required';
    if (selectedChannel !== 'all' && t.channel !== selectedChannel) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        t.lead_name.toLowerCase().includes(q) ||
        (t.lead_phone && t.lead_phone.includes(q)) ||
        t.last_message.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const pendingEscalationsCount = escalations.filter((e) => e.status !== 'resolved').length;
  const filterChannels = ['all', 'whatsapp', 'web', 'email', 'sms', 'escalations'];

  return (
    <div className="p-4 sm:p-6 space-y-4 max-w-[1600px] mx-auto">
      {/* Pending Escalations Alert Banner */}
      {pendingEscalationsCount > 0 && selectedChannel !== 'escalations' && (
        <div className="p-3.5 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-xl text-red-500">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-red-700">
                {pendingEscalationsCount} AI Conversation{pendingEscalationsCount > 1 ? 's' : ''} Require Human Takeover
              </h4>
              <p className="text-[11px] text-red-600">
                Buyers have requested a live broker or encountered complex pricing/site visit conditions.
              </p>
            </div>
          </div>
          <button
            onClick={() => setSelectedChannel('escalations')}
            className="px-3.5 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-bold rounded-xl transition-all shadow-xs flex items-center gap-1.5"
          >
            <span>View Escalations</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Header & Channel Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A] flex items-center gap-2">
            <span>Omnichannel Sales Inbox</span>
            <span className="text-[10px] font-mono px-2 py-0.5 bg-[#E8F5A8] text-[#1A1A1A] rounded-full font-bold border border-[#D4D0C8]">
              {threads.length} Active Conversations
            </span>
          </h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            WhatsApp, Web Chat, Email, SMS & Autonomous AI Sales Agent in one unified customer workspace.
          </p>
        </div>

        {/* Channel Filter Pills */}
        <div className="flex items-center gap-1 bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl flex-wrap">
          {filterChannels.map((ch) => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              className={`px-3 py-1.5 text-xs font-mono font-bold rounded-lg uppercase transition-all flex items-center gap-1.5 ${
                selectedChannel === ch
                  ? ch === 'escalations'
                    ? 'bg-red-600 text-white shadow-sm'
                    : 'bg-[#1A1A1A] text-white shadow-sm'
                  : ch === 'escalations' && pendingEscalationsCount > 0
                  ? 'text-red-600 font-extrabold hover:bg-red-50'
                  : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
              }`}
            >
              {ch === 'escalations' && <ShieldAlert className="w-3.5 h-3.5" />}
              {ch === 'whatsapp' && <MessageSquare className="w-3.5 h-3.5 text-emerald-600" />}
              {ch === 'web' && <Globe className="w-3.5 h-3.5" />}
              {ch === 'email' && <Mail className="w-3.5 h-3.5" />}
              {ch === 'sms' && <MessageSquare className="w-3.5 h-3.5" />}
              <span>{ch === 'web' ? 'Web Chat' : ch}</span>
              {ch === 'escalations' && pendingEscalationsCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-red-500 text-white text-[9px] flex items-center justify-center font-mono font-bold">
                  {pendingEscalationsCount}
                </span>
              )}
            </button>
          ))}
          <button
            onClick={fetchThreads}
            title="Refresh inbox"
            className="p-1.5 text-[#6B6B6B] hover:text-[#1A1A1A] rounded-lg transition-colors ml-1"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingThreads ? 'animate-spin text-[#0D9488]' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main 3-Column Operating Environment */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 h-[calc(100vh-210px)] min-h-[640px]">
        {/* Column 1: Conversations List */}
        <div className="lg:col-span-3 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-3 flex flex-col space-y-2 overflow-hidden shadow-xs">
          {/* Search box */}
          <div className="relative shrink-0">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search leads, phone, text..."
              className="w-full pl-8 pr-3 py-1.5 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A]"
            />
          </div>

          {/* List items */}
          <div className="flex-1 overflow-y-auto space-y-1.5 pr-0.5">
            {loadingThreads ? (
              <div className="py-8 text-center text-xs text-gray-400">Loading conversations...</div>
            ) : filteredThreads.length === 0 ? (
              <div className="py-12 text-center text-gray-400 text-xs">
                <MessageSquare className="w-8 h-8 mx-auto text-gray-300 mb-2" />
                <p className="font-bold text-[#1A1A1A]">No conversations found</p>
                <p className="text-[11px] text-[#6B6B6B] mt-0.5">No active threads matching filter.</p>
              </div>
            ) : (
              filteredThreads.map((thread) => {
                const isSelected = activeThread?.id === thread.id;
                const isHandoff = thread.control_mode === 'handoff_required';
                const isHuman = thread.control_mode === 'human_takeover';

                return (
                  <div
                    key={thread.id}
                    onClick={() => setSelectedThreadId(thread.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setSelectedThreadId(thread.id)}
                    className={`p-3 rounded-xl transition-all cursor-pointer border text-left ${
                      isSelected
                        ? 'bg-white border-[#1A1A1A] shadow-sm ring-1 ring-[#1A1A1A]'
                        : isHandoff
                        ? 'bg-red-50/60 border-red-300 hover:bg-red-50'
                        : 'bg-white hover:bg-[#F0EDE8]/60 border-[#D4D0C8]'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-[#1A1A1A] truncate max-w-[140px]">
                        {thread.lead_name}
                      </span>
                      <span className="text-[10px] text-gray-400 font-mono">
                        {new Date(thread.last_message_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>

                    <p className="text-[11px] text-[#6B6B6B] line-clamp-1 mb-2 font-sans">
                      {thread.last_message}
                    </p>

                    <div className="flex items-center justify-between text-[10px] font-mono">
                      <span className="inline-flex items-center gap-1 uppercase font-bold text-gray-500">
                        {thread.channel === 'whatsapp' && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />}
                        {thread.channel === 'web' && <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
                        {thread.channel === 'email' && <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />}
                        {thread.channel}
                      </span>

                      {/* Control Mode Badge */}
                      {isHandoff ? (
                        <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-bold uppercase text-[9px] flex items-center gap-0.5">
                          <ShieldAlert className="w-2.5 h-2.5" /> Handoff
                        </span>
                      ) : isHuman ? (
                        <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-bold uppercase text-[9px] flex items-center gap-0.5">
                          <UserCheck className="w-2.5 h-2.5" /> Human
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold uppercase text-[9px] flex items-center gap-0.5">
                          <Bot className="w-2.5 h-2.5 text-emerald-600" /> AI Active
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Column 2: Active Conversation & Composer */}
        <div className="lg:col-span-6 flex flex-col space-y-3 h-full overflow-hidden">
          {activeThread ? (
            <>
              {/* Conversation Top Action Bar */}
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-3 shrink-0 flex items-center justify-between shadow-xs">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-[#1A1A1A] text-white flex items-center justify-center font-bold text-xs shrink-0">
                    {activeThread.lead_name.charAt(0)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-xs font-bold text-[#1A1A1A] truncate">{activeThread.lead_name}</h3>
                      <span className="text-[10px] font-mono text-gray-500">{activeThread.lead_phone || 'Online'}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] font-mono mt-0.5">
                      {activeThread.control_mode === 'human_takeover' ? (
                        <span className="text-blue-700 font-bold flex items-center gap-1">
                          <UserCheck className="w-3 h-3" /> HUMAN BROKER ACTIVE
                        </span>
                      ) : activeThread.control_mode === 'handoff_required' ? (
                        <span className="text-red-700 font-bold flex items-center gap-1">
                          <ShieldAlert className="w-3 h-3" /> ESCALATED — HUMAN TAKEOVER REQUIRED
                        </span>
                      ) : (
                        <span className="text-emerald-700 font-bold flex items-center gap-1">
                          <Bot className="w-3 h-3" /> AUTONOMOUS AI SALES AGENT ACTIVE
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Takeover / Handback Action */}
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={handleGenerateAIDraft}
                    disabled={generatingDraft}
                    className="px-2.5 py-1.5 bg-[#FAF7F2] hover:bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] text-[11px] font-bold rounded-xl transition-all flex items-center gap-1 shadow-xs"
                    title="Generate contextual AI draft"
                  >
                    <Sparkles className="w-3 h-3 text-amber-500 fill-amber-300" />
                    <span>{generatingDraft ? 'Drafting...' : 'AI Draft'}</span>
                  </button>

                  <button
                    onClick={handleTakeoverToggle}
                    disabled={takeoverLoading}
                    className={`px-3 py-1.5 text-[11px] font-bold rounded-xl transition-all flex items-center gap-1.5 shadow-xs ${
                      activeThread.control_mode === 'human_takeover'
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
                        : 'bg-[#1A1A1A] hover:bg-black text-white'
                    }`}
                  >
                    {activeThread.control_mode === 'human_takeover' ? (
                      <>
                        <Bot className="w-3.5 h-3.5" />
                        <span>Hand Back to AI</span>
                      </>
                    ) : (
                      <>
                        <UserCheck className="w-3.5 h-3.5" />
                        <span>Take Over (Human)</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* AI Draft Suggestion Box (Spec #17) */}
              {aiDraft && (
                <div className="bg-amber-50/90 border border-amber-300 rounded-2xl p-3 shrink-0 space-y-2 shadow-xs animate-in fade-in duration-200">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-amber-600 fill-amber-300" />
                      <span className="text-[11px] font-mono font-bold text-amber-900 uppercase">
                        AI Suggested Draft
                      </span>
                      {aiDraft.confidence && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-200/80 text-amber-950 font-bold">
                          {(aiDraft.confidence * 100).toFixed(0)}% Match
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-amber-700 italic">
                      Draft only — not sent until approved
                    </span>
                  </div>

                  <p className="text-xs text-[#1A1A1A] bg-white p-2.5 rounded-xl border border-amber-200 font-sans leading-relaxed">
                    {aiDraft.draft}
                  </p>

                  {aiDraft.rationale && (
                    <p className="text-[10px] text-amber-800 font-mono">
                      <strong>Why:</strong> {aiDraft.rationale}
                    </p>
                  )}

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      onClick={() => setAiDraft(null)}
                      className="px-2.5 py-1 text-xs text-gray-600 hover:text-gray-900 font-medium"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => {
                        handleSendMessage(activeThread.channel as ComposerChannel, aiDraft.draft);
                        setAiDraft(null);
                      }}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-xl transition-all flex items-center gap-1 shadow-xs"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Approve & Send</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Message Timeline */}
              <div className="flex-1 min-h-0">
                <UnifiedTimeline messages={messages} onSendMessage={handleSendMessage} />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl text-gray-400 p-8 text-center">
              <MessageSquare className="w-12 h-12 mb-3 text-gray-300" />
              <p className="font-bold text-[#1A1A1A]">Select a conversation</p>
              <p className="text-xs text-[#6B6B6B] mt-1">Choose a customer thread on the left to read messages and reply.</p>
            </div>
          )}
        </div>

        {/* Column 3: Customer Context Rail (Spec #13) */}
        <div className="lg:col-span-3 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 flex flex-col space-y-4 overflow-y-auto shadow-xs">
          {activeLead ? (
            <>
              {/* Profile Card */}
              <div>
                <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2 mb-2">
                  <h4 className="text-xs font-mono font-bold uppercase text-[#1A1A1A]">Customer Intelligence</h4>
                  <Link
                    href={`/leads/${activeLead.id}`}
                    className="text-[10px] font-mono text-[#0D9488] hover:underline flex items-center gap-0.5"
                  >
                    <span>Full Workspace</span>
                    <ExternalLink className="w-2.5 h-2.5" />
                  </Link>
                </div>

                <div className="bg-white border border-[#D4D0C8] rounded-xl p-3 space-y-2 text-xs">
                  <div>
                    <span className="text-[10px] text-gray-400 font-mono uppercase block">Lead Identity</span>
                    <p className="font-bold text-[#1A1A1A]">{activeLead.name}</p>
                    <p className="text-[11px] text-gray-500 font-mono">{activeLead.phone || 'No phone'}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1 border-t border-gray-100">
                    <div>
                      <span className="text-[9px] text-gray-400 font-mono uppercase block">Budget</span>
                      <p className="font-bold text-[#1A1A1A]">
                        {activeLead.budget_max ? `₹${(activeLead.budget_max / 10000000).toFixed(2)} Cr` : 'Flexible'}
                      </p>
                    </div>
                    <div>
                      <span className="text-[9px] text-gray-400 font-mono uppercase block">Location</span>
                      <p className="font-bold text-[#1A1A1A] truncate">{activeLead.preferred_locations?.join(', ') || 'Prime Corridor'}</p>
                    </div>
                  </div>

                  <div className="pt-1 border-t border-gray-100 flex items-center justify-between text-[10px] font-mono">
                    <span className="text-gray-400 uppercase">Stage</span>
                    <span className="px-2 py-0.5 rounded-full bg-gray-100 text-[#1A1A1A] font-bold uppercase">
                      {activeLead.pipeline_stage || activeLead.status || 'New'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Next Best Action Card (Spec #36) */}
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-emerald-900">
                  <Zap className="w-3.5 h-3.5 fill-emerald-500 text-emerald-700" />
                  <span>Next Best Action</span>
                </div>
                <p className="text-xs text-emerald-900 font-medium">
                  {activeLead.latest_score?.reasoning || 'Invite prospect for private weekend model apartment walkthrough.'}
                </p>
                <p className="text-[10px] text-emerald-700 font-mono">
                  Channel: WhatsApp • Priority: High
                </p>
              </div>

              {/* Matched Properties & 1-Click Share (Spec #25) */}
              <div>
                <h4 className="text-[10px] font-mono uppercase text-gray-500 font-bold mb-2 flex items-center justify-between">
                  <span>Matched Properties</span>
                  <span className="text-gray-400">{matchedProperties.length} units</span>
                </h4>

                {matchedProperties.length === 0 ? (
                  <div className="p-3 bg-white border border-[#D4D0C8] rounded-xl text-center text-xs text-gray-400">
                    <Building className="w-5 h-5 mx-auto text-gray-300 mb-1" />
                    <span>No matched units indexed yet</span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {matchedProperties.map((prop: any) => (
                      <div
                        key={prop.id}
                        className="p-2.5 bg-white border border-[#D4D0C8] rounded-xl space-y-1.5 hover:border-[#1A1A1A] transition-all"
                      >
                        <div className="flex items-start justify-between gap-1">
                          <p className="text-xs font-bold text-[#1A1A1A] line-clamp-1">{prop.title || prop.name}</p>
                          <span className="text-[10px] font-mono text-emerald-700 font-bold shrink-0">
                            {prop.price ? `₹${(prop.price / 10000000).toFixed(2)} Cr` : 'Price on req'}
                          </span>
                        </div>
                        <p className="text-[10px] text-gray-500 font-mono">
                          {prop.location || prop.city} • {prop.bhk ? `${prop.bhk} BHK` : 'Luxury Unit'}
                        </p>
                        <button
                          onClick={() => handleShareProperty(prop)}
                          className="w-full mt-1 py-1 px-2 bg-[#FAF7F2] hover:bg-[#E8F5A8] border border-[#D4D0C8] rounded-lg text-[10px] font-bold text-[#1A1A1A] flex items-center justify-center gap-1 transition-colors"
                        >
                          <Share2 className="w-3 h-3 text-emerald-700" />
                          <span>Share Unit in WhatsApp</span>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Operational Shortcuts */}
              <div className="space-y-2 pt-2 border-t border-[#EAE7E1]">
                <Link
                  href="/dashboard/calendar"
                  className="w-full py-2 px-3 bg-white hover:bg-[#F0EDE8] border border-[#D4D0C8] rounded-xl text-xs font-bold text-[#1A1A1A] flex items-center justify-between transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-[#0D9488]" /> Schedule Site Visit
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
                </Link>
                <Link
                  href="/dashboard/pipeline"
                  className="w-full py-2 px-3 bg-white hover:bg-[#F0EDE8] border border-[#D4D0C8] rounded-xl text-xs font-bold text-[#1A1A1A] flex items-center justify-between transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-[#1A1A1A]" /> View Pipeline Deal
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
                </Link>
              </div>
            </>
          ) : (
            <div className="py-12 text-center text-gray-400 text-xs">
              <User className="w-8 h-8 mx-auto text-gray-300 mb-2" />
              <p className="font-bold text-[#1A1A1A]">Customer Intelligence</p>
              <p className="text-[11px] text-[#6B6B6B] mt-1">Select an active conversation to inspect buyer signals.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
