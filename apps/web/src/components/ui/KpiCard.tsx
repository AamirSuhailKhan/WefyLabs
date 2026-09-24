'use client';

import React from 'react';
import { LucideIcon } from 'lucide-react';
import { Skeleton } from './Skeleton';

interface KpiCardProps {
  label: string;
  value?: string | number | null;
  sublabel?: string;
  icon: LucideIcon;
  variant?: 'default' | 'lime' | 'brand' | 'warning' | 'danger';
  isLoading?: boolean;
  className?: string;
}

export function KpiCard({
  label,
  value,
  sublabel,
  icon: Icon,
  variant = 'default',
  isLoading = false,
  className = '',
}: KpiCardProps) {
  const iconVariants = {
    default: 'bg-[#FAF7F2] text-[#1A1A1A] border-[#D4D0C8]',
    lime: 'bg-[#E8F5A8] text-[#1A1A1A] border-[#D4D0C8]',
    brand: 'bg-[#EFF6FF] text-[#2C4BFB] border-[#BFDBFE]',
    warning: 'bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]',
    danger: 'bg-[#FEF2F2] text-[#B91C1C] border-[#FECACA]',
  };

  return (
    <div
      className={`bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-5 shadow-xs transition-all hover:border-[#B0ACA4] ${className}`}
    >
      <div className="flex items-center justify-between gap-3 mb-2">
        <span
          className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#6B6B6B]"
        >
          {label}
        </span>
        <div className={`p-2 rounded-xl border shrink-0 ${iconVariants[variant]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="mt-1">
        {isLoading ? (
          <Skeleton className="h-8 w-24 rounded-lg my-1" />
        ) : (
          <div
            className="text-2xl sm:text-3xl font-extrabold text-[#1A1A1A] tracking-tight tabular-nums"
            style={{ fontFamily: 'JetBrains Mono, monospace' }}
          >
            {value !== undefined && value !== null ? value : '—'}
          </div>
        )}

        {sublabel && (
          <p className="text-xs text-[#6B6B6B] font-sans mt-1">
            {sublabel}
          </p>
        )}
      </div>
    </div>
  );
}
