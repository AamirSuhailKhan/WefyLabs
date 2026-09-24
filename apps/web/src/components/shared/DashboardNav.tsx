'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UserPlus, Menu, X, LogOut, Settings, Clock, AlertTriangle,
  ChevronDown, CheckSquare, BookOpen, Sparkles, Building2,
  Users, Briefcase, BarChart3, Megaphone, ShieldCheck
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { useBroker } from '@/lib/auth-context';
import { WefyLabsLogo } from './WefyLabsLogo';
import { getEntitlementBadge, EntitlementState, DEFAULT_ENTITLEMENT_STATE } from '@/lib/entitlements';

interface NavWorkspace {
  label: string;
  href: string;
  icon?: any;
  matchPrefixes?: string[];
  subItems?: { label: string; href: string }[];
}

const PRIMARY_WORKSPACES: NavWorkspace[] = [
  {
    label: 'Command Center',
    href: '/dashboard',
    matchPrefixes: ['/dashboard'],
  },
  {
    label: 'CRM',
    href: '/dashboard/crm',
    matchPrefixes: ['/dashboard/crm', '/dashboard/leads', '/dashboard/pipeline', '/dashboard/lead-capture'],
    subItems: [
      { label: 'Overview', href: '/dashboard/crm' },
      { label: 'Leads Directory', href: '/dashboard/leads' },
      { label: 'Pipeline Kanban', href: '/dashboard/pipeline' },
      { label: 'Lead Capture', href: '/dashboard/lead-capture' },
      { label: 'Activities', href: '/dashboard/crm/activities' },
    ],
  },
  {
    label: 'Deals',
    href: '/dashboard/deals',
    matchPrefixes: ['/dashboard/deals'],
  },
  {
    label: 'Inventory',
    href: '/dashboard/inventory',
    matchPrefixes: ['/dashboard/inventory', '/dashboard/matching'],
    subItems: [
      { label: 'Supply & Units', href: '/dashboard/inventory' },
      { label: 'Unit Matching', href: '/dashboard/matching' },
    ],
  },
  {
    label: 'Marketing',
    href: '/dashboard/marketing',
    matchPrefixes: ['/dashboard/marketing'],
    subItems: [
      { label: 'Campaigns', href: '/dashboard/marketing' },
      { label: 'Listing Studio', href: '/dashboard/marketing/listings' },
      { label: 'Project Launches', href: '/dashboard/marketing/launches' },
      { label: 'Landing Pages', href: '/dashboard/marketing/landing-pages' },
    ],
  },
  {
    label: 'Partners',
    href: '/dashboard/partners',
    matchPrefixes: ['/dashboard/partners'],
  },
  {
    label: 'Intelligence',
    href: '/dashboard/revenue-intelligence',
    matchPrefixes: ['/dashboard/revenue-intelligence', '/dashboard/analytics'],
    subItems: [
      { label: 'Revenue Funnel', href: '/dashboard/revenue-intelligence' },
      { label: 'Predictive AI', href: '/dashboard/analytics/predictions' },
    ],
  },
];

interface DashboardNavProps {
  onAddLead?: () => void;
}

export default function DashboardNav({ onAddLead }: DashboardNavProps) {
  const { broker, firstName, logout } = useBroker();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const [entitlement, setEntitlement] = useState<EntitlementState>(DEFAULT_ENTITLEMENT_STATE);
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 15);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    async function checkSubscription() {
      try {
        const res = await api.billing.getStatus();
        setEntitlement({
          status: (res.subscription_status as any) || 'trial',
          plan: 'starter',
          trialDaysRemaining: res.trial_days_remaining ?? 7,
          trialEndsAt: res.trial_ends_at,
        });
      } catch (e) {
        setEntitlement(DEFAULT_ENTITLEMENT_STATE);
      }
    }
    checkSubscription();
  }, []);

  const badge = getEntitlementBadge(entitlement);

  const isWorkspaceActive = (ws: NavWorkspace) => {
    if (ws.href === '/dashboard') {
      return pathname === '/dashboard';
    }
    if (ws.matchPrefixes) {
      return ws.matchPrefixes.some((prefix) => pathname.startsWith(prefix));
    }
    return pathname.startsWith(ws.href);
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-40 flex flex-col">
      {/* Top Banner (Only if Expired, strictly integrated in flow without mt-8 offset) */}
      {badge.isExpired && (
        <div className="bg-[#B91C1C] text-white px-4 py-1.5 text-center text-xs font-semibold flex items-center justify-center gap-2 select-none shadow-xs">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>Your Free Trial has expired. Existing data is preserved in Read-Only mode.</span>
          <Link
            href="/dashboard/settings"
            className="underline font-bold hover:text-red-100 ml-1.5"
          >
            Upgrade Plan →
          </Link>
        </div>
      )}

      {/* Main Navigation Bar */}
      <nav
        className={`h-16 transition-all duration-200 ${
          scrolled
            ? 'bg-[rgba(240,237,232,0.96)] backdrop-blur-xl border-b border-[#D4D0C8] shadow-xs'
            : 'bg-[rgba(240,237,232,0.88)] backdrop-blur-md border-b border-[#D4D0C8]'
        }`}
      >
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-full flex items-center justify-between gap-4">
          {/* Left: Brand Logo & Product Badge */}
          <div className="flex items-center gap-3.5 shrink-0">
            <WefyLabsLogo href="/dashboard" iconSize={24} textSize="text-lg" />
            <div className="hidden xl:block h-4 w-px bg-[#D4D0C8]" />
            <span
              className="hidden xl:inline-block text-[10px] font-mono font-bold uppercase tracking-widest text-[#6B6B6B]"
            >
              Revenue OS
            </span>
          </div>

          {/* Center: Primary Workspaces */}
          <div className="hidden lg:flex items-center gap-1">
            {PRIMARY_WORKSPACES.map((ws) => {
              const active = isWorkspaceActive(ws);
              const hasSub = ws.subItems && ws.subItems.length > 0;

              return (
                <div
                  key={ws.label}
                  className="relative"
                  onMouseEnter={() => hasSub && setActiveDropdown(ws.label)}
                  onMouseLeave={() => hasSub && setActiveDropdown(null)}
                >
                  <Link
                    href={ws.href}
                    className={`relative px-3 py-1.5 rounded-xl text-xs sm:text-[13px] font-semibold flex items-center gap-1 transition-all duration-150 ${
                      active
                        ? 'text-white'
                        : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#FAF7F2]'
                    }`}
                    style={{ fontFamily: 'Inter, sans-serif' }}
                  >
                    {active && (
                      <motion.div
                        layoutId="activeWorkspaceTab"
                        className="absolute inset-0 bg-[#1A1A1A] rounded-xl -z-0 shadow-xs"
                        transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                      />
                    )}
                    <span className="relative z-10">{ws.label}</span>
                    {hasSub && (
                      <ChevronDown
                        className={`relative z-10 w-3 h-3 transition-transform ${
                          active ? 'text-zinc-300' : 'text-zinc-400'
                        } ${activeDropdown === ws.label ? 'rotate-180' : ''}`}
                      />
                    )}
                  </Link>

                  {/* Dropdown Menu for Sub-items */}
                  {hasSub && activeDropdown === ws.label && (
                    <div className="absolute top-full left-0 pt-1.5 z-50 min-w-[180px]">
                      <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-1.5 shadow-lg space-y-0.5">
                        {ws.subItems!.map((sub) => {
                          const subActive = pathname === sub.href;
                          return (
                            <Link
                              key={sub.label}
                              href={sub.href}
                              className={`block px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                subActive
                                  ? 'bg-[#1A1A1A] text-white font-semibold'
                                  : 'text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A]'
                              }`}
                            >
                              {sub.label}
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Right: Actions, Entitlement & Profile */}
          <div className="flex items-center gap-2.5 shrink-0">
            {/* Entitlement Status Pill */}
            {badge.variant === 'success' ? (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                {badge.label}
              </span>
            ) : badge.variant === 'danger' ? (
              <Link
                href="/dashboard/settings"
                className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[#FEF2F2] text-[#991B1B] border border-[#FECACA] hover:bg-red-100 transition-colors"
              >
                <Clock className="w-3 h-3 text-[#DC2626]" />
                <span>{badge.label}</span>
              </Link>
            ) : (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A]">
                <Clock className="w-3 h-3 text-[#D97706]" />
                {badge.label}
              </span>
            )}

            {/* Quick Action Button (+ Lead) */}
            {onAddLead && (
              <button
                onClick={onAddLead}
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D4D0C8] bg-[#FAF7F2] text-[#1A1A1A] text-xs font-semibold hover:bg-[#E8F5A8] transition-colors shadow-2xs cursor-pointer"
              >
                <UserPlus className="w-3.5 h-3.5 text-[#1A1A1A]" />
                <span>Add Lead</span>
              </button>
            )}

            {/* User Profile Menu */}
            <div
              className="relative"
              onMouseLeave={() => setProfileOpen(false)}
            >
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="h-8 px-2.5 rounded-full bg-[#FAF7F2] border border-[#D4D0C8] flex items-center gap-1.5 text-[#1A1A1A] text-xs font-bold shrink-0 hover:border-[#1A1A1A] transition-all cursor-pointer select-none shadow-2xs max-w-[140px]"
                title={broker?.name ? `Signed in as ${broker.name}` : `Signed in as ${firstName}`}
              >
                <span className="w-2 h-2 rounded-full bg-[#10B981] shrink-0" />
                <span className="truncate">{firstName}</span>
              </button>

              {profileOpen && (
                <div className="absolute right-0 top-full pt-1.5 z-50">
                  <div className="w-56 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-1.5 shadow-xl">
                    <div className="px-3 py-2 border-b border-[#E5E1DA] mb-1">
                      <p className="text-xs font-bold text-[#1A1A1A] truncate">
                        {broker?.name || 'Real Estate Broker'}
                      </p>
                      <p className="text-[10px] text-[#6B6B6B] font-mono truncate">
                        {broker?.email || 'broker@wefylabs.com'}
                      </p>
                      {broker?.agency_name && (
                        <p className="text-[10px] text-[#0F766E] font-medium truncate mt-0.5">
                          {broker.agency_name}
                        </p>
                      )}
                    </div>
                    <Link
                      href="/dashboard/tasks"
                      onClick={() => setProfileOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A] rounded-xl transition-colors"
                    >
                      <CheckSquare className="w-3.5 h-3.5" />
                      Tasks & Follow-ups
                    </Link>
                    <Link
                      href="/knowledge"
                      onClick={() => setProfileOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A] rounded-xl transition-colors"
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      Knowledge Base
                    </Link>
                    <Link
                      href="/dashboard/settings"
                      onClick={() => setProfileOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A] rounded-xl transition-colors"
                    >
                      <Settings className="w-3.5 h-3.5" />
                      Settings & Billing
                    </Link>
                    <div className="pt-1 mt-1 border-t border-[#E5E1DA]">
                      <button
                        onClick={() => {
                          setProfileOpen(false);
                          logout();
                          window.location.href = '/login';
                        }}
                        className="w-full text-left flex items-center gap-2 px-3 py-2 text-xs font-semibold text-[#991B1B] hover:bg-[#FEF2F2] rounded-xl transition-colors cursor-pointer"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        Sign out
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Mobile Hamburger Toggle */}
            <button
              className="lg:hidden p-2 text-[#1A1A1A] hover:bg-[#FAF7F2] rounded-xl border border-transparent hover:border-[#D4D0C8] transition-colors"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle mobile menu"
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile Slide-down Drawer */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="lg:hidden bg-[#FAF7F2] border-b border-[#D4D0C8] px-4 py-3 space-y-1 shadow-lg max-h-[80vh] overflow-y-auto"
            >
              {PRIMARY_WORKSPACES.map((ws) => {
                const active = isWorkspaceActive(ws);
                return (
                  <div key={ws.label} className="space-y-1">
                    <Link
                      href={ws.href}
                      onClick={() => setMobileOpen(false)}
                      className={`block px-3 py-2 rounded-xl text-xs font-bold transition-colors ${
                        active
                          ? 'bg-[#1A1A1A] text-white'
                          : 'text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A]'
                      }`}
                    >
                      {ws.label}
                    </Link>
                    {ws.subItems && (
                      <div className="pl-4 space-y-0.5 pb-1">
                        {ws.subItems.map((sub) => (
                          <Link
                            key={sub.label}
                            href={sub.href}
                            onClick={() => setMobileOpen(false)}
                            className="block px-2.5 py-1.5 rounded-lg text-[11px] text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]"
                          >
                            • {sub.label}
                          </Link>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="pt-2 border-t border-[#D4D0C8] flex items-center justify-between">
                <span className="text-xs font-mono font-semibold text-[#6B6B6B]">
                  {badge.label}
                </span>
                <Link
                  href="/dashboard/settings"
                  onClick={() => setMobileOpen(false)}
                  className="text-xs font-semibold text-[#2C4BFB] underline"
                >
                  Settings
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>
    </header>
  );
}
