'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRegion } from '@/lib/i18n/region-context';
import { REGIONS, RegionCode } from '@/lib/i18n/regions';
import { Globe, X, Check, Sparkles } from 'lucide-react';
import { FlagIcon } from '@/components/shared/FlagIcon';

const MARKET_METADATA: Record<RegionCode, { platform: string; agentTerm: string; desc: string }> = {
  IN: { platform: 'Housing / Ads', agentTerm: 'Real Estate Brokers', desc: 'Pre-set defaults in ₹ INR with WhatsApp 360dialog' },
  AE: { platform: 'Property Finder', agentTerm: 'Dubai Brokers', desc: 'Pre-set defaults in AED with expat lead qualification' },
  GB: { platform: 'Rightmove / Zoopla', agentTerm: 'Estate Agents', desc: 'Pre-set defaults in £ GBP with Twilio WhatsApp' },
  SG: { platform: 'PropertyGuru', agentTerm: 'CEA Property Agents', desc: 'Pre-set defaults in S$ SGD with HDB/Private logic' },
  US: { platform: 'Zillow / Realtor', agentTerm: 'Real Estate Agents', desc: 'Pre-set defaults in $ USD with Twilio WhatsApp' },
  AU: { platform: 'REA Group / Domain', agentTerm: 'Sales & Rental Agents', desc: 'Pre-set defaults in A$ AUD with Twilio WhatsApp' },
  CA: { platform: 'Realtor.ca', agentTerm: 'Realtors & Agents', desc: 'Pre-set defaults in C$ CAD with Twilio WhatsApp' },
};

export default function MarketSelector() {
  const { region, regionCode, setRegion, isModalOpen, openModal, closeModal } = useRegion();
  const [dismissedBanner, setDismissedBanner] = useState(false);

  const handleSelectCountry = (code: RegionCode) => {
    setRegion(code);
    closeModal();
  };

  return (
    <>
      {/* ─── TOP ANNOUNCEMENT BANNER ─────────────────────────────────── */}
      {!dismissedBanner && (
        <div className="bg-white border-b border-gray-200 py-2 px-4 text-xs font-sans relative z-30">
          <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 text-gray-700">
              <FlagIcon code={regionCode} className="w-4 h-3 rounded-[2px] shadow-2xs border border-black/10 shrink-0" />
              <span className="font-medium">
                BeetleLabs is active in <strong className="text-gray-900 font-semibold">{region.name}</strong>.
              </span>
              <span className="hidden md:inline text-gray-500">
                Localized in {region.currency} ({region.currencySymbol.trim()}) for {MARKET_METADATA[regionCode].agentTerm}.
              </span>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <button
                onClick={openModal}
                className="flex items-center gap-1.5 bg-[#FAF7F2] border border-[#D4D0C8] text-gray-900 font-semibold text-[11px] px-3 py-1 rounded-full hover:bg-[#E8F5A8] transition-colors"
              >
                <Globe className="w-3.5 h-3.5" />
                <span>Select Country</span>
                <span className="font-mono text-gray-500">({region.code})</span>
              </button>

              <button
                onClick={() => setDismissedBanner(true)}
                className="text-gray-400 hover:text-gray-600 p-0.5 rounded"
                aria-label="Dismiss banner"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── INTERACTIVE COUNTRY SELECTION MODAL ──────────────────────── */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm p-4 sm:p-6 flex flex-col items-center justify-start sm:justify-center min-h-full">
            {/* Modal Box */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="relative w-full max-w-3xl bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-5 sm:p-7 shadow-2xl z-10 space-y-5 overflow-hidden my-auto"
            >
              {/* Decorative top bar */}
              <div className="absolute top-0 left-0 right-0 h-1.5 bg-[#d4f5a4]" />

              {/* Close Button */}
              <button
                onClick={closeModal}
                className="absolute top-5 right-5 p-2 rounded-full text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 transition-colors"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>

              {/* Header */}
              <div className="space-y-2 pr-8">
                <div className="inline-flex items-center gap-2 bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] font-mono text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider">
                  <Sparkles className="w-3 h-3 text-[#1A1A1A]" />
                  Global Localization Engine
                </div>
                <h2 className="text-2xl sm:text-3xl font-bold font-mono text-gray-900 tracking-tight">
                  Select Your Market / Country
                </h2>
                <p className="text-xs sm:text-sm text-gray-600 font-sans leading-relaxed">
                  Choose your operating country below. BeetleLabs will automatically adapt lead qualification metrics, currencies, pricing plans, and ad platform defaults specifically for your region.
                </p>
              </div>

              {/* Countries Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 max-h-[52vh] overflow-y-auto p-1 pr-2 no-scrollbar">
                {(Object.keys(REGIONS) as RegionCode[]).map((code) => {
                  const item = REGIONS[code];
                  const meta = MARKET_METADATA[code];
                  const isSelected = code === regionCode;

                  return (
                    <motion.button
                      key={code}
                      whileHover={{ scale: 1.02, y: -2 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => handleSelectCountry(code)}
                      className={`relative flex flex-col justify-between p-4 rounded-2xl text-left border transition-all ${
                        isSelected
                          ? 'bg-white border-2 border-gray-900 shadow-md ring-2 ring-[#d4f5a4]'
                          : 'bg-white border-gray-200 hover:border-gray-400 shadow-sm'
                      }`}
                    >
                      {/* Active Checkmark Pill */}
                      {isSelected && (
                        <span className="absolute top-3 right-3 bg-[#d4f5a4] text-black p-1 rounded-full text-xs shadow-xs">
                          <Check className="w-3.5 h-3.5" />
                        </span>
                      )}

                      <div>
                        {/* Flag & Name */}
                        <div className="flex items-center gap-2.5 mb-2">
                          <FlagIcon code={code} className="w-6 h-4.5 rounded-[2px] shadow-xs border border-black/10 shrink-0" />
                          <div>
                            <h3 className="font-mono font-bold text-sm text-gray-900 leading-tight">
                              {item.name}
                            </h3>
                            <span className="text-[10px] font-mono text-gray-500">
                              {item.currency} ({item.currencySymbol.trim()})
                            </span>
                          </div>
                        </div>

                        {/* Details */}
                        <p className="text-xs text-gray-600 font-sans mt-2 line-clamp-2 leading-relaxed">
                          {meta.desc}
                        </p>
                      </div>

                      <div className="mt-3 pt-2.5 border-t border-gray-100 flex items-center justify-between gap-2 text-[10px] font-mono text-gray-500">
                        <span className="truncate">Platform: <strong className="text-gray-800 font-semibold">{meta.platform}</strong></span>
                        <span className="text-emerald-700 font-bold shrink-0 bg-emerald-50 px-2 py-0.5 rounded">Active</span>
                      </div>
                    </motion.button>
                  );
                })}
              </div>

              {/* Footer */}
              <div className="pt-3 border-t border-gray-200/80 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500 font-sans">
                <span className="flex items-center gap-1.5 flex-wrap">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
                  <span>Currently viewing website configured for:</span>
                  <strong className="text-gray-900 font-mono inline-flex items-center gap-1.5">
                    {region.name}
                    <FlagIcon code={regionCode} className="w-4 h-3 rounded-[2px] shadow-2xs border border-black/10 inline-block" />
                  </strong>
                </span>

                <button
                  onClick={closeModal}
                  className="w-full sm:w-auto bg-[#1A1A1A] text-white font-semibold px-5 py-2 rounded-xl hover:bg-gray-800 transition-colors text-xs text-center shrink-0"
                >
                  Continue with {region.name} →
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
