'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { UserPlus, Menu, X, LogOut, Settings, Clock, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api-client';
import { BeetleLabsLogo } from './BeetleLabsLogo';

const NAV_LINKS = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Leads', href: '/dashboard/leads' },
  { label: 'Pipeline', href: '/dashboard/pipeline' },
  { label: 'Tasks', href: '/dashboard/tasks' },
  { label: 'Settings', href: '/dashboard/settings' },
];

interface DashboardNavProps {
  onAddLead?: () => void;
}

export default function DashboardNav({ onAddLead }: DashboardNavProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [trialDays, setTrialDays] = useState<number | null>(7);
  const [subStatus, setSubStatus] = useState<string>('trial');
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    async function checkSubscription() {
      try {
        const res = await api.billing.getStatus();
        setTrialDays(res.trial_days_remaining ?? 7);
        setSubStatus(res.subscription_status || 'trial');
      } catch (e) {
        // Fallback default for demo
        setTrialDays(7);
      }
    }
    checkSubscription();
  }, []);

  const isActive = (href: string) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    return pathname.startsWith(href);
  };

  return (
    <>
      {/* Expired Trial Blocking Banner */}
      {subStatus === 'expired' || (trialDays !== null && trialDays <= 0 && subStatus !== 'active') ? (
        <div className="bg-red-600 text-white px-4 py-2 text-center text-xs font-semibold flex items-center justify-center gap-2 fixed top-0 left-0 right-0 z-50">
          <AlertTriangle className="w-4 h-4" />
          <span>Your 7-Day Free Trial has expired. Upgrade your plan to continue qualifying leads.</span>
          <Link href="/dashboard/settings" className="underline font-bold hover:text-red-100 ml-2">
            Upgrade Now →
          </Link>
        </div>
      ) : null}

      <nav className={`fixed top-0 left-0 right-0 h-16 transition-all duration-300 z-40 ${
        (subStatus === 'expired' || (trialDays !== null && trialDays <= 0 && subStatus !== 'active')) ? 'mt-8' : ''
      } ${
        scrolled
          ? 'bg-[rgba(240,237,232,0.95)] backdrop-blur-xl border-b border-[#D4D0C8] shadow-sm'
          : 'bg-[rgba(240,237,232,0.85)] backdrop-blur-md border-b border-[#D4D0C8]'
      }`}>
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-full flex items-center justify-between gap-4">

          {/* Left: Logo & Context */}
          <div className="flex items-center gap-4 shrink-0">
            <BeetleLabsLogo href="/" iconSize={24} textSize="text-lg" />

            <div className="hidden sm:block h-5 w-px bg-[#D4D0C8]" />

            <div className="hidden sm:flex items-center gap-2">
              <span
                className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]"
                style={{ fontFamily: 'JetBrains Mono, monospace' }}
              >
                Broker Dashboard
              </span>

              {subStatus === 'active' ? (
                <span className="bg-[#CCFBF1] text-[#0F766E] text-[10px] font-bold px-2.5 py-0.5 rounded-full border border-[#99F6E4]">
                  Pro Active
                </span>
              ) : (
                <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border flex items-center gap-1 ${
                  trialDays && trialDays < 3
                    ? 'bg-red-100 text-red-700 border-red-200'
                    : 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]'
                }`}>
                  <Clock className="w-3 h-3" />
                  {trialDays !== null && trialDays > 0 ? `${trialDays} Days Trial Left` : 'Trial Expired'}
                </span>
              )}
            </div>
          </div>

          {/* Center: Nav Tabs */}
          <div className="hidden lg:flex items-center gap-1">
            {NAV_LINKS.map((link) => {
              const active = isActive(link.href);
              return (
                <Link
                  key={link.label}
                  href={link.href}
                  className={`relative px-3.5 py-1.5 rounded-lg text-sm transition-colors ${
                    active ? 'text-white font-semibold' : 'text-[#6B6B6B] font-medium hover:text-[#1A1A1A]'
                  }`}
                  style={{ fontFamily: 'Inter, sans-serif' }}
                >
                  {active && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-[#1A1A1A] rounded-lg -z-0"
                      transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                    />
                  )}
                  <span className="relative z-10">{link.label}</span>
                </Link>
              );
            })}
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-3 shrink-0">
            {onAddLead && (
              <button
                onClick={onAddLead}
                className="hidden sm:flex items-center gap-1.5 px-3 py-2 rounded-lg border border-[#D4D0C8] bg-transparent text-[#1A1A1A] text-[12px] font-semibold hover:bg-[#FAF7F2] transition-colors"
              >
                <UserPlus className="w-3.5 h-3.5" />
                Add Lead
              </button>
            )}

            <div className="relative group">
              <button className="w-8 h-8 rounded-full bg-[#E8F5A8] border border-[#D4D0C8] flex items-center justify-center text-[#1A1A1A] text-[11px] font-extrabold shrink-0 hover:ring-2 hover:ring-[#D4D0C8] transition-all">
                RS
              </button>
              <div className="absolute right-0 top-10 hidden group-hover:block w-44 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl py-1 z-50 shadow-sm">
                <Link
                  href="/dashboard/settings"
                  className="flex items-center gap-2.5 px-3 py-2 text-xs text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A] transition-colors"
                >
                  <Settings className="w-3.5 h-3.5" />
                  Settings
                </Link>
                <button
                  onClick={() => {
                    api.auth.logout();
                    window.location.href = '/login';
                  }}
                  className="w-full text-left flex items-center gap-2.5 px-3 py-2 text-xs text-[#B45309] hover:bg-[#FEF3C7] transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign out
                </button>
              </div>
            </div>

            <button
              className="lg:hidden p-2 text-[#1A1A1A]"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileOpen && (
          <div className="lg:hidden bg-[#FAF7F2] border-b border-[#D4D0C8] px-5 py-4 space-y-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.label}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className={`block px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive(link.href)
                    ? 'bg-[#1A1A1A] text-white'
                    : 'text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A]'
                }`}
              >
                {link.label}
              </Link>
            ))}
            <div className="pt-2 border-t border-[#D4D0C8]">
              {onAddLead && (
                <button
                  onClick={() => { setMobileOpen(false); onAddLead(); }}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-[#E8F5A8] text-[#1A1A1A] text-sm font-semibold"
                >
                  <UserPlus className="w-4 h-4" /> Add Lead
                </button>
              )}
            </div>
          </div>
        )}
      </nav>
    </>
  );
}
