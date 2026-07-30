'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Check, Sparkles, Zap, ShieldCheck } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';
import { FlagIcon } from '@/components/shared/FlagIcon';

export default function GlobalPricing() {
  const { region } = useRegion();
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');

  const discountFactor = billingCycle === 'annual' ? 0.83 : 1.0;

  const starterPrice = Math.round(region.starterPrice * discountFactor);
  const proPrice = Math.round(region.proPrice * discountFactor);

  const getStarterDescription = () => {
    switch (region.code) {
      case 'AE':
        return 'Ideal for independent brokers in Dubai.';
      case 'GB':
        return 'For independent estate agents & letting agents.';
      case 'SG':
        return 'For CEA-licensed property agents.';
      case 'US':
        return 'For solo agents and small teams.';
      case 'AU':
        return 'For solo agents & property specialists.';
      case 'CA':
        return 'For independent realtors & sales reps.';
      case 'IN':
      default:
        return 'Perfect for solo real estate brokers.';
    }
  };

  return (
    <section id="pricing" className="py-24 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="text-center mb-12"
      >
        <div className="flex items-center justify-center gap-3 mb-4">
          <span className="bg-gray-100 text-gray-700 border border-gray-200 rounded-full text-xs uppercase tracking-wider px-3.5 py-1 font-mono font-semibold flex items-center gap-2">
            <span>PRICING FOR {region.name.toUpperCase()}</span>
            <FlagIcon code={region.code} className="w-4 h-3 rounded-[2px] shadow-2xs border border-black/10 inline-block shrink-0" />
          </span>
          <div className="h-px w-8 bg-gray-300" />
          <div className="w-2 h-2 bg-[#d4f5a4] rounded-sm" />
        </div>

        <h2 className="text-3xl md:text-5xl font-mono text-gray-900 font-bold tracking-tight mb-4">
          Simple pricing. No hidden fees.
        </h2>
        <p className="text-base md:text-lg text-gray-600 font-sans leading-relaxed max-w-xl mx-auto">
          Cancel anytime. No credit card required to start your free 7-day trial.
        </p>

        {/* Monthly / Annual Toggle */}
        <div className="inline-flex items-center gap-3 mt-8 p-1.5 bg-gray-100 border border-gray-200 rounded-2xl">
          <button
            onClick={() => setBillingCycle('monthly')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              billingCycle === 'monthly'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Monthly
          </button>
          <button
            onClick={() => setBillingCycle('annual')}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
              billingCycle === 'annual'
                ? 'bg-[#d4f5a4] text-black shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Annual
            <span className="bg-black text-white text-[10px] px-1.5 py-0.5 rounded-full uppercase">17% OFF</span>
          </button>
        </div>
      </motion.div>

      {/* Pricing Cards Grid */}
      <div className="grid md:grid-cols-2 gap-8 items-stretch">
        {/* Starter Plan Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm flex flex-col justify-between"
        >
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold text-gray-900 font-mono">Starter Plan</h3>
              <span className="text-xs font-mono text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
                {region.currency}
              </span>
            </div>
            <p className="text-xs text-gray-600 mb-6 font-sans">{getStarterDescription()}</p>

            <div className="mb-6">
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold font-mono text-gray-900">
                  {formatCurrency(starterPrice, region)}
                </span>
                <span className="text-sm font-sans text-gray-500">/mo</span>
              </div>
              {billingCycle === 'annual' && (
                <p className="text-xs text-emerald-600 mt-1 font-sans">Billed annually</p>
              )}
            </div>

            <ul className="space-y-3 mb-8 text-sm text-gray-600 font-sans">
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{region.defaultLeadsPerMonth} leads qualified/month</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>GPT-4o AI Qualification</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Pipeline Stages & Notes</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Up to 3 Color Tags</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>WhatsApp Instant qualification</span>
              </li>
            </ul>
          </div>

          <Link
            href="/register"
            className="w-full py-3.5 px-4 border border-gray-300 bg-white text-gray-900 text-center font-bold text-sm rounded-xl hover:bg-gray-50 transition-colors"
          >
            START FREE TRIAL →
          </Link>
        </motion.div>

        {/* Pro Plan Card (Featured) */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="bg-white border-2 border-gray-900 rounded-3xl p-8 shadow-md flex flex-col justify-between relative"
        >
          <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-[#d4f5a4] text-black text-xs font-bold font-mono px-4 py-1 rounded-full uppercase tracking-wider border border-gray-900 shadow-sm">
            MOST POPULAR
          </div>

          <div>
            <div className="flex justify-between items-center mb-4 mt-2">
              <h3 className="text-xl font-bold text-gray-900 font-mono">Pro Plan</h3>
              <span className="text-xs font-mono text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
                {region.currency}
              </span>
            </div>
            <p className="text-xs text-gray-600 mb-6 font-sans">For active brokers & growing agencies in {region.name}.</p>

            <div className="mb-6">
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-extrabold font-mono text-gray-900">
                  {formatCurrency(proPrice, region)}
                </span>
                <span className="text-sm font-sans text-gray-500">/mo</span>
              </div>
              {billingCycle === 'annual' && (
                <p className="text-xs text-emerald-600 mt-1 font-sans">Billed annually</p>
              )}
            </div>

            <ul className="space-y-3 mb-8 text-sm text-gray-600 font-sans">
              <li className="flex items-center gap-2.5 font-semibold text-gray-900">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>{region.defaultLeadsPerMonth * 3} leads qualified/month</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>GPT-4o Advanced Qualification & Scoring</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Unlimited Tags & Pipeline Stages</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Task Reminders & Smart Alerts</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Lead Source Tracking</span>
              </li>
              <li className="flex items-center gap-2.5">
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Automated WhatsApp Follow-ups</span>
              </li>
            </ul>
          </div>

          <Link
            href="/register"
            className="w-full py-3.5 px-4 bg-[#d4f5a4] text-black text-center font-bold text-sm rounded-xl hover:bg-[#c5e894] transition-colors shadow-sm"
          >
            START 7-DAY FREE TRIAL →
          </Link>
        </motion.div>
      </div>

      <p className="text-center text-xs text-gray-500 mt-8 font-sans">
        All prices in {region.currency} ({region.currencySymbol.trim()}). Local taxes may apply.
      </p>
    </section>
  );
}
