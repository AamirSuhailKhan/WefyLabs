'use client';

import { Bot, MessageSquareCode, Sparkles } from 'lucide-react';
import WhatsAppSimulator from '@/components/simulator/WhatsAppSimulator';

export default function SimulatorPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <div className="text-center max-w-2xl mx-auto mb-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold mb-3">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Interactive Bot Playground</span>
        </div>
        <h1 className="text-3xl font-extrabold text-white">WhatsApp Bot Live Simulator</h1>
        <p className="text-xs text-slate-400 mt-2">
          Test how WefyLabs AI interacts with leads, extracts budget, timeline, location, loan status & generates Hot/Warm/Cold scorecards in real time.
        </p>
      </div>

      <WhatsAppSimulator />
    </div>
  );
}
