import React, { useState, useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  Sparkles, X, Send, Bot, User, CheckCircle2, RefreshCw,
  ChevronUp, ChevronDown, Copy, Check, RotateCcw, AlertTriangle,
  Info, Zap, Trash2, Plus, Clock, ShieldAlert, CheckCircle, ExternalLink
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { WefyLabsIcon } from '@/components/shared/WefyLabsIcon';

interface ActionPreview {
  tool_name: string;
  title: string;
  summary: string;
  impacted_records: number;
  is_destructive: boolean;
  confirmation_token: string;
  arguments: any;
}

interface Message {
  id: string;
  sender: 'user' | 'copilot';
  text: string;
  reasoning?: string;
  rich_cards?: Array<{
    type: string;
    title: string;
    subtitle?: string;
    details?: string;
    badge?: string;
    badge_color?: string;
  }>;
  action_buttons?: Array<{
    label: string;
    action_type: string;
    payload?: any;
  }>;
  executed_tools?: Array<{
    tool_name: string;
    arguments?: any;
  }>;
  citations?: string[];
  suggested_followups?: string[];
  action_preview?: ActionPreview | null;
  action_confirmed?: boolean;
  isError?: boolean;
}

interface ConversationSummary {
  id: string;
  title: string;
  route_context: string;
  created_at: string;
  updated_at: string;
}

export function GlobalAICopilot() {
  const pathname = usePathname();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [queryInput, setQueryInput] = useState('');
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'init-1',
      sender: 'copilot',
      text: "👋 Hi! I'm your WefyLabs enterprise AI Copilot. Ask me anything about your leads, follow-ups, calendar availability, or to execute verified CRM actions."
    }
  ]);

  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({});
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [confirmingToken, setConfirmingToken] = useState<string | null>(null);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(messages.length);

  // Auto-scroll when new message is added
  useEffect(() => {
    if (isOpen && messages.length > prevMessagesLengthRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages.length, isOpen, loading]);

  // Global event listener for navbar / keyboard triggers
  useEffect(() => {
    const handleToggle = () => setIsOpen((prev) => !prev);
    window.addEventListener('wefylabs:toggle-copilot', handleToggle);
    return () => window.removeEventListener('wefylabs:toggle-copilot', handleToggle);
  }, []);

  // Load conversation list when opened
  useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
  }, [isOpen]);

  const loadConversations = async () => {
    try {
      const list = await apiClient.listCopilotConversations();
      setConversations(list);
    } catch {
      // Ignored for unauthenticated/testing states
    }
  };

  // Fetch route-specific suggested actions from API
  useEffect(() => {
    let isMounted = true;
    const currentRoute = pathname || '/dashboard';

    apiClient.getCopilotSuggestedActions(currentRoute)
      .then((res) => {
        if (isMounted && res?.suggested_actions) {
          setSuggestedActions(res.suggested_actions);
        }
      })
      .catch(() => {
        if (isMounted) {
          const r = currentRoute.toLowerCase();
          if (r.includes('/settings')) {
            setSuggestedActions(["Compare Plans", "Explain 7-Day Trial", "Open Billing Settings"]);
          } else if (r.includes('/leads') || r.includes('/inbox')) {
            setSuggestedActions(["Show my hottest leads", "Which leads haven't been contacted in 7 days?", "Create follow-up task"]);
          } else if (r.includes('/deals') || r.includes('/pipeline')) {
            setSuggestedActions(["Analyze Pipeline Velocity", "Show At-Risk Deals", "Schedule Meeting"]);
          } else {
            setSuggestedActions(["Show my hottest leads", "What tasks are due today?", "Explain how billing works"]);
          }
        }
      });

    return () => { isMounted = false; };
  }, [pathname]);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await apiClient.createCopilotConversation("New Consultation", pathname || "/dashboard");
      setActiveConversationId(newConv.id);
      setMessages([
        {
          id: `init-${Date.now()}`,
          sender: 'copilot',
          text: "Fresh session started. How can I assist with your workspace today?"
        }
      ]);
      setShowHistory(false);
      loadConversations();
    } catch {
      setActiveConversationId(null);
      setMessages([
        {
          id: `init-${Date.now()}`,
          sender: 'copilot',
          text: "Fresh session started. How can I assist with your workspace today?"
        }
      ]);
      setShowHistory(false);
    }
  };

  const handleSelectConversation = async (convId: string) => {
    try {
      setLoading(true);
      const conv = await apiClient.getCopilotConversation(convId);
      setActiveConversationId(conv.id);
      if (conv.messages && conv.messages.length > 0) {
        setMessages(
          conv.messages.map((m) => ({
            id: m.id,
            sender: m.sender,
            text: m.content,
            reasoning: m.reasoning,
            tool_calls: m.tool_calls,
            citations: m.citations,
            action_preview: m.action_preview
          }))
        );
      } else {
        setMessages([
          {
            id: `init-${Date.now()}`,
            sender: 'copilot',
            text: `Resumed conversation: "${conv.title}". What would you like to explore?`
          }
        ]);
      }
      setShowHistory(false);
    } catch (err: any) {
      setActionFeedback(`Could not load session: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    try {
      await apiClient.deleteCopilotConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewConversation();
      }
    } catch (err: any) {
      setActionFeedback(`Delete failed: ${err.message}`);
    }
  };

  const handleActionButtonClick = async (btn: { label: string; action_type: string; payload?: any }) => {
    if (btn.action_type === 'OPEN_PAGE' && btn.payload?.url) {
      router.push(btn.payload.url);
      setActionFeedback(`Navigating to ${btn.payload.url}...`);
      setTimeout(() => setActionFeedback(null), 3000);
      return;
    }

    try {
      setActionFeedback(`Executing ${btn.label}...`);
      const res = await apiClient.executeCopilotAction(btn.action_type, undefined, btn.payload);
      setActionFeedback(`✓ ${res.message || 'Action executed successfully'}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err: any) {
      setActionFeedback(`⚠️ Execution notice: ${err.message || 'Action failed'}`);
      setTimeout(() => setActionFeedback(null), 4000);
    }
  };

  const handleConfirmAction = async (msgId: string, preview: ActionPreview) => {
    setConfirmingToken(preview.confirmation_token);
    setActionFeedback(`Confirming and executing ${preview.tool_name}...`);

    try {
      const res = await apiClient.confirmCopilotAction(
        preview.confirmation_token,
        preview.tool_name,
        preview.arguments,
        activeConversationId || undefined
      );

      // Mark preview as confirmed
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                action_confirmed: true,
                text: res.answer_markdown || `✓ Executed: ${preview.title}`,
                action_preview: null,
                citations: res.citations || m.citations
              }
            : m
        )
      );
      setActionFeedback(`✓ Action confirmed and executed successfully.`);
      setTimeout(() => setActionFeedback(null), 4000);
    } catch (err: any) {
      setActionFeedback(`⚠️ Action failed: ${err.message}`);
      setTimeout(() => setActionFeedback(null), 4000);
    } finally {
      setConfirmingToken(null);
    }
  };

  const handleCancelAction = (msgId: string) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId
          ? {
              ...m,
              action_preview: null,
              text: `${m.text}\n\n*Action cancelled by user.*`
            }
          : m
      )
    );
    setActionFeedback("Action cancelled.");
    setTimeout(() => setActionFeedback(null), 2500);
  };

  const handleSend = async (textToSend?: string) => {
    const q = textToSend || queryInput;
    if (!q.trim() || loading) return;

    const userMessageId = `user-${Date.now()}`;
    const userMsg: Message = { id: userMessageId, sender: 'user', text: q };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setQueryInput('');
    setLoading(true);

    try {
      const historyContext = messages
        .filter((m) => !m.isError)
        .slice(-8)
        .map((m) => ({ sender: m.sender, text: m.text }));

      const currentRoute = pathname || '/dashboard';
      const res = await apiClient.copilotQuery(
        q,
        currentRoute,
        historyContext,
        undefined,
        activeConversationId || undefined
      );

      if (res.conversation_id && !activeConversationId) {
        setActiveConversationId(res.conversation_id);
      }

      const copilotMsg: Message = {
        id: `copilot-${Date.now()}`,
        sender: 'copilot',
        text: res.answer_markdown || "I'm unable to generate a response right now.",
        reasoning: res.reasoning,
        rich_cards: res.rich_cards,
        action_buttons: res.action_buttons,
        executed_tools: res.executed_tools,
        citations: res.citations,
        suggested_followups: res.suggested_followups,
        action_preview: res.action_preview
      };

      setMessages((prev) => [...prev, copilotMsg]);
      loadConversations();
    } catch (err: any) {
      const detailedErr = err?.message || String(err);
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        sender: 'copilot',
        text: `⚠️ **Copilot Notice:** ${detailedErr}`,
        isError: true
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.sender === 'user');
    if (lastUserMsg) {
      handleSend(lastUserMsg.text);
    }
  };

  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, lIdx) => {
      if (line.startsWith('### ')) {
        return (
          <h3 key={lIdx} className="font-bold text-xs text-gray-900 mt-2 mb-1">
            {line.replace('### ', '')}
          </h3>
        );
      }
      if (line.startsWith('## ')) {
        return (
          <h2 key={lIdx} className="font-bold text-sm text-gray-900 mt-2 mb-1">
            {line.replace('## ', '')}
          </h2>
        );
      }

      const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ');
      const cleanLine = isBullet ? line.trim().substring(2) : line;
      const parts = cleanLine.split(/(\*\*.*?\*\*)/g);

      return (
        <div
          key={lIdx}
          className={`${
            isBullet
              ? 'pl-3 relative before:content-["•"] before:absolute before:left-0 before:text-amber-600'
              : ''
          } ${lIdx > 0 && !isBullet ? 'mt-1' : ''}`}
        >
          {parts.map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={pIdx} className="font-bold text-gray-900 dark:text-gray-100">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            return <span key={pIdx}>{part}</span>;
          })}
        </div>
      );
    });
  };

  return (
    <>
      {/* Floating Trigger Button (z-30 so modals at z-50 take priority) */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-30 flex items-center gap-2.5 px-4 py-2.5 bg-[#1A1A1A] hover:bg-black text-white border border-[#3A3A3A] rounded-full shadow-2xl transition-all duration-300 hover:scale-105 active:scale-95 group font-mono text-xs font-bold"
          aria-label="Open WefyLabs AI Copilot"
        >
          <WefyLabsIcon size={14} theme="dark" />
          <span>AI Copilot</span>
          <span className="w-2 h-2 rounded-full bg-[#E8F5A8] border border-[#1A1A1A]/30" />
        </button>
      )}

      {/* Slide-out Drawer / Bottom Sheet */}
      {isOpen && (
        <>
          {/* Mobile backdrop */}
          <div
            className="fixed inset-0 bg-black/30 backdrop-blur-xs z-40 sm:hidden"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="fixed bottom-0 sm:bottom-4 right-0 sm:right-4 z-40 w-full sm:w-[440px] h-[85vh] sm:h-[640px] max-h-[92vh] bg-[#FAF7F2] border border-[#D4D0C8] rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-5 duration-300"
          >
          {/* Drawer Header */}
          <div className="p-3.5 bg-[#1A1A1A] text-white flex items-center justify-between border-b border-gray-800 shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="p-1 rounded-xl bg-[#2A2A2A] flex items-center justify-center border border-gray-700">
                <WefyLabsIcon size={16} theme="dark" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h2 className="font-bold text-xs tracking-wide">WefyLabs AI Copilot</h2>
                  <span className="text-[9px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.2 rounded-full">
                    ACTIVE
                  </span>
                </div>
                <p className="text-[10px] text-gray-400 font-mono">Product-Native CRM Assistant</p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleNewConversation}
                className="p-1.5 text-gray-300 hover:text-white hover:bg-white/10 rounded-lg transition-colors text-[10px] font-mono flex items-center gap-1"
                title="Start New Chat"
              >
                <Plus className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">New Chat</span>
              </button>

              <button
                type="button"
                onClick={() => setShowHistory((prev) => !prev)}
                className={`p-1.5 rounded-lg transition-colors text-[10px] font-mono flex items-center gap-1 ${
                  showHistory ? 'bg-white/20 text-white' : 'text-gray-300 hover:text-white hover:bg-white/10'
                }`}
                title="Conversation History"
              >
                <Clock className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors ml-1"
                aria-label="Close Copilot"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Feedback Banner */}
          {actionFeedback && (
            <div className="bg-amber-100/90 border-b border-amber-200 text-amber-900 px-3 py-1.5 text-[11px] font-mono flex items-center gap-1.5 shrink-0 animate-in fade-in duration-200">
              <Info className="w-3 h-3 text-amber-700 shrink-0" />
              <span className="truncate">{actionFeedback}</span>
            </div>
          )}

          {/* Sliding History View */}
          {showHistory && (
            <div className="bg-[#FAF7F2] border-b border-[#D4D0C8] p-3 max-h-48 overflow-y-auto space-y-1.5 shrink-0 animate-in slide-in-from-top-2 duration-200">
              <div className="flex items-center justify-between text-[11px] font-bold text-gray-700 pb-1 border-b border-gray-200">
                <span>Recent Conversations</span>
                <span className="text-[10px] text-gray-400 font-mono">{conversations.length} total</span>
              </div>
              {conversations.length === 0 ? (
                <p className="text-[11px] text-gray-500 font-mono py-2 text-center">No past conversations yet.</p>
              ) : (
                conversations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => handleSelectConversation(c.id)}
                    className={`flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer border transition-colors ${
                      activeConversationId === c.id
                        ? 'bg-amber-50 border-amber-300 text-amber-900 font-bold'
                        : 'bg-white hover:bg-gray-50 border-gray-200 text-gray-800'
                    }`}
                  >
                    <div className="truncate pr-2">
                      <p className="truncate text-[11px]">{c.title || 'Conversation'}</p>
                      <span className="text-[9px] font-mono text-gray-400">{c.route_context}</span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteConversation(e, c.id)}
                      className="text-gray-400 hover:text-rose-600 p-1 rounded transition-colors"
                      title="Delete conversation"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Context Pills */}
          {suggestedActions.length > 0 && showSuggestions && !showHistory && (
            <div className="p-2.5 bg-[#FAF7F2] border-b border-[#D4D0C8] flex items-center gap-1.5 overflow-x-auto shrink-0 no-scrollbar">
              <span className="text-[10px] font-mono font-bold text-gray-500 shrink-0 uppercase tracking-wider pl-1">
                Suggested:
              </span>
              {suggestedActions.map((action, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSend(action)}
                  className="px-2.5 py-1 bg-white hover:bg-gray-100 text-gray-800 text-[10px] font-mono font-bold rounded-lg border border-[#D4D0C8] shadow-2xs whitespace-nowrap transition-all shrink-0 hover:border-gray-400 active:scale-95"
                >
                  {action}
                </button>
              ))}
            </div>
          )}

          {/* Messages Stream */}
          <div className="flex-1 p-3.5 overflow-y-auto space-y-3.5" ref={scrollContainerRef}>
            {messages.map((m) => (
              <div
                key={m.id}
                className={`p-3.5 rounded-2xl text-xs space-y-2 relative group ${
                  m.sender === 'user'
                    ? 'bg-[#1A1A1A] text-white ml-8 shadow-xs'
                    : m.isError
                    ? 'bg-rose-50 border border-rose-200 text-rose-900 mr-4'
                    : 'bg-white text-[#1A1A1A] border border-[#D4D0C8] mr-4 shadow-sm'
                }`}
              >
                <div className="flex items-center justify-between text-[10px] font-mono font-bold text-gray-500">
                  <div className="flex items-center gap-1.5">
                    {m.sender === 'user' ? (
                      <User className="w-3 h-3 text-emerald-400" />
                    ) : m.isError ? (
                      <AlertTriangle className="w-3 h-3 text-rose-600" />
                    ) : (
                      <Bot className="w-3 h-3 text-amber-500" />
                    )}
                    <span>{m.sender === 'user' ? 'You' : 'Copilot AI'}</span>
                  </div>

                  {m.sender === 'copilot' && !m.isError && (
                    <button
                      type="button"
                      onClick={() => handleCopy(m.id, m.text)}
                      className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-700 transition-opacity p-0.5"
                      title="Copy response"
                    >
                      {copiedId === m.id ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    </button>
                  )}
                </div>

                {/* Reasoning Accordion */}
                {m.reasoning && (
                  <div className="bg-[#FAF7F2] border border-[#E5E0D8] rounded-xl p-2 text-[10px] font-mono">
                    <button
                      type="button"
                      onClick={() => setExpandedReasoning((prev) => ({ ...prev, [m.id]: !prev[m.id] }))}
                      className="flex items-center justify-between w-full text-gray-600 hover:text-gray-900 font-bold"
                    >
                      <div className="flex items-center gap-1">
                        <Info className="w-3 h-3 text-amber-600" />
                        <span>Why this recommendation?</span>
                      </div>
                      {expandedReasoning[m.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    </button>
                    {expandedReasoning[m.id] && (
                      <div className="mt-1.5 pt-1.5 border-t border-gray-200 text-gray-700 leading-relaxed whitespace-pre-line font-sans text-[11px]">
                        {m.reasoning}
                      </div>
                    )}
                  </div>
                )}

                {/* Answer Content */}
                <div className="leading-relaxed font-sans text-xs">
                  {renderFormattedContent(m.text)}
                </div>

                {/* ACTION CONFIRMATION PREVIEW CARD */}
                {m.action_preview && (
                  <div
                    className={`mt-2 p-3 rounded-xl border space-y-2 ${
                      m.action_preview.is_destructive
                        ? 'bg-rose-50/90 border-rose-300 text-rose-950'
                        : 'bg-amber-50/90 border-amber-300 text-amber-950'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 font-bold text-xs">
                        <ShieldAlert className={`w-4 h-4 ${m.action_preview.is_destructive ? 'text-rose-600' : 'text-amber-600'}`} />
                        <span>{m.action_preview.title}</span>
                      </div>
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                          m.action_preview.is_destructive
                            ? 'bg-rose-200 border-rose-300 text-rose-900'
                            : 'bg-amber-200 border-amber-300 text-amber-900'
                        }`}
                      >
                        {m.action_preview.is_destructive ? 'DESTRUCTIVE' : 'CONFIRMATION REQUIRED'}
                      </span>
                    </div>

                    <p className="text-[11px] leading-relaxed font-sans">{m.action_preview.summary}</p>
                    <p className="text-[10px] font-mono text-gray-600">
                      Impacted records: <strong>{m.action_preview.impacted_records}</strong>
                    </p>

                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        disabled={confirmingToken === m.action_preview.confirmation_token}
                        onClick={() => handleConfirmAction(m.id, m.action_preview!)}
                        className={`text-[10px] font-mono font-bold px-3 py-1.5 rounded-lg flex items-center gap-1 transition-all active:scale-95 ${
                          m.action_preview.is_destructive
                            ? 'bg-rose-700 hover:bg-rose-800 text-white'
                            : 'bg-[#1A1A1A] hover:bg-black text-[#E8F5A8]'
                        }`}
                      >
                        {confirmingToken === m.action_preview.confirmation_token ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          <CheckCircle className="w-3 h-3" />
                        )}
                        <span>Confirm & Execute</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleCancelAction(m.id)}
                        className="text-[10px] font-mono text-gray-600 hover:text-gray-900 px-2.5 py-1.5 rounded-lg border border-gray-300 hover:bg-white transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {/* Rich Native UI Cards */}
                {m.rich_cards && m.rich_cards.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    {m.rich_cards.map((card, cIdx) => (
                      <div key={cIdx} className="bg-[#FAF7F2] border border-[#D4D0C8] p-2.5 rounded-xl text-xs space-y-1">
                        <div className="flex items-center justify-between font-bold text-gray-900">
                          <span>{card.title}</span>
                          {card.badge && (
                            <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                              {card.badge}
                            </span>
                          )}
                        </div>
                        {card.subtitle && <p className="text-[11px] font-mono text-gray-600">{card.subtitle}</p>}
                        {card.details && <p className="text-[10px] text-gray-500">{card.details}</p>}
                      </div>
                    ))}
                  </div>
                )}

                {/* 1-Click Action Buttons */}
                {m.action_buttons && m.action_buttons.length > 0 && (
                  <div className="pt-2 flex flex-wrap gap-1.5">
                    {m.action_buttons.map((btn, bIdx) => (
                      <button
                        key={bIdx}
                        type="button"
                        onClick={() => handleActionButtonClick(btn)}
                        className="text-[10px] font-mono font-bold bg-[#1A1A1A] hover:bg-black text-[#E8F5A8] border border-gray-800 px-2.5 py-1.5 rounded-xl transition-all flex items-center gap-1 hover:scale-102 active:scale-95"
                      >
                        <Zap className="w-3 h-3 text-[#E8F5A8] fill-[#E8F5A8]" />
                        <span>{btn.label}</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Provenance Citations */}
                {m.citations && m.citations.length > 0 && (
                  <div className="flex items-center gap-1 pt-1.5 border-t border-gray-100 text-[9px] font-mono text-gray-500 flex-wrap">
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600 shrink-0" />
                    <span>Sources: {m.citations.join(' • ')}</span>
                  </div>
                )}

                {/* Followup suggestions */}
                {m.suggested_followups && m.suggested_followups.length > 0 && (
                  <div className="pt-2 flex flex-wrap gap-1">
                    {m.suggested_followups.map((fol, fIdx) => (
                      <button
                        key={fIdx}
                        type="button"
                        onClick={() => handleSend(fol)}
                        className="text-[9px] font-mono bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200 px-2 py-0.5 rounded transition-colors"
                      >
                        ↳ {fol}
                      </button>
                    ))}
                  </div>
                )}

                {m.isError && (
                  <div className="pt-1.5 flex items-center justify-end">
                    <button
                      type="button"
                      onClick={handleRetry}
                      className="flex items-center gap-1 text-[10px] font-mono text-rose-700 hover:text-rose-900 font-bold"
                    >
                      <RotateCcw className="w-3 h-3" /> Retry
                    </button>
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 p-3 bg-white rounded-2xl border border-[#D4D0C8] mr-4 text-xs text-gray-600 font-mono shadow-xs animate-pulse">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-500 shrink-0" />
                <span>Copilot is reasoning with live CRM tools...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Sticky Input Composer */}
          <div className="p-3 bg-white border-t border-[#D4D0C8] flex items-center gap-2 shrink-0">
            <input
              type="text"
              value={queryInput}
              disabled={loading}
              onChange={(e) => setQueryInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask Copilot to analyze, search, or act..."
              className="flex-1 px-3.5 py-2 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-gray-800 transition-colors disabled:opacity-50"
            />
            <button
              type="button"
              disabled={loading || !queryInput.trim()}
              onClick={() => handleSend()}
              className="btn-lime p-2 rounded-xl shrink-0 disabled:opacity-50 transition-all active:scale-95"
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
        </>
      )}
    </>
  );
}
