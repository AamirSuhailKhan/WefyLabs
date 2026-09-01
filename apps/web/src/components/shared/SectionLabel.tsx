'use client';

import React from 'react';

interface SectionLabelProps {
  text?: string;
  children?: React.ReactNode;
  variant?: 'default' | 'pill';
  className?: string;
  id?: string;
}

export default function SectionLabel({
  text,
  children,
  className = '',
  id,
}: SectionLabelProps) {
  const content = text || children;

  return (
    <div
      id={id}
      className={`inline-flex items-center justify-center mb-4 sm:mb-6 select-none ${className}`}
    >
      <span
        className="bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] rounded-full text-[13px] sm:text-[14px] md:text-[15px] font-bold uppercase tracking-[0.16em] px-4 sm:px-4.5 py-1.5 sm:py-2 leading-tight inline-flex items-center gap-2 shadow-2xs transition-all hover:bg-[#D4E894] hover:border-[#B0ACA4]"
        style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
      >
        {content}
      </span>
    </div>
  );
}
