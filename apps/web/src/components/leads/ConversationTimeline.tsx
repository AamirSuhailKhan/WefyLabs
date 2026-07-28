'use client';

import { Bot, User, ShieldAlert, CheckCheck } from 'lucide-react';
import { Conversation } from '@/types';

interface ConversationTimelineProps {
  conversations: Conversation[];
}

export default function ConversationTimeline({ conversations }: ConversationTimelineProps) {
  return (
    <div className="glass-panel rounded-2xl border border-dark-border overflow-hidden flex flex-col h-[580px]">
      {/* WhatsApp Header */}
      <div className="bg-whatsapp-dark p-4 flex items-center justify-between border-b border-dark-border">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-whatsapp-light/20 text-whatsapp-light flex items-center justify-center font-bold">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-extrabold text-white text-sm">BeetleLabs AI WhatsApp Assistant</h3>
            <p className="text-[11px] text-emerald-300 font-medium">WhatsApp Qualification Chat</p>
          </div>
        </div>
        <span className="text-xs bg-black/20 text-slate-200 px-3 py-1 rounded-full font-mono font-medium">
          Encrypted Thread
        </span>
      </div>

      {/* Messages Scroll Container */}
      <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-whatsapp-bg/90">
        {conversations.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500 text-xs font-medium">
            No WhatsApp messages recorded yet.
          </div>
        ) : (
          conversations.map((msg) => {
            const isBot = msg.sender_type === 'bot';
            const isLead = msg.sender_type === 'lead';

            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isLead ? 'items-start' : 'items-end'}`}
              >
                <div
                  className={`max-w-[82%] sm:max-w-[70%] p-3.5 rounded-2xl text-xs font-medium shadow-md ${
                    isLead
                      ? 'bg-whatsapp-bubbleIn text-slate-100 rounded-tl-none border border-white/5'
                      : isBot
                      ? 'bg-whatsapp-bubbleOut text-emerald-50 rounded-tr-none border border-emerald-500/20'
                      : 'bg-indigo-600/30 text-indigo-100 rounded-tr-none border border-indigo-500/30'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1 opacity-75 text-[10px] font-bold uppercase tracking-wider">
                    <span>{isLead ? 'Lead' : isBot ? 'BeetleLabs Bot' : 'Broker Note'}</span>
                    <span className="font-mono" suppressHydrationWarning>
                      {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>

                  <p className="whitespace-pre-wrap leading-relaxed">{msg.message}</p>

                  <div className="flex justify-end mt-1 text-[10px] text-emerald-200/60">
                    <CheckCheck className="w-3.5 h-3.5" />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
