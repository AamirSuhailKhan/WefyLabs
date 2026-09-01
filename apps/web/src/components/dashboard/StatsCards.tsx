'use client';

import { motion } from 'framer-motion';
import { Users, Flame, CheckCircle2, TrendingUp } from 'lucide-react';
import { Lead } from '@/types';
import { formatCurrencyINR } from '@/lib/utils';
import { CountUpNumber } from '@/components/animations/CountUpNumber';

interface StatsCardsProps {
  leads: Lead[];
}

export default function StatsCards({ leads }: StatsCardsProps) {
  const totalLeads = leads.length;
  const hotLeads = leads.filter((l) => l.score === 'hot').length;
  const warmLeads = leads.filter((l) => l.score === 'warm').length;
  const qualifiedCount = leads.filter((l) => l.status === 'qualified' || l.status === 'converted').length;
  const qualRate = totalLeads > 0 ? Math.round((qualifiedCount / totalLeads) * 100) : 0;

  const totalPipelineValue = leads
    .filter((l) => l.score === 'hot' || l.score === 'warm')
    .reduce((acc, l) => acc + (l.budget_max || l.budget_min || 0), 0);

  // Compute trend from real timestamps
  const now = new Date();
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const fourteenDaysAgo = new Date(now.getTime() - 14 * 24 * 60 * 60 * 1000);

  const leadsThisWeek = leads.filter((l) => l.created_at && new Date(l.created_at) >= sevenDaysAgo).length;
  const leadsLastWeek = leads.filter(
    (l) => l.created_at && new Date(l.created_at) >= fourteenDaysAgo && new Date(l.created_at) < sevenDaysAgo
  ).length;

  let trendSub = '--';
  if (totalLeads > 0 && (leadsThisWeek > 0 || leadsLastWeek > 0)) {
    if (leadsLastWeek === 0) {
      trendSub = `+${leadsThisWeek} new this week`;
    } else {
      const diffPct = Math.round(((leadsThisWeek - leadsLastWeek) / leadsLastWeek) * 100);
      trendSub = `${diffPct >= 0 ? '+' : ''}${diffPct}% this week`;
    }
  }

  const stats = [
    {
      label: 'TOTAL FORWARDED LEADS',
      rawNum: totalLeads,
      suffix: '',
      prefix: '',
      sub: trendSub,
      icon: Users,
      iconBg: '#CCFBF1',
      iconColor: '#0D9488',
    },
    {
      label: 'HOT LEADS (READY NOW)',
      rawNum: hotLeads,
      suffix: '',
      prefix: '',
      sub: `${warmLeads} warm leads in pipeline`,
      icon: Flame,
      iconBg: '#FEF3C7',
      iconColor: '#B45309',
    },
    {
      label: 'AI QUALIFICATION RATE',
      rawNum: qualRate,
      suffix: '%',
      prefix: '',
      sub: totalLeads > 0 ? `${qualifiedCount} of ${totalLeads} auto-qualified` : 'No leads to qualify',
      icon: CheckCircle2,
      iconBg: '#CCFBF1',
      iconColor: '#0D9488',
    },
    {
      label: 'QUALIFIED PIPELINE BUDGET',
      displayVal: totalPipelineValue > 0 ? formatCurrencyINR(totalPipelineValue) : '₹0',
      sub: 'Combined hot/warm budget',
      icon: TrendingUp,
      iconBg: '#DCFCE7',
      iconColor: '#15803D',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat, idx) => {
        const Icon = stat.icon;
        return (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: idx * 0.08, ease: [0.16, 1, 0.3, 1] }}
            whileHover={{ y: -4 }}
            className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-5 hover:border-[#B0ACA4] transition-colors"
          >
            {/* Label + Icon */}
            <div className="flex items-start justify-between mb-4">
              <span
                className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] leading-tight max-w-[140px]"
                style={{ fontFamily: 'JetBrains Mono, monospace' }}
              >
                {stat.label}
              </span>
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ml-2"
                style={{ backgroundColor: stat.iconBg }}
              >
                <Icon className="w-4 h-4" style={{ color: stat.iconColor }} />
              </div>
            </div>

            {/* Big Number */}
            <div
              className="text-[36px] font-extrabold text-[#1A1A1A] tracking-tight leading-none mb-2"
              style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
            >
              {stat.rawNum !== undefined ? (
                <CountUpNumber end={stat.rawNum} prefix={stat.prefix} suffix={stat.suffix} />
              ) : (
                stat.displayVal
              )}
            </div>

            {/* Subtext */}
            <p className="text-[12px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
              {stat.sub}
            </p>
          </motion.div>
        );
      })}
    </div>
  );
}
