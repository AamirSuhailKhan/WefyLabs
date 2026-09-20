'use client';

import React, { useState } from 'react';
import { AISalesChat } from '@/components/portal/AISalesChat';
import { useParams } from 'next/navigation';

/**
 * Public customer-facing AI Real Estate Sales Chat page.
 *
 * URL: /portal/[org]/chat
 * - [org] is the organization slug or ID used to scope the AI agent
 * - No authentication required — lead identity captured from form
 * - Fully public-accessible entry point for buyer conversations
 */
export default function CustomerAIChatPage() {
  const params = useParams();
  const orgId = String(params?.org || '');

  // Lead identity state — collected before showing chat
  const [phase, setPhase] = useState<'intro' | 'chat'>('intro');
  const [leadName, setLeadName] = useState('');
  const [leadPhone, setLeadPhone] = useState('');
  const [leadId, setLeadId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [introError, setIntroError] = useState('');

  // In production: capture lead → backend creates/finds lead → returns lead_id
  // For now: use a deterministic guest ID based on phone to enable real session continuity
  async function handleStartChat() {
    if (!leadPhone.trim()) {
      setIntroError('Please enter your phone number to continue');
      return;
    }
    setIsSubmitting(true);
    setIntroError('');
    try {
      // Try to capture lead via the public capture endpoint
      const base = typeof window !== 'undefined'
        ? `${window.location.origin}/api/v1`
        : 'http://localhost:8000/api/v1';

      const resp = await fetch(`${base}/lead-capture/public`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          organization_id: orgId,
          name: leadName.trim() || 'Web Visitor',
          phone: leadPhone.trim(),
          source: 'ai_chat_portal',
          channel: 'web',
        }),
      });

      let capturedLeadId = '';
      if (resp.ok) {
        const data = await resp.json();
        capturedLeadId = data.lead_id || data.id || '';
      } else {
        // Degrade gracefully: use phone hash as guest ID
        setIntroError('We could not start your conversation right now. Please try again.');
      }

      if (capturedLeadId) {
        sessionStorage.setItem(`wefylabs:chat:${orgId}`, JSON.stringify({ leadId: capturedLeadId, leadName: leadName.trim() }));
        setLeadId(capturedLeadId);
        setPhase('chat');
      }
    } catch {
      // Network error — still allow chat with guest ID
      setIntroError('We could not start your conversation right now. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  // ── Intro / Lead Capture Screen ───────────────────────────────────────────
  React.useEffect(() => {
    const saved = sessionStorage.getItem(`wefylabs:chat:${orgId}`);
    if (!saved) return;
    try {
      const identity = JSON.parse(saved) as { leadId?: string; leadName?: string };
      if (identity.leadId) {
        setLeadId(identity.leadId);
        setLeadName(identity.leadName || '');
        setPhase('chat');
      }
    } catch {
      sessionStorage.removeItem(`wefylabs:chat:${orgId}`);
    }
  }, [orgId]);

  if (phase === 'intro') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-violet-950 to-indigo-950 flex items-center justify-center p-4">
        {/* Ambient glows */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-96 h-96 bg-violet-600/20 rounded-full blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        </div>

        <div className="relative w-full max-w-md">
          {/* Logo / Brand */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-2xl mb-4">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight">
              Property Advisor
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Powered by WefyLabs AI · Verified Inventory
            </p>
          </div>

          {/* Card */}
          <div className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-3xl p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-white mb-1">
              Find your perfect property
            </h2>
            <p className="text-slate-300 text-sm mb-6">
              Our AI advisor will show you verified listings matching your requirements —
              no agents, no spam, just smart search.
            </p>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  Your Name (optional)
                </label>
                <input
                  id="chat-lead-name"
                  type="text"
                  value={leadName}
                  onChange={e => setLeadName(e.target.value)}
                  placeholder="e.g. Rohit Sharma"
                  className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-400 focus:bg-white/15 transition"
                  onKeyDown={e => e.key === 'Enter' && handleStartChat()}
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  Phone Number <span className="text-violet-400">*</span>
                </label>
                <input
                  id="chat-lead-phone"
                  type="tel"
                  value={leadPhone}
                  onChange={e => setLeadPhone(e.target.value)}
                  placeholder="+91 98765 43210"
                  className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-400 focus:bg-white/15 transition"
                  onKeyDown={e => e.key === 'Enter' && handleStartChat()}
                />
                {introError && (
                  <p className="text-xs text-red-400 mt-1">{introError}</p>
                )}
              </div>
            </div>

            <button
              id="start-ai-chat-btn"
              onClick={handleStartChat}
              disabled={isSubmitting}
              className="
                w-full mt-5 py-3.5 rounded-2xl text-sm font-black text-white
                bg-gradient-to-r from-violet-600 to-indigo-700
                hover:shadow-xl hover:shadow-violet-500/30 hover:scale-[1.02]
                active:scale-[0.98] transition-all
                disabled:opacity-50 disabled:cursor-not-allowed disabled:scale-100
              "
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/60 border-t-transparent rounded-full animate-spin" />
                  Getting Started…
                </span>
              ) : (
                'Start Chat with AI Advisor →'
              )}
            </button>

            {/* Trust signals */}
            <div className="flex items-center justify-center gap-4 mt-4">
              <div className="flex items-center gap-1 text-[10px] text-slate-400">
                <svg className="w-3 h-3 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.86L12 17.77l-6.18 3.23L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                </svg>
                Verified listings only
              </div>
              <div className="flex items-center gap-1 text-[10px] text-slate-400">
                <svg className="w-3 h-3 text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                </svg>
                No unsolicited calls
              </div>
              <div className="flex items-center gap-1 text-[10px] text-slate-400">
                <svg className="w-3 h-3 text-violet-400" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>
                </svg>
                Data protected
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Full Chat Interface ────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-slate-50 to-white overflow-hidden">
      {/* Top nav bar for mobile */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-900/95 backdrop-blur-md sm:hidden">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </div>
          <span className="text-white text-xs font-bold">Property Advisor</span>
        </div>
        <span className="text-slate-500 text-[10px]">WefyLabs AI</span>
      </div>

      {/* Chat fills remaining height */}
      <div className="flex-1 min-h-0 relative">
        <AISalesChat
          organizationId={orgId}
          leadId={leadId}
          leadName={leadName || undefined}
          agentDisplayName="Property Advisor"
          onEscalated={(_sid) => {}}
        />
      </div>
    </div>
  );
}
