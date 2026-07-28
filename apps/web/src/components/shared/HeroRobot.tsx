'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const stages = [
  { 
    id: 0, 
    label: "New lead received", 
    value: "+91 98765 43210", 
    type: "thinking",
    position: "top-right"
  },
  { 
    id: 1, 
    label: "Budget extracted", 
    value: "₹40L – ₹50L", 
    type: "data",
    position: "left"
  },
  { 
    id: 2, 
    label: "Location detected", 
    value: "Whitefield, Bengaluru", 
    type: "data",
    position: "top-right"
  },
  { 
    id: 3, 
    label: "Property type", 
    value: "2 BHK Apartment", 
    type: "data",
    position: "bottom-left"
  },
  { 
    id: 4, 
    label: "Timeline", 
    value: "Ready to move", 
    type: "data",
    position: "bottom-right"
  },
  { 
    id: 5, 
    label: "Intent signal", 
    value: "Pre-approved loan", 
    type: "data",
    position: "right"
  },
  { 
    id: 6, 
    label: "Qualification complete", 
    value: "🔥 HOT LEAD", 
    subvalue: "94% confidence",
    type: "score",
    position: "bubble"
  },
];

const positionMap: Record<
  string,
  {
    top?: string;
    bottom?: string;
    left?: string;
    right?: string;
    initial: { x: number; y: number };
  }
> = {
  left:          { top: "15%",   left: "-38%",  initial: { x: -30, y: 0 } },
  right:         { top: "35%",   right: "-42%", initial: { x: 30, y: 0 } },
  "top-right":   { top: "-8%",   right: "-35%", initial: { x: 15, y: -20 } },
  "bottom-left": { bottom: "22%", left: "-32%", initial: { x: -20, y: 15 } },
  "bottom-right":{ bottom: "12%", right: "-35%", initial: { x: 20, y: 15 } },
};

const headTiltMap: Record<string, number> = {
  left: -3,
  right: 3,
  "top-right": 2,
  "bottom-left": -2,
  "bottom-right": 2,
  bubble: 0,
  thinking: 0,
};

export default function HeroRobot() {
  const [stageIndex, setStageIndex] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);

  const stage = stages[stageIndex];
  const currentPos = positionMap[stage.position];
  const headTilt = headTiltMap[stage.position] || 0;

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      setReducedMotion(mediaQuery.matches);
      const listener = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
      mediaQuery.addEventListener('change', listener);
      return () => mediaQuery.removeEventListener('change', listener);
    }
  }, []);

  useEffect(() => {
    if (reducedMotion) return;
    const interval = setInterval(() => {
      setStageIndex((prev) => (prev + 1) % stages.length);
    }, 1200);
    return () => clearInterval(interval);
  }, [reducedMotion]);

  return (
    <div className="relative w-full max-w-sm flex flex-col items-center justify-center min-h-[360px] py-4 select-none">
      {/* ── Ground Shadow (scales inversely to robot float height) ── */}
      <motion.div
        className="w-36 h-4 bg-[#1A1A1A]/10 rounded-full blur-md mb-2 absolute bottom-2"
        animate={reducedMotion ? undefined : { scale: [1, 0.82, 1], opacity: [0.25, 0.12, 0.25] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* ── Radar Scanning Rings (active during "thinking" stage) ── */}
      <AnimatePresence>
        {!reducedMotion && stage.type === 'thinking' && (
          <>
            <motion.div
              className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border border-[#0D9488]/30 rounded-full pointer-events-none z-0"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1.6, opacity: [0.6, 0] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
            />
            <motion.div
              className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-32 h-32 border border-[#0D9488]/20 rounded-full pointer-events-none z-0"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1.6, opacity: [0.6, 0] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut', delay: 0.75 }}
            />
          </>
        )}
      </AnimatePresence>

      {/* ── Main Robot Container (Gently Float) ── */}
      <motion.div
        className="relative w-full flex justify-center z-10"
        animate={reducedMotion ? undefined : { y: [0, -12, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      >
        <svg viewBox="0 0 280 280" className="w-full max-w-xs overflow-visible" fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Antenna Group (Sway) */}
          <motion.g
            style={{ transformOrigin: '140px 55px' }}
            animate={reducedMotion ? undefined : { rotate: [-3, 3, -3] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
          >
            <line x1="140" y1="55" x2="140" y2="32" stroke="#0D9488" strokeWidth="2" />
            <circle cx="140" cy="28" r="6" fill="#D9F99D" stroke="#D4D0C8" strokeWidth="1" />
          </motion.g>

          {/* Left Arm (Sway) */}
          <motion.g
            style={{ transformOrigin: '70px 135px' }}
            animate={reducedMotion ? undefined : { rotate: [0, 5, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          >
            <rect x="30" y="125" width="40" height="20" rx="10" fill="#0D9488" opacity="0.15" stroke="#0D9488" strokeWidth="1.5" />
          </motion.g>

          {/* Right Arm (Sway opposite) */}
          <motion.g
            style={{ transformOrigin: '210px 135px' }}
            animate={reducedMotion ? undefined : { rotate: [0, -5, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
          >
            <rect x="210" y="125" width="40" height="20" rx="10" fill="#0D9488" opacity="0.15" stroke="#0D9488" strokeWidth="1.5" />
          </motion.g>

          {/* Legs */}
          <rect x="95" y="225" width="35" height="40" rx="10" fill="#0D9488" opacity="0.15" stroke="#0D9488" strokeWidth="1.5" />
          <rect x="150" y="225" width="35" height="40" rx="10" fill="#0D9488" opacity="0.15" stroke="#0D9488" strokeWidth="1.5" />

          {/* Robot Body */}
          <rect x="70" y="110" width="140" height="120" rx="20" fill="#0D9488" opacity="0.15" stroke="#0D9488" strokeWidth="1.5" />

          {/* Head (with reactive head tilt based on active tag position) */}
          <motion.g
            style={{ transformOrigin: '140px 95px' }}
            animate={reducedMotion ? undefined : { rotate: stage.type === 'score' ? [0, -5, 0] : headTilt }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <rect x="90" y="55" width="100" height="80" rx="16" fill="#0D9488" opacity="0.2" stroke="#0D9488" strokeWidth="1.5" />

            {/* Left Eye (Blink) */}
            <motion.g
              style={{ transformOrigin: '120px 88px' }}
              animate={reducedMotion ? undefined : { scaleY: [1, 0.1, 1] }}
              transition={{ duration: 0.2, repeat: Infinity, repeatDelay: 4, ease: 'easeInOut' }}
            >
              <circle cx="120" cy="88" r="10" fill="#0D9488" />
              <circle cx="122" cy="86" r="4" fill="white" />
            </motion.g>

            {/* Right Eye (Blink with slight delay) */}
            <motion.g
              style={{ transformOrigin: '160px 88px' }}
              animate={reducedMotion ? undefined : { scaleY: [1, 0.1, 1] }}
              transition={{ duration: 0.2, repeat: Infinity, repeatDelay: 4, delay: 0.05, ease: 'easeInOut' }}
            >
              <circle cx="160" cy="88" r="10" fill="#0D9488" />
              <circle cx="162" cy="86" r="4" fill="white" />
            </motion.g>

            {/* Mouth (Subtle Smile Breath) */}
            <motion.path
              d="M115 108 Q140 122 165 108"
              stroke="#0D9488"
              strokeWidth="2.5"
              strokeLinecap="round"
              fill="none"
              style={{ transformOrigin: '140px 108px' }}
              animate={reducedMotion ? undefined : { scaleX: [1, 1.05, 1] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            />
          </motion.g>
        </svg>

        {/* ── FLOATING ORBITAL DATA TAG (STRICTLY ONE VISIBLE AT A TIME) ── */}
        <AnimatePresence mode="wait">
          {!reducedMotion && stage.type === 'data' && currentPos && (
            <motion.div
              key={stage.id}
              style={{
                position: 'absolute',
                top: currentPos.top,
                bottom: currentPos.bottom,
                left: currentPos.left,
                right: currentPos.right,
              }}
              initial={{ 
                opacity: 0, 
                scale: 0.8, 
                x: currentPos.initial.x, 
                y: currentPos.initial.y 
              }}
              animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: -10 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="bg-white border border-slate-200 rounded-xl px-3 py-2 shadow-md z-30 pointer-events-none whitespace-nowrap"
            >
              <span className="text-[10px] uppercase tracking-wider text-slate-500 font-mono block">
                {stage.label}
              </span>
              <span className="text-sm font-mono font-bold text-slate-900 block">
                {stage.value}
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── MAIN DYNAMIC SPEECH BUBBLE ── */}
        <AnimatePresence mode="wait">
          <motion.div
            key={stage.id}
            initial={reducedMotion ? undefined : { scale: 0.8, opacity: 0, y: 10 }}
            animate={reducedMotion ? undefined : { scale: 1, opacity: 1, y: 0 }}
            exit={reducedMotion ? undefined : { scale: 0.9, opacity: 0, y: -10 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="absolute -top-6 right-0 sm:-right-4 z-30"
          >
            {/* Glow blur effect on score stage */}
            {!reducedMotion && stage.type === 'score' && (
              <motion.div
                className="absolute inset-0 bg-[#D9F99D] rounded-2xl blur-xl -z-10"
                animate={{ opacity: [0.4, 0.8, 0.4], scale: [1, 1.2, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              />
            )}

            {/* Expanding success ring on score stage */}
            {!reducedMotion && stage.type === 'score' && (
              <motion.div
                className="absolute inset-0 border-2 border-[#84CC16] rounded-2xl -z-10"
                initial={{ scale: 0.8, opacity: 1 }}
                animate={{ scale: 1.5, opacity: 0 }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
              />
            )}

            <div
              className={`relative rounded-2xl px-4 py-2.5 shadow-lg border transition-colors bg-[#D9F99D] border-slate-300 min-w-[140px]`}
            >
              {/* Bubble Tail */}
              <div className="absolute bottom-2 -left-2 w-3.5 h-3.5 rotate-45 bg-[#D9F99D] border-l border-b border-slate-300" />

              <AnimatePresence mode="wait">
                {/* Stage 0: Thinking / New lead */}
                {stage.type === 'thinking' && (
                  <motion.div
                    key="thinking"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="flex flex-col gap-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] uppercase tracking-wider text-slate-600 font-mono font-semibold">
                        {stage.label}
                      </span>
                      {!reducedMotion && (
                        <div className="flex gap-1 items-center">
                          {[0, 1, 2].map((i) => (
                            <motion.div
                              key={i}
                              className="w-1.5 h-1.5 bg-slate-800 rounded-full"
                              animate={{ y: [0, -3, 0] }}
                              transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {stage.value}
                    </span>
                  </motion.div>
                )}

                {/* Stages 1-5: Data Extraction ("Qualifying...") */}
                {stage.type === 'data' && (
                  <motion.div
                    key="data"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="flex flex-col"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-slate-900">
                        Qualifying...
                      </span>
                      {!reducedMotion && (
                        <div className="flex gap-1 items-center">
                          {[0, 1, 2].map((i) => (
                            <motion.div
                              key={i}
                              className="w-1.5 h-1.5 bg-slate-800 rounded-full"
                              animate={{ y: [0, -3, 0] }}
                              transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                            />
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Progress Bar Visual Timeline */}
                    <div className="h-0.5 bg-slate-300/80 rounded-full mt-2 overflow-hidden w-full">
                      <motion.div
                        className="h-full bg-teal-600 rounded-full"
                        animate={{ width: `${(stageIndex / (stages.length - 1)) * 100}%` }}
                        transition={{ duration: 0.3 }}
                      />
                    </div>
                  </motion.div>
                )}

                {/* Stage 6: HOT LEAD Qualification Complete */}
                {stage.type === 'score' && (
                  <motion.div
                    key="score"
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    className="text-center"
                  >
                    <div className="flex items-center justify-center gap-1.5">
                      <motion.span
                        animate={reducedMotion ? false : { rotate: [0, -10, 10, 0], scale: [1, 1.25, 1] }}
                        transition={{ duration: 0.6 }}
                        className="text-sm"
                      >
                        🔥
                      </motion.span>
                      <span className="text-xs font-mono font-bold text-slate-900 tracking-wide">
                        {stage.value}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-700 block mt-0.5 font-medium">
                      {stage.subvalue}
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

