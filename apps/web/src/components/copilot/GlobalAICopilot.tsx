'use client';

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Sparkles, X, Send, Bot, User, ArrowRight, Zap, CheckCircle2, RefreshCw } from 'lucide-react';

export function GlobalAICopilot() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [queryInput, setQueryInput] = useState('');
  const [messages, setMessages] = useState<Array<{ sender: 'user' | 'copilot'; text: string; citations?: string[] }>>([
    {
      sender: 'copilot',
      text: "👋 Hi! I'm your BeetleLabs AI Copilot. Ask me anything about your leads, matching inventory, or transaction milestones."
    }
  ]);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Determine route-aware quick action pills based on current path
    const r = (pathname || '').toLowerCase();
    if (r.includes('/inbox')) {
      setSuggestedActions([
        "Generate WhatsApp response",
        "Detect buyer objections in latest chat",
        "Summarize recent voice call recording"
      ]);
    } else if (r.includes('/properties')) {
      setSuggestedActions([
        "Which buyers match this property?",
        "Is this property overpriced compared to market?",
        "Recommend price adjustment strategy"
      ]);
    } else if (r.includes('/deals')) {
      setSuggestedActions([
        "Which transactions are currently stalled?",
        "List missing documents for active deals",
        "Show expected commission payouts"
      ]);
    } else {
      setSuggestedActions([
        "Who should I call today?",
        "Which deals need immediate attention?",
        "Summarize yesterday's lead activity",
        "Forecast total revenue for this month"
      ]);
    }
  }, [pathname]);

  const handleSend = (textToSend?: string) => {
    const q = textToSend || queryInput;
    if (!q.trim()) return;

    setMessages((prev) => [...prev, { sender: 'user', text: q }]);
    if (!textToSend) setQueryInput('');
    setLoading(true);

    setTimeout(() => {
      let reply = "I've analyzed your current page context.";
      const r = (pathname || '').toLowerCase();

      if (r.includes('/inbox')) {
        reply = "**AI Copilot Analysis:**\n- High Intent Lead (Cash funding, 2.5 Cr+ budget).\n- Recommended Action: Send ready-to-move brochure and invite for viewing tomorrow 4 PM.";
      } else if (r.includes('/properties')) {
        reply = "**AI Property Intelligence:**\n- Property listed 11.9% below market AVM.\n- Matching Buyers: Rahul Sharma (98% match), Tariq Al-Mansoor (91% match).";
      } else if (r.includes('/deals')) {
        reply = "**AI Deal Intelligence:**\n- DLF Marina Gate Penthouse is stalled (Missing: *Signed Reservation Form*).\n- Closing probability: 78.5%.";
      } else {
        reply = "**AI Daily Briefing:**\n1. Call Rahul Sharma (+91 98765 43210) regarding 3BHK pricing.\n2. Review 1 stalled deal in Booking stage.\n3. On track for AED 134,500 in commissions this month.";
      }

      setMessages((prev) => [
        ...prev,
        {
          sender: 'copilot',
          text: reply,
          citations: ['BeetleLabs Core Engine v2.5', 'Active Route Context']
        }
      ]);
      setLoading(false);
    }, 600);
  };

  return (
    <>
      {/* Floating Copilot Trigger Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 bg-[#1A1A1A] hover:bg-black text-white p-3.5 rounded-full shadow-xl border-2 border-[#E8F5A8] flex items-center gap-2 transition-transform hover:scale-105"
        >
          <Sparkles className="w-5 h-5 text-[#E8F5A8] fill-[#E8F5A8] animate-pulse" />
          <span className="text-xs font-mono font-bold pr-1">AI Copilot</span>
        </button>
      )}

      {/* Floating Copilot Drawer Panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-96 h-[560px] bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
          {/* Header */}
          <div className="bg-[#1A1A1A] text-white p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#E8F5A8] fill-[#E8F5A8]" />
              <span className="text-xs font-mono font-bold">BeetleLabs Copilot</span>
              <span className="bg-white/20 text-[9px] font-mono px-2 py-0.5 rounded text-[#E8F5A8]">
                Route: {pathname || '/'}
              </span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Quick Action Suggestions */}
          <div className="p-2.5 bg-white/60 border-b border-[#D4D0C8] flex flex-wrap gap-1.5 overflow-x-auto">
            {suggestedActions.slice(0, 3).map((act, i) => (
              <button
                key={i}
                onClick={() => handleSend(act)}
                className="text-[10px] font-mono bg-white hover:bg-[#E8F5A8] text-gray-800 border border-[#D4D0C8] px-2.5 py-1 rounded-lg transition-colors text-left truncate"
              >
                {act}
              </button>
            ))}
          </div>

          {/* Message Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-2xl text-xs space-y-1.5 ${
                  m.sender === 'user'
                    ? 'bg-[#1A1A1A] text-white ml-6'
                    : 'bg-white text-[#1A1A1A] border border-[#D4D0C8] mr-6 shadow-2xs'
                }`}
              >
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-gray-400 font-bold">
                  {m.sender === 'user' ? <User className="w-3 h-3 text-white" /> : <Bot className="w-3 h-3 text-amber-500" />}
                  <span>{m.sender === 'user' ? 'You' : 'Copilot AI'}</span>
                </div>
                <p className="whitespace-pre-wrap leading-relaxed font-sans">{m.text}</p>
                {m.citations && (
                  <div className="flex items-center gap-1 pt-1 border-t border-gray-100 text-[9px] font-mono text-gray-400">
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                    <span>Citations: {m.citations.join(', ')}</span>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex items-center gap-2 p-3 bg-white rounded-2xl border border-[#D4D0C8] mr-6 text-xs text-gray-500 font-mono">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-500" />
                <span>Copilot is reasoning over active page context...</span>
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="p-3 bg-white border-t border-[#D4D0C8] flex items-center gap-2">
            <input
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask Copilot anything..."
              className="flex-1 px-3 py-2 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none"
            />
            <button onClick={() => handleSend()} className="btn-lime p-2 rounded-xl">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
