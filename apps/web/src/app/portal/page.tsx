'use client';

import React, { useState } from 'react';
import { CustomerTimelineTracker } from '@/components/portal/CustomerTimelineTracker';
import { Home, Sparkles, MessageSquare, PhoneCall, Download, ShieldCheck, Heart, Calculator, Send } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { useBroker, getInitials } from '@/lib/auth-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function CustomerPortalPage() {
  const { region } = useRegion();
  const { broker } = useBroker();
  const [aiQuestion, setAiQuestion] = useState('');
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);

  const buyerName = "Client Account";
  const buyerInitials = getInitials(buyerName);
  const agentName = broker?.name || "Senior Realty Consultant";

  const handleAskAI = () => {
    if (!aiQuestion.trim()) return;
    setAiAnswer(
      "**AI Property Advisor:** For AED 2,850,000 with a 20% down payment (AED 570,000), your monthly mortgage EMI is approx. **AED 11,450/month** (25 years @ 4.25% interest). The Land Department registration fee is 4% (AED 114,000)."
    );
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] p-6 space-y-8 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white border border-[#D4D0C8] p-6 rounded-3xl shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-[#1A1A1A] text-white flex items-center justify-center font-mono font-bold text-lg">
            {buyerInitials}
          </div>
          <div>
            <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">Welcome to Customer Portal</h1>
            <p className="text-xs text-gray-500 font-sans">Customer Portal • Buyer Account (#22222222)</p>
          </div>
        </div>

        {/* Assigned Broker Info */}
        <div className="flex items-center gap-3 bg-[#FAF7F2] border border-[#D4D0C8] p-3 rounded-2xl">
          <div className="text-right">
            <span className="text-[10px] font-mono text-gray-500 font-bold uppercase block">Your Assigned Agent</span>
            <span className="text-xs font-bold font-mono text-[#1A1A1A]">{agentName}</span>
          </div>
          <a href="tel:+971501234567" className="btn-lime p-2 rounded-xl">
            <PhoneCall className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* Main Deal Tracker */}
      <CustomerTimelineTracker />

      {/* AI Property Advisor & Mortgage Calculator Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI Property Assistant */}
        <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-[#F0EDE8] pb-3">
            <Sparkles className="w-4 h-4 text-amber-500 fill-amber-300" />
            <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Ask AI Property Assistant</h3>
          </div>

          <p className="text-xs text-gray-600 font-sans">
            Get instant answers regarding mortgage estimations, Land Department legal fees, and title deed transfer steps.
          </p>

          <div className="flex items-center gap-2">
            <input
              type="text"
              value={aiQuestion}
              onChange={(e) => setAiQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAskAI()}
              placeholder="e.g., What is my monthly mortgage EMI and DLD transfer fee?"
              className="flex-1 px-3.5 py-2 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
            />
            <button onClick={handleAskAI} className="btn-lime px-4 py-2 text-xs flex items-center gap-1">
              <Send className="w-3.5 h-3.5" />
              <span>Ask AI</span>
            </button>
          </div>

          {aiAnswer && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-2xl text-xs text-amber-950 whitespace-pre-wrap font-sans">
              {aiAnswer}
            </div>
          )}
        </div>

        {/* Documents & Downloads Widget */}
        <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Verified Deal Documents</h3>
            </div>
            <span className="text-xs font-mono text-gray-500">3 Files</span>
          </div>

          <div className="space-y-2">
            <div className="p-3 rounded-2xl border border-[#D4D0C8] bg-[#FAF7F2] flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">Signed Reservation Form (MOU)</h4>
                <p className="text-[10px] text-gray-500 font-sans">Verified on Jul 28, 2026</p>
              </div>
              <button className="p-2 text-gray-700 hover:text-black">
                <Download className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 rounded-2xl border border-[#D4D0C8] bg-[#FAF7F2] flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">Bank Loan Pre-Approval Letter</h4>
                <p className="text-[10px] text-gray-500 font-sans">Verified on Jul 30, 2026</p>
              </div>
              <button className="p-2 text-gray-700 hover:text-black">
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
