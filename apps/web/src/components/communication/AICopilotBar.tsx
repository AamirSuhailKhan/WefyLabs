'use client';

import React from 'react';
import { Sparkles, AlertCircle, CheckCircle2, ArrowRight, Zap } from 'lucide-react';

interface Props {
  aiSummary?: string;
  aiSentiment?: string;
  aiUrgencyScore?: number;
  aiObjections?: string[];
  aiNextBestAction?: string;
  smartReplies?: string[];
  onSelectReply?: (reply: string) => void;
}

export function AICopilotBar({
  aiSummary = 'Lead is inquiring for 3BHK ready to move villa in Dubai Marina.',
  aiSentiment = 'highly_urgent',
  aiUrgencyScore = 0.92,
  aiObjections = ['Possession timeline negotiation', 'Price breakdown requested'],
  aiNextBestAction = 'Schedule physical viewing & share Golden Visa brochure.',
  smartReplies = [
    "Hi, I've attached the complete 3BHK brochure and pricing breakdown.",
    "Would you be available for a quick viewing tomorrow at 4 PM?",
    "Our team can schedule a video walkthrough if you're currently overseas."
  ],
  onSelectReply
}: Props) {
  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-amber-500 fill-amber-300" />
          <span>AI Communication Copilot</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          Urgency {(aiUrgencyScore * 100).toFixed(0)}%
        </span>
      </div>

      {/* Summary */}
      <div>
        <h4 className="text-[10px] font-mono uppercase text-gray-500 font-bold mb-1">AI Summary</h4>
        <p className="text-xs text-[#1A1A1A] leading-relaxed font-sans bg-white p-2.5 rounded-xl border border-[#D4D0C8]">
          {aiSummary}
        </p>
      </div>

      {/* Next Best Action */}
      <div className="bg-emerald-50 border border-emerald-200 p-2.5 rounded-xl">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-emerald-900 mb-1">
          <Zap className="w-3.5 h-3.5 fill-emerald-500 text-emerald-700" />
          <span>Next Best Action</span>
        </div>
        <p className="text-xs text-emerald-800 font-sans">{aiNextBestAction}</p>
      </div>

      {/* Objections */}
      {aiObjections && aiObjections.length > 0 && (
        <div>
          <h4 className="text-[10px] font-mono uppercase text-gray-500 font-bold mb-1.5">Detected Objections</h4>
          <div className="space-y-1">
            {aiObjections.map((obj, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-amber-900 bg-amber-50 border border-amber-200 p-1.5 rounded-lg">
                <AlertCircle className="w-3 h-3 text-amber-600 shrink-0" />
                <span>{obj}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Smart Replies */}
      <div>
        <h4 className="text-[10px] font-mono uppercase text-gray-500 font-bold mb-2">1-Click AI Smart Replies</h4>
        <div className="space-y-2">
          {smartReplies.map((reply, idx) => (
            <button
              key={idx}
              onClick={() => onSelectReply?.(reply)}
              className="w-full text-left p-2 bg-white hover:bg-[#E8F5A8] border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] transition-colors flex items-center justify-between group"
            >
              <span className="line-clamp-2">{reply}</span>
              <ArrowRight className="w-3.5 h-3.5 text-gray-400 group-hover:text-[#1A1A1A] shrink-0 ml-1" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
