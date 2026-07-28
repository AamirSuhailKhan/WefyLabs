'use client';

import { motion } from 'framer-motion';
import { EASE, DURATIONS } from '@/lib/animations';

interface Props {
  children: React.ReactNode;
  delay?: number;
  duration?: number;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  distance?: number;
  className?: string;
  once?: boolean;
}

export function FadeIn({
  children,
  delay = 0,
  duration = DURATIONS.slow,
  direction = 'up',
  distance = 40,
  className = '',
  once = true,
}: Props) {
  const directions = {
    up: { y: distance },
    down: { y: -distance },
    left: { x: distance },
    right: { x: -distance },
    none: {},
  };

  return (
    <motion.div
      initial={{ opacity: 0, ...directions[direction] }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once, margin: '-60px' }}
      transition={{ duration, delay, ease: EASE.smooth }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
