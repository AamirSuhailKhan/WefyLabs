'use client';

import React, { useState, useMemo } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calculator,
  Clock,
  AlertTriangle,
  Zap,
  ChevronDown,
  ArrowRight,
  TrendingDown,
  DollarSign,
  CheckCircle2,
  Sparkles,
  ShieldAlert
} from 'lucide-react';

interface CalculationResults {
  coldLeads: number;
  hotLeads: number;
  costPerLead: number;
  adWaste: number;
  hoursPerMonth: number;
  hoursPerWeek: number;
  opportunityCost: number;
  hotLeadsMissed: number;
  commissionLost: number;
  totalWaste: number;
  netSavings: number;
  roi: string;
  paybackDays: number;
}

export function calculateWaste(
  leadsPerMonth: number,
  adSpend: number,
  timePerLead: number,
  commissionPerDeal: number,
  conversionRate: number,
  coldLeadPercent: number
): CalculationResults {
  const coldPercent = coldLeadPercent / 100;
  const convRate = conversionRate / 100;

  const coldLeads = Math.round(leadsPerMonth * coldPercent);
  const hotLeads = leadsPerMonth - coldLeads;
  const costPerLead = Math.round(adSpend / Math.max(1, leadsPerMonth));
  const adWaste = Math.round(coldLeads * costPerLead);

  const hoursPerMonth = coldLeads * (timePerLead / 60);
  const hoursPerWeek = hoursPerMonth / 4.33;

  // Conservative 0.2% of commission per deal as broker's hourly valuation
  const hourlyValue = commissionPerDeal * 0.002;
  const opportunityCost = Math.round(hoursPerMonth * hourlyValue);

  // 30% of hot leads missed due to time drain on cold calls
  const hotLeadsMissed = Math.round(hotLeads * 0.30);
  const commissionLost = Math.round(hotLeadsMissed * convRate * commissionPerDeal);

  const totalWaste = adWaste + opportunityCost + commissionLost;
  const beetleLabsCost = 2999;
  const netSavings = Math.max(0, totalWaste - beetleLabsCost);
  const roi = (totalWaste / beetleLabsCost).toFixed(1);
  const paybackDays = Math.max(1, Math.ceil(beetleLabsCost / Math.max(1, totalWaste / 30)));

  return {
    coldLeads,
    hotLeads,
    costPerLead,
    adWaste,
    hoursPerMonth,
    hoursPerWeek,
    opportunityCost,
    hotLeadsMissed,
    commissionLost,
    totalWaste,
    netSavings,
    roi,
    paybackDays
  };
}

export function formatINR(val: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(val);
}

import SectionLabel from '@/components/shared/SectionLabel';

export default function WasteCalculator() {
  // Input states with product defaults
  const [leadsPerMonth, setLeadsPerMonth] = useState<number>(80);
  const [adSpend, setAdSpend] = useState<number>(25000);
  const [timePerLead, setTimePerLead] = useState<number>(8);
  const [commissionPerDeal, setCommissionPerDeal] = useState<number>(150000);
  const [conversionRate, setConversionRate] = useState<number>(8);
  const [coldLeadPercent, setColdLeadPercent] = useState<number>(70);

  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);
  const [hasCalculated, setHasCalculated] = useState<boolean>(true);

  // Real-time calculation
  const results = useMemo(
    () =>
      calculateWaste(
        leadsPerMonth,
        adSpend,
        timePerLead,
        commissionPerDeal,
        conversionRate,
        coldLeadPercent
      ),
    [leadsPerMonth, adSpend, timePerLead, commissionPerDeal, conversionRate, coldLeadPercent]
  );

  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
      {/* Header Pill & Title */}
      <motion.div
        initial={{ opacity: 0, y: 25 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-50px' }}
        transition={{ duration: 0.5 }}
        className="text-center mb-12"
      >
        <SectionLabel text="CALCULATOR" variant="pill" />
        <h2 className="text-4xl md:text-5xl font-bold text-[#1A1A1A] mb-3 tracking-tight" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
          How much are you wasting on cold leads?
        </h2>
        <p className="text-base md:text-lg text-[#4A4A4A] max-w-2xl mx-auto leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
          Indian brokers spend ₹15,000–50,000/month on ads. 70% of those leads are cold, fake, or just browsing. Put in your numbers and see the damage.
        </p>
      </motion.div>

      {/* Main 2-Column Grid */}
      <div className="grid lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Input Form (5 cols) */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-5 bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-6 sm:p-8 shadow-sm space-y-6"
        >
          <div className="flex items-center justify-between border-b border-[#D4D0C8] pb-4">
            <h3 className="text-lg font-bold text-[#1A1A1A] flex items-center gap-2" style={{ fontFamily: 'Inter, sans-serif' }}>
              <Calculator className="w-5 h-5 text-[#1A1A1A]" />
              Your Brokerage Inputs
            </h3>
            <span className="text-xs font-mono text-[#6B6B6B] bg-[#EAE0D7] px-2.5 py-1 rounded-full border border-[#D4D0C8]">
              Live Estimate
            </span>
          </div>

          <div className="space-y-5">
            {/* Input 1: New leads per month */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm">
                <label className="font-medium text-[#1A1A1A]">New leads per month</label>
                <div className="flex items-center gap-1 bg-white border border-[#D4D0C8] rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-[#1A1A1A]">
                  <input
                    type="number"
                    min={10}
                    max={300}
                    value={leadsPerMonth}
                    onChange={(e) => setLeadsPerMonth(Math.max(10, Math.min(300, Number(e.target.value) || 10)))}
                    className="w-12 text-right outline-none bg-transparent"
                  />
                </div>
              </div>
              <input
                type="range"
                min={10}
                max={300}
                step={5}
                value={leadsPerMonth}
                onChange={(e) => setLeadsPerMonth(Number(e.target.value))}
                className="w-full h-2 bg-[#EAE0D7] rounded-lg appearance-none cursor-pointer accent-[#1A1A1A]"
              />
            </div>

            {/* Input 2: Monthly ad spend */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm">
                <label className="font-medium text-[#1A1A1A]">Monthly ad spend (₹)</label>
                <div className="flex items-center gap-1 bg-white border border-[#D4D0C8] rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-[#1A1A1A]">
                  <span>₹</span>
                  <input
                    type="number"
                    min={5000}
                    max={100000}
                    step={1000}
                    value={adSpend}
                    onChange={(e) => setAdSpend(Math.max(5000, Math.min(100000, Number(e.target.value) || 5000)))}
                    className="w-20 text-right outline-none bg-transparent"
                  />
                </div>
              </div>
              <input
                type="range"
                min={5000}
                max={100000}
                step={1000}
                value={adSpend}
                onChange={(e) => setAdSpend(Number(e.target.value))}
                className="w-full h-2 bg-[#EAE0D7] rounded-lg appearance-none cursor-pointer accent-[#1A1A1A]"
              />
            </div>

            {/* Input 3: Time per lead call */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm">
                <label className="font-medium text-[#1A1A1A]">Time per lead call (min)</label>
                <div className="flex items-center gap-1 bg-white border border-[#D4D0C8] rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-[#1A1A1A]">
                  <input
                    type="number"
                    min={2}
                    max={20}
                    value={timePerLead}
                    onChange={(e) => setTimePerLead(Math.max(2, Math.min(20, Number(e.target.value) || 2)))}
                    className="w-10 text-right outline-none bg-transparent"
                  />
                  <span>m</span>
                </div>
              </div>
              <input
                type="range"
                min={2}
                max={20}
                step={1}
                value={timePerLead}
                onChange={(e) => setTimePerLead(Number(e.target.value))}
                className="w-full h-2 bg-[#EAE0D7] rounded-lg appearance-none cursor-pointer accent-[#1A1A1A]"
              />
            </div>

            {/* Input 4: Commission per deal */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm">
                <label className="font-medium text-[#1A1A1A]">Commission per deal (₹)</label>
                <div className="flex items-center gap-1 bg-white border border-[#D4D0C8] rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-[#1A1A1A]">
                  <span>₹</span>
                  <input
                    type="number"
                    min={50000}
                    max={500000}
                    step={10000}
                    value={commissionPerDeal}
                    onChange={(e) => setCommissionPerDeal(Math.max(50000, Math.min(500000, Number(e.target.value) || 50000)))}
                    className="w-24 text-right outline-none bg-transparent"
                  />
                </div>
              </div>
              <input
                type="range"
                min={50000}
                max={500000}
                step={10000}
                value={commissionPerDeal}
                onChange={(e) => setCommissionPerDeal(Number(e.target.value))}
                className="w-full h-2 bg-[#EAE0D7] rounded-lg appearance-none cursor-pointer accent-[#1A1A1A]"
              />
            </div>

            {/* Input 5: Conversion rate */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm">
                <label className="font-medium text-[#1A1A1A]">Conversion rate (%)</label>
                <div className="flex items-center gap-1 bg-white border border-[#D4D0C8] rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-[#1A1A1A]">
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={conversionRate}
                    onChange={(e) => setConversionRate(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                    className="w-10 text-right outline-none bg-transparent"
                  />
                  <span>%</span>
                </div>
              </div>
              <input
                type="range"
                min={1}
                max={30}
                step={1}
                value={conversionRate}
                onChange={(e) => setConversionRate(Number(e.target.value))}
                className="w-full h-2 bg-[#EAE0D7] rounded-lg appearance-none cursor-pointer accent-[#1A1A1A]"
              />
            </div>

            {/* Input 6: % of leads that are cold/fake */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm">
                <label className="font-medium text-[#1A1A1A]">% Cold/Fake Leads</label>
                <div className="flex items-center gap-1 bg-white border border-[#D4D0C8] rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-rose-600">
                  <input
                    type="number"
                    min={30}
                    max={90}
                    value={coldLeadPercent}
                    onChange={(e) => setColdLeadPercent(Math.max(30, Math.min(90, Number(e.target.value) || 30)))}
                    className="w-10 text-right outline-none bg-transparent"
                  />
                  <span>%</span>
                </div>
              </div>
              <input
                type="range"
                min={30}
                max={90}
                step={5}
                value={coldLeadPercent}
                onChange={(e) => setColdLeadPercent(Number(e.target.value))}
                className="w-full h-2 bg-[#EAE0D7] rounded-lg appearance-none cursor-pointer accent-rose-600"
              />
              <p className="text-[11px] text-[#6B6B6B] mt-1 font-sans">
                Industry average for Indian real estate: 70%
              </p>
            </div>
          </div>

          <button
            onClick={() => setHasCalculated(true)}
            className="w-full py-3.5 px-4 rounded-xl bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] font-bold text-sm hover:bg-[#dcee8d] transition-all flex items-center justify-center gap-2 shadow-sm"
          >
            <Sparkles className="w-4 h-4" />
            Recalculate My Waste
          </button>
        </motion.div>

        {/* Right Column: Results Display (7 cols) */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-7 space-y-6"
        >
          {/* Top 3 Stat Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Card 1: Ad Spend Wasted */}
            <div className="bg-white border border-rose-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-rose-600 mb-2">
                <TrendingDown className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Ad Wasted</span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-rose-600 font-mono tracking-tight">
                {formatINR(results.adWaste)}
              </div>
              <p className="text-xs text-[#6B6B6B] mt-1">On cold & fake leads</p>
            </div>

            {/* Card 2: Hours Wasted/Week */}
            <div className="bg-white border border-rose-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-rose-600 mb-2">
                <Clock className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Time Wasted</span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-rose-600 font-mono tracking-tight">
                {results.hoursPerWeek.toFixed(1)} hrs/wk
              </div>
              <p className="text-xs text-[#6B6B6B] mt-1">Calling bad leads</p>
            </div>

            {/* Card 3: Deals Lost */}
            <div className="bg-white border border-amber-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-amber-600 mb-2">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Deals Lost</span>
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-amber-600 font-mono tracking-tight">
                {results.hotLeadsMissed} deals
              </div>
              <p className="text-xs text-[#6B6B6B] mt-1">Hot leads missed</p>
            </div>
          </div>

          {/* Middle Card — Total Monthly Loss */}
          <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="text-xs font-bold uppercase tracking-widest text-[#6B6B6B] font-mono">
                  ESTIMATED TOTAL LOSS
                </span>
                <h4 className="text-2xl sm:text-3xl font-extrabold text-rose-600 font-mono mt-1">
                  {formatINR(results.totalWaste)} <span className="text-sm font-sans font-normal text-[#6B6B6B]">/ month</span>
                </h4>
              </div>
              <span className="bg-rose-100 text-rose-700 text-xs font-bold px-3 py-1 rounded-full border border-rose-200">
                Money + Time + Opportunity
              </span>
            </div>

            {/* Visual Loss Progress Bar */}
            <div className="space-y-1.5">
              <div className="h-3 w-full bg-rose-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, (results.totalWaste / 150000) * 100)}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                  className="h-full bg-rose-500 rounded-full"
                />
              </div>
              <p className="text-[11px] text-[#6B6B6B] text-right">
                Based on {results.coldLeads} cold leads ({coldLeadPercent}% of total)
              </p>
            </div>
          </div>

          {/* Bottom Card — With BeetleLabs */}
          <div className="bg-[#FAF7F2] border-l-4 border-[#0D9488] border-y border-r border-[#D4D0C8] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase tracking-widest text-[#0D9488] font-mono">
                    WITH BEETLELABS (₹2,999/MO)
                  </span>
                  <span className="bg-[#CCFBF1] text-[#0F766E] text-[10px] font-bold px-2.5 py-0.5 rounded-full border border-[#99F6E4]">
                    AI qualifies in 2 min
                  </span>
                </div>
                <h4 className="text-3xl sm:text-4xl font-extrabold text-[#0D9488] font-mono mt-2">
                  {formatINR(results.netSavings)} <span className="text-sm font-sans font-normal text-[#6B6B6B]">net savings / mo</span>
                </h4>
              </div>
            </div>

            <div className="pt-2 border-t border-[#D4D0C8] flex flex-wrap items-center justify-between gap-3 text-xs sm:text-sm font-semibold text-[#0F766E]">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-[#0D9488]" />
                {results.roi}x ROI — pays for itself in {results.paybackDays} {results.paybackDays === 1 ? 'day' : 'days'}
              </span>
              <span className="text-[#6B6B6B] font-normal">
                Net savings after ₹2,999 Starter plan
              </span>
            </div>
          </div>

          {/* Collapsible Breakdown Accordion */}
          <div className="bg-white border border-[#D4D0C8] rounded-2xl overflow-hidden">
            <button
              onClick={() => setShowBreakdown(!showBreakdown)}
              className="w-full p-4 text-left flex items-center justify-between text-xs font-bold uppercase tracking-wider text-[#6B6B6B] hover:bg-[#FAF7F2] transition-colors"
            >
              <span>View Calculation Breakdown</span>
              <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${showBreakdown ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {showBreakdown && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="px-5 pb-5 pt-2 border-t border-[#D4D0C8] space-y-2 text-xs text-[#4A4A4A] font-mono"
                >
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Cold leads per month:</span>
                    <span className="font-bold text-[#1A1A1A]">{results.coldLeads} leads</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Cost per cold lead:</span>
                    <span className="font-bold text-[#1A1A1A]">₹{results.costPerLead}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Ad spend wasted:</span>
                    <span className="font-bold text-rose-600">{formatINR(results.adWaste)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Hours spent on cold leads/wk:</span>
                    <span className="font-bold text-[#1A1A1A]">{results.hoursPerWeek.toFixed(1)} hrs</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Opportunity cost of time:</span>
                    <span className="font-bold text-rose-600">{formatINR(results.opportunityCost)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Hot leads missed (30% assumption):</span>
                    <span className="font-bold text-[#1A1A1A]">{results.hotLeadsMissed} leads</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Commission lost on missed leads:</span>
                    <span className="font-bold text-amber-600">{formatINR(results.commissionLost)}</span>
                  </div>
                  <div className="flex justify-between py-1 pt-2 font-bold text-[#1A1A1A]">
                    <span>BeetleLabs subscription:</span>
                    <span>₹2,999 / mo</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
