'use client';

import { useState } from 'react';
import { useRegion } from '@/lib/i18n/region-context';
import Link from 'next/link';
import type { Variants, Easing } from 'framer-motion';
import Navbar from '@/components/shared/Navbar';
import { BeetleLabsLogo } from '@/components/shared/BeetleLabsLogo';
import FeaturesGrid from '@/components/shared/FeaturesGrid';
import MarketSelector from '@/components/landing/MarketSelector';
import GlobalWasteCalculator from '@/components/landing/GlobalWasteCalculator';
import GlobalPricing from '@/components/landing/GlobalPricing';
import HeroRobot from '@/components/shared/HeroRobot';
import { motion, AnimatePresence } from 'framer-motion';
import ScrollReveal from '@/components/shared/ScrollReveal';
import { useReducedMotion } from '@/lib/animations';
import { CursorGlow } from '@/components/animations/CursorGlow';
import { CountUpNumber } from '@/components/animations/CountUpNumber';
import {
  ArrowRight, ChevronDown, Check, X,
  Lock, ShieldCheck, Database, Sparkles
} from 'lucide-react';

// ─── Global easing & animation variants ───────────────────────────────────────
const EXPO: Easing = [0.22, 1, 0.36, 1];

// How It Works — card stagger
const howItWorksContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.2 } },
};
const howItWorksCard: Variants = {
  hidden: { opacity: 0, y: 40, scale: 0.96 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.6, ease: EXPO } },
};

// Early Access — text stagger
const textContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const textItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EXPO } },
};

// Security — right rows stagger
const rowContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.2 } },
};
const rowItem: Variants = {
  hidden: { opacity: 0, x: 30 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.5, ease: EXPO } },
};

// FAQ stagger
const faqContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
};
const faqItem: Variants = {
  hidden: { opacity: 0, x: -20 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.4, ease: EXPO } },
};

// Pricing stagger
const pricingContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.2 } },
};
const pricingCard: Variants = {
  hidden: { opacity: 0, y: 50, scale: 0.96 },
  visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.6, ease: EXPO } },
};

// Final CTA — left content stagger
const ctaContent: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
};
const ctaItem: Variants = {
  hidden: { y: 20, opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { duration: 0.5, ease: EXPO } },
};

// Final CTA — emoji icons
const iconContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.3 } },
};
const iconItem: Variants = {
  hidden: { opacity: 0, scale: 0, y: 20 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { type: 'spring' as const, stiffness: 300, damping: 15 } },
};

const VP = { once: true, margin: '-80px' } as const;
const VP60 = { once: true, margin: '-60px' } as const;

export default function LandingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [annual, setAnnual] = useState(false);
  const [waitlistEmail, setWaitlistEmail] = useState('');
  const [waitlistJoined, setWaitlistJoined] = useState(false);
  const reduced = useReducedMotion();
  const { region } = useRegion();

  // Region-specific hero subheadline
  const getHeroSubheadline = () => {
    switch (region.code) {
      case 'AE': return 'Dubai real estate brokers lose 12 hours/week on unqualified Property Finder leads. Our AI bot qualifies every lead on WhatsApp and scores them';
      case 'GB': return 'Estate agents lose 10+ hours/week chasing unqualified Rightmove leads. Our AI bot qualifies every lead on WhatsApp and scores them';
      case 'SG': return 'Singapore property agents lose 10 hours/week on cold PropertyGuru leads. Our AI bot qualifies every lead on WhatsApp and scores them';
      case 'US': return 'Real estate agents lose 10+ hours/week on Zillow leads that never convert. Our AI bot qualifies every lead and scores them';
      case 'AU': return 'Aussie real estate agents lose hours every week on unqualified REA leads. Our AI bot qualifies every lead on WhatsApp and scores them';
      case 'CA': return 'Canadian realtors lose 10+ hours/week on Realtor.ca leads that never close. Our AI bot qualifies every lead and scores them';
      case 'IN':
      default:   return 'Indian real estate brokers lose 15 hours/week calling unqualified leads. Our AI bot chats with every lead on WhatsApp and scores them';
    }
  };

  // Region-specific stats bar data
  const getRegionStats = () => {
    switch (region.code) {
      case 'AE': return { coldPct: 65, platform: 'Property Finder', agentTerm: 'brokers' };
      case 'GB': return { coldPct: 60, platform: 'Rightmove', agentTerm: 'estate agents' };
      case 'SG': return { coldPct: 60, platform: 'PropertyGuru', agentTerm: 'property agents' };
      case 'US': return { coldPct: 65, platform: 'Zillow', agentTerm: 'agents' };
      case 'AU': return { coldPct: 60, platform: 'REA Group', agentTerm: 'agents' };
      case 'CA': return { coldPct: 60, platform: 'Realtor.ca', agentTerm: 'realtors' };
      case 'IN':
      default:   return { coldPct: 70, platform: 'online ad', agentTerm: 'brokers' };
    }
  };
  const regionStats = getRegionStats();

  const faqs = [
    {
      q: 'Do I need to know how to code to use BeetleLabs?',
      a: 'No coding required. BeetleLabs works entirely over WhatsApp. Just forward a lead\'s phone number and our AI handles the rest.',
    },
    {
      q: "What happens when a lead doesn't reply?",
      a: 'The AI sends 2 polite follow-ups over 48 hours. If no response, it marks them Cold so you don\'t waste time.',
    },
    {
      q: 'How long does it take to set up?',
      a: 'Under 2 minutes. Sign up, connect your WhatsApp, and start forwarding leads immediately.',
    },
    {
      q: 'Can I integrate BeetleLabs with my existing CRM?',
      a: 'You can export all leads to Excel anytime. Native integrations with Sell.Do and Zoho are on our roadmap.',
    },
    {
      q: 'Why not just use a VA or assistant?',
      a: 'A VA costs ₹15,000+/month and works 9-5. BeetleLabs costs ₹2,999, works 24/7, and never forgets to follow up.',
    },
    {
      q: 'Can I use this for rental leads too?',
      a: 'Absolutely. The AI qualifies both buyers and renters with the same accuracy.',
    },
  ];

  const handleWaitlistSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!waitlistEmail) return;
    setWaitlistJoined(true);
  };

  // Hero headline words for word-by-word stagger
  const headlineWords = ['Stop', 'wasting', 'hours', 'on', 'cold', 'leads.'];

  return (
    <>
      <MarketSelector />
      <Navbar />
      <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] pt-24 relative overflow-hidden">
        <CursorGlow />

        {/* ─── SECTION 1: HERO ─────────────────────────────────────── */}
        <section className="px-4 sm:px-6 lg:px-8 pb-16 max-w-6xl mx-auto">
          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-8 md:p-12 lg:p-16 shadow-sm">
            <div className="grid lg:grid-cols-5 gap-12 items-center">
              {/* Left: Text */}
              <div className="lg:col-span-3 space-y-7">
                {/* Headline — word-by-word stagger */}
                <h1
                  className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.1] tracking-tight text-[#1A1A1A]"
                  style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
                >
                  {headlineWords.map((word, i) => (
                    reduced ? (
                      <span key={i} className="inline-block mr-[0.25em]">{word}</span>
                    ) : (
                      <motion.span
                        key={i}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 + i * 0.06, duration: 0.5, ease: EXPO }}
                        className="inline-block mr-[0.25em]"
                      >
                        {word}
                      </motion.span>
                    )
                  ))}
                </h1>

                {/* Subheadline */}
                <motion.p
                  initial={reduced ? false : { opacity: 0, y: 15 }}
                  animate={reduced ? {} : { opacity: 1, y: 0 }}
                  transition={{ delay: 0.8, duration: 0.6, ease: EXPO }}
                  className="text-[17px] text-[#4A4A4A] leading-[1.65] max-w-lg"
                  style={{ fontFamily: 'Inter, sans-serif' }}
                >
                  {getHeroSubheadline()}{' '}
                  <strong className="text-[#1A1A1A]">Hot 🔥</strong>,{' '}
                  <strong className="text-[#1A1A1A]">Warm 🟡</strong>, or{' '}
                  <strong className="text-[#1A1A1A]">Cold 🔵</strong>.
                </motion.p>

                {/* CTA Buttons */}
                <motion.div
                  initial={reduced ? false : { opacity: 0, y: 20 }}
                  animate={reduced ? {} : { opacity: 1, y: 0 }}
                  transition={{ delay: 1.0, duration: 0.5, ease: EXPO }}
                  className="flex flex-wrap items-center gap-4"
                >
                  <Link
                    href="/register"
                    className="btn-lime flex items-center gap-2"
                  >
                    START FREE TRIAL
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <a
                    href="#pricing"
                    className="text-sm font-medium text-[#4A4A4A] hover:text-[#1A1A1A] transition-colors"
                  >
                    Want to learn more?{' '}
                    <span className="font-bold text-[#1A1A1A] underline underline-offset-2 cursor-pointer">
                      SEE PRICING
                    </span>
                  </a>
                </motion.div>

                {/* Trust badges */}
                <motion.div
                  initial={reduced ? false : { opacity: 0 }}
                  animate={reduced ? {} : { opacity: 1 }}
                  transition={{ delay: 1.3, duration: 0.5 }}
                  className="flex items-center gap-5 text-sm text-[#6B6B6B]"
                >
                  <span className="flex items-center gap-1.5">
                    <Check className="w-4 h-4 text-[#1A1A1A]" />
                    No credit card
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check className="w-4 h-4 text-[#1A1A1A]" />
                    Setup in 2 minutes
                  </span>
                </motion.div>
              </div>

              {/* Right: Animated Mascot */}
              <motion.div
                initial={reduced ? false : { opacity: 0, x: 30 }}
                animate={reduced ? {} : { opacity: 1, x: 0 }}
                transition={{ delay: 0.5, duration: 0.8, ease: EXPO }}
                className="lg:col-span-2 flex items-center justify-center"
              >
                <HeroRobot />
              </motion.div>
            </div>
          </div>
        </section>

        {/* ─── SECTION 2: DEMO SECTION (AI SIMULATOR) ──────────────── */}
        <section id="how-it-works" className="py-16 px-4 max-w-6xl mx-auto">
          <ScrollReveal>
            <div className="text-center mb-12">
              <h2 className="text-4xl md:text-5xl font-bold mb-4 mono-headline">
                AI qualifies your leads on WhatsApp
              </h2>
              <p className="text-[17px] text-[#4A4A4A] max-w-xl mx-auto leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                No scripts. No manual calling. Just forward a lead's number and watch the AI chat, ask questions, and score them like a senior broker.
              </p>
            </div>

            <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl overflow-hidden shadow-sm">
              <div className="grid md:grid-cols-5">
                {/* Left panel */}
                <div className="md:col-span-2 p-6 border-b md:border-b-0 md:border-r border-[#D4D0C8]">
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-[#1A1A1A]" />
                      <span className="text-sm font-bold text-[#1A1A1A]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>New Lead</span>
                    </div>
                    <span className="text-xs text-[#6B6B6B] font-medium bg-[#F0EDE8] border border-[#D4D0C8] px-2 py-1 rounded-md">
                      Qualifying...
                    </span>
                  </div>

                  <div className="mb-5">
                    <div className="flex items-center gap-2 p-2.5 bg-[#F0EDE8] border border-[#D4D0C8] rounded-lg">
                      <span className="text-xs text-[#4A4A4A] font-mono flex-1">+91 98765 43210</span>
                      <button onClick={() => window.location.href = '/simulator'} className="bg-[#1A1A1A] text-white text-xs font-semibold px-3 py-1 rounded-md hover:bg-[#333]">
                        Run
                      </button>
                    </div>
                  </div>

                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-semibold text-[#6B6B6B] uppercase tracking-wider">Step 2/5</span>
                    </div>
                    <div className="h-1.5 bg-[#E8E4DE] rounded-full">
                      <div className="h-1.5 bg-[#E8F5A8] rounded-full w-2/5 border border-[#D4D0C8]" />
                    </div>
                  </div>

                  <div>
                    <p className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-3">Agent Thoughts</p>
                    <div className="space-y-3 text-xs text-[#4A4A4A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                      <div className="flex gap-2.5">
                        <span className="text-[#1A1A1A] font-bold shrink-0">1.</span>
                        <span>Initiating WhatsApp conversation and sending greeting...</span>
                      </div>
                      <div className="flex gap-2.5">
                        <span className="text-[#1A1A1A] font-bold shrink-0">2.</span>
                        <span>Lead replied with budget range. Analyzing intent signals.</span>
                      </div>
                    </div>
                    <div className="mt-4 flex items-center gap-2 text-xs text-[#6B6B6B]">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#6B6B6B] typing-dot" />
                        <span className="w-1.5 h-1.5 rounded-full bg-[#6B6B6B] typing-dot" />
                        <span className="w-1.5 h-1.5 rounded-full bg-[#6B6B6B] typing-dot" />
                      </div>
                      <span>Thinking...</span>
                    </div>
                  </div>
                </div>

                {/* Right panel */}
                <div className="md:col-span-3 p-4">
                  <div className="bg-[#F0EDE8] border border-[#D4D0C8] rounded-xl overflow-hidden h-full">
                    <div className="bg-[#FAF7F2] border-b border-[#D4D0C8] px-4 py-2.5 flex items-center gap-3">
                      <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
                        <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
                        <div className="w-3 h-3 rounded-full bg-[#28C840]" />
                      </div>
                      <div className="flex-1 bg-[#F0EDE8] border border-[#D4D0C8] rounded-md px-3 py-1 text-[11px] text-[#6B6B6B] font-mono">
                        https://wa.me/beetlelabs-bot
                      </div>
                      <span className="text-[10px] font-bold flex items-center gap-1 text-[#DC2626]">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#DC2626] animate-pulse" />
                        LIVE
                      </span>
                    </div>

                    <div className="p-4 space-y-3 bg-[#EAE0D7]" style={{ minHeight: '200px' }}>
                      <div className="flex justify-start">
                        <div className="max-w-[80%] bg-white rounded-xl rounded-tl-sm p-3 text-sm text-[#1A1A1A] shadow-sm" style={{ fontFamily: 'Inter, sans-serif' }}>
                          <p>Hi! I'm assisting Apex Realty. What's your approximate budget range?</p>
                          <p className="text-[10px] text-[#6B6B6B] text-right mt-1">10:30 AM ✓✓</p>
                        </div>
                      </div>

                      <div className="flex justify-end">
                        <div className="max-w-[80%] bg-[#DCF8C6] rounded-xl rounded-tr-sm p-3 text-sm text-[#1A1A1A] shadow-sm" style={{ fontFamily: 'Inter, sans-serif' }}>
                          <p>Around 40-50 lakhs</p>
                          <p className="text-[10px] text-[#6B6B6B] text-right mt-1">10:31 AM ✓✓</p>
                        </div>
                      </div>

                      <div className="flex justify-start">
                        <div className="bg-white rounded-xl rounded-tl-sm px-4 py-3 shadow-sm">
                          <div className="flex gap-1">
                            <span className="w-2 h-2 rounded-full bg-[#6B6B6B] typing-dot" />
                            <span className="w-2 h-2 rounded-full bg-[#6B6B6B] typing-dot" />
                            <span className="w-2 h-2 rounded-full bg-[#6B6B6B] typing-dot" />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </section>

        {/* ─── SECTION 3: STATS (REGION-AWARE) ───────────────────────── */}
        <section className="py-16 px-4 max-w-6xl mx-auto">
          <ScrollReveal>
            <div className="text-center mb-10">
              <h2 className="text-4xl md:text-5xl font-bold mono-headline">
                Built for {region.name} real estate {regionStats.agentTerm}
              </h2>
            </div>

            <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-8 md:p-10 shadow-sm">
              <div className="grid md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-[#D4D0C8]">
                {[
                  { end: regionStats.coldPct, suffix: '%', label: `of ${regionStats.platform} leads are cold or fake`, sub: 'based on industry data' },
                  { end: 15, suffix: '+', label: 'hours wasted per week', sub: 'on unqualified prospects' },
                  { end: 2, suffix: ' min', label: 'to qualify with AI', sub: 'using AI WhatsApp bot' },
                ].map((stat, i) => (
                  <motion.div
                    key={i}
                    whileHover={{ y: -3 }}
                    transition={{ duration: 0.2 }}
                    className="text-center py-8 px-6"
                  >
                    <div
                      className="text-6xl md:text-7xl font-extrabold text-[#1A1A1A] mb-3 leading-none"
                      style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
                    >
                      <CountUpNumber end={stat.end} suffix={stat.suffix} />
                    </div>
                    <p className="text-base font-semibold text-[#1A1A1A] mb-1" style={{ fontFamily: 'Inter, sans-serif' }}>{stat.label}</p>
                    <p className="text-sm text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>{stat.sub}</p>
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="text-center mt-12">
              <h2 className="text-3xl md:text-4xl font-bold mono-headline mb-3">
                Stop chasing. Start closing deals at scale.
              </h2>
              <p className="text-[17px] text-[#4A4A4A] max-w-2xl mx-auto leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                BeetleLabs multiplies your output without multiplying your hours. Use WhatsApp to engage leads, and let AI agents qualify and score them automatically.
              </p>
            </div>
          </ScrollReveal>
        </section>

        {/* ─── SECTION 3.5: GLOBAL WASTE CALCULATOR ────────────────── */}
        <GlobalWasteCalculator />

        {/* ─── SECTION 4: WORKFLOW (NEW INDEPENDENT 4-CARD FEATURES GRID) ─ */}
        <FeaturesGrid />

        {/* ─── SECTION 5: HOW IT WORKS (3 STEPS) ───────────────────── */}
        <section className="py-16 px-4 max-w-6xl mx-auto">
          {/* Section Header */}
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 30 }}
            whileInView={reduced ? {} : { opacity: 1, y: 0 }}
            viewport={VP}
            transition={{ duration: 0.6, ease: EXPO }}
            className="text-center mb-10"
          >
            <div className="flex items-center justify-center gap-3 mb-4">
              <span className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                HOW IT WORKS
              </span>
              <div className="h-px w-8 bg-[#D4D0C8]" />
              <div className="w-2 h-2 bg-[#E8F5A8] border border-[#D4D0C8]" />
            </div>
            <h2 className="text-4xl md:text-5xl font-bold mono-headline mb-3">
              From WhatsApp to qualified lead in 3 steps
            </h2>
            <p className="text-[17px] text-[#4A4A4A] max-w-xl mx-auto" style={{ fontFamily: 'Inter, sans-serif' }}>
              No apps to install. No complex setup. Just forward a number and let AI do the rest.
            </p>
          </motion.div>

          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-8 md:p-12 shadow-sm">
            {/* Cards stagger container */}
            <motion.div
              variants={reduced ? undefined : howItWorksContainer}
              initial={reduced ? false : 'hidden'}
              whileInView={reduced ? {} : 'visible'}
              viewport={VP60}
              className="grid md:grid-cols-3 gap-8"
            >
              {[
                {
                  num: '01',
                  title: "Forward the lead's number",
                  desc: "Send any lead's phone number to your dedicated BeetleLabs WhatsApp bot. That's it.",
                },
                {
                  num: '02',
                  title: 'AI chats & qualifies',
                  desc: 'Our bot asks about budget, location, timeline, and property type — just like you would. Takes 2 minutes.',
                },
                {
                  num: '03',
                  title: 'Get your score instantly',
                  desc: 'Hot 🔥, Warm 🟡, or Cold 🔵 — with confidence % and full conversation history in your dashboard.',
                },
              ].map((step, i) => (
                <motion.div
                  key={i}
                  variants={reduced ? undefined : howItWorksCard}
                  className="space-y-4"
                >
                  <motion.span
                    className="inline-block bg-[#E8F5A8] border border-[#D4D0C8] text-[#1A1A1A] font-mono text-xs font-bold px-3 py-1 rounded-full cursor-default"
                    whileHover={reduced ? {} : { scale: 1.1, rotate: 5 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 10 }}
                  >
                    {step.num}
                  </motion.span>
                  <h3 className="text-xl font-bold mono-headline">{step.title}</h3>
                  <p className="text-sm text-[#4A4A4A] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                    {step.desc}
                  </p>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* ─── SECTION 6: EARLY ACCESS WAITLIST ────────────────────── */}
        <section className="py-16 px-4 max-w-4xl mx-auto text-center">
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 50, scale: 0.97 }}
            whileInView={reduced ? {} : { opacity: 1, y: 0, scale: 1 }}
            viewport={VP}
            transition={{ duration: 0.7, ease: EXPO }}
            className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-8 md:p-12 shadow-sm"
          >
            {/* Text stagger */}
            <motion.div
              variants={reduced ? undefined : textContainer}
              initial={reduced ? false : 'hidden'}
              whileInView={reduced ? {} : 'visible'}
              viewport={{ once: true }}
            >
              <motion.div variants={reduced ? undefined : textItem} className="flex items-center justify-center gap-3 mb-4">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  EARLY ACCESS
                </span>
                <div className="h-px w-8 bg-[#D4D0C8]" />
                <div className="w-2 h-2 bg-[#E8F5A8] border border-[#D4D0C8]" />
              </motion.div>

              <motion.h2 variants={reduced ? undefined : textItem} className="text-3xl md:text-4xl font-bold mono-headline mb-3">
                Be among the first {regionStats.agentTerm} in {region.name}
              </motion.h2>
              <motion.p variants={reduced ? undefined : textItem} className="text-[16px] text-[#4A4A4A] max-w-xl mx-auto mb-8" style={{ fontFamily: 'Inter, sans-serif' }}>
                We're rolling out to a small group of active brokers. Get 14 days free + 20% off for life as an early user.
              </motion.p>
            </motion.div>

            {waitlistJoined ? (
              <div className="p-4 bg-[#DCFCE7] border border-[#BBF7D0] text-[#15803D] rounded-2xl font-semibold text-sm max-w-md mx-auto">
                🎉 You're on the waitlist! We'll invite you shortly.
              </div>
            ) : (
              <motion.form
                onSubmit={handleWaitlistSubmit}
                initial={reduced ? false : { opacity: 0, y: 20 }}
                whileInView={reduced ? {} : { opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.4, duration: 0.5, ease: EXPO }}
                className="flex flex-col sm:flex-row items-center justify-center gap-3 max-w-md mx-auto mb-4"
              >
                <input
                  type="email"
                  required
                  value={waitlistEmail}
                  onChange={(e) => setWaitlistEmail(e.target.value)}
                  placeholder="Enter your email"
                  className="w-full bg-white border border-[#D4D0C8] rounded-full px-5 py-3 text-sm text-[#1A1A1A] placeholder-[#A0A0A0] focus:outline-none focus:border-[#1A1A1A]"
                />
                <motion.button
                  type="submit"
                  whileHover={reduced ? {} : { scale: 1.03, y: -2 }}
                  whileTap={reduced ? {} : { scale: 0.97 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                  className="btn-lime w-full sm:w-auto shrink-0 justify-center flex items-center gap-1.5 py-3"
                >
                  JOIN WAITLIST →
                </motion.button>
              </motion.form>
            )}

            <motion.p
              className="text-xs text-[#6B6B6B] font-mono mt-3"
              animate={reduced ? {} : { opacity: [0.7, 1, 0.7] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            >
              Limited to 50 brokers. Currently 12 spots left.
            </motion.p>
          </motion.div>
        </section>

        {/* ─── SECTION 6.5: GLOBAL PRICING ──────────────────────────── */}
        <GlobalPricing />

        {/* ─── SECTION 7: SECURITY ──────────────────────────────────── */}
        <section className="py-16 px-4 max-w-6xl mx-auto">
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 30 }}
            whileInView={reduced ? {} : { opacity: 1, y: 0 }}
            viewport={VP}
            transition={{ duration: 0.6, ease: EXPO }}
            className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl overflow-hidden shadow-sm"
          >
            <div className="grid md:grid-cols-5">
              {/* Left column — slides from left */}
              <motion.div
                initial={reduced ? false : { opacity: 0, x: -40 }}
                whileInView={reduced ? {} : { opacity: 1, x: 0 }}
                viewport={VP}
                transition={{ duration: 0.7, ease: EXPO }}
                className="md:col-span-2 p-8 md:p-10 border-b md:border-b-0 md:border-r border-[#D4D0C8]"
              >
                <div className="flex items-center gap-3 mb-6">
                  <span className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    SECURITY
                  </span>
                  <div className="h-px w-8 bg-[#D4D0C8]" />
                  <div className="w-2 h-2 bg-[#E8F5A8] border border-[#D4D0C8]" />
                </div>
                <h2 className="text-3xl font-bold mono-headline mb-4">Your data, handled with care</h2>
                <p className="text-[16px] text-[#4A4A4A] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                  No shortcuts, no excuses. Your lead data is protected by design, not by afterthought.
                </p>
              </motion.div>

              {/* Right column — rows stagger from right */}
              <motion.div
                variants={reduced ? undefined : rowContainer}
                initial={reduced ? false : 'hidden'}
                whileInView={reduced ? {} : 'visible'}
                viewport={VP60}
                className="md:col-span-3 divide-y divide-[#D4D0C8]"
              >
                {[
                  { icon: Lock, title: 'Encryption at rest & in transit', desc: 'All data is protected with TLS 1.3 in transit and AES-256 at rest.' },
                  { icon: ShieldCheck, title: 'Zero training on your data', desc: 'We never use your lead conversations to train AI models. Ever.' },
                  { icon: Database, title: 'You own your data', desc: 'Export all your leads, conversations, and notes anytime. No lock-in.' },
                ].map((item, i) => (
                  <motion.div
                    key={i}
                    variants={reduced ? undefined : rowItem}
                    className="p-6 flex items-start gap-4"
                  >
                    <motion.div
                      className="w-10 h-10 bg-[#F0EDE8] border border-[#D4D0C8] rounded-xl flex items-center justify-center shrink-0"
                      whileHover={reduced ? {} : { scale: 1.1, rotate: 3 }}
                      transition={{ type: 'spring', stiffness: 300 }}
                    >
                      <item.icon className="w-4 h-4 text-[#1A1A1A]" />
                    </motion.div>
                    <div>
                      <h4 className="text-sm font-bold text-[#1A1A1A] mb-1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                        {item.title}
                      </h4>
                      <p className="text-xs text-[#6B6B6B] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {item.desc}
                      </p>
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            </div>
          </motion.div>
        </section>

        {/* ─── SECTION 8: FAQ ───────────────────────────────────────── */}
        <section className="py-16 px-4 max-w-3xl mx-auto">
          {/* Header fade-up */}
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 30 }}
            whileInView={reduced ? {} : { opacity: 1, y: 0 }}
            viewport={VP}
            transition={{ duration: 0.6, ease: EXPO }}
            className="text-center mb-12"
          >
            <div className="flex items-center justify-center gap-3 mb-5">
              <span className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                FAQ
              </span>
              <div className="h-px w-8 bg-[#D4D0C8]" />
              <div className="w-2 h-2 bg-[#E8F5A8] border border-[#D4D0C8]" />
            </div>
            <h2 className="text-4xl font-bold text-[#1A1A1A] tracking-tight" style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}>
              Have Questions?{' '}
              <span className="font-extrabold">We've Answers!</span>
            </h2>
          </motion.div>

          {/* FAQ items stagger */}
          <motion.div
            variants={reduced ? undefined : faqContainer}
            initial={reduced ? false : 'hidden'}
            whileInView={reduced ? {} : 'visible'}
            viewport={{ once: true }}
            className="border-b border-[#D4D0C8]"
          >
            {faqs.map((faq, i) => (
              <motion.div
                key={i}
                variants={reduced ? undefined : faqItem}
                className="border-t border-[#D4D0C8]"
              >
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between py-5 text-left gap-4"
                >
                  <span
                    className="text-base font-semibold text-[#1A1A1A]"
                    style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
                  >
                    {faq.q}
                  </span>
                  <motion.div
                    animate={{ rotate: openFaq === i ? 180 : 0 }}
                    transition={{ duration: 0.3, ease: EXPO }}
                  >
                    <ChevronDown className="w-5 h-5 text-[#6B6B6B] shrink-0" />
                  </motion.div>
                </button>
                <AnimatePresence>
                  {openFaq === i && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: EXPO }}
                      className="overflow-hidden"
                    >
                      <div className="pb-5 text-[16px] text-[#4A4A4A] leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                        {faq.a}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </motion.div>
        </section>

        {/* ─── SECTION 9: PRICING — handled by GlobalPricing above (section 6.5) ─── */}

        {/* ─── SECTION 10: FINAL CTA ────────────────────────────────── */}
        <section className="py-16 px-4 max-w-6xl mx-auto pb-28">
          <motion.div
            initial={reduced ? false : { opacity: 0, y: 60, scale: 0.98 }}
            whileInView={reduced ? {} : { opacity: 1, y: 0, scale: 1 }}
            viewport={VP}
            transition={{ duration: 0.7, ease: EXPO }}
            className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl overflow-hidden flex shadow-sm"
          >
            <div className="w-1.5 bg-[#3B82F6] shrink-0" />

            <div className="flex-1 p-8 md:p-12">
              <div className="flex gap-2 mb-8">
                <div className="w-3 h-3 rounded-full bg-[#FF5F57]" />
                <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
                <div className="w-3 h-3 rounded-full bg-[#28C840]" />
              </div>

              <div className="grid md:grid-cols-5 gap-10 items-center">
                {/* Left content stagger */}
                <motion.div
                  variants={reduced ? undefined : ctaContent}
                  initial={reduced ? false : 'hidden'}
                  whileInView={reduced ? {} : 'visible'}
                  viewport={{ once: true }}
                  className="md:col-span-3 space-y-6"
                >
                  <motion.h2 variants={reduced ? undefined : ctaItem} className="text-4xl md:text-5xl font-bold mono-headline">
                    Join us today!
                  </motion.h2>
                  <motion.p variants={reduced ? undefined : ctaItem} className="text-[17px] text-[#4A4A4A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    Start qualifying leads for free. No credit card required.
                  </motion.p>
                  <motion.div variants={reduced ? undefined : ctaItem} className="flex flex-wrap gap-4">
                    <motion.div
                      whileHover={reduced ? {} : { scale: 1.03, y: -2, boxShadow: '0 10px 30px -10px rgba(217, 249, 157, 0.5)' }}
                      whileTap={reduced ? {} : { scale: 0.98 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                    >
                      <Link href="/register" className="btn-lime flex items-center gap-2">
                        START FREE TRIAL
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </motion.div>
                    <motion.div
                      whileHover={reduced ? {} : { scale: 1.03, y: -2 }}
                      whileTap={reduced ? {} : { scale: 0.98 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
                    >
                      <Link href="/dashboard" className="btn-outline">
                        OPEN DASHBOARD
                      </Link>
                    </motion.div>
                  </motion.div>
                </motion.div>

                {/* Right: Emoji icons — spring bounce */}
                <motion.div
                  variants={reduced ? undefined : iconContainer}
                  initial={reduced ? false : 'hidden'}
                  whileInView={reduced ? {} : 'visible'}
                  viewport={{ once: true }}
                  className="md:col-span-2 flex items-center justify-center gap-4"
                >
                  {[
                    { emoji: '🤖', bg: 'bg-blue-200', border: 'border-blue-300' },
                    { emoji: '💬', bg: 'bg-purple-200', border: 'border-purple-300' },
                    { emoji: '🔥', bg: 'bg-pink-200', border: 'border-pink-300' },
                  ].map((item, i) => (
                    <motion.div
                      key={i}
                      variants={reduced ? undefined : iconItem}
                      whileHover={reduced ? {} : { scale: 1.15, rotate: 8 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 12 }}
                      className={`w-16 h-20 rounded-2xl ${item.bg} border ${item.border} flex items-center justify-center text-2xl`}
                    >
                      {item.emoji}
                    </motion.div>
                  ))}
                </motion.div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* ─── FOOTER ───────────────────────────────────────────────── */}
        <motion.footer
          initial={reduced ? false : { opacity: 0, y: 30 }}
          whileInView={reduced ? {} : { opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, ease: EXPO }}
          className="border-t border-[#D4D0C8] py-12 px-4 max-w-6xl mx-auto"
        >
          <div className="grid md:grid-cols-3 gap-8 mb-10">
            <div>
              <BeetleLabsLogo href="/" iconSize={24} textSize="text-xl" />
              <p className="text-sm text-[#6B6B6B] mt-2 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                Qualify real estate leads smarter with AI.
              </p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-[#6B6B6B] mb-4">Product</p>
              <div className="space-y-2.5 text-sm text-[#4A4A4A]">
                <Link href="/register" className="block hover:text-[#1A1A1A] transition-colors">Sign Up</Link>
                <Link href="#pricing" className="block hover:text-[#1A1A1A] transition-colors">Pricing</Link>
                <Link href="#how-it-works" className="block hover:text-[#1A1A1A] transition-colors">How it works</Link>
              </div>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest text-[#6B6B6B] mb-4">Contact</p>
              <div className="space-y-2.5 text-sm text-[#4A4A4A]">
                <a href="mailto:support@beetlelabs.ai" className="block hover:text-[#1A1A1A] transition-colors">Contact Us</a>
                <span className="block hover:text-[#1A1A1A] cursor-pointer transition-colors">Privacy Policy</span>
                <span className="block hover:text-[#1A1A1A] cursor-pointer transition-colors">Terms of Service</span>
              </div>
            </div>
          </div>

          <div className="border-t border-[#D4D0C8] pt-6 flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-[#6B6B6B]">
            <span>© 2026 BeetleLabs. All rights reserved.</span>
            <div className="flex gap-6">
              <span className="hover:text-[#1A1A1A] cursor-pointer transition-colors">Privacy Policy</span>
              <span className="hover:text-[#1A1A1A] cursor-pointer transition-colors">Terms of Service</span>
            </div>
          </div>
        </motion.footer>
      </div>
    </>
  );
}
