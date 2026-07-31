'use client';

import React from 'react';
import { Sparkles, Trophy, Award, Zap, ArrowRight, UserCheck, CheckCircle2 } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

interface LeaderboardItem {
  rank: number;
  broker_name: string;
  office_name: string;
  revenue_closed: number;
  deals_count: number;
}

interface Props {
  leaderboard?: LeaderboardItem[];
}

export function BrokerCoachingWidget({
  leaderboard = [
    { rank: 1, broker_name: 'Tariq Al-Mansoor', office_name: 'Dubai Marina Hub', revenue_closed: 4200000, deals_count: 7 },
    { rank: 2, broker_name: 'Aamir Khan (You)', office_name: 'Downtown Dubai Branch', revenue_closed: 2850000, deals_count: 4 },
    { rank: 3, broker_name: 'Rahul Sharma', office_name: 'Gurgaon DLF Office', revenue_closed: 2400000, deals_count: 5 },
    { rank: 4, broker_name: 'Sarah Jenkins', office_name: 'London Mayfair Branch', revenue_closed: 1950000, deals_count: 3 }
  ]
}: Props) {
  const { region } = useRegion();

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Trophy className="w-4 h-4 text-amber-500 fill-amber-300" />
          <span>Regional Broker Leaderboard (Q3 2026)</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          Rank #2 Regional
        </span>
      </div>

      {/* Leaderboard Table */}
      <div className="space-y-2">
        {leaderboard.map((item) => {
          const isYou = item.broker_name.includes('You');
          return (
            <div
              key={item.rank}
              className={`p-3 rounded-xl border flex items-center justify-between transition-colors ${
                isYou
                  ? 'bg-[#1A1A1A] text-white border-black shadow-xs'
                  : 'bg-white text-[#1A1A1A] border-[#D4D0C8]'
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`w-6 h-6 rounded-full font-mono text-xs font-extrabold flex items-center justify-center ${
                    item.rank === 1
                      ? 'bg-amber-400 text-amber-950'
                      : isYou
                      ? 'bg-[#E8F5A8] text-[#1A1A1A]'
                      : 'bg-gray-100 text-gray-700'
                  }`}
                >
                  #{item.rank}
                </span>
                <div>
                  <h4 className="text-xs font-bold font-mono">{item.broker_name}</h4>
                  <p className={`text-[10px] font-sans ${isYou ? 'text-gray-300' : 'text-gray-500'}`}>
                    {item.office_name} • {item.deals_count} Deals
                  </p>
                </div>
              </div>

              <span className="text-xs font-extrabold font-mono">
                {formatCurrency(item.revenue_closed, region)}
              </span>
            </div>
          );
        })}
      </div>

      {/* AI Coaching Skill Gap Card */}
      <div className="bg-indigo-50 border border-indigo-200 p-3 rounded-xl space-y-1.5">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-indigo-950">
          <Sparkles className="w-3.5 h-3.5 text-indigo-600 fill-indigo-200" />
          <span>AI Coaching Priority: Improve Response Speed</span>
        </div>
        <p className="text-xs text-indigo-900 font-sans leading-relaxed">
          Your WhatsApp response time for Dubai Marina inquiries averages 4.2 mins. Reducing to under 2 mins increases lead conversion by 34%.
        </p>
      </div>
    </div>
  );
}
