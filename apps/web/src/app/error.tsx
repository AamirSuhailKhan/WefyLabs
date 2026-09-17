'use client';

import React, { useEffect } from 'react';
import Link from 'next/link';
import { WefyLabsLogo } from '@/components/shared/WefyLabsLogo';
import { RefreshCw, Home } from 'lucide-react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[WefyLabs Application Error]', error);
  }, [error]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#F0EDE8] px-4 text-center">
      <div className="w-full max-w-md bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-8 sm:p-10 shadow-sm">
        <div className="flex justify-center mb-6">
          <WefyLabsLogo href="/" size="md" />
        </div>
        
        <span className="inline-block px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-red-100 text-red-700 border border-red-200 mb-4">
          Unexpected Error
        </span>
        
        <h1 className="text-2xl font-bold font-mono text-[#1A1A1A] tracking-tight mb-2">
          Something went wrong
        </h1>
        
        <p className="text-sm text-[#6B6B6B] leading-relaxed mb-8">
          An unexpected application error occurred. You can retry the operation or return to your dashboard.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => reset()}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-[#1A1A1A] text-white text-xs font-semibold hover:bg-black transition-colors cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
          <Link
            href="/dashboard"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-[#D4D0C8] text-[#1A1A1A] text-xs font-semibold hover:bg-[#F0EDE8] transition-colors"
          >
            <Home className="w-4 h-4" />
            Dashboard
          </Link>
        </div>
      </div>
      
      <p className="text-xs text-[#9A9A9A] font-mono mt-8">
        WefyLabs Enterprise Platform
      </p>
    </div>
  );
}
