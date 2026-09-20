'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  aiSendMessage,
  aiCreateChatWebSocket,
  aiGetHistory,
  aiGetShortlist,
  aiGetQualification,
  aiAddToShortlist,
  type AISendMessageResponse,
  type AIConversationTurn,
  type AIShortlistItem,
} from '@/lib/api-client';
import { PropertyCardInline } from './PropertyCardInline';
import { ShortlistPanel } from './ShortlistPanel';
import { ComparisonModal } from './ComparisonModal';
import { AppointmentFlow } from './AppointmentFlow';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  timestamp: Date;
  turnIndex?: number;
  state?: string;
  toolResults?: Array<{ tool: string; success: boolean; result: unknown }>;
  wasBlocked?: boolean;
  escalated?: boolean;
}

export interface PropertyResult {
  id: string;
  name: string;
  type?: string | null;
  bedrooms?: number | null;
  price?: number | null;
  currency?: string | null;
  location?: string | null;
  status?: string | null;
  source_verified: boolean;
}

interface AISalesChatProps {
  organizationId: string;
  leadId: string;
  leadName?: string;
  agentDisplayName?: string;
  /** Called when escalation happens */
  onEscalated?: (sessionId: string) => void;
}

// ─── Message ID generator ────────────────────────────────────────────────────
let _msgCounter = 0;
function nextId(): string {
  return `msg-${Date.now()}-${++_msgCounter}`;
}

// ─── Parse properties from tool results ──────────────────────────────────────
function extractPropertyResults(
  toolResults: AISendMessageResponse['tool_results']
): PropertyResult[] {
  if (!toolResults) return [];
  const props: PropertyResult[] = [];
  for (const tr of toolResults) {
    if (tr.tool === 'search_properties' && tr.success && tr.result) {
      const r = tr.result as { properties?: PropertyResult[] };
      if (r.properties) props.push(...r.properties.slice(0, 3));
    }
  }
  return props;
}

function hasEmptyPropertySearch(
  toolResults: AISendMessageResponse['tool_results']
): boolean {
  if (!toolResults) return false;
  for (const tr of toolResults) {
    if (tr.tool === 'search_properties' && tr.success && tr.result) {
      const r = tr.result as { properties?: PropertyResult[] };
      if (Array.isArray(r.properties) && r.properties.length === 0) {
        return true;
      }
    }
  }
  return false;
}

// ─── Chat Status Indicator ────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex items-center gap-2 px-4 py-3 max-w-xs">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
        <span className="text-white text-xs font-bold">AI</span>
      </div>
      <div className="bg-white/80 backdrop-blur border border-white/60 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <div className="flex gap-1 items-center h-4">
          <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce [animation-delay:0ms]" />
          <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce [animation-delay:150ms]" />
          <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  );
}

// ─── Single Chat Message ──────────────────────────────────────────────────────
function MessageBubble({
  msg,
  organizationId,
  onShortlist,
  onCompare,
  onSchedule,
  compareList,
}: {
  msg: ChatMessage;
  organizationId?: string;
  onShortlist?: (propId: string) => void;
  onCompare?: (propId: string) => void;
  onSchedule?: (propId: string) => void;
  compareList?: string[];
}) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs text-slate-400 bg-slate-100/80 rounded-full px-3 py-1">
          {msg.content}
        </span>
      </div>
    );
  }

  // Extract inline property results from tool results
  const props = extractPropertyResults(msg.toolResults);
  const hadEmptySearch = hasEmptyPropertySearch(msg.toolResults);

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} group`}>
      {/* Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-lg mt-1">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
      )}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center flex-shrink-0 shadow-lg mt-1">
          <span className="text-white text-xs font-bold">You</span>
        </div>
      )}

      <div className={`flex flex-col gap-2 max-w-[75%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Bubble */}
        <div
          className={`
            px-4 py-3 rounded-2xl shadow-sm text-sm leading-relaxed
            ${isUser
              ? 'bg-gradient-to-br from-violet-600 to-indigo-700 text-white rounded-tr-sm'
              : 'bg-white/90 backdrop-blur border border-slate-100 text-slate-800 rounded-tl-sm'
            }
          `}
        >
          {msg.wasBlocked && (
            <div className="text-amber-500 text-xs font-medium mb-1 flex items-center gap-1">
              <span>⚠</span> Response filtered for safety
            </div>
          )}
          {msg.escalated && (
            <div className="text-blue-500 text-xs font-medium mb-1 flex items-center gap-1">
              <span>👤</span> Connecting you with a human specialist…
            </div>
          )}
          <p className="whitespace-pre-wrap">{msg.content}</p>
        </div>

        {/* Inline property cards (from search_properties tool result) */}
        {props.length > 0 && !isUser && (
          <div className="flex flex-col gap-3 w-full max-w-md">
            {props.map((prop) => (
              <PropertyCardInline
                key={prop.id}
                property={prop}
                organizationId={organizationId}
                inCompareList={compareList?.includes(prop.id)}
                onShortlist={() => onShortlist?.(prop.id)}
                onCompare={() => onCompare?.(prop.id)}
                onSchedule={() => onSchedule?.(prop.id)}
              />
            ))}
          </div>
        )}

        {/* No-match hint when search returned 0 properties */}
        {hadEmptySearch && props.length === 0 && !isUser && (
          <div className="w-full max-w-md bg-amber-50/70 border border-amber-200/80 rounded-2xl p-3 text-xs text-amber-800 flex items-start gap-2.5">
            <span className="text-amber-500 font-bold mt-0.5">ℹ</span>
            <div className="space-y-1">
              <p className="font-semibold">No exact matches found right now.</p>
              <p className="text-[11px] text-amber-700 leading-normal">
                Try broadening your budget, preferred locations, or bedroom requirements to explore more options.
              </p>
            </div>
          </div>
        )}

        {/* Timestamp */}
        <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity px-1">
          {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </div>
  );
}

// ─── Quick Reply Suggestions ──────────────────────────────────────────────────
const QUICK_REPLIES = [
  "I'm looking for a 3 BHK",
  "My budget is around 1.5 crore",
  "I need it ready to move in",
  "Show me available properties",
  "Book a site visit",
  "Talk to a human",
];

// ─── Main AISalesChat Component ───────────────────────────────────────────────
export function AISalesChat({
  organizationId,
  leadId,
  leadName,
  agentDisplayName = 'Property Advisor',
  onEscalated,
}: AISalesChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [shortlistOpen, setShortlistOpen] = useState(false);
  const [shortlistItems, setShortlistItems] = useState<AIShortlistItem[]>([]);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [appointmentPropertyId, setAppointmentPropertyId] = useState<string | null>(null);
  const [qualificationPct, setQualificationPct] = useState(0);
  const [currentState, setCurrentState] = useState<string>('new');
  const [isEscalated, setIsEscalated] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionStorageKey = `wefylabs:ai-session:${organizationId}:${leadId}`;

  // ── Scroll to latest message ─────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // ── Initial greeting ─────────────────────────────────────────────────────
  useEffect(() => {
    const greeting: ChatMessage = {
      id: nextId(),
      role: 'agent',
      content: `Hello${leadName ? ` ${leadName}` : ''}! 👋 I'm your AI Property Advisor. I'll help you find your perfect property from our verified inventory.\n\nTo get started, could you tell me what kind of property you're looking for?`,
      timestamp: new Date(),
      state: 'greeting',
    };
    const storedSession = sessionStorage.getItem(sessionStorageKey);
    if (storedSession) {
      void Promise.all([aiGetHistory(storedSession), aiGetQualification(storedSession)])
        .then(([history, qualification]) => {
          setSessionId(storedSession);
          setQualificationPct(qualification.completion_pct || 0);
          setMessages(history.flatMap(turn => [
            ...(turn.customer_message ? [{ id: `customer-${turn.turn_index}`, role: 'user' as const, content: turn.customer_message, timestamp: new Date(turn.created_at), turnIndex: turn.turn_index, state: turn.to_state }] : []),
            ...(turn.agent_response ? [{ id: `agent-${turn.turn_index}`, role: 'agent' as const, content: turn.agent_response, timestamp: new Date(turn.created_at), turnIndex: turn.turn_index, state: turn.to_state }] : []),
          ]));
        })
        .catch(() => {
          sessionStorage.removeItem(sessionStorageKey);
          setMessages([greeting]);
        });
    } else {
      setMessages([greeting]);
    }
    // Try WebSocket connection
    const ws = aiCreateChatWebSocket(organizationId, leadId);
    if (ws) {
      wsRef.current = ws;
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          handleWsMessage(data);
        } catch { /* ignore parse errors */ }
      };
    }
    return () => ws?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organizationId, leadId, sessionStorageKey]);

  useEffect(() => {
    if (sessionId) sessionStorage.setItem(sessionStorageKey, sessionId);
  }, [sessionId, sessionStorageKey]);

  // ── Handle incoming WebSocket message ────────────────────────────────────
  const handleWsMessage = useCallback((data: Record<string, unknown>) => {
    if (data.type === 'token' || data.type === 'response') {
      const content = String(data.content || data.text || '');
      if (!content) return;
      setIsTyping(false);
      const agentMsg: ChatMessage = {
        id: nextId(),
        role: 'agent',
        content,
        timestamp: new Date(),
        state: String(data.current_state || ''),
        escalated: Boolean(data.escalated),
        wasBlocked: Boolean(data.was_blocked),
        toolResults: (data.tool_results as ChatMessage['toolResults']) || [],
      };
      if (data.session_id) setSessionId(String(data.session_id));
      if (data.current_state) setCurrentState(String(data.current_state));
      if (data.escalated) {
        setIsEscalated(true);
        onEscalated?.(String(data.session_id || ''));
      }
      setMessages(prev => [...prev, agentMsg]);
    } else if (data.type === 'human_message') {
      const humanMsg: ChatMessage = {
        id: nextId(),
        role: 'agent',
        content: `👤 ${data.agent_name || 'Agent'}: ${data.content}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, humanMsg]);
    }
  }, [onEscalated]);

  // ── Send message via REST (with WS fallback) ──────────────────────────────
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isTyping) return;
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Try WebSocket first
    if (wsConnected && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content: text.trim() }));
      return; // Response comes via onmessage
    }

    // REST fallback
    try {
      const resp: AISendMessageResponse = await aiSendMessage({
        lead_id: leadId,
        organization_id: organizationId,
        content: text.trim(),
        channel: 'web',
        sender_name: leadName,
      });
      setSessionId(resp.session_id);
      setCurrentState(resp.current_state);
      if (resp.escalated) {
        setIsEscalated(true);
        onEscalated?.(resp.session_id);
      }
      const agentMsg: ChatMessage = {
        id: nextId(),
        role: 'agent',
        content: resp.content,
        timestamp: new Date(),
        turnIndex: resp.turn_index,
        state: resp.current_state,
        toolResults: resp.tool_results || [],
        wasBlocked: resp.was_blocked,
        escalated: resp.escalated,
      };
      setMessages(prev => [...prev, agentMsg]);
    } catch (err) {
      const errMsg: ChatMessage = {
        id: nextId(),
        role: 'system',
        content: 'Temporarily unavailable. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
    }
  }, [isTyping, wsConnected, leadId, organizationId, leadName, onEscalated]);

  // ── Shortlist handler ────────────────────────────────────────────────────
  const handleShortlist = useCallback(async (propId: string) => {
    if (!sessionId) {
      setMessages(prev => [...prev, {
        id: nextId(), role: 'system',
        content: 'Send a message first so we can save properties to your shortlist.',
        timestamp: new Date(),
      }]);
      return;
    }
    try {
      await aiAddToShortlist(sessionId, propId);
      try {
        const refreshed = await aiGetShortlist(sessionId);
        setShortlistItems(refreshed.items);
      } catch {
        setShortlistItems(prev => {
          if (prev.find(i => i.property_id === propId)) return prev;
          return [...prev, {
            property_id: propId,
            name: 'Property',
            status: 'shortlisted',
            source_verified: true,
          }];
        });
      }
      const sysMsg: ChatMessage = {
        id: nextId(),
        role: 'system',
        content: '✓ Property added to your shortlist',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, sysMsg]);
    } catch {
      setMessages(prev => [...prev, {
        id: nextId(),
        role: 'system',
        content: 'Could not save property — please try again.',
        timestamp: new Date(),
      }]);
    }
  }, [sessionId]);

  // ── Compare handler ──────────────────────────────────────────────────────
  const handleCompare = useCallback((propId: string) => {
    setCompareIds(prev => {
      if (prev.includes(propId)) return prev.filter(id => id !== propId);
      if (prev.length >= 4) return prev; // max 4
      const next = [...prev, propId];
      if (next.length >= 2) setCompareOpen(true);
      return next;
    });
  }, []);

  const handleSchedule = useCallback((propId: string) => {
    setAppointmentPropertyId(propId);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }, [input, sendMessage]);

  // ── State badge color ────────────────────────────────────────────────────
  const stateBadgeColor: Record<string, string> = {
    new: 'bg-slate-100 text-slate-500',
    greeting: 'bg-blue-50 text-blue-600',
    discovering: 'bg-violet-50 text-violet-600',
    qualifying: 'bg-amber-50 text-amber-600',
    explaining: 'bg-emerald-50 text-emerald-600',
    recommending: 'bg-teal-50 text-teal-600',
    booking: 'bg-green-50 text-green-600',
    follow_up: 'bg-orange-50 text-orange-600',
    human_handoff: 'bg-red-50 text-red-600',
  };

  const stateBadge = stateBadgeColor[currentState] || 'bg-slate-100 text-slate-500';

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-slate-50 to-white relative" id="ai-sales-chat">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 bg-white/80 backdrop-blur-md border-b border-slate-100 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg">
              <span className="text-white text-sm font-bold">AI</span>
            </div>
            <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-white ${wsConnected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800">{agentDisplayName}</h2>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${stateBadge}`}>
                {currentState.replace('_', ' ')}
              </span>
              {isEscalated && (
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-red-50 text-red-600">
                  Human agent joining…
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-2">
          {qualificationPct > 0 && (
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-[10px] text-slate-400 font-medium">Profile</span>
              <div className="flex items-center gap-1">
                <div className="w-24 h-1.5 bg-slate-200 rounded-full">
                  <div
                    className="h-full bg-gradient-to-r from-violet-500 to-indigo-600 rounded-full transition-all duration-500"
                    style={{ width: `${qualificationPct}%` }}
                  />
                </div>
                <span className="text-[10px] text-violet-600 font-bold">{qualificationPct}%</span>
              </div>
            </div>
          )}

          {shortlistItems.length > 0 && (
            <button
              id="shortlist-toggle-btn"
              onClick={() => setShortlistOpen(true)}
              className="relative flex items-center gap-1.5 px-3 py-1.5 bg-violet-50 hover:bg-violet-100 border border-violet-200 rounded-xl text-xs font-medium text-violet-700 transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 5.82 21 7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
              Shortlist
              <span className="absolute -top-1 -right-1 w-4 h-4 bg-violet-600 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                {shortlistItems.length}
              </span>
            </button>
          )}

          {compareIds.length >= 2 && (
            <button
              id="compare-btn"
              onClick={() => setCompareOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-teal-50 hover:bg-teal-100 border border-teal-200 rounded-xl text-xs font-medium text-teal-700 transition-all"
            >
              Compare ({compareIds.length})
            </button>
          )}
        </div>
      </div>

      {/* ── Messages Area ───────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            msg={msg}
            organizationId={organizationId}
            onShortlist={handleShortlist}
            onCompare={handleCompare}
            onSchedule={handleSchedule}
            compareList={compareIds}
          />
        ))}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* ── Quick Replies ────────────────────────────────────────────────── */}
      {messages.length <= 2 && (
        <div className="px-4 pb-2 flex gap-2 overflow-x-auto scrollbar-none flex-shrink-0">
          {QUICK_REPLIES.map((qr) => (
            <button
              key={qr}
              id={`quick-reply-${qr.replace(/\s+/g, '-').toLowerCase()}`}
              onClick={() => sendMessage(qr)}
              className="flex-shrink-0 px-3 py-1.5 bg-white border border-slate-200 hover:border-violet-300 hover:bg-violet-50 rounded-full text-xs text-slate-600 hover:text-violet-700 transition-all whitespace-nowrap shadow-xs"
            >
              {qr}
            </button>
          ))}
        </div>
      )}

      {/* ── Input Area ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-3 bg-white border-t border-slate-100 flex-shrink-0">
        <div className="flex-1 flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-2xl px-4 py-2.5 focus-within:border-violet-300 focus-within:bg-white transition-all">
          <input
            ref={inputRef}
            id="ai-chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message…"
            className="flex-1 bg-transparent text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none"
            disabled={isTyping}
          />
        </div>
        <button
          id="ai-chat-send-btn"
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || isTyping}
          className="w-10 h-10 rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-700 text-white flex items-center justify-center shadow-md hover:shadow-lg hover:scale-105 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:scale-100"
        >
          <svg className="w-4 h-4 rotate-90" fill="currentColor" viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </div>

      {/* ── Panels & Modals ──────────────────────────────────────────────── */}
      {shortlistOpen && sessionId && (
        <ShortlistPanel
          sessionId={sessionId}
          organizationId={organizationId}
          onClose={() => setShortlistOpen(false)}
          onSchedule={handleSchedule}
          onCompare={handleCompare}
        />
      )}

      {compareOpen && compareIds.length >= 2 && sessionId && (
        <ComparisonModal
          sessionId={sessionId}
          propertyIds={compareIds}
          onClose={() => setCompareOpen(false)}
          onRemove={(id) => setCompareIds(prev => prev.filter(pid => pid !== id))}
          onSchedule={handleSchedule}
        />
      )}

      {appointmentPropertyId && sessionId && (
        <AppointmentFlow
          sessionId={sessionId}
          propertyId={appointmentPropertyId}
          organizationId={organizationId}
          leadId={leadId}
          onClose={() => setAppointmentPropertyId(null)}
          onRequestHuman={() => {
            setAppointmentPropertyId(null);
            void sendMessage("I'd like to speak with a human specialist.");
          }}
          onConfirmed={() => {
            setAppointmentPropertyId(null);
            const sysMsg: ChatMessage = {
              id: nextId(),
              role: 'system',
              content: '✓ Site visit booked! Our agent will confirm shortly.',
              timestamp: new Date(),
            };
            setMessages(prev => [...prev, sysMsg]);
          }}
        />
      )}
    </div>
  );
}
