'use client';

import React, { useState, useEffect } from 'react';
import { UnifiedTimeline, TimelineMessage } from '@/components/communication/UnifiedTimeline';
import { AICopilotBar } from '@/components/communication/AICopilotBar';
import {
  MessageSquare,
  Mail,
  PhoneCall,
  Filter,
  Search,
  UserCheck,
  Clock,
  Tag,
  ShieldAlert,
  AlertTriangle,
  Sparkles,
  Bot,
  Send,
  CheckCircle2,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';
import {
  api,
  aiGetEscalations,
  aiHumanReply,
  aiGetHistory,
  AIEscalationItem,
  getOrganizationId,
} from '@/lib/api-client';

export default function InboxPage() {
  const [selectedChannel, setSelectedChannel] = useState<string>('all');
  const [activeLeadId, setActiveLeadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TimelineMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Escalation state
  const [escalations, setEscalations] = useState<AIEscalationItem[]>([]);
  const [activeEscalation, setActiveEscalation] = useState<AIEscalationItem | null>(null);
  const [loadingEscalations, setLoadingEscalations] = useState(false);
  const [humanReplyText, setHumanReplyText] = useState('');
  const [resolving, setResolving] = useState(false);
  const [resolveSuccess, setResolveSuccess] = useState(false);

  const orgId = getOrganizationId() || 'org-default';

  const fetchEscalations = async () => {
    setLoadingEscalations(true);
    try {
      const data = await aiGetEscalations(orgId, 'pending');
      if (Array.isArray(data)) {
        setEscalations(data);
      }
    } catch {
      // Fallback empty or mock if offline
    } finally {
      setLoadingEscalations(false);
    }
  };

  useEffect(() => {
    fetchEscalations();
  }, [orgId]);

  useEffect(() => {
    if (!activeLeadId) return;
    const fetchMessages = async () => {
      setIsLoading(true);
      try {
        const data = await api.inbox.getConversations(activeLeadId);
        setMessages(data.items || data || []);
      } catch {
        setMessages([]);
      } finally {
        setIsLoading(false);
      }
    };
    fetchMessages();
  }, [activeLeadId]);

  const handleSelectEscalation = async (esc: AIEscalationItem) => {
    setActiveEscalation(esc);
    setActiveLeadId(esc.lead_id);
    setSelectedChannel('escalations');
    setResolveSuccess(false);

    // Fetch session history as timeline messages
    try {
      const history = await aiGetHistory(esc.session_id, 30);
      if (Array.isArray(history) && history.length > 0) {
        const timelineMsgs: TimelineMessage[] = [];
        history.forEach((turn, idx) => {
          if (turn.customer_message) {
            timelineMsgs.push({
              id: `cust-${idx}`,
              channel: 'whatsapp',
              direction: 'inbound',
              sender_name: esc.lead_name || 'Buyer',
              content: turn.customer_message,
              created_at: turn.created_at || new Date().toISOString(),
            });
          }
          if (turn.agent_response) {
            timelineMsgs.push({
              id: `agent-${idx}`,
              channel: 'whatsapp',
              direction: 'outbound',
              sender_name: 'AI Sales Agent',
              content: turn.agent_response,
              created_at: turn.created_at || new Date().toISOString(),
            });
          }
        });
        setMessages(timelineMsgs);
      }
    } catch {
      // fallback
    }
  };

  const handleResolveAndReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeEscalation || !humanReplyText.trim() || resolving) return;
    setResolving(true);
    try {
      await aiHumanReply(activeEscalation.session_id, {
        content: humanReplyText.trim(),
        agent_name: 'Broker Staff',
        resolve_escalation: true,
        resolution_notes: 'Human broker responded directly via Omnichannel Inbox.',
      });

      // Optimistically add to messages
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          channel: 'whatsapp',
          direction: 'outbound',
          sender_name: 'Human Broker (You)',
          content: humanReplyText.trim(),
          created_at: new Date().toISOString(),
        },
      ]);

      setResolveSuccess(true);
      setHumanReplyText('');
      setEscalations((prev) => prev.filter((e) => e.id !== activeEscalation.id));
      setActiveEscalation(null);
    } catch (e: any) {
      alert(`Reply failed: ${e.message}`);
    } finally {
      setResolving(false);
    }
  };

  const handleSendMessage = async (channel: string, content: string) => {
    const newMsg: TimelineMessage = {
      id: String(Date.now()),
      channel: channel as any,
      direction: 'outbound',
      sender_name: 'Agent',
      content: content,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, newMsg]);
    if (activeLeadId) {
      try {
        await api.inbox.sendMessage({ lead_id: activeLeadId, channel, content });
      } catch {
        /* message already optimistically added */
      }
    }
  };

  const handleSelectReply = (reply: string) => {
    handleSendMessage('whatsapp', reply);
  };

  const pendingEscalationsCount = escalations.filter((e) => e.status !== 'resolved').length;

  return (
    <div className="p-6 space-y-6">
      {/* Pending Escalations Alert Banner */}
      {pendingEscalationsCount > 0 && selectedChannel !== 'escalations' && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-2xl flex items-center justify-between shadow-sm animate-pulse">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/20 rounded-xl text-red-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-red-400">
                {pendingEscalationsCount} AI Conversation{pendingEscalationsCount > 1 ? 's' : ''} Require Human Takeover
              </h4>
              <p className="text-[11px] text-slate-400">
                Buyers have requested a live broker or encountered complex pricing/site visit conditions.
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setSelectedChannel('escalations');
              if (escalations[0]) handleSelectEscalation(escalations[0]);
            }}
            className="px-4 py-2 bg-red-500 hover:bg-red-400 text-slate-950 text-xs font-bold rounded-xl transition-all shadow-md shadow-red-500/20 flex items-center gap-1.5"
          >
            <span>View Escalations</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A] flex items-center gap-2">
            <span>Unified Omnichannel Inbox</span>
            {pendingEscalationsCount > 0 && (
              <span className="text-[10px] font-mono px-2 py-0.5 bg-red-100 text-red-700 rounded-full font-bold">
                {pendingEscalationsCount} Urgent
              </span>
            )}
          </h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Manage WhatsApp, Email, SMS, Calls, and AI Agent Escalations in one customer timeline.
          </p>
        </div>

        {/* Channel Filter Pills */}
        <div className="flex items-center gap-1.5 bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl">
          {['all', 'escalations', 'whatsapp', 'email', 'sms', 'call'].map((ch) => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              className={`px-3 py-1 text-xs font-mono font-bold rounded-lg uppercase transition-all flex items-center gap-1.5 ${
                selectedChannel === ch
                  ? ch === 'escalations'
                    ? 'bg-red-600 text-white shadow-sm'
                    : 'bg-[#1A1A1A] text-white'
                  : ch === 'escalations' && pendingEscalationsCount > 0
                  ? 'text-red-600 font-extrabold hover:bg-red-50'
                  : 'text-gray-600 hover:bg-gray-200'
              }`}
            >
              {ch === 'escalations' && <ShieldAlert className="w-3.5 h-3.5" />}
              <span>{ch}</span>
              {ch === 'escalations' && pendingEscalationsCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-red-500 text-white text-[9px] flex items-center justify-center font-mono font-bold">
                  {pendingEscalationsCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[720px]">
        {/* Left Column: Conversation / Escalation List */}
        <div className="lg:col-span-3 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-3 flex flex-col space-y-2 overflow-y-auto shadow-xs">
          <div className="relative mb-2">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder={selectedChannel === 'escalations' ? 'Search escalations...' : 'Search conversations...'}
              className="w-full pl-9 pr-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
            />
          </div>

          {selectedChannel === 'escalations' ? (
            /* Escalation List */
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1 text-[10px] font-mono text-gray-500">
                <span>PENDING ESCALATIONS</span>
                <button onClick={fetchEscalations} title="Refresh">
                  <RefreshCw className={`w-3 h-3 ${loadingEscalations ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {escalations.length === 0 ? (
                <div className="p-6 text-center text-gray-400 text-xs">
                  <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500 mb-2" />
                  <p className="font-bold text-gray-700">All Escalations Handled</p>
                  <p className="text-[11px]">No pending handoffs at this time.</p>
                </div>
              ) : (
                escalations.map((esc) => {
                  const isSelected = activeEscalation?.id === esc.id;
                  return (
                    <div
                      key={esc.id}
                      onClick={() => handleSelectEscalation(esc)}
                      className={`p-3 rounded-xl transition-all cursor-pointer border ${
                        isSelected
                          ? 'bg-red-50/80 border-red-500 shadow-xs'
                          : 'bg-white hover:bg-red-50/30 border-[#D4D0C8]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold font-mono text-[#1A1A1A]">
                          {esc.lead_name || 'VIP Buyer'}
                        </span>
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold uppercase ${
                            esc.priority === 'critical'
                              ? 'bg-red-200 text-red-900'
                              : esc.priority === 'high'
                              ? 'bg-amber-200 text-amber-900'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          {esc.priority}
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-700 font-medium line-clamp-2">
                        {esc.briefing?.escalation_trigger || esc.reason || 'Requested human broker assistance'}
                      </p>
                      <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                        <span>{esc.created_at ? new Date(esc.created_at).toLocaleTimeString() : 'Just now'}</span>
                        <span className="text-red-600 font-bold flex items-center gap-1">
                          <ShieldAlert className="w-3 h-3" /> Needs Handoff
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          ) : (
            /* Standard Channel Conversation List */
            <>
              {/* Active Conversation Card */}
              <div
                onClick={() => {
                  setActiveLeadId('lead-demo-1');
                  setActiveEscalation(null);
                }}
                className={`p-3 rounded-xl shadow-2xs cursor-pointer border ${
                  activeLeadId === 'lead-demo-1' ? 'bg-white border-[#1A1A1A]' : 'bg-white/70 border-[#D4D0C8]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold font-mono text-[#1A1A1A]">Rahul Sharma</span>
                  <span className="bg-emerald-100 text-emerald-800 text-[9px] font-mono px-1.5 py-0.5 rounded">
                    WhatsApp
                  </span>
                </div>
                <p className="text-[11px] text-gray-600 line-clamp-1">Looking for 3BHK ready to move DLF Phase 5...</p>
                <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                  <span>2 min ago</span>
                  <span className="bg-[#E8F5A8] text-[#1A1A1A] font-bold px-1 rounded">Qualified</span>
                </div>
              </div>

              {/* Secondary Card */}
              <div
                onClick={() => {
                  setActiveLeadId('lead-demo-2');
                  setActiveEscalation(null);
                }}
                className={`p-3 rounded-xl transition-colors cursor-pointer border ${
                  activeLeadId === 'lead-demo-2' ? 'bg-white border-[#1A1A1A]' : 'bg-white/60 hover:bg-white border-[#D4D0C8]'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold font-mono text-[#1A1A1A]">Tariq Al-Mansoor</span>
                  <span className="bg-blue-100 text-blue-800 text-[9px] font-mono px-1.5 py-0.5 rounded">Email</span>
                </div>
                <p className="text-[11px] text-gray-600 line-clamp-1">Please send Golden Visa brochure...</p>
                <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400 font-mono">
                  <span>1 hour ago</span>
                  <span>Dubai</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Middle Column: Unified Customer Timeline & Escalation Takeover */}
        <div className="lg:col-span-6 h-full flex flex-col space-y-4">
          {activeEscalation && (
            /* Escalation Briefing Header Card */
            <div className="p-4 bg-red-50 border border-red-200 rounded-2xl space-y-2 shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-red-600" />
                  <span className="text-xs font-bold text-red-900 font-mono">
                    HUMAN HANDOFF BRIEFING — SESSION {activeEscalation.session_id}
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 bg-red-600 text-white rounded-md font-bold uppercase">
                  {activeEscalation.priority}
                </span>
              </div>

              <div className="text-xs text-red-800 space-y-1">
                <p>
                  <strong>Trigger:</strong>{' '}
                  {activeEscalation.briefing?.escalation_trigger || activeEscalation.reason}
                </p>
                {activeEscalation.briefing?.recommended_action && (
                  <p>
                    <strong>Recommended Action:</strong> {activeEscalation.briefing.recommended_action}
                  </p>
                )}
              </div>

              {/* Takeover & Reply Form */}
              <form onSubmit={handleResolveAndReply} className="pt-2 flex gap-2">
                <input
                  type="text"
                  value={humanReplyText}
                  onChange={(e) => setHumanReplyText(e.target.value)}
                  placeholder="Type your response as human broker to take over & resolve..."
                  className="flex-1 px-3 py-2 bg-white border border-red-200 rounded-xl text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-red-500"
                />
                <button
                  type="submit"
                  disabled={resolving || !humanReplyText.trim()}
                  className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-bold rounded-xl transition-all disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{resolving ? 'Sending...' : 'Send & Resolve'}</span>
                </button>
              </form>
            </div>
          )}

          <div className="flex-1 min-h-0">
            <UnifiedTimeline messages={messages} onSendMessage={handleSendMessage} />
          </div>
        </div>

        {/* Right Column: AI Communication Copilot */}
        <div className="lg:col-span-3 h-full overflow-y-auto">
          <AICopilotBar onSelectReply={handleSelectReply} />
        </div>
      </div>
    </div>
  );
}
