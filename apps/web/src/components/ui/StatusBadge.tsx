'use client';

import React from 'react';

export type RealEstateStatus =
  | 'available' | 'active' | 'published' | 'closed_won' | 'verified' | 'ready'
  | 'reserved' | 'in_review' | 'pending' | 'under_offer' | 'scheduled'
  | 'booked' | 'approved' | 'qualified'
  | 'sold'
  | 'blocked' | 'cancelled' | 'closed_lost' | 'stale' | 'rejected'
  | 'draft' | 'paused' | 'unpublished' | 'archived'
  | string;

interface StatusBadgeProps {
  status: RealEstateStatus;
  label?: string;
  size?: 'sm' | 'md';
  showDot?: boolean;
}

export function StatusBadge({
  status,
  label,
  size = 'sm',
  showDot = true,
}: StatusBadgeProps) {
  const norm = (status || '').toLowerCase().trim();

  let styles = 'bg-[#F0EDE8] text-[#6B6B6B] border-[#D4D0C8]';
  let dotColor = 'bg-[#6B6B6B]';
  let pulse = false;

  // SUCCESS STATES (Available, Active, Published, Won)
  if (['available', 'active', 'published', 'closed_won', 'verified', 'ready'].includes(norm)) {
    styles = 'bg-[#ECFDF5] text-[#065F46] border-[#A7F3D0]';
    dotColor = 'bg-[#10B981]';
  }
  // WARNING STATES (Reserved, In Review, Under Offer, Pending)
  else if (['reserved', 'in_review', 'pending', 'under_offer', 'scheduled'].includes(norm)) {
    styles = 'bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]';
    dotColor = 'bg-[#F59E0B]';
    pulse = true;
  }
  // INFO / APPROVED STATES (Booked, Approved, Qualified)
  else if (['booked', 'approved', 'qualified'].includes(norm)) {
    styles = 'bg-[#EFF6FF] text-[#1E40AF] border-[#BFDBFE]';
    dotColor = 'bg-[#2C4BFB]';
  }
  // SOLD / COMPLETED
  else if (['sold', 'completed'].includes(norm)) {
    styles = 'bg-[#F5F3FF] text-[#5B21B6] border-[#DDD6FE]';
    dotColor = 'bg-[#7C3AED]';
  }
  // DANGER / TERMINAL BLOCKED (Blocked, Cancelled, Lost, Stale)
  else if (['blocked', 'cancelled', 'closed_lost', 'stale', 'rejected'].includes(norm)) {
    styles = 'bg-[#FEF2F2] text-[#991B1B] border-[#FECACA]';
    dotColor = 'bg-[#EF4444]';
  }
  // NEUTRAL (Draft, Paused, Archived)
  else if (['draft', 'paused', 'unpublished', 'archived'].includes(norm)) {
    styles = 'bg-[#F5F0EB] text-[#6B6B6B] border-[#D4D0C8]';
    dotColor = 'bg-[#9CA3AF]';
  }

  const displayLabel = label || norm.replace(/_/g, ' ').toUpperCase();
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-mono font-bold uppercase tracking-wider border select-none ${styles} ${sizeClasses}`}
    >
      {showDot && (
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor} ${
            pulse ? 'animate-pulse' : ''
          }`}
        />
      )}
      <span>{displayLabel}</span>
    </span>
  );
}
