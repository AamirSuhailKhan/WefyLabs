'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calculator,
  Clock,
  AlertTriangle,
  TrendingDown,
  ChevronDown,
  CheckCircle2,
  Zap
} from 'lucide-react';
import Link from 'next/link';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

export default function GlobalWasteCalculator() {
  const { region } = useRegion();

  // State populated from active region
  const [leadsPerMonth, setLeadsPerMonth] = useState<number>(region.defaultLeadsPerMonth);
  const [adSpend, setAdSpend] = useState<number>(region.defaultAdSpend);
  const [timePerLead, setTimePerLead] = useState<number>(region.defaultTimePerLead);
  const [commissionPerDeal, setCommissionPerDeal] = useState<number>(region.defaultCommission);
  const [conversionRate, setConversionRate] = useState<number>(region.defaultConversionRate);
  const [coldLeadPercent, setColdLeadPercent] = useState<number>(region.defaultColdLeadPercent);
  const [showBreakdown, setShowBreakdown] = useState<boolean>(false);

  // Update inputs whenever region changes
  useEffect(() => {
    setLeadsPerMonth(region.defaultLeadsPerMonth);
    setAdSpend(region.defaultAdSpend);
    setTimePerLead(region.defaultTimePerLead);
    setCommissionPerDeal(region.defaultCommission);
    setConversionRate(region.defaultConversionRate);
    setColdLeadPercent(region.defaultColdLeadPercent);
  }, [region]);

  // Real calculation logic
  const results = useMemo(() => {
    const coldPercent = coldLeadPercent / 100;
    const convRate = conversionRate / 100;

    const coldLeads = Math.round(leadsPerMonth * coldPercent);
    const hotLeads = leadsPerMonth - coldLeads;
    const costPerLead = Math.max(1, adSpend / Math.max(1, leadsPerMonth));
    const adWaste = Math.round(coldLeads * costPerLead);

    const hoursPerMonth = coldLeads * (timePerLead / 60);
    const hoursPerWeek = hoursPerMonth / 4.33;

    const hourlyValue = commissionPerDeal * 0.002;
    const opportunityCost = Math.round(hoursPerMonth * hourlyValue);

    const hotLeadsMissed = Math.round(hotLeads * 0.30);
    const commissionLost = Math.round(hotLeadsMissed * convRate * commissionPerDeal);

    const totalWaste = adWaste + opportunityCost + commissionLost;
    const leadScoreCost = region.starterPrice;
    const netSavings = Math.max(0, totalWaste - leadScoreCost);
    const roi = (totalWaste / Math.max(1, leadScoreCost)).toFixed(1);
    const paybackDays = Math.max(1, Math.ceil(leadScoreCost / Math.max(1, totalWaste / 30)));

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
      leadScoreCost,
      netSavings,
      roi,
      paybackDays
    };
  }, [leadsPerMonth, adSpend, timePerLead, commissionPerDeal, conversionRate, coldLeadPercent, region]);

  // Dynamic regional subheadline
  const getSubheadline = () => {
    switch (region.code) {
      case 'AE':
        return 'Dubai brokers spend AED 2,000–8,000/month on Property Finder ads. 65% of leads are unqualified expat inquiries.';
      case 'GB':
        return 'Estate agents pay £20–50 per Rightmove lead. 60% are time-wasters. See what it\'s costing you.';
      case 'SG':
        return 'Property agents spend S$1,500–4,000/month on PropertyGuru. 60% of leads are cold.';
      case 'US':
        return 'Real estate agents spend $1,000–5,000/month on Zillow leads. 65% never convert.';
      case 'AU':
        return 'Agents spend A$1,500–4,000/month on REA leads. 60% of leads are unqualified.';
      case 'CA':
        return 'Realtors spend C$1,500–4,000/month on Realtor.ca leads. 60% are time-wasters.';
      case 'IN':
      default:
        return 'Indian brokers spend ₹15,000–50,000/month on ads. 70% of those leads are cold, fake, or just browsing.';
    }
  };

  // Region-specific agent terminology
  const getAgentTerm = () => {
    switch (region.code) {
      case 'GB': return 'estate agents';
      case 'SG': return 'property agents';
      case 'CA': return 'realtors';
      case 'US': return 'agents';
      default:   return 'brokers';
    }
  };

  return (
    <section id="calculator" className="py-20 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
      {/* Section Header with Pill Pattern */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="text-center mb-12"
      >
        <div className="flex items-center justify-center gap-3 mb-4">
          <span className="bg-gray-100 text-gray-600 rounded-full text-xs uppercase tracking-wider px-3 py-1 font-sans">
            CALCULATOR
          </span>
          <div className="h-px w-8 bg-gray-300" />
          <div className="w-2 h-2 bg-[#d4f5a4] rounded-sm" />
        </div>

        <h2 className="text-3xl md:text-5xl font-mono text-gray-900 font-bold tracking-tight mb-4">
          How much are you wasting on cold leads?
        </h2>
        <p className="text-base md:text-lg text-gray-600 font-sans leading-relaxed max-w-2xl mx-auto">
          {getSubheadline()}
        </p>
      </motion.div>

      {/* Main 2-Column Layout */}
      <div className="grid lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Inputs */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-5 bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-6"
        >
          <div className="flex items-center justify-between border-b border-gray-100 pb-4">
            <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2 font-sans">
              <Calculator className="w-5 h-5 text-gray-700" />
              {region.name} Broker Inputs
            </h3>
            <span className="text-xs font-mono text-gray-600 bg-gray-100 px-2.5 py-1 rounded-full">
              {region.currency}
            </span>
          </div>

          <div className="space-y-5">
            {/* Input 1: Leads per month */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm font-sans">
                <label className="text-gray-600">New leads per month</label>
                <div className="bg-white border border-gray-300 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-gray-900">
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
              />
            </div>

            {/* Input 2: Monthly ad spend */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm font-sans">
                <label className="text-gray-600">Monthly ad spend ({region.currencySymbol.trim()})</label>
                <div className="flex items-center gap-1 bg-white border border-gray-300 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-gray-900">
                  <span>{region.currencySymbol.trim()}</span>
                  <input
                    type="number"
                    min={500}
                    max={200000}
                    step={100}
                    value={adSpend}
                    onChange={(e) => setAdSpend(Math.max(100, Number(e.target.value) || 100))}
                    className="w-20 text-right outline-none bg-transparent"
                  />
                </div>
              </div>
              <input
                type="range"
                min={500}
                max={Math.max(50000, region.defaultAdSpend * 4)}
                step={100}
                value={adSpend}
                onChange={(e) => setAdSpend(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
              />
            </div>

            {/* Input 3: Time per lead call */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm font-sans">
                <label className="text-gray-600">Time per lead call (min)</label>
                <div className="flex items-center gap-1 bg-white border border-gray-300 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-gray-900">
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
              />
            </div>

            {/* Input 4: Commission per deal */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm font-sans">
                <label className="text-gray-600">Commission per deal ({region.currencySymbol.trim()})</label>
                <div className="flex items-center gap-1 bg-white border border-gray-300 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-gray-900">
                  <span>{region.currencySymbol.trim()}</span>
                  <input
                    type="number"
                    min={1000}
                    max={1000000}
                    step={500}
                    value={commissionPerDeal}
                    onChange={(e) => setCommissionPerDeal(Math.max(500, Number(e.target.value) || 500))}
                    className="w-24 text-right outline-none bg-transparent"
                  />
                </div>
              </div>
              <input
                type="range"
                min={1000}
                max={Math.max(100000, region.defaultCommission * 3)}
                step={500}
                value={commissionPerDeal}
                onChange={(e) => setCommissionPerDeal(Number(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
              />
            </div>

            {/* Input 5: Conversion rate */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm font-sans">
                <label className="text-gray-600">Conversion rate (%)</label>
                <div className="flex items-center gap-1 bg-white border border-gray-300 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-gray-900">
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-black"
              />
            </div>

            {/* Input 6: % Cold/Fake Leads */}
            <div>
              <div className="flex justify-between items-center mb-1.5 text-sm font-sans">
                <label className="text-gray-600">% Cold/Fake Leads</label>
                <div className="flex items-center gap-1 bg-white border border-gray-300 rounded-lg px-2.5 py-1 text-xs font-mono font-bold text-rose-600">
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-rose-600"
              />
              <p className="text-[11px] text-gray-400 mt-1 font-sans">
                Average for {region.name} real estate: {region.defaultColdLeadPercent}%
              </p>
            </div>
          </div>
        </motion.div>

        {/* Right Column: Results */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="lg:col-span-7 space-y-6"
        >
          {/* Top 3 Stat Cards Row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-rose-600 mb-2">
                <TrendingDown className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Ad Wasted</span>
              </div>
              <div className="text-2xl sm:text-3xl font-bold font-mono text-rose-600 tracking-tight">
                {formatCurrency(results.adWaste, region)}
              </div>
              <p className="text-xs text-gray-500 mt-1 font-sans">On cold & fake leads</p>
            </div>

            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-rose-600 mb-2">
                <Clock className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Time Wasted</span>
              </div>
              <div className="text-2xl sm:text-3xl font-bold font-mono text-rose-600 tracking-tight">
                {results.hoursPerWeek.toFixed(1)} hrs
              </div>
              <p className="text-xs text-gray-500 mt-1 font-sans">Calling bad leads/week</p>
            </div>

            <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 text-amber-600 mb-2">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Deals Lost</span>
              </div>
              <div className="text-2xl sm:text-3xl font-bold font-mono text-amber-600 tracking-tight">
                {results.hotLeadsMissed} deals
              </div>
              <p className="text-xs text-gray-500 mt-1 font-sans">Hot leads missed</p>
            </div>
          </div>

          {/* Total Monthly Loss Card */}
          <div className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="text-xs font-bold uppercase tracking-widest text-gray-400 font-mono">
                  ESTIMATED TOTAL MONTHLY LOSS
                </span>
                <h4 className="text-3xl sm:text-4xl font-bold font-mono text-rose-600 tracking-tight mt-1">
                  {formatCurrency(results.totalWaste, region)} <span className="text-sm font-sans font-normal text-gray-500">/ month</span>
                </h4>
              </div>
              <span className="bg-rose-50 text-rose-600 text-xs font-bold px-3 py-1 rounded-full border border-rose-200 font-sans">
                Money + Time + Opportunity
              </span>
            </div>

            {/* Progress Bar */}
            <div className="space-y-1">
              <div className="h-3 w-full bg-rose-50 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, (results.totalWaste / (region.defaultAdSpend * 4)) * 100)}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                  className="h-full bg-rose-500 rounded-full"
                />
              </div>
              <p className="text-[11px] text-gray-400 text-right font-sans">
                Based on {results.coldLeads} cold leads ({coldLeadPercent}% of total)
              </p>
            </div>
          </div>

          {/* With LeadScore Card */}
          <div className="bg-white border-l-4 border-l-[#d4f5a4] border-y border-r border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold uppercase tracking-widest text-emerald-700 font-mono">
                    WITH BEETLELABS ({formatCurrency(results.leadScoreCost, region)}/MO)
                  </span>
                  <span className="bg-emerald-50 text-emerald-700 text-[10px] font-bold px-2 py-0.5 rounded-full border border-emerald-200">
                    AI qualifies in 2 min
                  </span>
                </div>
                <h4 className="text-3xl sm:text-4xl font-bold font-mono text-emerald-600 tracking-tight">
                  {formatCurrency(results.netSavings, region)} <span className="text-sm font-sans font-normal text-gray-500">net savings / mo</span>
                </h4>
              </div>
            </div>

            <div className="pt-2 border-t border-gray-100 flex flex-wrap items-center justify-between gap-3 text-xs sm:text-sm font-semibold text-emerald-700 font-sans">
              <span className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                {results.roi}x ROI — pays for itself in {results.paybackDays} {results.paybackDays === 1 ? 'day' : 'days'}
              </span>
              <span className="text-gray-500 font-normal">
                Net savings after {formatCurrency(results.leadScoreCost, region)} subscription
              </span>
            </div>
          </div>

          {/* Calculation Breakdown Accordion */}
          <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
            <button
              onClick={() => setShowBreakdown(!showBreakdown)}
              className="w-full p-4 text-left flex items-center justify-between text-xs font-bold uppercase tracking-wider text-gray-500 hover:bg-gray-50 transition-colors font-sans"
            >
              <span>View Calculation Breakdown ({region.name})</span>
              <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${showBreakdown ? 'rotate-180' : ''}`} />
            </button>

            <AnimatePresence>
              {showBreakdown && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="px-5 pb-5 pt-2 border-t border-gray-100 space-y-2 text-xs text-gray-600 font-mono"
                >
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Cold leads per month:</span>
                    <span className="font-bold text-gray-900">{results.coldLeads} leads</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Cost per cold lead:</span>
                    <span className="font-bold text-gray-900">{formatCurrency(results.costPerLead, region)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Ad spend wasted:</span>
                    <span className="font-bold text-rose-600">{formatCurrency(results.adWaste, region)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Hours on cold leads/week:</span>
                    <span className="font-bold text-gray-900">{results.hoursPerWeek.toFixed(1)} hrs</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Opportunity cost of time:</span>
                    <span className="font-bold text-rose-600">{formatCurrency(results.opportunityCost, region)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Hot leads missed (30% rate):</span>
                    <span className="font-bold text-gray-900">{results.hotLeadsMissed} leads</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span>Commission lost on missed deals:</span>
                    <span className="font-bold text-amber-600">{formatCurrency(results.commissionLost, region)}</span>
                  </div>
                  <div className="flex justify-between py-1 pt-2 font-bold text-gray-900">
                    <span>BeetleLabs starter price:</span>
                    <span>{formatCurrency(region.starterPrice, region)} / mo</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>

      {/* CTA Card — below results */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
        className="mt-12 bg-white border border-gray-200 rounded-3xl p-8 sm:p-10 shadow-sm"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
          {/* Icon */}
          <div className="shrink-0 w-14 h-14 bg-[#d4f5a4] rounded-2xl flex items-center justify-center border border-[#c5e894]">
            <Zap className="w-7 h-7 text-black" />
          </div>

          {/* Text */}
          <div className="flex-1 min-w-0">
            <h3 className="text-xl sm:text-2xl font-bold font-mono text-gray-900 tracking-tight mb-2">
              Stop the bleed. Start qualifying.
            </h3>
            <p className="text-sm sm:text-base text-gray-600 font-sans leading-relaxed">
              Join {getAgentTerm()} in{' '}
              <span className="font-semibold text-gray-900">{region.name}</span>{' '}
              using BeetleLabs to qualify leads in 2 minutes — and stop wasting time on cold contacts.
            </p>
          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 shrink-0 w-full sm:w-auto">
            <motion.div
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            >
              <Link
                href="/register"
                className="flex items-center justify-center gap-2 bg-[#d4f5a4] text-black font-semibold text-sm px-6 py-3 rounded-xl hover:bg-[#c5e894] transition-colors w-full sm:w-auto whitespace-nowrap"
              >
                START FREE TRIAL →
              </Link>
            </motion.div>
            <motion.div
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            >
              <Link
                href="/simulator"
                className="flex items-center justify-center gap-2 border border-gray-300 bg-white text-gray-900 font-semibold text-sm px-6 py-3 rounded-xl hover:bg-gray-50 transition-colors w-full sm:w-auto whitespace-nowrap"
              >
                See Live Demo
              </Link>
            </motion.div>
          </div>
        </div>
      </motion.div>
    </section>
  );
}
