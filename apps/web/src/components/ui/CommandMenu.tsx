'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search, LayoutGrid, Users, CheckSquare, Settings, Globe, Plus, X,
  Building2, MessageSquare, Briefcase, Calendar, TrendingUp, Sparkles,
  ArrowRight, Clock, ShieldCheck, Tag, Loader2
} from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { api } from '@/lib/api-client';
import { CRMSearchResultItem } from '@/types/crm';

interface SearchGroup {
  type: string;
  label: string;
  items: Array<{
    id: string;
    title: string;
    subtitle?: string;
    badge?: string;
    badgeColor?: string;
    href: string;
    icon?: any;
    action?: () => void;
  }>;
}

export function openCommandMenu() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('wefylabs:open-command-palette'));
  }
}

export function CommandMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<CRMSearchResultItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const { openModal } = useRegion();

  // Listen for open events
  useEffect(() => {
    const handleOpenEvent = () => {
      setIsOpen(true);
      setQuery('');
      setSelectedIndex(0);
    };
    window.addEventListener('wefylabs:open-command-palette', handleOpenEvent);
    return () => window.removeEventListener('wefylabs:open-command-palette', handleOpenEvent);
  }, []);

  // Keyboard navigation & shortcuts
  useEffect(() => {
    let lastKey = '';
    let lastKeyTime = 0;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K to toggle
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
        return;
      }

      // Escape to close
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        setIsOpen(false);
        return;
      }

      const activeTag = document.activeElement?.tagName.toLowerCase();
      const isInputActive = activeTag === 'input' || activeTag === 'textarea' || (document.activeElement as HTMLElement)?.isContentEditable;

      // Single "/" to open search when not typing in an input
      if (e.key === '/' && !isInputActive && !isOpen) {
        e.preventDefault();
        setIsOpen(true);
        setQuery('');
        return;
      }

      // Two-key chord shortcuts (e.g. g then l for leads)
      if (!isInputActive && !isOpen) {
        const now = Date.now();
        const key = e.key.toLowerCase();

        if (lastKey === 'g' && now - lastKeyTime < 800) {
          if (key === 'l') { router.push('/dashboard/leads'); lastKey = ''; return; }
          if (key === 'i') { router.push('/dashboard/inbox'); lastKey = ''; return; }
          if (key === 'p') { router.push('/dashboard/deals'); lastKey = ''; return; }
          if (key === 't') { router.push('/dashboard/tasks'); lastKey = ''; return; }
          if (key === 'c') { router.push('/dashboard/calendar'); lastKey = ''; return; }
          if (key === 'r') { router.push('/dashboard/revenue-intelligence'); lastKey = ''; return; }
          if (key === 'h') { router.push('/dashboard'); lastKey = ''; return; }
        }

        lastKey = key;
        lastKeyTime = now;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, router]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Debounced search query
  useEffect(() => {
    if (!query.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await api.crm.search(query, 15);
        setSearchResults(res.results || []);
      } catch (e) {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query]);

  // Default Quick Navigation Commands
  const defaultCommands = [
    { id: 'cmd-home', title: 'Command Center (Home)', subtitle: 'Daily operational priorities & urgent items', href: '/dashboard', icon: LayoutGrid, badge: 'g + h' },
    { id: 'cmd-inbox', title: 'Omnichannel Inbox', subtitle: 'Web Chat, WhatsApp, Email, Call escalations', href: '/dashboard/inbox', icon: MessageSquare, badge: 'g + i' },
    { id: 'cmd-leads', title: 'Leads Directory', subtitle: 'Search, filter, and score buyer inquiries', href: '/dashboard/leads', icon: Users, badge: 'g + l' },
    { id: 'cmd-properties', title: 'Properties & Inventory', subtitle: 'Explore projects, availability, and unit matching', href: '/dashboard/properties', icon: Building2 },
    { id: 'cmd-deals', title: 'Sales Pipeline & Deals', subtitle: 'Track deal stages, bookings, and commissions', href: '/dashboard/deals', icon: Briefcase, badge: 'g + p' },
    { id: 'cmd-calendar', title: 'Calendar & Appointments', subtitle: 'Schedule site visits, viewings, and callbacks', href: '/dashboard/calendar', icon: Calendar, badge: 'g + c' },
    { id: 'cmd-tasks', title: 'Tasks & Follow-Ups', subtitle: 'Overdue SLAs, follow-up calls, and agenda items', href: '/dashboard/tasks', icon: CheckSquare, badge: 'g + t' },
    { id: 'cmd-revenue', title: 'Revenue Command Center', subtitle: 'Funnel analytics, attribution models, and leakage', href: '/dashboard/revenue-intelligence', icon: TrendingUp, badge: 'g + r' },
    { id: 'cmd-settings', title: 'Workspace Settings', subtitle: 'Team members, WhatsApp provider, and billing', href: '/dashboard/settings', icon: Settings },
    { id: 'cmd-market', title: 'Switch Operating Market', subtitle: 'Change region or operating country', action: () => { setIsOpen(false); openModal(); }, href: '#', icon: Globe },
    { id: 'cmd-simulator', title: 'WhatsApp AI Simulator', subtitle: 'Test automated buyer qualification loop', href: '/simulator', icon: Plus }
  ];

  // Grouped search results
  const groupedResults: SearchGroup[] = [];

  if (searchResults.length > 0) {
    const leads = searchResults.filter(r => r.entity_type === 'lead' || r.entity_type === 'customer');
    const properties = searchResults.filter(r => r.entity_type === 'property');
    const deals = searchResults.filter(r => r.entity_type === 'opportunity');
    const tasks = searchResults.filter(r => r.entity_type === 'task' || r.entity_type === 'appointment');
    const other = searchResults.filter(r => !['lead', 'customer', 'property', 'opportunity', 'task', 'appointment'].includes(r.entity_type as string));

    if (leads.length > 0) {
      groupedResults.push({
        type: 'lead',
        label: `Leads (${leads.length})`,
        items: leads.map(l => ({
          id: `lead-${l.id}`,
          title: l.title,
          subtitle: l.subtitle || 'Active Buyer',
          badge: l.status || 'Lead',
          badgeColor: 'bg-emerald-50 text-emerald-700 border-emerald-200',
          href: l.deep_link.startsWith('/dashboard/crm/customers') ? `/leads/${l.id}` : l.deep_link,
          icon: Users
        }))
      });
    }

    if (properties.length > 0) {
      groupedResults.push({
        type: 'property',
        label: `Properties (${properties.length})`,
        items: properties.map(p => ({
          id: `prop-${p.id}`,
          title: p.title,
          subtitle: p.subtitle || 'Available Inventory',
          badge: p.status || 'Unit',
          badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
          href: `/dashboard/properties?id=${p.id}`,
          icon: Building2
        }))
      });
    }

    if (deals.length > 0) {
      groupedResults.push({
        type: 'deal',
        label: `Deals & Pipeline (${deals.length})`,
        items: deals.map(d => ({
          id: `deal-${d.id}`,
          title: d.title,
          subtitle: d.subtitle || 'Commercial Opportunity',
          badge: d.status || 'Deal',
          badgeColor: 'bg-purple-50 text-purple-700 border-purple-200',
          href: `/dashboard/deals?id=${d.id}`,
          icon: Briefcase
        }))
      });
    }

    if (tasks.length > 0) {
      groupedResults.push({
        type: 'task',
        label: `Tasks (${tasks.length})`,
        items: tasks.map(t => ({
          id: `task-${t.id}`,
          title: t.title,
          subtitle: t.subtitle || 'Action Item',
          badge: t.status || 'Task',
          badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
          href: `/dashboard/tasks`,
          icon: CheckSquare
        }))
      });
    }

    if (other.length > 0) {
      groupedResults.push({
        type: 'other',
        label: `Other Results (${other.length})`,
        items: other.map(o => ({
          id: `other-${o.id}`,
          title: o.title,
          subtitle: o.subtitle,
          badge: o.entity_type,
          badgeColor: 'bg-zinc-100 text-zinc-700 border-zinc-200',
          href: o.deep_link,
          icon: Tag
        }))
      });
    }
  }

  // Flatten items for arrow key navigation
  const flatItems = query.trim() && groupedResults.length > 0
    ? groupedResults.flatMap(g => g.items)
    : defaultCommands.filter(c => !query.trim() || c.title.toLowerCase().includes(query.toLowerCase()) || c.subtitle.toLowerCase().includes(query.toLowerCase())).map(c => ({
        id: c.id,
        title: c.title,
        subtitle: c.subtitle,
        badge: c.badge,
        badgeColor: 'bg-zinc-100 text-zinc-600 border-zinc-200 font-mono',
        href: c.href,
        icon: c.icon,
        action: c.action
      }));

  const handleSelect = (item: (typeof flatItems)[0]) => {
    setIsOpen(false);
    if (item.action) {
      item.action();
    } else if (item.href && item.href !== '#') {
      router.push(item.href);
    }
  };

  const handleMenuKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, flatItems.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + flatItems.length) % Math.max(1, flatItems.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (flatItems[selectedIndex]) {
        handleSelect(flatItems[selectedIndex]);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-label="Universal Command Palette"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center p-4 pt-16 sm:pt-24"
      onClick={() => setIsOpen(false)}
    >
      <div
        className="w-full max-w-2xl bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[82vh]"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleMenuKeyDown}
      >
        {/* Search Input Bar */}
        <div className="p-3.5 border-b border-[#D4D0C8] flex items-center gap-2.5 bg-white shrink-0">
          {isSearching ? (
            <Loader2 className="w-4 h-4 text-teal-600 animate-spin shrink-0 ml-1" />
          ) : (
            <Search className="w-4 h-4 text-gray-400 shrink-0 ml-1" />
          )}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Search leads, properties, deals, tasks, or jump to workspace..."
            className="w-full bg-transparent text-sm font-medium text-[#1A1A1A] placeholder-gray-400 focus:outline-none"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); setSearchResults([]); inputRef.current?.focus(); }}
              className="text-xs text-gray-400 hover:text-gray-600 px-1"
            >
              Clear
            </button>
          )}
          <button
            onClick={() => setIsOpen(false)}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-md"
            aria-label="Close command palette"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results Container */}
        <div className="overflow-y-auto p-2 space-y-3 flex-1 scrollbar-thin">
          {query.trim() && groupedResults.length > 0 ? (
            groupedResults.map((group) => (
              <div key={group.type} className="space-y-1">
                <div className="px-2.5 py-1 text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider flex items-center justify-between">
                  <span>{group.label}</span>
                </div>
                {group.items.map((item) => {
                  const itemIndex = flatItems.findIndex(f => f.id === item.id);
                  const isSelected = itemIndex === selectedIndex;
                  const Icon = item.icon || Tag;

                  return (
                    <button
                      key={item.id}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelectedIndex(itemIndex)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-all group ${
                        isSelected
                          ? 'bg-[#1A1A1A] text-white shadow-xs'
                          : 'hover:bg-[#F0EDE8] text-[#1A1A1A]'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`p-1.5 rounded-lg shrink-0 ${isSelected ? 'bg-white/20 text-white' : 'bg-white border border-[#D4D0C8] text-gray-600'}`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold truncate leading-snug">
                            {item.title}
                          </div>
                          {item.subtitle && (
                            <div className={`text-[11px] truncate ${isSelected ? 'text-zinc-300' : 'text-gray-500'}`}>
                              {item.subtitle}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0 ml-3">
                        {item.badge && (
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${isSelected ? 'bg-white/20 text-white border-white/30' : item.badgeColor}`}>
                            {item.badge}
                          </span>
                        )}
                        <ArrowRight className={`w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity ${isSelected ? 'opacity-100 text-white' : 'text-gray-400'}`} />
                      </div>
                    </button>
                  );
                })}
              </div>
            ))
          ) : query.trim() && !isSearching && searchResults.length === 0 ? (
            <div className="p-8 text-center text-xs text-gray-500 font-sans">
              <Search className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="font-semibold text-gray-700">No matching records found</p>
              <p className="text-[11px] text-gray-400 mt-0.5">Try searching with a phone number, property name, or lead tag.</p>
            </div>
          ) : (
            /* Default Commands list */
            <div className="space-y-1">
              <div className="px-2.5 py-1 text-[10px] font-bold font-mono text-[#6B6B6B] uppercase tracking-wider">
                Workspaces & Operational Shortcuts
              </div>
              {flatItems.map((item, idx) => {
                const isSelected = idx === selectedIndex;
                const Icon = item.icon || LayoutGrid;

                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelect(item)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-all group ${
                      isSelected
                        ? 'bg-[#1A1A1A] text-white shadow-xs'
                        : 'hover:bg-[#F0EDE8] text-[#1A1A1A]'
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`p-1.5 rounded-lg shrink-0 ${isSelected ? 'bg-white/20 text-white' : 'bg-white border border-[#D4D0C8] text-gray-600'}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-xs font-semibold truncate leading-snug">
                          {item.title}
                        </div>
                        {item.subtitle && (
                          <div className={`text-[11px] truncate ${isSelected ? 'text-zinc-300' : 'text-gray-500'}`}>
                            {item.subtitle}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {item.badge && (
                        <kbd className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${isSelected ? 'bg-white/20 text-white border-white/30' : 'bg-[#F0EDE8] border-[#D4D0C8] text-gray-600'}`}>
                          {item.badge}
                        </kbd>
                      )}
                      <ArrowRight className={`w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity ${isSelected ? 'opacity-100 text-white' : 'text-gray-400'}`} />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer shortcuts info */}
        <div className="bg-[#F0EDE8] border-t border-[#D4D0C8] px-4 py-2 flex items-center justify-between text-[11px] font-mono text-gray-500 shrink-0">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1 py-0.5 bg-white border border-[#D4D0C8] rounded text-[9px]">↑</kbd> <kbd className="px-1 py-0.5 bg-white border border-[#D4D0C8] rounded text-[9px]">↓</kbd> Navigate</span>
            <span><kbd className="px-1.5 py-0.5 bg-white border border-[#D4D0C8] rounded text-[9px]">↵</kbd> Select</span>
            <span><kbd className="px-1.5 py-0.5 bg-white border border-[#D4D0C8] rounded text-[9px]">Esc</kbd> Exit</span>
          </div>
          <span className="hidden sm:inline text-[#0F766E] font-semibold">
            Tenant-Safe Universal Search
          </span>
        </div>
      </div>
    </div>
  );
}
