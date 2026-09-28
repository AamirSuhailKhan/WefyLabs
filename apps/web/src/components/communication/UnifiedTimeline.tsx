'use client';

import React, { useState } from 'react';
import { MessageSquare, Mail, PhoneCall, FileText, Send, User, Paperclip, Play } from 'lucide-react';

/**
 * Part 12 — Unified Communication Timeline (operator view)
 *
 * Channel support reflects actual backend channel status:
 *   WEB / EMAIL / SMS — IMPLEMENTED
 *   WHATSAPP          — DISABLED (removed from composer + type)
 *   VOICE             — FUTURE (read-only call records only)
 *
 * The composer only exposes channels that the Communication Hub
 * can actually send on today.
 */

export type TimelineMessageChannel = 'whatsapp' | 'web' | 'email' | 'sms' | 'call' | 'internal_note' | 'other';

export interface TimelineMessage {
  id: string;
  channel: TimelineMessageChannel;
  direction: 'inbound' | 'outbound';
  sender_name: string;
  content: string;
  attachments?: { name: string; url?: string }[];
  call_record?: {
    recording_url?: string;
    duration_seconds: number;
    transcript?: string;
    ai_summary?: string;
  };
  mentions?: string[];
  created_at: string;
  delivery_status?: 'queued' | 'sent' | 'delivered' | 'read' | 'failed' | 'unknown';
}

export type ComposerChannel = 'whatsapp' | 'web' | 'email' | 'sms' | 'internal_note';

interface Props {
  messages: TimelineMessage[];
  onSendMessage: (channel: ComposerChannel, content: string) => void;
}

const CHANNEL_BADGES: Record<string, JSX.Element> = {
  whatsapp: (
    <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-800 text-[10px] font-mono px-2 py-0.5 rounded-full font-bold">
      <MessageSquare className="w-3 h-3 text-emerald-600" /> WhatsApp
    </span>
  ),
  web: (
    <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 text-[10px] font-mono px-2 py-0.5 rounded-full">
      <MessageSquare className="w-3 h-3" /> Web Chat
    </span>
  ),
  email: (
    <span className="inline-flex items-center gap-1 bg-indigo-100 text-indigo-800 text-[10px] font-mono px-2 py-0.5 rounded-full">
      <Mail className="w-3 h-3" /> Email
    </span>
  ),
  sms: (
    <span className="inline-flex items-center gap-1 bg-purple-100 text-purple-800 text-[10px] font-mono px-2 py-0.5 rounded-full">
      <MessageSquare className="w-3 h-3" /> SMS
    </span>
  ),
  call: (
    <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-[10px] font-mono px-2 py-0.5 rounded-full">
      <PhoneCall className="w-3 h-3" /> Voice Call
    </span>
  ),
  internal_note: (
    <span className="inline-flex items-center gap-1 bg-yellow-100 text-yellow-900 text-[10px] font-mono px-2 py-0.5 rounded-full font-bold">
      <FileText className="w-3 h-3" /> Internal Note
    </span>
  ),
  other: (
    <span className="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-[10px] font-mono px-2 py-0.5 rounded-full">
      <MessageSquare className="w-3 h-3" /> Other
    </span>
  ),
};

const DELIVERY_STATUS_LABEL: Record<string, string> = {
  queued: '· Queued',
  sent: '✓ Sent',
  delivered: '✓✓ Delivered',
  read: '✓✓ Read',
  failed: '✗ Failed',
  unknown: '',
};

export function UnifiedTimeline({ messages, onSendMessage }: Props) {
  const [activeChannel, setActiveChannel] = useState<ComposerChannel>('whatsapp');
  const [inputText, setInputText] = useState('');

  const handleSend = () => {
    const text = inputText.trim();
    if (!text) return;
    onSendMessage(activeChannel, text);
    setInputText('');
  };

  const composerChannels: { id: ComposerChannel; label: string }[] = [
    { id: 'whatsapp', label: 'WhatsApp' },
    { id: 'web', label: 'Web Chat' },
    { id: 'email', label: 'Email' },
    { id: 'sms', label: 'SMS' },
    { id: 'internal_note', label: 'Internal Note' },
  ];

  return (
    <div className="flex flex-col h-full bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-xs overflow-hidden">
      {/* Timeline Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 py-12 select-none">
            <MessageSquare className="w-8 h-8 mb-2 opacity-30" />
            <p className="text-xs font-mono">No messages yet</p>
            <p className="text-[11px] mt-1">Start a conversation using the composer below.</p>
          </div>
        )}

        {messages.map((msg) => {
          const isNote = msg.channel === 'internal_note';
          const isCall = msg.channel === 'call';
          const statusLabel = msg.delivery_status ? DELIVERY_STATUS_LABEL[msg.delivery_status] : '';

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
                  {CHANNEL_BADGES[msg.channel] ?? CHANNEL_BADGES.other}
                </div>
                <div className="flex items-center gap-2">
                  {statusLabel && (
                    <span
                      className={`text-[10px] font-mono ${
                        msg.delivery_status === 'failed' ? 'text-red-500 font-bold' : 'text-gray-400'
                      }`}
                    >
                      {statusLabel}
                    </span>
                  )}
                  <span className="text-[10px] text-gray-400 font-mono">
                    {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>

              <p className="text-xs text-[#1A1A1A] leading-relaxed font-sans whitespace-pre-wrap">{msg.content}</p>

              {/* Attachments */}
              {msg.attachments && msg.attachments.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {msg.attachments.map((att, i) => (
                    <a
                      key={i}
                      href={att.url ?? '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-blue-700 underline font-mono hover:text-blue-900"
                    >
                      <Paperclip className="w-3 h-3" />
                      {att.name}
                    </a>
                  ))}
                </div>
              )}

              {/* Voice Call Recording & AI Summary */}
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
        {/* Channel selector — WhatsApp intentionally absent (channel not live) */}
        <div className="flex items-center gap-2 flex-wrap">
          {composerChannels.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveChannel(id)}
              aria-pressed={activeChannel === id}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-bold transition-colors ${
                id === 'internal_note'
                  ? activeChannel === id
                    ? 'bg-yellow-400 text-yellow-950'
                    : 'bg-yellow-100 text-yellow-900 hover:bg-yellow-200'
                  : activeChannel === id
                  ? 'bg-[#1A1A1A] text-white'
                  : 'bg-[#F0EDE8] text-gray-700 hover:bg-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
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
                : `Send message via ${activeChannel === 'web' ? 'Web Chat' : activeChannel.toUpperCase()}...`
            }
            className="flex-1 px-3 py-2 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none focus:border-[#1A1A1A] transition-colors"
          />
          <button
            onClick={handleSend}
            disabled={!inputText.trim()}
            className="btn-lime px-4 py-2 text-xs flex items-center gap-1.5 disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
