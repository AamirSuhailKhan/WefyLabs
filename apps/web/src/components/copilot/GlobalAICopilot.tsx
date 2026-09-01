import React, { useState, useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Sparkles, X, Send, Bot, User, CheckCircle2, RefreshCw, ChevronUp, ChevronDown, Copy, Check, RotateCcw, AlertTriangle, Info, Zap, Phone, ExternalLink, Calendar, CheckCircle } from 'lucide-react';
import { apiClient } from '@/lib/api-client';

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
  citations?: string[];
  suggested_followups?: string[];
  isError?: boolean;
}

export function GlobalAICopilot() {
  const pathname = usePathname();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [queryInput, setQueryInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'init-1',
      sender: 'copilot',
      text: "👋 Hi! I'm your BeetleLabs AI Copilot powered by Google Gemini. Ask me anything about your leads, at-risk deals, revenue forecasts, or daily call lists."
    }
  ]);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({});
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevMessagesLengthRef = useRef(messages.length);

  // Auto-scroll ONLY when a new message arrives
  useEffect(() => {
    if (isOpen && messages.length > prevMessagesLengthRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevMessagesLengthRef.current = messages.length;
  }, [messages.length, isOpen, loading]);

  // Fetch route-specific suggested actions from API or fallback pills
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
            setSuggestedActions(["Compare Plans", "Open Billing", "Contact Sales", "Start Checkout"]);
          } else if (r.includes('/leads') || r.includes('/inbox')) {
            setSuggestedActions(["View Leads", "Draft WhatsApp", "Create Follow-up"]);
          } else if (r.includes('/deals') || r.includes('/pipeline')) {
            setSuggestedActions(["Open Pipeline", "Schedule Meeting", "Generate Proposal"]);
          } else {
            setSuggestedActions(["View Leads", "Open Pipeline", "Compare Plans"]);
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
      setActionFeedback(`⚠️ Execution notice: ${err.message || 'Action sent to queue'}`);
      setTimeout(() => setActionFeedback(null), 4000);
    }
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
      // Prepare history turns for conversation memory
      const historyContext = messages
        .filter((m) => !m.isError)
        .slice(-8)
        .map((m) => ({ sender: m.sender, text: m.text }));

      const currentRoute = pathname || '/dashboard';
      const res = await apiClient.copilotQuery(q, currentRoute, historyContext);

      const copilotMsg: Message = {
        id: `copilot-${Date.now()}`,
        sender: 'copilot',
        text: res.answer_markdown || "I'm unable to generate a response right now.",
        reasoning: res.reasoning,
        rich_cards: res.rich_cards,
        action_buttons: res.action_buttons,
        citations: res.citations,
        suggested_followups: res.suggested_followups
      };

      setMessages((prev) => [...prev, copilotMsg]);
    } catch (err: any) {
      const detailedErr = (err && err.message) ? err.message : String(err);
      console.error('[Copilot API Exception]', err);
      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        sender: 'copilot',
        text: `⚠️ **Copilot Connection Error:** ${detailedErr}`,
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

  // Render clean formatted Markdown with headers, bolding, bullet points, and code blocks
  const renderFormattedContent = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, lIdx) => {
      // Headers
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

      // Bullet points
      const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ');
      const cleanLine = isBullet ? line.trim().substring(2) : line;

      const parts = cleanLine.split(/(\*\*.*?\*\*)/g);
      return (
        <div key={lIdx} className={`${isBullet ? 'pl-3 relative before:content-["•"] before:absolute before:left-0 before:text-amber-600' : ''} ${lIdx > 0 && !isBullet ? 'mt-1' : ''}`}>
          {parts.map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={pIdx} className="font-bold text-gray-900 dark:text-gray-100">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            return part;
          })}
        </div>
      );
    });
  };

  return (
    <>
      {/* Floating Copilot Trigger Button */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 bg-[#1A1A1A] hover:bg-black text-white p-3.5 rounded-full shadow-2xl border-2 border-[#E8F5A8] flex items-center gap-2 transition-all hover:scale-105 active:scale-95"
        >
          <Sparkles className="w-5 h-5 text-[#E8F5A8] fill-[#E8F5A8] animate-pulse" />
          <span className="text-xs font-mono font-bold pr-1">AI Copilot</span>
        </button>
      )}

      {/* Floating Copilot Drawer Panel */}
      {isOpen && (
        <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-[100] w-[calc(100vw-2rem)] sm:w-[420px] h-[640px] max-h-[88vh] bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
          
          {/* Fixed Header */}
          <div className="bg-[#1A1A1A] text-white p-3.5 flex items-center justify-between shrink-0 border-b border-gray-800">
            <div className="flex items-center gap-2 truncate">
              <Sparkles className="w-4 h-4 text-[#E8F5A8] fill-[#E8F5A8] shrink-0" />
              <span className="text-xs font-mono font-bold">BeetleLabs Copilot</span>
              <span className="bg-white/20 text-[9px] font-mono px-2 py-0.5 rounded text-[#E8F5A8] truncate">
                {pathname || '/dashboard'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white p-1 rounded transition-colors"
              aria-label="Close Copilot"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Action Feedback Banner */}
          {actionFeedback && (
            <div className="bg-emerald-600 text-white text-[10px] font-mono px-3 py-1.5 flex items-center justify-between shrink-0 animate-in fade-in duration-150">
              <div className="flex items-center gap-1.5 truncate">
                <CheckCircle className="w-3 h-3 text-[#E8F5A8] shrink-0" />
                <span className="truncate">{actionFeedback}</span>
              </div>
            </div>
          )}

          {/* Collapsible Quick Action Suggestions */}
          {suggestedActions.length > 0 && (
            <div className="bg-white border-b border-[#D4D0C8] shrink-0">
              <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-100 text-[10px] font-mono text-gray-500">
                <span className="font-semibold uppercase tracking-wider">Suggested Actions</span>
                <button
                  type="button"
                  onClick={() => setShowSuggestions(!showSuggestions)}
                  className="hover:text-gray-900 flex items-center gap-1 font-sans text-[11px]"
                >
                  {showSuggestions ? (
                    <><span>Hide</span><ChevronUp className="w-3 h-3" /></>
                  ) : (
                    <><span>Show ({suggestedActions.length})</span><ChevronDown className="w-3 h-3" /></>
                  )}
                </button>
              </div>

              {showSuggestions && (
                <div className="p-2 flex flex-nowrap gap-1.5 overflow-x-auto no-scrollbar">
                  {suggestedActions.map((act, i) => (
                    <button
                      key={i}
                      type="button"
                      disabled={loading}
                      onClick={() => handleSend(act)}
                      className="text-[10px] font-mono bg-[#FAF7F2] hover:bg-[#E8F5A8] text-gray-800 border border-[#D4D0C8] px-2.5 py-1 rounded-lg transition-colors whitespace-nowrap shrink-0 disabled:opacity-50"
                    >
                      {act}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Message Stream with Independent Scrolling & Event Isolation */}
          <div
            ref={scrollContainerRef}
            onWheel={(e) => e.stopPropagation()}
            className="flex-1 overflow-y-auto overscroll-contain p-4 space-y-3 scroll-smooth"
          >
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
                    <span>{m.sender === 'user' ? 'You' : 'Copilot AI OS'}</span>
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

                {/* Explainability Accordion ("Why this recommendation?") */}
                {m.reasoning && (
                  <div className="bg-[#FAF7F2] border border-[#E5E0D8] rounded-xl p-2 text-[10px] font-mono">
                    <button
                      type="button"
                      onClick={() => setExpandedReasoning(prev => ({ ...prev, [m.id]: !prev[m.id] }))}
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

                <div className="leading-relaxed font-sans text-xs">
                  {renderFormattedContent(m.text)}
                </div>

                {/* Rich Native UI Cards */}
                {m.rich_cards && m.rich_cards.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    {m.rich_cards.map((card, cIdx) => (
                      <div key={cIdx} className="bg-[#FAF7F2] border border-[#D4D0C8] p-2.5 rounded-xl text-xs space-y-1">
                        <div className="flex items-center justify-between font-bold text-gray-900">
                          <span>{card.title}</span>
                          {card.badge && (
                            <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-${card.badge_color || 'emerald'}-100 text-${card.badge_color || 'emerald'}-800 border border-${card.badge_color || 'emerald'}-300`}>
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

                {/* Executable 1-Click Action Buttons */}
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

                {m.citations && m.citations.length > 0 && (
                  <div className="flex items-center gap-1 pt-1.5 border-t border-gray-100 text-[9px] font-mono text-gray-400 flex-wrap">
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600 shrink-0" />
                    <span>Citations: {m.citations.join(' • ')}</span>
                  </div>
                )}

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
                <span>Copilot AI OS is querying CRM tools & Gemini...</span>
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
              placeholder="Ask Copilot AI OS to execute actions..."
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
      )}
    </>
  );
}
