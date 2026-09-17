'use client';

import React, { useEffect, useState } from 'react';
import { CheckCircle2, Circle, X, Sparkles, ArrowRight, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api-client';
import { OnboardingStatusResponse, TenantActivationResponse, ChecklistItem } from '@/types';

export function OnboardingChecklist() {
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<OnboardingStatusResponse | null>(null);
  const [activation, setActivation] = useState<TenantActivationResponse | null>(null);

  useEffect(() => {
    let isMounted = true;
    async function fetchProgress() {
      try {
        const [statusRes, actRes] = await Promise.all([
          api.onboarding.getStatus().catch(() => null),
          api.onboarding.getActivation().catch(() => null),
        ]);
        if (isMounted) {
          if (statusRes) setStatus(statusRes);
          if (actRes) setActivation(actRes);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) setLoading(false);
      }
    }
    fetchProgress();
    return () => {
      isMounted = false;
    };
  }, []);

  if (dismissed || loading || !status) return null;

  // Once activated, render a compact activation badge or auto-collapse
  if (status.is_activated && status.progress_percentage >= 80) {
    return (
      <div className="bg-emerald-950/40 border border-emerald-800/60 rounded-2xl p-4 mb-6 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold font-mono text-emerald-400 uppercase tracking-wide">Workspace Activated</span>
              <span className="text-[11px] bg-emerald-900/60 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-700">
                Score: {status.activation_score}/100
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-0.5">
              Core CRM operations, AI property matching, and agent command center are operational.
            </p>
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          aria-label="Dismiss banner"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  const items = status.checklist || [];
  const completedCount = items.filter((i) => i.is_completed).length;
  const progressPct = status.progress_percentage || 0;

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 mb-6 shadow-xl relative backdrop-blur-sm text-slate-100">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 p-1 rounded-full hover:bg-slate-800 transition"
        aria-label="Dismiss checklist"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pr-6">
        <div>
          <div className="inline-flex items-center gap-1.5 bg-indigo-500/20 border border-indigo-500/40 px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono text-indigo-300 uppercase tracking-wider mb-1">
            <Sparkles className="w-3 h-3" />
            Workspace Setup Guide
          </div>
          <h2 className="text-base font-bold text-white font-mono">
            Complete your setup to reach 100% activation
          </h2>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <div className="text-xs font-mono font-bold text-indigo-400">{progressPct}% Complete</div>
            <div className="text-[10px] text-slate-400">{completedCount} of {items.length} tasks</div>
          </div>
          <div className="w-12 h-12 rounded-full border border-slate-700 flex items-center justify-center p-1 bg-slate-950">
            <div
              className="w-full h-full rounded-full flex items-center justify-center text-[10px] font-mono font-extrabold text-white"
              style={{ background: `conic-gradient(#6366F1 ${progressPct}%, #1E293B 0)` }}
            >
              <div className="w-8 h-8 rounded-full bg-slate-950 flex items-center justify-center">
                {progressPct}%
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {items.slice(0, 8).map((item) => (
          <div
            key={item.id}
            className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between ${
              item.is_completed
                ? 'bg-slate-950/40 border-slate-800 opacity-75'
                : 'bg-slate-950 border-slate-700/80 hover:border-indigo-500/50 shadow-md'
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-slate-400">
                  {item.is_completed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Circle className="w-4 h-4 text-slate-500" />
                  )}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">#{item.order}</span>
              </div>
              <h3 className={`text-xs font-bold mb-1 ${item.is_completed ? 'line-through text-slate-400' : 'text-white'}`}>
                {item.title}
              </h3>
              <p className="text-[11px] text-slate-400 leading-tight mb-3">{item.description}</p>
            </div>

            <a
              href={item.action_route}
              className={`w-full py-1.5 px-2.5 rounded-lg text-[11px] font-semibold transition text-center flex items-center justify-center gap-1 ${
                item.is_completed
                  ? 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs'
              }`}
            >
              <span>{item.action_label}</span>
              <ArrowRight className="w-3 h-3" />
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
