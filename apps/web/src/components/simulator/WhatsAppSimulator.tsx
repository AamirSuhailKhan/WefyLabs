'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, RotateCcw, Bot, CheckCheck, Sparkles, User, Brain } from 'lucide-react';
import { api } from '@/lib/api-client';

interface Message {
  id: string | number;
  sender: 'bot' | 'user';
  text: string;
  time: string;
}

const CONVERSATION_FLOW = [
  {
    bot: "Hi! I'm assisting Apex Realty Bengaluru's office. I see you're looking for a property. To help you better, may I ask a few quick questions? What's your approximate budget range?",
    userOptions: ["40-50 Lakhs", "Around 1 Crore", "30-35 Lakhs"],
  },
  {
    bot: "Great, thanks! Which areas or localities are you considering in Bengaluru?",
    userOptions: ["Koramangala, HSR", "Whitefield", "Indiranagar"],
  },
  {
    bot: "Noted. When do you plan to move or finalize the purchase?",
    userOptions: ["Within a month", "In 2-3 months", "Just exploring"],
  },
  {
    bot: "Are you looking to buy, rent, or lease?",
    userOptions: ["Buy 2BHK", "Buy 3BHK", "Rent"],
  },
  {
    bot: "Have you arranged or started your home loan process?",
    userOptions: ["Pre-approved", "In process", "Not yet"],
  },
];

export default function WhatsAppSimulator({ fullWidth = false }: { fullWidth?: boolean }) {
  const [phoneInput, setPhoneInput] = useState('+919876543210');
  const [hasStarted, setHasStarted] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [step, setStep] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [showScore, setShowScore] = useState(false);
  const [scoreData, setScoreData] = useState<{ score: string; confidence: number; reasoning: string } | null>(null);
  const [customInput, setCustomInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping, showScore]);

  const handleStartSimulation = async () => {
    if (!phoneInput.trim()) return;
    setHasStarted(true);
    const initialMsg: Message = {
      id: 1,
      sender: 'bot',
      text: CONVERSATION_FLOW[0].bot,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages([initialMsg]);
    setStep(0);
    setShowScore(false);
    setScoreData(null);
  };

  const handleUserReply = async (text: string) => {
    const nextStep = step + 1;
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: Message = {
      id: Date.now(),
      sender: 'user',
      text,
      time: timeStr,
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);

    try {
      // Call real backend simulator API
      const simRes = await api.simulateWhatsApp({
        lead_phone: phoneInput,
        message: text
      });

      setTimeout(() => {
        setIsTyping(false);

        if (nextStep < CONVERSATION_FLOW.length) {
          const botMsg: Message = {
            id: Date.now() + 1,
            sender: 'bot',
            text: simRes.reply_message || CONVERSATION_FLOW[nextStep].bot,
            time: timeStr,
          };
          setMessages((prev) => [...prev, botMsg]);
          setStep(nextStep);
        } else {
          // Qualification complete
          const finalBotMsg: Message = {
            id: Date.now() + 1,
            sender: 'bot',
            text: "Thanks! Rahul Sharma from Apex Realty will call you shortly with curated listings.",
            time: timeStr,
          };
          setMessages((prev) => [...prev, finalBotMsg]);
          setShowScore(true);
          setScoreData({
            score: simRes.score || 'hot',
            confidence: simRes.score_card?.confidence || 0.94,
            reasoning: simRes.score_card?.reasoning || 'High budget interest, ready to view in Koramangala & HSR within 1 month. Loan pre-approved.'
          });
        }
      }, 900);
    } catch (e) {
      setIsTyping(false);
      if (nextStep < CONVERSATION_FLOW.length) {
        const botMsg: Message = {
          id: Date.now() + 1,
          sender: 'bot',
          text: CONVERSATION_FLOW[nextStep].bot,
          time: timeStr,
        };
        setMessages((prev) => [...prev, botMsg]);
        setStep(nextStep);
      } else {
        setShowScore(true);
        setScoreData({
          score: 'hot',
          confidence: 0.94,
          reasoning: 'High intent buyer looking for 2BHK to buy in < 3 months in Koramangala. Call immediately.'
        });
      }
    }
  };

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customInput.trim() || isTyping) return;
    handleUserReply(customInput.trim());
    setCustomInput('');
  };

  const reset = () => {
    setHasStarted(false);
    setMessages([]);
    setStep(0);
    setIsTyping(false);
    setShowScore(false);
    setScoreData(null);
  };

  return (
    <div className={`mx-auto w-full ${fullWidth ? 'max-w-4xl' : 'max-w-md'}`}>
      <div className="bg-[#121824] rounded-3xl border border-white/10 overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="bg-blue-600/10 px-5 py-4 flex items-center justify-between border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30 text-blue-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <div className="text-sm font-semibold text-white">WefyLabs AI Assistant</div>
              <div className="text-xs text-blue-400 flex items-center gap-1.5 font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                WhatsApp Live Simulator
              </div>
            </div>
          </div>
          {hasStarted && (
            <button
              onClick={reset}
              className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/5"
              title="Reset Simulator"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Start State or Chat Body */}
        {!hasStarted ? (
          <div className="p-8 text-center space-y-4 bg-[#0A0D14]">
            <div className="w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center mx-auto text-blue-400">
              <Sparkles className="w-8 h-8" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Test Real-Time AI Lead Qualification</h3>
              <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto">
                Enter a sample lead phone number to test how WefyLabs AI qualifies buyers &amp; outputs Hot/Warm/Cold scores.
              </p>
            </div>

            <div className="max-w-xs mx-auto space-y-3 pt-2">
              <input
                type="tel"
                value={phoneInput}
                onChange={(e) => setPhoneInput(e.target.value)}
                placeholder="+919876543210"
                className="w-full text-center px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white font-mono text-sm focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={handleStartSimulation}
                className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-blue-500/25 transition-all"
              >
                Run AI Qualification Demo
              </button>
            </div>
          </div>
        ) : (
          <div className="h-80 overflow-y-auto p-4 space-y-3 bg-[#0A0D14]">
            <AnimatePresence>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.3 }}
                  className={`flex ${msg.sender === 'bot' ? 'justify-start' : 'justify-end'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-xs sm:text-sm font-medium leading-relaxed ${
                      msg.sender === 'bot'
                        ? 'bg-[#1E2638] text-white rounded-tl-sm border border-white/10'
                        : 'bg-blue-600 text-white rounded-tr-sm shadow-lg shadow-blue-500/20'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.text}</p>
                    <div className={`text-[10px] mt-1 flex items-center justify-end gap-1 ${msg.sender === 'bot' ? 'text-gray-400' : 'text-blue-200'}`}>
                      <span>{msg.time}</span>
                      <CheckCheck className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {isTyping && (
              <motion.div initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} className="flex justify-start">
                <div className="bg-[#1E2638] border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    {[0, 0.15, 0.3].map((delay, idx) => (
                      <motion.span
                        key={idx}
                        animate={{ y: [0, -5, 0] }}
                        transition={{ duration: 0.6, repeat: Infinity, delay }}
                        className="w-2 h-2 rounded-full bg-gray-400"
                      />
                    ))}
                  </div>
                </div>
              </motion.div>
            )}

            {showScore && scoreData && (
              <motion.div
                initial={{ scale: 0.85, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 220, damping: 14 }}
              >
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 mt-2 text-white">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">🔥</span>
                      <span className="font-extrabold text-amber-400 uppercase tracking-wider">{scoreData.score} LEAD</span>
                    </div>
                    <span className="text-xs font-bold bg-amber-500/20 text-amber-400 px-2.5 py-0.5 rounded-full border border-amber-500/30">
                      {Math.round(scoreData.confidence * 100)}% Confidence
                    </span>
                  </div>
                  <div className="flex items-start gap-2 text-xs text-gray-300 mt-2">
                    <Brain className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold text-white">Agent Thoughts: </span>
                      {scoreData.reasoning}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input Controls */}
        {hasStarted && (
          <div className="p-4 bg-[#121824] border-t border-white/10 space-y-3">
            {!showScore ? (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {CONVERSATION_FLOW[step]?.userOptions.map((opt, i) => (
                    <button
                      key={i}
                      onClick={() => handleUserReply(opt)}
                      disabled={isTyping}
                      className="px-3 py-2 rounded-full bg-white/5 border border-white/10 text-xs text-white hover:border-blue-500 hover:bg-blue-500/10 transition-all disabled:opacity-50 font-medium"
                    >
                      + {opt}
                    </button>
                  ))}
                </div>

                <form onSubmit={handleCustomSubmit} className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder="Or type custom reply as lead..."
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <button
                    type="submit"
                    disabled={isTyping || !customInput.trim()}
                    className="bg-blue-600 hover:bg-blue-500 text-white p-2 rounded-xl transition-all disabled:opacity-40"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            ) : (
              <div className="flex items-center justify-between text-xs text-gray-300">
                <span className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-blue-400" />
                  Qualification complete. Result logged!
                </span>
                <button
                  onClick={reset}
                  className="text-blue-400 font-bold hover:underline"
                >
                  Run Another Demo
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
