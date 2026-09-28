'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UserPlus, Menu, X, LogOut, Settings, Clock, AlertTriangle,
  ChevronDown, CheckSquare, BookOpen, Sparkles, Building2,
  Users, Briefcase, BarChart3, Megaphone, ShieldCheck, Search,
  MessageSquare, Calendar, TrendingUp
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { useBroker } from '@/lib/auth-context';
import { WefyLabsLogo } from './WefyLabsLogo';
import { getEntitlementBadge, EntitlementState, DEFAULT_ENTITLEMENT_STATE } from '@/lib/entitlements';
import { openCommandMenu } from '@/components/ui/CommandMenu';

interface NavWorkspace {
  label: string;
  href: string;
  icon?: any;
  matchPrefixes?: string[];
  subItems?: { label: string; href: string }[];
}

const PRIMARY_WORKSPACES: NavWorkspace[] = [
  {
    label: 'Home',
    href: '/dashboard',
    matchPrefixes: ['/dashboard'],
  },
  {
    label: 'Inbox',
    href: '/dashboard/inbox',
    matchPrefixes: ['/dashboard/inbox'],
  },
  {
    label: 'Leads',
    href: '/dashboard/leads',
    matchPrefixes: ['/dashboard/leads', '/dashboard/lead-capture', '/dashboard/crm/leads'],
    subItems: [
      { label: 'Leads Directory', href: '/dashboard/leads' },
      { label: 'Lead Capture Hub', href: '/dashboard/lead-capture' },
      { label: 'Customer Activities', href: '/dashboard/crm/activities' },
    ],
  },
  {
    label: 'Properties',
    href: '/dashboard/properties',
    matchPrefixes: ['/dashboard/properties', '/dashboard/inventory', '/dashboard/matching'],
    subItems: [
      { label: 'Property Search & Detail', href: '/dashboard/properties' },
      { label: 'Supply & Unit Inventory', href: '/dashboard/inventory' },
      { label: 'AI Unit Matching', href: '/dashboard/matching' },
    ],
  },
  {
    label: 'Pipeline',
    href: '/dashboard/deals',
    matchPrefixes: ['/dashboard/deals', '/dashboard/pipeline', '/dashboard/crm/pipeline'],
    subItems: [
      { label: 'Commercial Deals & Bookings', href: '/dashboard/deals' },
      { label: 'Pipeline Kanban Board', href: '/dashboard/pipeline' },
    ],
  },
  {
    label: 'Tasks',
    href: '/dashboard/tasks',
    matchPrefixes: ['/dashboard/tasks', '/dashboard/crm/tasks'],
  },
  {
    label: 'Calendar',
    href: '/dashboard/calendar',
    matchPrefixes: ['/dashboard/calendar'],
  },
  {
    label: 'Revenue',
    href: '/dashboard/revenue-intelligence',
    matchPrefixes: ['/dashboard/revenue-intelligence', '/dashboard/analytics'],
    subItems: [
      { label: 'Revenue Command Center', href: '/dashboard/revenue-intelligence' },
      { label: 'Intelligence OS (Moat & Benchmarks)', href: '/dashboard/intelligence' },
      { label: 'Executive Analytics', href: '/dashboard/analytics' },
      { label: 'Predictive Propensity', href: '/dashboard/analytics/predictions' },
    ],
  },
  {
    label: 'Settings',
    href: '/dashboard/settings',
    matchPrefixes: ['/dashboard/settings'],
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
          <div className="flex items-center gap-2 shrink-0">
            {/* Universal Search Trigger */}
            <button
              onClick={() => openCommandMenu()}
              className="hidden md:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-[#D4D0C8] bg-white text-[#6B6B6B] hover:text-[#1A1A1A] hover:border-[#1A1A1A] text-xs transition-colors shadow-2xs cursor-pointer"
              title="Universal Search (⌘K / Ctrl+K)"
              aria-label="Universal Search"
            >
              <Search className="w-3.5 h-3.5 text-gray-500" />
              <span className="hidden xl:inline text-[11px] font-medium text-gray-600">Search CRM...</span>
              <kbd className="text-[9px] font-mono px-1 py-0.5 rounded bg-[#F0EDE8] border border-[#D4D0C8] text-gray-600 font-semibold">⌘K</kbd>
            </button>

            {/* AI Copilot Trigger */}
            <button
              onClick={() => {
                if (typeof window !== 'undefined') {
                  window.dispatchEvent(new CustomEvent('wefylabs:toggle-copilot'));
                }
              }}
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-teal-200 bg-teal-50/80 text-[#0F766E] hover:bg-teal-100 hover:border-teal-400 text-xs font-semibold transition-colors shadow-2xs cursor-pointer"
              title="AI Copilot"
              aria-label="Toggle AI Copilot"
            >
              <Sparkles className="w-3.5 h-3.5 text-teal-600 animate-pulse" />
              <span className="text-[11px]">AI Copilot</span>
            </button>

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
              {/* Mobile Quick Triggers: Search & AI Copilot */}
              <div className="grid grid-cols-2 gap-2 pb-2 mb-2 border-b border-[#D4D0C8]">
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    openCommandMenu();
                  }}
                  className="flex items-center justify-center gap-1.5 py-2 px-3 bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A]"
                >
                  <Search className="w-3.5 h-3.5 text-gray-500" />
                  <span>Search ⌘K</span>
                </button>
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    if (typeof window !== 'undefined') {
                      window.dispatchEvent(new CustomEvent('wefylabs:toggle-copilot'));
                    }
                  }}
                  className="flex items-center justify-center gap-1.5 py-2 px-3 bg-teal-50 border border-teal-200 rounded-xl text-xs font-semibold text-[#0F766E]"
                >
                  <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                  <span>AI Copilot</span>
                </button>
              </div>

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
