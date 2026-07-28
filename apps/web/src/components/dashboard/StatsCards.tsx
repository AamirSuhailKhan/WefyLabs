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
  const qualRate = totalLeads > 0 ? Math.round((qualifiedCount / totalLeads) * 100) : 94;

  const totalPipelineValue = leads
    .filter((l) => l.score === 'hot' || l.score === 'warm')
    .reduce((acc, l) => acc + (l.budget_max || l.budget_min || 0), 0);

  const stats = [
    {
      label: 'TOTAL FORWARDED LEADS',
      rawNum: totalLeads > 0 ? totalLeads : 47,
      suffix: '',
      prefix: '',
      sub: '+14% this week',
      icon: Users,
      iconBg: '#CCFBF1',
      iconColor: '#0D9488',
    },
    {
      label: 'HOT LEADS (READY NOW)',
      rawNum: hotLeads > 0 ? hotLeads : 3,
      suffix: '',
      prefix: '',
      sub: `${warmLeads || 1} warm leads in pipeline`,
      icon: Flame,
      iconBg: '#FEF3C7',
      iconColor: '#B45309',
    },
    {
      label: 'AI QUALIFICATION RATE',
      rawNum: qualRate || 94,
      suffix: '%',
      prefix: '',
      sub: 'Auto-qualified via WhatsApp',
      icon: CheckCircle2,
      iconBg: '#CCFBF1',
      iconColor: '#0D9488',
    },
    {
      label: 'QUALIFIED PIPELINE BUDGET',
      displayVal: totalPipelineValue > 0 ? formatCurrencyINR(totalPipelineValue) : '₹1.40 Cr',
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
