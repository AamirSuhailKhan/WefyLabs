'use client';

import React, { useState } from 'react';
import { CheckCircle2, Circle, Globe, MessageSquare, Plus, UserPlus, X, Sparkles } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { FlagIcon } from '../shared/FlagIcon';

export function OnboardingChecklist() {
  const { region, openModal } = useRegion();
  const [dismissed, setDismissed] = useState(false);
  const [completedSteps, setCompletedSteps] = useState<number[]>([1]); // Step 1 completed by default

  if (dismissed) return null;

  const steps = [
    {
      id: 1,
      title: `Set operating region (${region.name})`,
      desc: `Configured in ${region.currency} for ${region.name}`,
      icon: Globe,
      action: openModal,
      actionLabel: 'Change',
    },
    {
      id: 2,
      title: 'Forward your first WhatsApp lead',
      desc: 'Send a phone number to your AI WhatsApp bot',
      icon: MessageSquare,
      action: () => (window.location.href = '/simulator'),
      actionLabel: 'Test Simulator',
    },
    {
      id: 3,
      title: 'Add a manual lead or note',
      desc: 'Add lead details directly into your dashboard',
      icon: Plus,
      action: () => (window.location.href = '/dashboard/leads'),
      actionLabel: 'Go to Leads',
    },
    {
      id: 4,
      title: 'Invite a team member',
      desc: 'Add assistant or co-broker to your workspace',
      icon: UserPlus,
      action: () => (window.location.href = '/dashboard/settings'),
      actionLabel: 'Invite',
    },
  ];

  const progressPct = Math.round((completedSteps.length / steps.length) * 100);

  const toggleStep = (id: number) => {
    if (completedSteps.includes(id)) {
      setCompletedSteps(completedSteps.filter((s) => s !== id));
    } else {
      setCompletedSteps([...completedSteps, id]);
    }
  };

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-5 mb-6 shadow-xs relative">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 p-1 rounded-full hover:bg-[#F0EDE8] transition-colors"
        aria-label="Dismiss checklist"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pr-6">
        <div>
          <div className="inline-flex items-center gap-1.5 bg-[#E8F5A8] border border-[#D4D0C8] px-2.5 py-0.5 rounded-full text-[10px] font-bold font-mono text-[#1A1A1A] uppercase tracking-wider mb-1">
            <Sparkles className="w-3 h-3" />
            Quick Setup Checklist
          </div>
          <h2 className="text-base font-bold text-[#1A1A1A] font-mono">
            Welcome to BeetleLabs! Let's get your CRM ready.
          </h2>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <div className="text-xs font-mono font-bold text-[#1A1A1A]">{progressPct}% Complete</div>
            <div className="text-[10px] text-[#6B6B6B]">{completedSteps.length} of {steps.length} tasks</div>
          </div>
          <div className="w-12 h-12 rounded-full border-2 border-[#D4D0C8] flex items-center justify-center p-1 bg-white">
            <div
              className="w-full h-full rounded-full bg-[#E8F5A8] flex items-center justify-center text-xs font-mono font-extrabold text-[#1A1A1A]"
              style={{ background: `conic-gradient(#1A1A1A ${progressPct}%, #E8F5A8 0)` }}
            >
              <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center text-[11px]">
                {progressPct}%
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {steps.map((step) => {
          const isDone = completedSteps.includes(step.id);
          return (
            <div
              key={step.id}
              className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between ${
                isDone
                  ? 'bg-white/80 border-[#D4D0C8] opacity-85'
                  : 'bg-white border-[#D4D0C8] shadow-2xs hover:border-gray-400'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <button onClick={() => toggleStep(step.id)} className="text-[#1A1A1A] hover:opacity-80 transition-opacity">
                    {isDone ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 fill-emerald-100" />
                    ) : (
                      <Circle className="w-4 h-4 text-gray-400" />
                    )}
                  </button>
                  {step.id === 1 && (
                    <FlagIcon code={region.code} className="w-4 h-3 rounded-[2px] shadow-2xs border border-black/10 inline-block" />
                  )}
                </div>
                <h3 className={`text-xs font-bold font-mono mb-1 ${isDone ? 'line-through text-gray-500' : 'text-[#1A1A1A]'}`}>
                  {step.title}
                </h3>
                <p className="text-[11px] text-[#6B6B6B] leading-tight font-sans mb-3">{step.desc}</p>
              </div>

              <button
                onClick={step.action}
                className="w-full py-1 px-2 bg-[#F0EDE8] hover:bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] rounded-lg text-[10px] font-bold font-mono transition-colors text-center"
              >
                {step.actionLabel} →
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
