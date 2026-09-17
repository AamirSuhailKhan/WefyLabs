'use client';

import Link from 'next/link';
import { WefyLabsLogo } from '@/components/shared/WefyLabsLogo';
import { ArrowLeft, Home } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#F0EDE8] px-4 text-center">
      <div className="w-full max-w-md bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-8 sm:p-10 shadow-sm">
        <div className="flex justify-center mb-6">
          <WefyLabsLogo href="/" size="md" />
        </div>
        
        <span className="inline-block px-3 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-wider bg-[#E8F5A8] text-[#1A1A1A] border border-[#D4D0C8] mb-4">
          404 — Page Not Found
        </span>
        
        <h1 className="text-2xl font-bold font-mono text-[#1A1A1A] tracking-tight mb-2">
          Lost in the Pipeline
        </h1>
        
        <p className="text-sm text-[#6B6B6B] leading-relaxed mb-8">
          The requested page or property record does not exist or has been moved.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/dashboard"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-[#1A1A1A] text-white text-xs font-semibold hover:bg-black transition-colors"
          >
            <Home className="w-4 h-4" />
            Go to Dashboard
          </Link>
          <Link
            href="/"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-[#D4D0C8] text-[#1A1A1A] text-xs font-semibold hover:bg-[#F0EDE8] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Home
          </Link>
        </div>
      </div>
      
      <p className="text-xs text-[#9A9A9A] font-mono mt-8">
        WefyLabs Enterprise Platform
      </p>
    </div>
  );
}
