'use client';

import React, { useRef, useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageCircle, Globe, Building2, Upload, UserPlus,
  Sparkles, Phone, Mail, Calendar, Clock,
  CheckCircle2, Circle, Zap, Target, TrendingUp,
  Star, ArrowRight, MapPin, Home, SlidersHorizontal,
  Layers, User,
} from 'lucide-react';
import { useReducedMotion } from '@/lib/animations';

// ─── Easing ────────────────────────────────────────────────────────────────────
const EASE = [0.16, 1, 0.3, 1] as const;

// ─── Static Data ───────────────────────────────────────────────────────────────
const LEAD_SOURCES = [
  { label: 'WhatsApp',         Icon: MessageCircle, color: '#22C55E' },
  { label: 'Website',          Icon: Globe,         color: '#3B82F6' },
  { label: 'Property Portals', Icon: Building2,     color: '#EC4899' },
  { label: 'CSV Import',       Icon: Upload,        color: '#2563EB' },
  { label: 'Manual Entry',     Icon: UserPlus,      color: '#6366F1' },
];

const FLOATING_LEADS = [
  { left: '44%', top: '2%',  scale: 0.93, delay: 0.00 },
  { left: '68%', top: '0%',  scale: 0.80, delay: 0.07 },
  { left: '84%', top: '13%', scale: 0.70, delay: 0.14 },
  { left: '48%', top: '25%', scale: 0.85, delay: 0.05 },
  { left: '72%', top: '23%', scale: 0.90, delay: 0.11 },
  { left: '56%', top: '44%', scale: 0.97, delay: 0.02 },
  { left: '80%', top: '47%', scale: 0.74, delay: 0.18 },
  { left: '48%', top: '64%', scale: 0.86, delay: 0.08 },
  { left: '70%', top: '68%', scale: 0.92, delay: 0.15 },
  { left: '56%', top: '84%', scale: 0.76, delay: 0.22 },
];

const ANALYSIS_ROWS = [
  { label: 'Budget',        value: '₹1Cr – ₹1.5Cr',         Icon: User,              pill: false },
  { label: 'Location',      value: 'Gurgaon',               Icon: MapPin,            pill: false },
  { label: 'Property Type', value: '3 BHK',                 Icon: Home,              pill: false },
  { label: 'Timeline',      value: '1–3 months',            Icon: Clock,             pill: false },
  { label: 'Intent',        value: 'High',                  Icon: Target,            pill: true  },
  { label: 'Preferences',   value: 'Good schools, parking', Icon: SlidersHorizontal, pill: false },
];

const MATCHES = [
  { label: 'Match 1', score: 96, bar1: '78%', bar2: '58%', tag: 'Luxury 3 BHK',    best: true  },
  { label: 'Match 2', score: 88, bar1: '70%', bar2: '50%', tag: 'Golf Course Ext.', best: false },
  { label: 'Match 3', score: 82, bar1: '64%', bar2: '46%', tag: 'Cyber City Hub',   best: false },
];

const ACTIONS = [
  { label: 'Call the lead',       Icon: Phone,    color: '#22C55E' },
  { label: 'Send properties',     Icon: Mail,     color: '#2563EB' },
  { label: 'Schedule site visit', Icon: Calendar, color: '#EC4899' },
  { label: 'Set follow-up',       Icon: Clock,    color: '#F59E0B' },
];

const PIPELINE_STEPS = [
  { label: 'Qualified',   done: true,  active: false },
  { label: 'Contacted',   done: true,  active: false },
  { label: 'Site Visit',  done: true,  active: false },
  { label: 'Negotiation', done: false, active: true  },
  { label: 'Booking',     done: false, active: false },
  { label: 'Closed',      done: false, active: false },
];

const BENEFITS = [
  { Icon: Zap,        title: 'Less Manual Work',  sub: 'Automate repetitive tasks',  color: '#22C55E', bg: '#DCFCE7' },
  { Icon: Clock,      title: 'Faster Follow-ups', sub: 'Never miss an opportunity',  color: '#3B82F6', bg: '#DBEAFE' },
  { Icon: Target,     title: 'Better Matches',    sub: 'Connect the right buyers',   color: '#8B5CF6', bg: '#EDE9FE' },
  { Icon: TrendingUp, title: 'More Deals Closed', sub: 'A more profitable business', color: '#22C55E', bg: '#DCFCE7' },
];

// Per-step accent colors for badge + background glow
const STEP_ACCENT = ['#16B866', '#2563EB', '#7C3AED', '#2563EB', '#16B866'] as const;
const STEP_BG     = ['#DCFCE7', '#DBEAFE', '#EDE9FE', '#DBEAFE', '#DCFCE7'] as const;
const STEP_ARROW_ACTIVE = ['#16B866', '#2563EB', '#7C3AED', '#2563EB'] as const;

// ─── Sub-visual components (one per stage) ─────────────────────────────────────

function Visual01({ active, reduced }: { active: boolean; reduced: boolean }) {
  return (
    <div className="relative min-h-[260px]" aria-hidden="true">
      {/* Source pill buttons */}
      <div className="flex flex-col gap-2 w-[138px] relative z-20">
        {LEAD_SOURCES.map(({ label, Icon, color }, i) => (
          <motion.div
            key={label}
            animate={active ? { opacity: 1, x: 0 } : { opacity: 0.55, x: 0 }}
            transition={{ duration: 0.22, ease: EASE, delay: active ? i * 0.05 : 0 }}
            className="flex items-center gap-2 bg-white border rounded-xl px-2.5 py-1.5 text-[11px] font-semibold text-[#1E293B]"
            style={{
              borderColor: active ? color + '55' : '#E2E8F0',
              boxShadow: active ? `0 2px 10px ${color}18` : '0 1px 2px rgba(0,0,0,0.04)',
              transition: 'border-color 0.2s, box-shadow 0.2s',
            }}
          >
            <Icon className="w-3.5 h-3.5 shrink-0" style={{ color }} />
            <span className="truncate">{label}</span>
          </motion.div>
        ))}
      </div>
      {/* Floating "New Lead" cards */}
      <div className="absolute inset-0 pointer-events-none">
        {FLOATING_LEADS.map((lead, i) => (
          <motion.div
            key={i}
            animate={reduced ? { opacity: active ? 1 : 0 } : {
              opacity:  active ? [0, 1] : [0],
              y:        active ? [6, 0] : [0],
              scale:    active ? [0.94, 1] : [1],
            }}
            transition={{ duration: 0.30, ease: EASE, delay: active ? lead.delay : 0 }}
            className="absolute bg-white border border-[#E2E8F0] rounded-xl px-2 py-1 shadow-xs flex items-center gap-1.5"
            style={{
              left: lead.left,
              top: lead.top,
              transform: `scale(${lead.scale})`,
              transformOrigin: 'left top',
            }}
          >
            <div className="w-3.5 h-3.5 rounded-full bg-[#DCFCE7] flex items-center justify-center shrink-0">
              <User className="w-2.5 h-2.5 text-[#16A34A]" />
            </div>
            <span className="text-[9px] font-semibold text-[#334155] whitespace-nowrap">New Lead</span>
          </motion.div>
        ))}
      </div>
      {/* Status chip */}
      <AnimatePresence>
        {active && (
          <motion.div
            key="s1-status"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            transition={{ duration: 0.20, ease: EASE, delay: 0.18 }}
            className="absolute bottom-0 left-0 flex items-center gap-1.5 bg-[#DCFCE7] border border-[#86EFAC] rounded-full px-2.5 py-1"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] animate-pulse" />
            <span className="text-[9.5px] font-bold text-[#15803D]">Leads capturing…</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Visual02({ active, reduced }: { active: boolean; reduced: boolean }) {
  const [phase, setPhase] = useState<'idle' | 'analyzing' | 'done'>('idle');

  useEffect(() => {
    if (!active) { setPhase('idle'); return; }
    setPhase('analyzing');
    const t = setTimeout(() => setPhase('done'), reduced ? 0 : 700);
    return () => clearTimeout(t);
  }, [active, reduced]);

  return (
    <div className="w-full max-w-[230px]" aria-hidden="true">
      <motion.div
        animate={{ scale: active ? 1 : 0.98, opacity: active ? 1 : 0.6 }}
        transition={{ duration: 0.22, ease: EASE }}
        className="bg-white border rounded-2xl p-3.5 shadow-xs"
        style={{
          borderColor: active ? '#BFDBFE' : '#E2E8F0',
          boxShadow: active ? '0 4px 18px rgba(37,99,235,0.10)' : '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        {/* Card header */}
        <div className="flex items-center justify-between gap-2 mb-3 pb-2 border-b border-[#F1F5F9]">
          <div className="flex items-center gap-1.5">
            <motion.div
              animate={active && phase === 'analyzing' && !reduced
                ? { rotate: [0, 15, -15, 0], scale: [1, 1.15, 1] }
                : { rotate: 0, scale: 1 }}
              transition={{ duration: 0.6, ease: 'easeInOut', repeat: phase === 'analyzing' ? Infinity : 0 }}
            >
              <Sparkles className="w-3.5 h-3.5" style={{ color: '#2563EB' }} />
            </motion.div>
            <span className="text-[11px] font-bold text-[#0B172A]">
              {phase === 'analyzing' ? 'Analyzing…' : 'Lead Analyzed'}
            </span>
          </div>
          <AnimatePresence mode="wait">
            {phase === 'done' && (
              <motion.span
                key="live"
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.85 }}
                transition={{ duration: 0.18 }}
                className="flex items-center gap-1 text-[9px] text-[#16A34A] font-semibold bg-[#DCFCE7] px-1.5 py-0.5 rounded-full"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] animate-pulse" />
                Live
              </motion.span>
            )}
            {phase === 'analyzing' && (
              <motion.span
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-1 text-[9px] text-[#2563EB] font-semibold bg-[#DBEAFE] px-1.5 py-0.5 rounded-full"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#2563EB] animate-pulse" />
                Working…
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        {/* Rows */}
        <div className="space-y-2">
          {ANALYSIS_ROWS.map(({ label, value, Icon, pill }, i) => (
            <motion.div
              key={label}
              animate={phase === 'done'
                ? { opacity: 1, y: 0 }
                : { opacity: 0.25, y: 3 }}
              transition={{ duration: 0.22, ease: EASE, delay: phase === 'done' ? i * 0.045 : 0 }}
              className="flex items-start justify-between gap-2"
            >
              <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                <Icon className="w-3 h-3 text-[#94A3B8]" />
                <span className="text-[10px] text-[#64748B] font-medium">{label}</span>
              </div>
              {pill ? (
                <span className="text-[9.5px] bg-[#DCFCE7] text-[#16A34A] rounded-md px-2 py-0.5 font-bold">
                  {value}
                </span>
              ) : (
                <span className="text-[10px] font-bold text-[#0B172A] text-right leading-snug">{value}</span>
              )}
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

function Visual03({ active, reduced }: { active: boolean; reduced: boolean }) {
  return (
    <div className="flex flex-col gap-2.5 w-full max-w-[230px]" aria-hidden="true">
      {MATCHES.map(({ label, score, bar1, bar2, tag, best }, i) => (
        <motion.div
          key={label}
          animate={active
            ? { opacity: 1, y: 0, scale: best ? 1.015 : 1 }
            : { opacity: best ? 0.7 : 0.45, y: 0, scale: 1 }}
          transition={{ duration: 0.25, ease: EASE, delay: active ? i * 0.07 : 0 }}
          className="bg-white rounded-xl p-2.5 flex items-center gap-3"
          style={{
            border: active && best ? '1.5px solid #86EFAC' : '1px solid #E2E8F0',
            boxShadow: active && best ? '0 4px 14px rgba(22,184,102,0.14)' : '0 1px 2px rgba(0,0,0,0.04)',
          }}
        >
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: active && best ? '#DCFCE7' : '#F8FAFC', border: '1px solid #E2E8F0' }}
          >
            <Layers className="w-3.5 h-3.5" style={{ color: active && best ? '#16A34A' : '#2563EB' }} />
          </div>
          <div className="flex-1 min-w-0 space-y-1">
            <div className="flex items-center justify-between gap-1">
              <span className="text-[11px] font-bold text-[#0B172A]">{label}</span>
              {best && active && (
                <motion.span
                  initial={reduced ? false : { opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.18, delay: 0.15 }}
                  className="text-[8.5px] bg-[#DCFCE7] text-[#15803D] font-bold px-1.5 py-0.5 rounded-full"
                >
                  Best Match
                </motion.span>
              )}
              {(!best || !active) && (
                <span className="text-[9px] text-[#94A3B8] font-medium truncate">{tag}</span>
              )}
            </div>
            <div className="space-y-1">
              <motion.div
                className="h-1.5 rounded-full bg-[#CBD5E1]"
                animate={{ width: active ? bar1 : '30%' }}
                transition={{ duration: 0.45, ease: EASE, delay: i * 0.07 }}
              />
              <motion.div
                className="h-1.5 rounded-full bg-[#E2E8F0]"
                animate={{ width: active ? bar2 : '20%' }}
                transition={{ duration: 0.45, ease: EASE, delay: i * 0.07 + 0.07 }}
              />
            </div>
          </div>
          <motion.div
            animate={active ? { scale: 1, opacity: 1 } : { scale: 0.85, opacity: 0.5 }}
            transition={{ duration: 0.22, ease: EASE, delay: i * 0.07 }}
            className="shrink-0 rounded-md px-1.5 py-0.5 text-[10.5px] font-extrabold"
            style={{
              background: active && best ? '#16B866' : '#DCFCE7',
              color:      active && best ? '#fff'    : '#16A34A',
            }}
          >
            {score}%
          </motion.div>
        </motion.div>
      ))}
    </div>
  );
}

function Visual04({ active, reduced }: { active: boolean; reduced: boolean }) {
  return (
    <div className="w-full max-w-[230px]" aria-hidden="true">
      <motion.div
        animate={{ scale: active ? 1 : 0.98, opacity: active ? 1 : 0.6 }}
        transition={{ duration: 0.22, ease: EASE }}
        className="bg-white border rounded-2xl p-3.5 shadow-xs"
        style={{
          borderColor: active ? '#BFDBFE' : '#E2E8F0',
          boxShadow: active ? '0 4px 18px rgba(37,99,235,0.10)' : '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#F1F5F9]">
          <span className="text-[11px] font-bold text-[#0B172A]">Recommended Actions</span>
          <motion.span
            animate={active ? { opacity: 1 } : { opacity: 0.4 }}
            className="text-[9px] bg-[#EFF6FF] text-[#2563EB] font-bold px-1.5 py-0.5 rounded-full"
          >
            4 Pending
          </motion.span>
        </div>
        <div className="space-y-2.5">
          {ACTIONS.map(({ label, Icon, color }, i) => (
            <motion.div
              key={label}
              animate={active
                ? { opacity: 1, x: 0 }
                : { opacity: 0.35, x: 0 }}
              transition={{ duration: 0.22, ease: EASE, delay: active ? i * 0.07 : 0 }}
              className="flex items-center justify-between gap-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <motion.div
                  className="w-5 h-5 rounded-md flex items-center justify-center shrink-0"
                  animate={{ backgroundColor: active ? color + '25' : color + '10' }}
                  transition={{ duration: 0.22 }}
                >
                  <Icon className="w-3 h-3" style={{ color }} />
                </motion.div>
                <span className="text-[10.5px] text-[#334155] font-semibold truncate">{label}</span>
              </div>
              <motion.span
                animate={active
                  ? { borderColor: '#94A3B8', color: '#0B172A', backgroundColor: '#fff' }
                  : { borderColor: '#E2E8F0', color: '#CBD5E1', backgroundColor: '#fff' }}
                transition={{ duration: 0.18, delay: i * 0.05 }}
                className="text-[9.5px] font-semibold border rounded-lg px-2 py-0.5 shrink-0"
              >
                Start
              </motion.span>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}

function Visual05({ active, reduced }: { active: boolean; reduced: boolean }) {
  // When active, animate pipeline progression: steps become done one by one
  const [doneCount, setDoneCount] = useState(3); // starts at 3 done
  const [showBadge, setShowBadge] = useState(false);

  useEffect(() => {
    if (!active) { setDoneCount(3); setShowBadge(false); return; }
    if (reduced) { setDoneCount(6); setShowBadge(true); return; }

    let count = 3;
    const timers: ReturnType<typeof setTimeout>[] = [];
    // Animate steps 4, 5, 6 becoming "done"
    [300, 550, 800].forEach((delay, idx) => {
      const t = setTimeout(() => {
        count = 4 + idx;
        setDoneCount(count);
      }, delay);
      timers.push(t);
    });
    const badge = setTimeout(() => setShowBadge(true), 1050);
    timers.push(badge);
    return () => timers.forEach(clearTimeout);
  }, [active, reduced]);

  return (
    <div className="flex items-start gap-3 w-full max-w-[260px]" aria-hidden="true">
      {/* Pipeline card */}
      <motion.div
        animate={{ scale: active ? 1 : 0.98, opacity: active ? 1 : 0.6 }}
        transition={{ duration: 0.22, ease: EASE }}
        className="bg-white border rounded-2xl p-3 shadow-xs flex-1"
        style={{
          borderColor: active ? '#86EFAC' : '#E2E8F0',
          boxShadow: active ? '0 4px 16px rgba(22,184,102,0.10)' : '0 1px 2px rgba(0,0,0,0.04)',
        }}
      >
        <div className="text-[11px] font-bold text-[#0B172A] mb-2 pb-1.5 border-b border-[#F1F5F9]">
          Deal Pipeline
        </div>
        <div className="relative space-y-1.5 pl-0.5">
          <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[#E2E8F0]" />
          {PIPELINE_STEPS.map(({ label }, i) => {
            const isDone   = i < doneCount;
            const isActive = i === doneCount && i < 6;
            return (
              <motion.div
                key={label}
                animate={{ opacity: isDone || isActive ? 1 : 0.35 }}
                transition={{ duration: 0.18 }}
                className="flex items-center gap-2 relative z-10"
              >
                {isDone ? (
                  <motion.div
                    initial={reduced ? false : { scale: 0.5, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 22 }}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-[#16B866]" />
                  </motion.div>
                ) : isActive ? (
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-[#2563EB] bg-white shrink-0 flex items-center justify-center">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#2563EB]" />
                  </div>
                ) : (
                  <Circle className="w-3.5 h-3.5 shrink-0 text-[#CBD5E1]" />
                )}
                <span
                  className="text-[9.5px] font-semibold leading-tight"
                  style={{
                    color: isDone ? '#1E293B' : isActive ? '#2563EB' : '#94A3B8',
                    fontWeight: isActive ? 700 : undefined,
                  }}
                >
                  {label}
                </span>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* Deal Closed badge */}
      <div className="relative shrink-0 flex flex-col items-center justify-center mt-6">
        <AnimatePresence>
          {showBadge && (
            <motion.div
              key="deal-badge"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 420, damping: 20 }}
            >
              {/* Spark rays */}
              <div className="absolute -top-3 -right-1 flex flex-col items-end gap-0.5" aria-hidden="true">
                <div className="w-2   h-0.5 bg-[#16B866] rotate-45  rounded-full" />
                <div className="w-2.5 h-0.5 bg-[#16B866] rotate-12  rounded-full" />
                <div className="w-1.5 h-0.5 bg-[#16B866] -rotate-30 rounded-full" />
              </div>
              <div
                className="w-[68px] h-[68px] rounded-full bg-[#F0FDF4] border-2 border-[#86EFAC] flex flex-col items-center justify-center"
                style={{ boxShadow: '0 6px 28px rgba(22,184,102,0.28)' }}
              >
                <Star className="w-4 h-4 text-[#16B866] mb-0.5" fill="#16B866" />
                <div className="text-[9px] font-extrabold text-[#0B172A] text-center leading-tight">
                  Deal<br />Closed
                </div>
              </div>
            </motion.div>
          )}
          {!showBadge && (
            <motion.div
              key="deal-inactive"
              initial={{ opacity: 0.4 }}
              animate={{ opacity: 0.4 }}
              exit={{ opacity: 0 }}
              className="w-[68px] h-[68px] rounded-full bg-[#F8FAFC] border-2 border-[#E2E8F0] flex flex-col items-center justify-center"
            >
              <Star className="w-4 h-4 text-[#CBD5E1] mb-0.5" />
              <div className="text-[9px] font-bold text-[#94A3B8] text-center leading-tight">
                Deal<br />Closed
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ─── Stage Header Button ────────────────────────────────────────────────────────
interface StageHeaderProps {
  num: string;
  title: string;
  desc: string;
  accentColor: string;
  badgeBg: string;
  active: boolean;
  reduced: boolean;
  onActivate: () => void;
}
function StageHeader({ num, title, desc, accentColor, badgeBg, active, reduced, onActivate }: StageHeaderProps) {
  return (
    <button
      type="button"
      className="w-full text-left mb-4 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 rounded-xl transition-none"
      style={{ focusRingColor: accentColor } as React.CSSProperties}
      onPointerEnter={onActivate}
      onFocus={onActivate}
      onClick={onActivate}
      aria-pressed={active}
    >
      <motion.div
        animate={reduced ? {} : { opacity: active ? 1 : 0.60, scale: active ? 1 : 0.98 }}
        transition={{ duration: 0.20, ease: EASE }}
        className="select-none"
      >
        <motion.div
          className="w-8 h-8 rounded-full text-[11px] font-extrabold flex items-center justify-center mb-2 shadow-sm"
          animate={{
            backgroundColor: active ? accentColor : badgeBg,
            color: active ? '#fff' : accentColor,
            scale: active ? 1.08 : 1,
          }}
          transition={{ duration: 0.20, ease: EASE }}
        >
          {num}
        </motion.div>
        <h3
          className="text-[14px] sm:text-[15px] font-extrabold leading-tight mb-0.5"
          style={{ color: active ? '#0B172A' : '#334155' }}
        >
          {title}
        </h3>
        <p className="text-[11px] text-[#64748B] leading-snug">{desc}</p>
      </motion.div>
    </button>
  );
}

// ─── Arrow Divider ──────────────────────────────────────────────────────────────
function ArrowDivider({ activeLeft, activeRight, color }: { activeLeft: boolean; activeRight: boolean; color: string }) {
  const lit = activeLeft || activeRight;
  return (
    <div className="hidden lg:flex flex-col items-center justify-center px-1 relative" aria-hidden="true">
      <motion.div
        className="h-36 border-r-2 border-dotted"
        animate={{ borderColor: lit ? color + '88' : '#CBD5E1' + '70' }}
        transition={{ duration: 0.22 }}
      />
      <motion.div
        animate={{ color: lit ? color : '#CBD5E1', scale: lit ? 1.15 : 1 }}
        transition={{ duration: 0.22 }}
      >
        <ArrowRight className="w-4 h-4 my-1" />
      </motion.div>
      <motion.div
        className="h-36 border-r-2 border-dotted"
        animate={{ borderColor: lit ? color + '88' : '#CBD5E1' + '70' }}
        transition={{ duration: 0.22 }}
      />
    </div>
  );
}

// ─── Pointer-position → active step calculator ────────────────────────────────
// Splits the track container into 5 equal bands with a ±2 % hysteresis buffer
// at each boundary so rapid boundary-crossing doesn't flicker.
const BAND = 1 / 5; // 0.20 each
const BUFFER = 0.02; // 2% deadband

function calcStep(relX: number, prev: number): 1 | 2 | 3 | 4 | 5 {
  // Raw band index 0-4
  const raw = Math.floor(Math.min(relX, 0.9999) / BAND); // 0..4
  const candidate = (raw + 1) as 1 | 2 | 3 | 4 | 5;
  if (candidate === prev) return prev as 1 | 2 | 3 | 4 | 5;

  // Hysteresis: require pointer to move BUFFER beyond the boundary before switching
  const boundaryBetween = Math.max(raw, prev - 1) * BAND; // lower boundary of candidate
  const pastBoundary =
    candidate > prev
      ? relX > boundaryBetween + BUFFER          // moving right: must be 2% past boundary
      : relX < boundaryBetween + BAND - BUFFER;  // moving left:  must be 2% before boundary

  return pastBoundary ? candidate : (prev as 1 | 2 | 3 | 4 | 5);
}

// ─── Main Component ─────────────────────────────────────────────────────────────
export default function HowItWorksSection() {
  const reduced = useReducedMotion();
  const sectionRef  = useRef<HTMLElement>(null);
  const trackAreaRef = useRef<HTMLDivElement>(null);
  const leaveTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Mutable ref holds last computed step so pointer handler avoids setState spam
  const lastStepRef  = useRef<1 | 2 | 3 | 4 | 5>(1);

  const [inView, setInView] = useState(false);
  const [activeStep, setActiveStep] = useState<1 | 2 | 3 | 4 | 5>(1);

  // IntersectionObserver: reveal header + benefit strip once in viewport
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) { setInView(true); obs.disconnect(); } },
      { threshold: 0.15 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Cleanup leave-timer on unmount
  useEffect(() => () => { if (leaveTimer.current) clearTimeout(leaveTimer.current); }, []);

  // ── Core pointer-move handler ───────────────────────────────────────────────
  // Reads pointer X relative to the track container and maps it to step 1–5.
  // State is updated ONLY when the computed step actually changes → no spam.
  const handlePointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const el = trackAreaRef.current;
    if (!el) return;
    // Cancel any pending leave-reset so it doesn't fire mid-interaction
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
    const rect = el.getBoundingClientRect();
    const relX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const next = calcStep(relX, lastStepRef.current);
    if (next !== lastStepRef.current) {
      lastStepRef.current = next;
      setActiveStep(next);
    }
  }, []);

  // ── Pointer leaves the track area ──────────────────────────────────────────
  // Wait 800ms then softly return to step 1 so the section looks complete.
  const handlePointerLeave = useCallback(() => {
    leaveTimer.current = setTimeout(() => {
      lastStepRef.current = 1;
      setActiveStep(1);
    }, 800);
  }, []);

  // ── Keyboard / tap fallback (buttons inside each stage) ────────────────────
  const activate = useCallback((step: 1 | 2 | 3 | 4 | 5) => {
    if (leaveTimer.current) { clearTimeout(leaveTimer.current); leaveTimer.current = null; }
    lastStepRef.current = step;
    setActiveStep(step);
  }, []);

  const headerAnim = inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 18 };
  const footerAnim = inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 18 };

  return (
    <section
      id="how-it-works"
      ref={sectionRef}
      className="relative py-20 lg:py-28 bg-white overflow-hidden"
      aria-labelledby="hiw-headline"
    >
      {/* ─── SVG FLOW BACKGROUND ─────────────────────────────────────────── */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <svg className="absolute w-full h-full" viewBox="0 0 1440 700" fill="none" preserveAspectRatio="xMidYMid slice">
          <defs>
            <linearGradient id="hiwBg2" x1="0%" y1="50%" x2="100%" y2="50%">
              <stop offset="0%"   stopColor="#E8FDF0" stopOpacity="0.90" />
              <stop offset="22%"  stopColor="#E8FDF0" stopOpacity="0.80" />
              <stop offset="38%"  stopColor="#EFF6FF" stopOpacity="0.72" />
              <stop offset="55%"  stopColor="#F5F3FF" stopOpacity="0.68" />
              <stop offset="72%"  stopColor="#F0FDF4" stopOpacity="0.74" />
              <stop offset="88%"  stopColor="#E8FDF0" stopOpacity="0.86" />
              <stop offset="100%" stopColor="#DCFCE7" stopOpacity="0.95" />
            </linearGradient>
          </defs>
          <path
            d="M 0 60 C 140 80, 310 200, 460 220 C 600 238, 760 244, 920 244
               C 1080 244, 1230 244, 1360 250 C 1420 253, 1440 275, 1440 350
               C 1440 425, 1420 448, 1360 452 C 1230 460, 1080 460, 920 460
               C 760 460, 600 466, 460 484 C 310 502, 140 600, 0 628 Z"
            fill="url(#hiwBg2)"
          />
        </svg>
      </div>

      {/* ─── PAGE CONTAINER ──────────────────────────────────────────────── */}
      <div className="relative max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8">

        {/* ─── HEADER ──────────────────────────────────────────────────── */}
        <motion.div
          className="text-center mb-10 lg:mb-14 relative"
          initial={{ opacity: 0, y: 18 }}
          animate={headerAnim}
          transition={{ duration: 0.55, ease: EASE }}
        >
          <div className="inline-flex items-center justify-center mb-4">
            <span
              className="bg-[#E8F5E9] text-[#1E293B] rounded-full text-[11px] font-bold uppercase tracking-[0.2em] px-4 py-1.5 leading-tight"
              style={{ fontFamily: 'JetBrains Mono, Geist Mono, monospace' }}
            >
              HOW IT WORKS
            </span>
          </div>
          <h2
            id="hiw-headline"
            className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1] mb-4"
          >
            <span className="text-[#0B172A]">From Lead to </span>
            <span className="text-[#16B866]">Deal.</span>
          </h2>
          <p
            className="text-base sm:text-lg text-[#64748B] max-w-xl mx-auto leading-relaxed"
            style={{ fontFamily: 'Inter, sans-serif' }}
          >
            Your entire real-estate sales process, in one intelligent system.
          </p>
          {/* Handwritten annotation */}
          <div className="absolute top-0 right-0 hidden md:block select-none pointer-events-none" aria-hidden="true">
            <div
              className="text-[#64748B] text-[14px] leading-snug text-right font-medium"
              style={{ fontFamily: 'Caveat, "Brush Script MT", cursive', transform: 'rotate(-4deg)', transformOrigin: 'right top' }}
            >
              More qualified buyers.<br />More deals.
            </div>
            <svg className="ml-auto mt-1 mr-3" width="48" height="40" viewBox="0 0 54 46" fill="none" style={{ transform: 'rotate(-3deg)' }}>
              <path d="M44 4 C38 16, 26 26, 12 36" stroke="#94A3B8" strokeWidth="1.8" strokeLinecap="round" fill="none" />
              <path d="M6 30 L11 37 L18 33" stroke="#94A3B8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            </svg>
          </div>
          {/* Explore hint — pointer/touch aware */}
          <motion.p
            className="mt-3 text-[11.5px] text-[#94A3B8] tracking-wide"
            animate={inView ? { opacity: 1 } : { opacity: 0 }}
            transition={{ delay: 0.5, duration: 0.4 }}
          >
            Move across the steps to explore the product
          </motion.p>
        </motion.div>

        {/* ─── INTERACTIVE STAGE AREA ──────────────────────────────────── */}
        {/*
          POINTER TRACKING ARCHITECTURE:
          - trackAreaRef is on the grid div (the actual hit target)
          - onPointerMove fires on every pointer move, reads clientX
          - calcStep() maps relX→stage with 2% hysteresis buffer
          - setActiveStep fires ONLY when computed stage changes
          - onPointerLeave resets to step 1 after 800ms
          - overflow-hidden clips any visual overflow of cards/badges
        */}
        <motion.div
          className="relative overflow-hidden rounded-2xl mb-12"
          initial={{ opacity: 0, y: 14 }}
          animate={inView ? { opacity: 1, y: 0 } : { opacity: 0, y: 14 }}
          transition={{ duration: 0.55, ease: EASE, delay: 0.12 }}
          aria-label="Product workflow — move pointer across stages to explore"
        >
          <div
            ref={trackAreaRef}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr_auto_1fr] gap-0 relative z-10"
            onPointerMove={handlePointerMove}
            onPointerLeave={handlePointerLeave}
            style={{ cursor: 'default' }}
          >

            {/* ── STAGE 01 ── */}
            <div
              className="flex flex-col px-3 lg:px-4 py-6 relative rounded-xl transition-colors duration-200"
              style={{ background: activeStep === 1 ? '#F0FDF4' : 'transparent' }}
            >
              <StageHeader
                num="01" title="Capture Leads" desc="Bring leads in from every source."
                accentColor={STEP_ACCENT[0]} badgeBg={STEP_BG[0]}
                active={activeStep === 1} reduced={reduced}
                onActivate={() => activate(1)}
              />
              <Visual01 active={activeStep === 1} reduced={reduced} />
            </div>

            {/* ── Arrow 1→2 ── */}
            <ArrowDivider activeLeft={activeStep === 1} activeRight={activeStep === 2} color={STEP_ARROW_ACTIVE[0]} />

            {/* ── STAGE 02 ── */}
            <div
              className="flex flex-col px-3 lg:px-4 py-6 relative rounded-xl transition-colors duration-200"
              style={{ background: activeStep === 2 ? '#EFF6FF' : 'transparent' }}
            >
              <StageHeader
                num="02" title="AI Understands" desc="Reads and structures buyer intent automatically."
                accentColor={STEP_ACCENT[1]} badgeBg={STEP_BG[1]}
                active={activeStep === 2} reduced={reduced}
                onActivate={() => activate(2)}
              />
              <Visual02 active={activeStep === 2} reduced={reduced} />
            </div>

            {/* ── Arrow 2→3 ── */}
            <ArrowDivider activeLeft={activeStep === 2} activeRight={activeStep === 3} color={STEP_ARROW_ACTIVE[1]} />

            {/* ── STAGE 03 ── */}
            <div
              className="flex flex-col px-3 lg:px-4 py-6 relative rounded-xl transition-colors duration-200"
              style={{ background: activeStep === 3 ? '#F5F3FF' : 'transparent' }}
            >
              <StageHeader
                num="03" title="Finds Best Matches" desc="AI searches inventory and ranks the best options."
                accentColor={STEP_ACCENT[2]} badgeBg={STEP_BG[2]}
                active={activeStep === 3} reduced={reduced}
                onActivate={() => activate(3)}
              />
              <Visual03 active={activeStep === 3} reduced={reduced} />
            </div>

            {/* ── Arrow 3→4 ── */}
            <ArrowDivider activeLeft={activeStep === 3} activeRight={activeStep === 4} color={STEP_ARROW_ACTIVE[2]} />

            {/* ── STAGE 04 ── */}
            <div
              className="flex flex-col px-3 lg:px-4 py-6 relative rounded-xl transition-colors duration-200"
              style={{ background: activeStep === 4 ? '#EFF6FF' : 'transparent' }}
            >
              <StageHeader
                num="04" title="Take Action" desc="Get clear next steps to move the deal forward."
                accentColor={STEP_ACCENT[3]} badgeBg={STEP_BG[3]}
                active={activeStep === 4} reduced={reduced}
                onActivate={() => activate(4)}
              />
              <Visual04 active={activeStep === 4} reduced={reduced} />
            </div>

            {/* ── Arrow 4→5 ── */}
            <ArrowDivider activeLeft={activeStep === 4} activeRight={activeStep === 5} color={STEP_ARROW_ACTIVE[3]} />

            {/* ── STAGE 05 ── */}
            <div
              className="flex flex-col px-3 lg:px-4 py-6 relative rounded-xl transition-colors duration-200"
              style={{ background: activeStep === 5 ? '#F0FDF4' : 'transparent' }}
            >
              <StageHeader
                num="05" title="Close the Deal" desc="Track progress from first contact to closed."
                accentColor={STEP_ACCENT[4]} badgeBg={STEP_BG[4]}
                active={activeStep === 5} reduced={reduced}
                onActivate={() => activate(5)}
              />
              <Visual05 active={activeStep === 5} reduced={reduced} />
            </div>

          </div>
          {/* Active-step progress bar — highlights current stage, hidden on mobile */}
          <div className="hidden lg:flex items-center justify-between px-4 pt-1 pb-3" aria-hidden="true">
            {([1, 2, 3, 4, 5] as const).map((s) => (
              <div key={s} className="flex-1 flex items-center justify-center">
                <motion.div
                  className="h-0.5 w-full rounded-full"
                  animate={{
                    backgroundColor: s === activeStep ? STEP_ACCENT[s - 1] : '#E2E8F0',
                    scaleX: s === activeStep ? 1 : 0.5,
                    opacity: s === activeStep ? 1 : 0.40,
                  }}
                  transition={{ duration: 0.20, ease: EASE }}
                  style={{ transformOrigin: 'center' }}
                />
              </div>
            ))}
          </div>
        </motion.div>

        {/* ─── BENEFIT STRIP ───────────────────────────────────────────── */}
        <motion.div
          className="border border-[#E2E8F0] rounded-2xl bg-white shadow-xs mb-12 overflow-hidden"
          initial={{ opacity: 0, y: 18 }}
          animate={footerAnim}
          transition={{ duration: 0.50, ease: EASE, delay: 0.30 }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            {BENEFITS.map(({ Icon, title, sub, color, bg }, i) => (
              <div
                key={title}
                className={`flex items-start gap-3.5 px-5 py-4 ${i > 0 ? 'sm:border-l sm:border-[#F1F5F9]' : ''} ${i >= 2 ? 'border-t lg:border-t-0 border-[#F1F5F9]' : ''}`}
              >
                <div
                  className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                  style={{ backgroundColor: bg }}
                >
                  <Icon className="w-4 h-4" style={{ color }} />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-bold text-[#0B172A] mb-0.5" style={{ fontFamily: 'JetBrains Mono, Geist Mono, monospace' }}>
                    {title}
                  </h4>
                  <p className="text-[11.5px] text-[#64748B]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    {sub}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* ─── CTA ─────────────────────────────────────────────────────── */}
        <motion.div
          className="text-center"
          initial={{ opacity: 0, y: 14 }}
          animate={footerAnim}
          transition={{ duration: 0.50, ease: EASE, delay: 0.42 }}
        >
          <Link href="/register">
            <motion.button
              type="button"
              className="inline-flex items-center gap-2 bg-[#0B172A] hover:bg-[#071426] text-white font-semibold text-[15px] px-8 py-3.5 rounded-full transition-all duration-200 shadow-md hover:shadow-lg cursor-pointer"
              whileHover={reduced ? {} : { y: -2, scale: 1.01 }}
              whileTap={reduced  ? {} : { scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 400, damping: 15 }}
            >
              See It In Action <ArrowRight className="w-4 h-4" />
            </motion.button>
          </Link>
          <p className="mt-4 text-[14px] text-[#64748B]" style={{ fontFamily: 'Inter, sans-serif' }}>
            From first conversation to final closing — all in one place.
          </p>
        </motion.div>

      </div>
    </section>
  );
}
