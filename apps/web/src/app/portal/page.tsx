'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { CustomerTimelineTracker } from '@/components/portal/CustomerTimelineTracker';
import { Home, Sparkles, MessageSquare, PhoneCall, Download, ShieldCheck, Heart, Calculator, ExternalLink } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { useBroker, getInitials } from '@/lib/auth-context';
import { formatCurrency } from '@/lib/i18n/currency';
import { getOrganizationId } from '@/lib/api-client';

export default function CustomerPortalPage() {
  const { region } = useRegion();
  const { broker } = useBroker();

  const buyerName = broker?.name || 'Client';
  const buyerInitials = getInitials(buyerName);
  const agentName = broker?.name || 'Senior Realty Consultant';
  // Organization ID from auth context — used to route to the right AI agent
  const orgId = getOrganizationId() || 'default';


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
            <p className="text-xs text-gray-500 font-sans">Customer Portal • Buyer Account</p>
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
        {/* AI Property Chat — redirect to real AI agent */}
        <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-[#F0EDE8] pb-3">
            <Sparkles className="w-4 h-4 text-amber-500 fill-amber-300" />
            <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">AI Property Advisor</h3>
          </div>

          <p className="text-xs text-gray-600 font-sans">
            Chat with our AI advisor to find properties, get pricing information, schedule visits, and compare options — all from verified inventory.
          </p>

          <div className="bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-200 rounded-2xl p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
                <span className="text-white text-[9px] font-black">AI</span>
              </div>
              <p className="text-xs text-slate-600">
                &ldquo;Hello! I can help you find your perfect property, check availability, compare options, and book a visit. What are you looking for?&rdquo;
              </p>
            </div>
            <Link
              href={`/portal/${orgId}/chat`}
              id="open-ai-chat-btn"
              className="flex items-center justify-center gap-2 w-full py-2.5 bg-gradient-to-r from-violet-600 to-indigo-700 text-white text-xs font-bold rounded-xl hover:shadow-lg hover:shadow-violet-500/20 transition-all"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Start AI Property Chat
              <ExternalLink className="w-3 h-3 opacity-60" />
            </Link>
          </div>
        </div>

        {/* Documents & Downloads Widget */}
        <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Your Deal Documents</h3>
            </div>
          </div>

          <div className="p-6 rounded-2xl border border-dashed border-[#D4D0C8] bg-[#FAF7F2] text-center space-y-2">
            <Download className="w-6 h-6 text-gray-400 mx-auto" />
            <p className="text-xs font-medium text-gray-700">No documents yet</p>
            <p className="text-[11px] text-gray-500 font-sans max-w-xs mx-auto">
              Verified agreements, booking receipts, and property brochures shared by your advisor will be available here.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
