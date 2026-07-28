'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Code2, Sparkles, Play, CheckCircle2, Check } from 'lucide-react';

const cards = [
  {
    icon: Code2,
    title: 'For solo brokers',
    bullets: [
      <>Forward <code className="bg-[#F0EDE8] border border-[#D4D0C8] px-1 rounded text-xs font-mono">+91-XXXXX</code> to send leads directly to the bot</>,
      'Track and manage leads in a simple dashboard',
      'Get Hot/Warm/Cold scores instantly',
      'Set reminders and never lose a lead'
    ]
  },
  {
    icon: Sparkles,
    title: 'AI that works for you',
    bullets: [
      'AI powered qualification',
      'Extracts budget, location, timeline automatically',
      'Scores leads like a senior broker',
      'Learns from every conversation'
    ]
  },
  {
    icon: Play,
    title: 'Run anywhere',
    bullets: [
      'Works entirely on WhatsApp — no app download needed',
      'Mobile-first dashboard for brokers on the move',
      'Get notified instantly when a lead is qualified'
    ]
  },
  {
    icon: CheckCircle2,
    title: 'Close everything',
    bullets: [
      'Automated follow-ups keep leads warm',
      'Task reminders ensure no lead is forgotten',
      'Pipeline from New → Closed Won'
    ]
  }
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.15,
    }
  }
};

const cardVariants = {
  hidden: { opacity: 0, y: 30, scale: 0.96 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      duration: 0.5,
      ease: [0.22, 1, 0.36, 1]
    }
  }
};

export default function FeaturesGrid() {
  return (
    <section id="features" className="py-20 px-4 max-w-5xl mx-auto">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="text-center mb-14"
      >
        <div className="inline-flex items-center gap-3 mb-4">
          <span
            className="text-xs font-mono uppercase tracking-[0.2em] text-[#6B6B6B]"
          >
            HOW IT WORKS
          </span>
          <motion.span
            className="w-1.5 h-1.5 bg-[#E8F5A8] border border-[#D4D0C8] rounded-sm block"
            animate={{ scale: [1, 1.35, 1], opacity: [1, 0.6, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          />
        </div>
        <h2
          className="text-4xl md:text-5xl font-bold text-[#1A1A1A] mb-4"
          style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
        >
          One platform, every workflow
        </h2>
        <p
          className="text-base sm:text-lg text-[#4A4A4A] max-w-2xl mx-auto leading-relaxed"
          style={{ fontFamily: 'Inter, sans-serif' }}
        >
          Whether you work from your phone or laptop, BeetleLabs meets you where you are.
        </p>
      </motion.div>

      {/* 4 Cards Grid */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-50px' }}
        className="grid grid-cols-1 md:grid-cols-2 gap-5"
      >
        {cards.map((card, idx) => {
          const IconComponent = card.icon;
          return (
            <motion.div
              key={card.title}
              variants={cardVariants}
              whileHover={{
                y: -6,
                boxShadow: '0 20px 40px -12px rgba(0,0,0,0.08)',
                borderColor: '#D4D0C8'
              }}
              transition={{ type: 'spring', stiffness: 300, damping: 20 }}
              role="region"
              aria-label={card.title}
              className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 sm:p-8 shadow-sm transition-all flex flex-col justify-between"
            >
              <div>
                {/* Icon Container with hover tilt micro-animation */}
                <motion.div
                  className="w-10 h-10 rounded-xl bg-[#F0EDE8] border border-[#D4D0C8] flex items-center justify-center mb-5 shrink-0"
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 10 }}
                >
                  <IconComponent className="w-5 h-5 text-[#1A1A1A]" aria-hidden="true" />
                </motion.div>

                {/* Card Title */}
                <h3
                  className="text-xl font-bold text-[#1A1A1A] mb-4"
                  style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
                >
                  {card.title}
                </h3>

                {/* Bullets List */}
                <ul className="space-y-3 text-sm text-[#4A4A4A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                  {card.bullets.map((bullet, i) => (
                    <motion.li
                      key={i}
                      initial={{ opacity: 0, x: -8 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.05 + 0.1, duration: 0.3 }}
                      className="flex items-start"
                    >
                      <Check className="w-4 h-4 text-[#1A1A1A] mr-3 flex-shrink-0 mt-0.5" aria-hidden="true" />
                      <span className="leading-snug">{bullet}</span>
                    </motion.li>
                  ))}
                </ul>
              </div>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
