'use client';

import React from 'react';
import { AlertCircle, ArrowRight, ShieldAlert } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface DemoBannerProps {
  isDemo?: boolean;
}

export function DemoBanner({ isDemo }: DemoBannerProps) {
  const router = useRouter();

  if (!isDemo) return null;

  return (
    <div className="bg-gradient-to-r from-amber-950/80 via-amber-900/60 to-amber-950/80 border-b border-amber-700/50 text-amber-200 px-4 py-2.5 shadow-md">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5">
          <div className="h-6 w-6 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center shrink-0">
            <ShieldAlert className="w-3.5 h-3.5" />
          </div>
          <div>
            <span className="font-bold uppercase tracking-wider text-amber-300 mr-2">Demo Mode Active:</span>
            <span>All properties, leads, and match scores are synthetic simulations. External emails & payments are disabled.</span>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => router.push('/onboarding')}
            className="px-3 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg transition text-xs flex items-center gap-1 shadow-xs"
          >
            <span>Create Real Workspace</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
