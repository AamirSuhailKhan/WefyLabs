import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrencyINR(amount?: number | null): string {
  if (!amount || amount === 0) return 'N/A';
  if (amount >= 10000000) {
    return `₹${(amount / 10000000).toFixed(2)} Cr`;
  } else if (amount >= 100000) {
    return `₹${(amount / 100000).toFixed(0)} Lakhs`;
  }
  return `₹${amount.toLocaleString('en-IN')}`;
}

export function formatTimeline(timeline?: string | null): string {
  if (!timeline) return 'Not specified';
  switch (timeline) {
    case 'immediate': return '⚡ Immediate (< 7 days)';
    case '1_month': return '📅 Within 1 Month';
    case '3_months': return '🗓️ 1 - 3 Months';
    case '6_months': return '⌛ 3 - 6 Months';
    case 'flexible': return '🛋️ Flexible';
    default: return timeline.replace('_', ' ');
  }
}

export function formatLoanStatus(loan?: string | null): string {
  if (!loan) return 'Unknown';
  switch (loan) {
    case 'pre_approved': return '✅ Pre-Approved';
    case 'in_process': return '⏳ In Process';
    case 'not_started': return '❌ Not Started';
    case 'not_needed': return '💰 Self-Funded / Cash';
    default: return loan.replace('_', ' ');
  }
}
