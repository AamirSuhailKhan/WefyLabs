'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, ChevronDown, Check } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { REGIONS, RegionCode } from '@/lib/i18n/regions';
import { FlagIcon } from './FlagIcon';

export default function RegionSwitcher() {
  const { regionCode, region, setRegion, openModal } = useRegion();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        aria-label="Select Region"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 border border-gray-300 bg-white rounded-lg px-2.5 py-1.5 text-xs font-semibold text-gray-800 hover:bg-gray-50 transition-colors shadow-sm"
      >
        <FlagIcon code={region.code} className="w-4 h-3 rounded-[2px] shadow-2xs border border-black/10 shrink-0" />
        <span className="font-mono uppercase">{region.code}</span>
        <span className="text-gray-500 font-sans hidden sm:inline">({region.currency})</span>
        <ChevronDown className={`w-3.5 h-3.5 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 mt-2 w-56 bg-white border border-gray-200 rounded-xl shadow-xl p-1.5 z-50 overflow-hidden"
          >
            <div className="px-2 py-1.5 text-[10px] font-bold font-mono text-gray-400 uppercase tracking-wider border-b border-gray-100 mb-1">
              Select Market / Region
            </div>
            <div className="space-y-0.5 max-h-64 overflow-y-auto">
              {(Object.keys(REGIONS) as RegionCode[]).map((code) => {
                const item = REGIONS[code];
                const isActive = code === regionCode;
                return (
                  <button
                    key={code}
                    onClick={() => {
                      setRegion(code);
                      setIsOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-medium text-left transition-colors ${
                      isActive
                        ? 'bg-[#d4f5a4]/30 text-gray-900 font-bold'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <FlagIcon code={code} className="w-5 h-3.5 rounded-[2px] shadow-xs border border-black/10 shrink-0" />
                      <div>
                        <div className="font-semibold text-gray-900">{item.name}</div>
                        <div className="text-[10px] text-gray-500 font-mono">
                          {item.currency} ({item.currencySymbol.trim()})
                        </div>
                      </div>
                    </div>
                    {isActive && <Check className="w-3.5 h-3.5 text-emerald-600" />}
                  </button>
                );
              })}
            </div>

            <div className="pt-1.5 mt-1 border-t border-gray-100">
              <button
                onClick={() => {
                  setIsOpen(false);
                  openModal();
                }}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-2 bg-gray-50 hover:bg-[#d4f5a4]/40 text-gray-900 rounded-lg text-[11px] font-semibold transition-colors"
              >
                <Globe className="w-3.5 h-3.5 text-gray-700" />
                <span>Browse All Markets →</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
