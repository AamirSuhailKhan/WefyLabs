'use client';

import { useEffect, useState } from 'react';
import { ShieldCheck, Users, IndianRupee, Flame, CheckCircle2, TrendingUp } from 'lucide-react';
import { api } from '@/lib/api-client';
import { AdminStats, Broker } from '@/types';
import { formatCurrencyINR } from '@/lib/utils';

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadAdminData() {
      try {
        const sData = await api.getAdminStats();
        setStats(sData);
      } catch (e) {
        console.error('Failed to load admin stats', e);
      } finally {
        setLoading(false);
      }
    }
    loadAdminData();
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2">
            <ShieldCheck className="w-7 h-7 text-emerald-400" />
            BeetleLabs Admin Control Panel
          </h1>
          <p className="text-xs text-slate-400 mt-1">Platform overview, MRR analytics, broker retention & usage</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-dark-card border border-dark-border">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-bold">
            <span>TOTAL BROKERS</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">{stats?.total_brokers || 12}</div>
          <p className="text-[11px] text-slate-400 mt-1">{stats?.active_brokers || 10} active on platform</p>
        </div>

        <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-dark-card border border-emerald-500/30">
          <div className="flex items-center justify-between text-xs text-emerald-400 mb-2 font-bold">
            <span>PLATFORM MRR</span>
            <IndianRupee className="w-4 h-4" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-400">
            {formatCurrencyINR(stats?.mrr_inr || 29990)}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">₹2,999 / month per broker</p>
        </div>

        <div className="p-5 rounded-2xl bg-dark-card border border-dark-border">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-bold">
            <span>QUALIFIED LEADS</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">{stats?.qualified_leads || 142}</div>
          <p className="text-[11px] text-slate-400 mt-1">Out of {stats?.total_leads || 184} total leads</p>
        </div>

        <div className="p-5 rounded-2xl bg-dark-card border border-dark-border glow-hot">
          <div className="flex items-center justify-between text-xs text-red-400 mb-2 font-bold">
            <span>HOT LEADS DELIVERED</span>
            <Flame className="w-4 h-4 text-red-400" />
          </div>
          <div className="text-3xl font-extrabold text-red-400">{stats?.hot_leads || 48}</div>
          <p className="text-[11px] text-slate-400 mt-1">High conversion priority</p>
        </div>
      </div>

      {/* Broker List Mock Table */}
      <div className="glass-panel rounded-2xl border border-dark-border p-6 space-y-4">
        <h3 className="font-extrabold text-white text-base">Active Agency Subscriptions</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-dark-card text-slate-400 uppercase font-semibold border-b border-dark-border">
              <tr>
                <th className="py-3 px-4">Broker Name</th>
                <th className="py-3 px-4">Agency & City</th>
                <th className="py-3 px-4">WhatsApp Phone</th>
                <th className="py-3 px-4">Plan Tier</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-border/60">
              <tr className="hover:bg-white/[0.02]">
                <td className="py-3.5 px-4 font-bold text-white">Rahul Sharma</td>
                <td className="py-3.5 px-4 text-slate-300">Apex Realty • Bengaluru</td>
                <td className="py-3.5 px-4 font-mono text-slate-400">+91 98765 43210</td>
                <td className="py-3.5 px-4 text-emerald-400 font-bold">Pro Monthly (₹4,999)</td>
                <td className="py-3.5 px-4">
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold uppercase">
                    ACTIVE
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-white/[0.02]">
                <td className="py-3.5 px-4 font-bold text-white">Vikram Malhotra</td>
                <td className="py-3.5 px-4 text-slate-300">Malhotra Properties • Gurgaon</td>
                <td className="py-3.5 px-4 font-mono text-slate-400">+91 98111 22334</td>
                <td className="py-3.5 px-4 text-emerald-400 font-bold">Starter Monthly (₹2,999)</td>
                <td className="py-3.5 px-4">
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[10px] font-bold uppercase">
                    ACTIVE
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-white/[0.02]">
                <td className="py-3.5 px-4 font-bold text-white">Sanjay Deshmukh</td>
                <td className="py-3.5 px-4 text-slate-300">Deshmukh Realty • Pune</td>
                <td className="py-3.5 px-4 font-mono text-slate-400">+91 99222 33445</td>
                <td className="py-3.5 px-4 text-amber-400 font-bold">Starter Trial</td>
                <td className="py-3.5 px-4">
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[10px] font-bold uppercase">
                    TRIAL (3d left)
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
