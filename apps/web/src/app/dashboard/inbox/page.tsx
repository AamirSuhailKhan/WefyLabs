'use client';

import React, { useState, useEffect } from 'react';
import { UnifiedTimeline, TimelineMessage } from '@/components/communication/UnifiedTimeline';
import { AICopilotBar } from '@/components/communication/AICopilotBar';
import { MessageSquare, Mail, PhoneCall, Filter, Search, UserCheck, Clock, Tag } from 'lucide-react';
import { api } from '@/lib/api-client';

export default function InboxPage() {
  const [selectedChannel, setSelectedChannel] = useState<string>('all');
  const [activeLeadId, setActiveLeadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TimelineMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

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

  const handleSendMessage = async (channel: string, content: string) => {
    const newMsg: TimelineMessage = {
      id: String(Date.now()),
      channel: channel as any,
      direction: 'outbound',
      sender_name: 'Agent',
      content: content,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, newMsg]);
    if (activeLeadId) {
      try {
        await api.inbox.sendMessage({ lead_id: activeLeadId, channel, content });
      } catch { /* message already optimistically added */ }
    }
  };

  const handleSelectReply = (reply: string) => {
    handleSendMessage('whatsapp', reply);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Unified Omnichannel Inbox</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Manage WhatsApp, Email, SMS, Calls, and Team Notes in one customer timeline.
          </p>
        </div>

        {/* Channel Filter Pills */}
        <div className="flex items-center gap-1.5 bg-[#FAF7F2] border border-[#D4D0C8] p-1 rounded-xl">
          {['all', 'whatsapp', 'email', 'sms', 'call'].map((ch) => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              className={`px-3 py-1 text-xs font-mono font-bold rounded-lg uppercase transition-colors ${
                selectedChannel === ch ? 'bg-[#1A1A1A] text-white' : 'text-gray-600 hover:bg-gray-200'
              }`}
            >
              {ch}
            </button>
          ))}
        </div>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[720px]">
        {/* Left Column: Conversation List */}
        <div className="lg:col-span-3 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-3 flex flex-col space-y-2 overflow-y-auto shadow-xs">
          <div className="relative mb-2">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search conversations..."
              className="w-full pl-9 pr-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
            />
          </div>

          {/* Active Conversation Card */}
          <div className="p-3 bg-white border border-[#1A1A1A] rounded-xl shadow-2xs cursor-pointer">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-bold font-mono text-[#1A1A1A]">Rahul Sharma</span>
              <span className="bg-emerald-100 text-emerald-800 text-[9px] font-mono px-1.5 py-0.5 rounded">WhatsApp</span>
            </div>
            <p className="text-[11px] text-gray-600 line-clamp-1">Looking for 3BHK ready to move DLF Phase 5...</p>
            <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400 font-mono">
              <span>2 min ago</span>
              <span className="bg-[#E8F5A8] text-[#1A1A1A] font-bold px-1 rounded">Urgent</span>
            </div>
          </div>

          {/* Secondary Card */}
          <div className="p-3 bg-white/60 hover:bg-white border border-[#D4D0C8] rounded-xl transition-colors cursor-pointer">
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
        </div>

        {/* Middle Column: Unified Customer Timeline */}
        <div className="lg:col-span-6 h-full">
          <UnifiedTimeline messages={messages} onSendMessage={handleSendMessage} />
        </div>

        {/* Right Column: AI Communication Copilot */}
        <div className="lg:col-span-3 h-full overflow-y-auto">
          <AICopilotBar onSelectReply={handleSelectReply} />
        </div>
      </div>
    </div>
  );
}
