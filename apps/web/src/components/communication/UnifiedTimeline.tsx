'use client';

import React, { useState } from 'react';
import { MessageSquare, Mail, PhoneCall, FileText, Send, User, Sparkles, Paperclip, Play } from 'lucide-react';

export interface TimelineMessage {
  id: string;
  channel: 'whatsapp' | 'email' | 'sms' | 'call' | 'internal_note';
  direction: 'inbound' | 'outbound';
  sender_name: string;
  content: string;
  attachments?: any[];
  call_record?: {
    recording_url?: string;
    duration_seconds: number;
    transcript?: string;
    ai_summary?: string;
  };
  mentions?: string[];
  created_at: string;
}

interface Props {
  messages: TimelineMessage[];
  onSendMessage: (channel: string, content: string) => void;
}

export function UnifiedTimeline({ messages, onSendMessage }: Props) {
  const [activeChannel, setActiveChannel] = useState<'whatsapp' | 'email' | 'sms' | 'internal_note'>('whatsapp');
  const [inputText, setInputText] = useState('');

  const handleSend = () => {
    if (!inputText.trim()) return;
    onSendMessage(activeChannel, inputText.trim());
    setInputText('');
  };

  const getChannelBadge = (channel: string) => {
    switch (channel) {
      case 'whatsapp':
        return <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-800 text-[10px] font-mono px-2 py-0.5 rounded-full"><MessageSquare className="w-3 h-3" /> WhatsApp</span>;
      case 'email':
        return <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 text-[10px] font-mono px-2 py-0.5 rounded-full"><Mail className="w-3 h-3" /> Email</span>;
      case 'sms':
        return <span className="inline-flex items-center gap-1 bg-purple-100 text-purple-800 text-[10px] font-mono px-2 py-0.5 rounded-full"><MessageSquare className="w-3 h-3" /> SMS</span>;
      case 'call':
        return <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-[10px] font-mono px-2 py-0.5 rounded-full"><PhoneCall className="w-3 h-3" /> Voice Call</span>;
      case 'internal_note':
        return <span className="inline-flex items-center gap-1 bg-yellow-100 text-yellow-900 text-[10px] font-mono px-2 py-0.5 rounded-full font-bold"><FileText className="w-3 h-3" /> Internal Note</span>;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-xs overflow-hidden">
      {/* Timeline Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => {
          const isNote = msg.channel === 'internal_note';
          const isCall = msg.channel === 'call';

          return (
            <div
              key={msg.id}
              className={`p-3.5 rounded-xl border ${
                isNote
                  ? 'bg-yellow-50/80 border-yellow-200 shadow-2xs'
                  : isCall
                  ? 'bg-amber-50/60 border-amber-200 shadow-2xs'
                  : msg.direction === 'outbound'
                  ? 'bg-white border-[#D4D0C8] ml-8 shadow-2xs'
                  : 'bg-[#F0EDE8] border-[#D4D0C8] mr-8'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <User className="w-3.5 h-3.5 text-gray-500" />
                  <span className="text-xs font-bold text-[#1A1A1A] font-mono">{msg.sender_name}</span>
                  {getChannelBadge(msg.channel)}
                </div>
                <span className="text-[10px] text-gray-400 font-mono">
                  {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              <p className="text-xs text-[#1A1A1A] leading-relaxed font-sans whitespace-pre-wrap">{msg.content}</p>

              {/* Voice Call Audio Recording & AI Summary */}
              {isCall && msg.call_record && (
                <div className="mt-3 p-2.5 rounded-lg bg-amber-100/70 border border-amber-200 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-amber-900 font-mono font-bold">
                    <Play className="w-3.5 h-3.5 fill-amber-900" />
                    <span>Call Recording ({msg.call_record.duration_seconds}s)</span>
                  </div>
                  {msg.call_record.ai_summary && (
                    <div className="text-[11px] text-amber-950 font-sans italic bg-white/60 p-2 rounded border border-amber-200">
                      <strong>AI Call Summary:</strong> {msg.call_record.ai_summary}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Composer Toolbar */}
      <div className="p-3 bg-white border-t border-[#D4D0C8] space-y-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveChannel('whatsapp')}
            className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-colors ${
              activeChannel === 'whatsapp' ? 'bg-[#1A1A1A] text-white' : 'bg-[#F0EDE8] text-gray-700 hover:bg-gray-200'
            }`}
          >
            WhatsApp
          </button>
          <button
            onClick={() => setActiveChannel('email')}
            className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-colors ${
              activeChannel === 'email' ? 'bg-[#1A1A1A] text-white' : 'bg-[#F0EDE8] text-gray-700 hover:bg-gray-200'
            }`}
          >
            Email
          </button>
          <button
            onClick={() => setActiveChannel('sms')}
            className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-colors ${
              activeChannel === 'sms' ? 'bg-[#1A1A1A] text-white' : 'bg-[#F0EDE8] text-gray-700 hover:bg-gray-200'
            }`}
          >
            SMS
          </button>
          <button
            onClick={() => setActiveChannel('internal_note')}
            className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-colors ${
              activeChannel === 'internal_note' ? 'bg-yellow-400 text-yellow-950' : 'bg-yellow-100 text-yellow-900 hover:bg-yellow-200'
            }`}
          >
            Internal Note
          </button>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={
              activeChannel === 'internal_note'
                ? 'Add internal team note (use @to mention team members)...'
                : `Send message via ${activeChannel.toUpperCase()}...`
            }
            className="flex-1 px-3 py-2 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none"
          />
          <button
            onClick={handleSend}
            className="btn-lime px-4 py-2 text-xs flex items-center gap-1.5"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
