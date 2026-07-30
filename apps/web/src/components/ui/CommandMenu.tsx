'use client';

import React, { useState, useEffect } from 'react';
import { Search, LayoutGrid, Users, CheckSquare, Settings, Globe, Plus, X } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';

export function CommandMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const { openModal } = useRegion();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  const actions = [
    { label: 'Go to Pipeline Board', href: '/dashboard/pipeline', icon: LayoutGrid },
    { label: 'View Leads Table', href: '/dashboard/leads', icon: Users },
    { label: 'View Tasks', href: '/dashboard/tasks', icon: CheckSquare },
    { label: 'Open Settings', href: '/dashboard/settings', icon: Settings },
    { label: 'Change Country / Market', action: () => { setIsOpen(false); openModal(); }, icon: Globe },
    { label: 'Run WhatsApp AI Simulator', href: '/simulator', icon: Plus },
  ];

  const filteredActions = actions.filter((a) =>
    a.label.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center p-4 pt-20 sm:pt-28">
      <div className="w-full max-w-xl bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        <div className="p-3 border-b border-[#D4D0C8] flex items-center gap-2 bg-white">
          <Search className="w-4 h-4 text-gray-400 shrink-0 ml-1" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or search leads... (Press Esc to exit)"
            className="w-full bg-transparent text-sm text-[#1A1A1A] placeholder-gray-400 focus:outline-none font-sans"
          />
          <button
            onClick={() => setIsOpen(false)}
            className="p-1 text-gray-400 hover:text-gray-600 rounded-md"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="max-h-72 overflow-y-auto p-2 space-y-1">
          <div className="px-2 py-1 text-[10px] font-bold font-mono text-gray-400 uppercase tracking-wider">
            Quick Navigation & Actions
          </div>
          {filteredActions.length > 0 ? (
            filteredActions.map((item, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setIsOpen(false);
                  if (item.action) {
                    item.action();
                  } else if (item.href) {
                    window.location.href = item.href;
                  }
                }}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold text-[#1A1A1A] hover:bg-[#E8F5A8] transition-colors text-left group"
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className="w-4 h-4 text-gray-600 group-hover:text-[#1A1A1A]" />
                  <span>{item.label}</span>
                </div>
                <span className="text-[10px] font-mono text-gray-400 group-hover:text-[#1A1A1A]">
                  ↵ Jump
                </span>
              </button>
            ))
          ) : (
            <div className="p-6 text-center text-xs text-gray-500 font-sans">
              No matching actions found for "{query}".
            </div>
          )}
        </div>

        <div className="bg-[#F0EDE8] border-t border-[#D4D0C8] px-4 py-2 flex items-center justify-between text-[10px] font-mono text-gray-500">
          <span>Navigation Shortcut</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-white border border-[#D4D0C8] rounded text-[9px]">Cmd+K</kbd> / <kbd className="px-1.5 py-0.5 bg-white border border-[#D4D0C8] rounded text-[9px]">Ctrl+K</kbd>
          </span>
        </div>
      </div>
    </div>
  );
}
