'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Bot,
  User,
  ShieldAlert,
  CheckCircle2,
  Clock,
  Send,
  AlertTriangle,
  RefreshCw,
  Layers,
  Wrench,
  Check,
  ChevronRight,
  UserCheck,
} from 'lucide-react';
import {
  aiGetHistory,
  aiGetQualification,
  aiSendMessage,
  aiForceEscalate,
  aiHumanReply,
  AIConversationTurn,
  AIQualificationProfile,
  getOrganizationId,
} from '@/lib/api-client';

interface AIConversationTabProps {
  leadId: string;
  leadName?: string | null;
  leadPhone?: string | null;
}

export default function AIConversationTab({ leadId, leadName, leadPhone }: AIConversationTabProps) {
  const [loading, setLoading] = useState<boolean>(true);
  const [turns, setTurns] = useState<AIConversationTurn[]>([]);
  const [qualification, setQualification] = useState<AIQualificationProfile | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string>(`session-${leadId}`);
  const [currentState, setCurrentState] = useState<string>('qualifying');
  const [isEscalated, setIsEscalated] = useState<boolean>(false);
  const [escalationReason, setEscalationReason] = useState<string>('');
  const [replyText, setReplyText] = useState<string>('');
  const [sendingReply, setSendingReply] = useState<boolean>(false);
  const [simText, setSimText] = useState<string>('');
  const [simulating, setSimulating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const orgId = getOrganizationId() || 'org-default';

  const fetchSessionData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch turns
      try {
        const history = await aiGetHistory(activeSessionId, 50);
        if (Array.isArray(history) && history.length > 0) {
          setTurns(history);
          const lastTurn = history[history.length - 1];
          if (lastTurn.to_state) setCurrentState(lastTurn.to_state);
        }
      } catch {
        // No session turns yet
      }

      // Fetch qualification
      try {
        const qual = await aiGetQualification(activeSessionId);
        if (qual) setQualification(qual);
      } catch {
        // No qualification yet
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load AI conversation history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSessionData();
  }, [leadId, activeSessionId]);

  const handleSimulateInbound = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!simText.trim() || simulating) return;
    setSimulating(true);
    try {
      const resp = await aiSendMessage({
        lead_id: leadId,
        organization_id: orgId,
        content: simText.trim(),
        sender_phone: leadPhone || undefined,
        sender_name: leadName || undefined,
      });

      setActiveSessionId(resp.session_id);
      setCurrentState(resp.current_state);
      setIsEscalated(resp.escalated);
      setSimText('');
      await fetchSessionData();
    } catch (e: any) {
      alert(`Simulation failed: ${e.message}`);
    } finally {
      setSimulating(false);
    }
  };

  const handleHumanReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim() || sendingReply) return;
    setSendingReply(true);
    try {
      await aiHumanReply(activeSessionId, {
        content: replyText.trim(),
        agent_name: 'Broker Staff',
        resolve_escalation: true,
        resolution_notes: 'Broker addressed customer concern directly.',
      });
      setIsEscalated(false);
      setReplyText('');
      await fetchSessionData();
    } catch (e: any) {
      alert(`Human reply failed: ${e.message}`);
    } finally {
      setSendingReply(false);
    }
  };

  const handleManualEscalate = async () => {
    const reason = prompt('Reason for escalating this conversation to a human broker?', 'Broker manual review needed');
    if (!reason) return;
    try {
      await aiForceEscalate(activeSessionId, {
        reason,
        priority: 'high',
        notes: 'Manually escalated from lead detail view.',
      });
      setIsEscalated(true);
      setEscalationReason(reason);
      alert('Conversation has been escalated to human brokers.');
    } catch (e: any) {
      alert(`Escalation failed: ${e.message}`);
    }
  };

  const getStateColor = (st: string) => {
    switch (st.toLowerCase()) {
      case 'discovering':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'qualifying':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'recommending':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'negotiating':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'closing':
      case 'scheduled':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="space-y-6">
      {/* Session State Banner */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-emerald-500 flex items-center justify-center text-slate-950 font-bold shadow-lg shadow-emerald-500/20">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-extrabold text-white">Autonomous AI Sales Agent</h2>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border uppercase ${getStateColor(currentState)}`}>
                  State: {currentState}
                </span>
                {isEscalated ? (
                  <span className="bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                    <ShieldAlert className="w-3 h-3" /> ESCALATED
                  </span>
                ) : (
                  <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                    <Check className="w-3 h-3" /> Autonomous Loop Active
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                Session ID: <span className="text-slate-300">{activeSessionId}</span> • Channel: <span className="text-emerald-400 uppercase">Omnichannel Web/WhatsApp</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchSessionData}
              className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs transition-colors"
              title="Refresh AI Session"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            {!isEscalated ? (
              <button
                onClick={handleManualEscalate}
                className="px-3 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Take Over / Escalate</span>
              </button>
            ) : (
              <span className="px-3 py-2 bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl text-xs font-bold flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5" />
                <span>Human Required</span>
              </span>
            )}
          </div>
        </div>

        {/* Escalation Alert Bar */}
        {isEscalated && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-red-400">
              <ShieldAlert className="w-4 h-4" />
              <span>Human Handoff Active — AI Paused for this Lead</span>
            </div>
            <p className="text-xs text-slate-300">
              {escalationReason || 'The buyer has requested human assistance or hit a complex objection.'}
            </p>

            <form onSubmit={handleHumanReply} className="flex gap-2">
              <input
                type="text"
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                placeholder="Send a human agent response to resolve & resume AI..."
                className="flex-1 px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={sendingReply || !replyText.trim()}
                className="px-4 py-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-extrabold rounded-xl transition-all disabled:opacity-50 flex items-center gap-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{sendingReply ? 'Sending...' : 'Reply & Resolve'}</span>
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Qualification Factsheet Pill Grid */}
      {qualification && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Extracted Buyer Facts (MEDDIC / BANT Grounded)</span>
            </h3>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
              Completion: {qualification.completion_pct || 0}%
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <span className="text-[10px] text-slate-400 block font-mono">Budget Max</span>
              <span className="font-bold text-white">
                {qualification.budget_max ? `₹${(qualification.budget_max / 10000000).toFixed(2)} Cr` : 'Pending'}
              </span>
            </div>
            <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <span className="text-[10px] text-slate-400 block font-mono">Bedrooms</span>
              <span className="font-bold text-white">{qualification.bedrooms ? `${qualification.bedrooms} BHK` : 'Pending'}</span>
            </div>
            <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <span className="text-[10px] text-slate-400 block font-mono">Preferred Locations</span>
              <span className="font-bold text-white truncate block">
                {qualification.preferred_locations && qualification.preferred_locations.length > 0
                  ? qualification.preferred_locations.join(', ')
                  : 'Pending'}
              </span>
            </div>
            <div className="p-2.5 bg-slate-950/60 rounded-xl border border-slate-800/80">
              <span className="text-[10px] text-slate-400 block font-mono">Timeline / Intent</span>
              <span className="font-bold text-white capitalize">{qualification.timeline || 'Investigating'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Conversation Turns Stream */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-4">
        <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>AI Turn History ({turns.length} turns)</span>
          </span>
          <span className="text-[10px] text-slate-400 font-mono">Grounded Tool Invocations</span>
        </h3>

        {turns.length === 0 ? (
          <div className="py-12 text-center text-slate-500 space-y-2">
            <Bot className="w-8 h-8 mx-auto text-slate-600 opacity-60" />
            <p className="text-xs">No autonomous AI turns recorded for this lead session yet.</p>
            <p className="text-[11px] text-slate-400">Use the simulation prompt below or send a message via public portal to initiate.</p>
          </div>
        ) : (
          <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
            {turns.map((turn, idx) => (
              <div key={turn.id || idx} className="space-y-2">
                {/* Customer Turn */}
                {turn.customer_message && (
                  <div className="flex items-start gap-3 pl-4">
                    <div className="w-7 h-7 rounded-lg bg-slate-800 text-slate-300 flex items-center justify-center shrink-0 text-xs">
                      <User className="w-3.5 h-3.5" />
                    </div>
                    <div className="flex-1 bg-slate-800/60 border border-slate-700/60 rounded-2xl p-3 text-xs text-slate-200">
                      <p className="whitespace-pre-wrap">{turn.customer_message}</p>
                      <span className="text-[10px] text-slate-400 font-mono mt-1 block">
                        Turn #{turn.turn_index ?? idx + 1} • {turn.created_at ? new Date(turn.created_at).toLocaleTimeString() : 'Recent'}
                      </span>
                    </div>
                  </div>
                )}

                {/* AI Agent Response */}
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center justify-center shrink-0 text-xs">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 bg-slate-950 border border-slate-800 rounded-2xl p-3.5 text-xs text-slate-100 space-y-2 shadow-sm">
                    <p className="whitespace-pre-wrap leading-relaxed">{turn.agent_response}</p>

                    {/* Tools Executed Chips */}
                    {turn.tool_calls && turn.tool_calls.length > 0 && (
                      <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                          <Wrench className="w-3 h-3" /> Tools:
                        </span>
                        {turn.tool_calls.map((tool: any, tIdx: number) => {
                          const toolName = typeof tool === 'string' ? tool : tool.tool || tool.name || 'tool';
                          return (
                            <span
                              key={tIdx}
                              className="text-[10px] font-mono px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-md flex items-center gap-1"
                            >
                              <CheckCircle2 className="w-2.5 h-2.5" />
                              {toolName}
                            </span>
                          );
                        })}
                      </div>
                    )}

                    {turn.to_state && (
                      <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 pt-1">
                        <span>State transition → <strong className="text-slate-300 capitalize">{turn.to_state}</strong></span>
                        {turn.escalated && (
                          <span className="text-red-400 font-bold flex items-center gap-1">
                            <ShieldAlert className="w-3 h-3" /> Escalated
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Inbound Buyer Simulation Sandbox */}
        <div className="pt-4 border-t border-slate-800">
          <form onSubmit={handleSimulateInbound} className="flex gap-2">
            <input
              type="text"
              value={simText}
              onChange={(e) => setSimText(e.target.value)}
              placeholder="Simulate buyer inbound query (e.g. 'Looking for 3BHK under 2.5 Cr in Sector 62')..."
              className="flex-1 px-3 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={simulating || !simText.trim()}
              className="px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 text-xs font-extrabold rounded-xl transition-all disabled:opacity-50 flex items-center gap-1.5 shadow-md shadow-emerald-500/20"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{simulating ? 'Processing...' : 'Simulate Turn'}</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
