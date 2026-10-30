'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  UserPlus, Menu, X, LogOut, Settings, Clock, AlertTriangle,
  ChevronDown, CheckSquare, BookOpen, Sparkles, Building2,
  Users, Briefcase, BarChart3, Megaphone, ShieldCheck, Search,
  MessageSquare, Calendar, TrendingUp, MoreHorizontal
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { useBroker } from '@/lib/auth-context';
import { WefyLabsLogo } from './WefyLabsLogo';
import { getEntitlementBadge, EntitlementState, DEFAULT_ENTITLEMENT_STATE } from '@/lib/entitlements';
import { openCommandMenu } from '@/components/ui/CommandMenu';

export interface NavWorkspace {
  label: string;
  href: string;
  icon?: any;
  matchPrefixes?: string[];
  subItems?: { label: string; href: string }[];
}

export const PRIMARY_WORKSPACES: NavWorkspace[] = [
  {
    label: 'Command Center',
    href: '/dashboard',
    matchPrefixes: ['/dashboard'],
    subItems: [
      { label: 'Overview', href: '/dashboard' },
      { label: 'Tasks & Follow-Ups', href: '/dashboard/tasks' },
    ],
  },
  {
    label: 'Leads & Inbox',
    href: '/dashboard/leads',
    matchPrefixes: ['/dashboard/leads', '/dashboard/inbox', '/dashboard/lead-capture', '/dashboard/crm/leads', '/leads', '/dashboard/crm/activities'],
    subItems: [
      { label: 'Leads Directory', href: '/dashboard/leads' },
      { label: 'WhatsApp Inbox', href: '/dashboard/inbox' },
      { label: 'Lead Capture Hub', href: '/dashboard/lead-capture' },
      { label: 'Customer Activities', href: '/dashboard/crm/activities' },
    ],
  },
  {
    label: 'Properties',
    href: '/dashboard/properties',
    matchPrefixes: ['/dashboard/properties', '/dashboard/inventory', '/dashboard/matching'],
    subItems: [
      { label: 'Property Catalog & Search', href: '/dashboard/properties' },
      { label: 'AI Property Matching', href: '/dashboard/matching' },
      { label: 'Supply & Unit Inventory', href: '/dashboard/inventory' },
    ],
  },
  {
    label: 'Site Visits',
    href: '/dashboard/calendar',
    matchPrefixes: ['/dashboard/calendar', '/dashboard/deals', '/dashboard/pipeline', '/dashboard/crm/pipeline'],
    subItems: [
      { label: 'Site Visits & Calendar', href: '/dashboard/calendar' },
      { label: 'Commercial Deals & Bookings', href: '/dashboard/deals' },
      { label: 'Pipeline Kanban Board', href: '/dashboard/pipeline' },
    ],
  },
  {
    label: 'Settings & Billing',
    href: '/dashboard/settings',
    matchPrefixes: ['/dashboard/settings', '/settings', '/dashboard/revenue-intelligence'],
    subItems: [
      { label: 'Workspace & Billing Settings', href: '/dashboard/settings' },
      { label: 'Revenue Command Center', href: '/dashboard/revenue-intelligence' },
    ],
  },
];

// The core 5 workspaces always visible across desktop viewports
const COMPACT_CORE_WORKSPACES = PRIMARY_WORKSPACES;
const COMPACT_MORE_WORKSPACES: NavWorkspace[] = [];

interface DashboardNavProps {
  onAddLead?: () => void;
}

export default function DashboardNav({ onAddLead }: DashboardNavProps) {
  const { broker, firstName, logout } = useBroker();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [moreDropdownOpen, setMoreDropdownOpen] = useState(false);
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

  const handleAddLeadClick = () => {
    if (onAddLead) {
      onAddLead();
    } else if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('wefylabs:open-add-lead'));
    }
  };

  const isMoreActive = COMPACT_MORE_WORKSPACES.some((ws) => isWorkspaceActive(ws));

  return (
    <header className="sticky top-0 left-0 right-0 z-40 flex flex-col w-full shrink-0 shadow-2xs">
      {/* Top Banner (Only if Expired, strictly integrated in flow) */}
      {badge.isExpired && (
        <div className="bg-[#B91C1C] text-white px-4 py-1.5 text-center text-xs font-semibold flex items-center justify-center gap-2 select-none shadow-xs w-full shrink-0">
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
        className={`h-16 w-full transition-all duration-200 ${
          scrolled
            ? 'bg-[rgba(240,237,232,0.98)] backdrop-blur-xl border-b border-[#D4D0C8] shadow-xs'
            : 'bg-[rgba(240,237,232,0.92)] backdrop-blur-md border-b border-[#D4D0C8]'
        }`}
      >
        <div className="max-w-[1440px] mx-auto px-3 sm:px-6 h-full flex items-center justify-between gap-2 sm:gap-4">
          {/* Left: Brand Logo & Product Badge */}
          <div className="flex items-center gap-2.5 sm:gap-3.5 shrink-0">
            <WefyLabsLogo href="/dashboard" iconSize={24} textSize="text-base sm:text-lg" />
            <div className="hidden 2xl:block h-4 w-px bg-[#D4D0C8]" />
            <span
              className="hidden 2xl:inline-block text-[10px] font-mono font-bold uppercase tracking-widest text-[#6B6B6B]"
            >
              Revenue OS
            </span>
          </div>

          {/* Center: Full Workspaces on 2XL / XL */}
          <div className="hidden xl:flex items-center gap-1 shrink-0">
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
                    className={`relative px-2.5 2xl:px-3 py-1.5 rounded-xl text-xs sm:text-[13px] font-semibold flex items-center gap-1 transition-all duration-150 select-none ${
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
                    <div className="absolute top-full left-0 pt-1.5 z-50 min-w-[200px]">
                      <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-1.5 shadow-lg space-y-0.5 animate-in fade-in-50 zoom-in-95 duration-100">
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

          {/* Center: Compact Workspaces on Medium Screens (LG: 1024px to 1279px) */}
          <div className="hidden lg:flex xl:hidden items-center gap-0.5 shrink-0">
            {COMPACT_CORE_WORKSPACES.map((ws) => {
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
                    className={`relative px-2 py-1 rounded-lg text-xs font-semibold flex items-center gap-0.5 transition-all select-none ${
                      active
                        ? 'bg-[#1A1A1A] text-white'
                        : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#FAF7F2]'
                    }`}
                  >
                    <span>{ws.label}</span>
                    {hasSub && <ChevronDown className="w-2.5 h-2.5 opacity-60" />}
                  </Link>

                  {hasSub && activeDropdown === ws.label && (
                    <div className="absolute top-full left-0 pt-1.5 z-50 min-w-[190px]">
                      <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-1.5 shadow-lg space-y-0.5">
                        {ws.subItems!.map((sub) => (
                          <Link
                            key={sub.label}
                            href={sub.href}
                            className={`block px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                              pathname === sub.href
                                ? 'bg-[#1A1A1A] text-white font-semibold'
                                : 'text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A]'
                            }`}
                          >
                            {sub.label}
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* "More" Dropdown for remaining workspaces (only rendered if extra workspaces exist) */}
            {COMPACT_MORE_WORKSPACES.length > 0 && (
              <div
                className="relative"
                onMouseEnter={() => setMoreDropdownOpen(true)}
                onMouseLeave={() => setMoreDropdownOpen(false)}
              >
                <button
                  className={`px-2 py-1 rounded-lg text-xs font-semibold flex items-center gap-1 transition-all ${
                    isMoreActive
                      ? 'bg-[#1A1A1A] text-white'
                      : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#FAF7F2]'
                  }`}
                >
                  <span>More</span>
                  <ChevronDown className="w-3 h-3 opacity-60" />
                </button>

                {moreDropdownOpen && (
                  <div className="absolute top-full right-0 pt-1.5 z-50 min-w-[210px]">
                    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-1.5 shadow-lg space-y-1">
                      {COMPACT_MORE_WORKSPACES.map((ws) => {
                        const active = isWorkspaceActive(ws);
                        return (
                          <div key={ws.label}>
                            <Link
                              href={ws.href}
                              className={`block px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                                active
                                  ? 'bg-[#1A1A1A] text-white font-semibold'
                                  : 'text-[#4A4A4A] hover:bg-[#F0EDE8] hover:text-[#1A1A1A]'
                              }`}
                            >
                              {ws.label}
                            </Link>
                            {ws.subItems && (
                              <div className="pl-3 py-0.5 space-y-0.5 border-l border-[#D4D0C8] ml-2 mt-0.5">
                                {ws.subItems.map((sub) => (
                                  <Link
                                    key={sub.label}
                                    href={sub.href}
                                    className="block px-2 py-1 text-[11px] text-[#6B6B6B] hover:text-[#1A1A1A] rounded"
                                  >
                                    {sub.label}
                                  </Link>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: Actions, Entitlement & Profile */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            {/* Universal Search Trigger */}
            <button
              onClick={() => openCommandMenu()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-[#D4D0C8] bg-white text-[#6B6B6B] hover:text-[#1A1A1A] hover:border-[#1A1A1A] text-xs transition-colors shadow-2xs cursor-pointer"
              title="Universal Search (⌘K / Ctrl+K)"
              aria-label="Universal Search"
            >
              <Search className="w-3.5 h-3.5 text-gray-600 shrink-0" />
              <span className="hidden xl:inline text-[11px] font-medium text-gray-700">Search CRM...</span>
              <kbd className="hidden sm:inline text-[9px] font-mono px-1 py-0.5 rounded bg-[#F0EDE8] border border-[#D4D0C8] text-gray-600 font-semibold">⌘K</kbd>
            </button>

            {/* AI Copilot Trigger */}
            <button
              onClick={() => {
                if (typeof window !== 'undefined') {
                  window.dispatchEvent(new CustomEvent('wefylabs:toggle-copilot'));
                }
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-teal-200 bg-teal-50/80 text-[#0F766E] hover:bg-teal-100 hover:border-teal-400 text-xs font-semibold transition-colors shadow-2xs cursor-pointer shrink-0"
              title="Toggle AI Copilot"
              aria-label="Toggle AI Copilot"
            >
              <Sparkles className="w-3.5 h-3.5 text-teal-600 animate-pulse shrink-0" />
              <span className="hidden md:inline text-[11px]">AI Copilot</span>
            </button>

            {/* Entitlement Status Pill */}
            {badge.variant === 'success' ? (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0] shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
                <span className="hidden xl:inline">{badge.label}</span>
              </span>
            ) : badge.variant === 'danger' ? (
              <Link
                href="/dashboard/settings"
                className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[#FEF2F2] text-[#991B1B] border border-[#FECACA] hover:bg-red-100 transition-colors shrink-0"
                title={badge.label}
              >
                <Clock className="w-3 h-3 text-[#DC2626] shrink-0" />
                <span className="hidden lg:inline">{badge.label}</span>
              </Link>
            ) : (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A] shrink-0">
                <Clock className="w-3 h-3 text-[#D97706] shrink-0" />
                <span className="hidden lg:inline">{badge.label}</span>
              </span>
            )}

            {/* Quick Action Button (+ Lead) */}
            <button
              onClick={handleAddLeadClick}
              className="hidden sm:flex items-center gap-1.5 px-2.5 2xl:px-3 py-1.5 rounded-xl border border-[#D4D0C8] bg-[#FAF7F2] text-[#1A1A1A] text-xs font-semibold hover:bg-[#E8F5A8] transition-colors shadow-2xs cursor-pointer shrink-0"
              title="Add New Lead"
              aria-label="Add New Lead"
            >
              <UserPlus className="w-3.5 h-3.5 text-[#1A1A1A] shrink-0" />
              <span className="hidden md:inline">Add Lead</span>
            </button>

            {/* User Profile Menu */}
            <div
              className="relative shrink-0"
              onMouseLeave={() => setProfileOpen(false)}
            >
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="h-8 px-2 sm:px-2.5 rounded-full bg-[#FAF7F2] border border-[#D4D0C8] flex items-center gap-1.5 text-[#1A1A1A] text-xs font-bold shrink-0 hover:border-[#1A1A1A] transition-all cursor-pointer select-none shadow-2xs max-w-[130px]"
                title={broker?.name ? `Signed in as ${broker.name}` : `Signed in as ${firstName}`}
                aria-label="User Account Menu"
              >
                <span className="w-2 h-2 rounded-full bg-[#10B981] shrink-0" />
                <span className="truncate">{firstName || 'Broker'}</span>
              </button>

              {profileOpen && (
                <div className="absolute right-0 top-full pt-1.5 z-50">
                  <div className="w-56 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-1.5 shadow-xl animate-in fade-in-50 zoom-in-95 duration-100">
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
                        onClick={async () => {
                          setProfileOpen(false);
                          await logout();
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

            {/* Mobile Hamburger Toggle (Visible on < 1024px) */}
            <button
              className="lg:hidden p-1.5 sm:p-2 text-[#1A1A1A] hover:bg-[#FAF7F2] rounded-xl border border-transparent hover:border-[#D4D0C8] transition-colors shrink-0"
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
              className="lg:hidden bg-[#FAF7F2] border-b border-[#D4D0C8] px-4 py-3 space-y-1 shadow-lg max-h-[85vh] overflow-y-auto"
            >
              {/* Mobile Quick Triggers: Search, AI Copilot, + Add Lead */}
              <div className="grid grid-cols-3 gap-2 pb-2 mb-2 border-b border-[#D4D0C8]">
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    openCommandMenu();
                  }}
                  className="flex items-center justify-center gap-1 py-2 px-2 bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A]"
                >
                  <Search className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                  <span>Search</span>
                </button>
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    if (typeof window !== 'undefined') {
                      window.dispatchEvent(new CustomEvent('wefylabs:toggle-copilot'));
                    }
                  }}
                  className="flex items-center justify-center gap-1 py-2 px-2 bg-teal-50 border border-teal-200 rounded-xl text-xs font-semibold text-[#0F766E]"
                >
                  <Sparkles className="w-3.5 h-3.5 text-teal-600 shrink-0" />
                  <span>Copilot</span>
                </button>
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    handleAddLeadClick();
                  }}
                  className="flex items-center justify-center gap-1 py-2 px-2 bg-[#E8F5A8] border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A]"
                >
                  <UserPlus className="w-3.5 h-3.5 shrink-0" />
                  <span>+ Lead</span>
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
                  Settings & Billing
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>
    </header>
  );
}
