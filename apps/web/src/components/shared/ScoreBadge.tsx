'use client';

import { Flame, Sun, Snowflake, Ban, Clock } from 'lucide-react';
import { ScoreType } from '@/types';

interface ScoreBadgeProps {
  score?: ScoreType | string;
  confidence?: number;
  showConfidence?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export default function ScoreBadge({ score = 'pending', confidence, showConfidence = false, size = 'md' }: ScoreBadgeProps) {
  const normalizedScore = (score || 'pending').toLowerCase();

  const configs = {
    hot: {
      label: 'HOT LEAD',
      bg: 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]',
      icon: Flame,
    },
    warm: {
      label: 'WARM LEAD',
      bg: 'bg-[#FEF9C3] text-[#854D0E] border-[#FEF08A]',
      icon: Sun,
    },
    cold: {
      label: 'COLD LEAD',
      bg: 'bg-[#E0E7FF] text-[#4338CA] border-[#C7D2FE]',
      icon: Snowflake,
    },
    spam: {
      label: 'SPAM / FAKE',
      bg: 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]',
      icon: Ban,
    },
    pending: {
      label: 'QUALIFYING...',
      bg: 'bg-[#F5F0EB] text-[#6B6B6B] border-[#D4D0C8]',
      icon: Clock,
    },
  };

  const config = configs[normalizedScore as keyof typeof configs] || configs.pending;
  const Icon = config.icon;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-[11px] gap-1 font-bold',
    md: 'px-2.5 py-1 text-xs gap-1.5 font-bold',
    lg: 'px-3.5 py-1.5 text-xs gap-2 font-black',
  };

  return (
    <div className={`inline-flex items-center rounded-full border ${config.bg} ${sizeClasses[size]} tracking-wide uppercase`}>
      <Icon className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />
      <span>{config.label}</span>
      {showConfidence && confidence !== undefined && confidence > 0 && (
        <span className="opacity-70 text-[10px] font-medium border-l border-current pl-1.5 ml-0.5">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}
