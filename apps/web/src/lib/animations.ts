import { Variants } from 'framer-motion';
import { useState, useEffect } from 'react';

// Easing curves used by Apple, Linear, Stripe
export const EASE = {
  smooth: [0.16, 1, 0.3, 1] as const,      // Primary — cubic-bezier(0.16, 1, 0.3, 1)
  bounce: [0.34, 1.56, 0.64, 1] as const,   // Springy overshoot
  gentle: [0.4, 0, 0.2, 1] as const,       // Material Design standard
  snappy: [0.25, 0.1, 0.25, 1] as const,   // Quick response
};

// Ease-out-expo — the master easing for all scroll animations
export const EXPO_EASE = [0.22, 1, 0.36, 1] as const;

// Respects OS prefers-reduced-motion setting
export function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}

export const DURATIONS = {
  fast: 0.2,
  normal: 0.4,
  slow: 0.6,
  slower: 0.8,
  hero: 1.0,
};

export const STAGGER = {
  fast: 0.05,
  normal: 0.1,
  slow: 0.15,
};

// Spring configs
export const SPRING = {
  soft: { type: 'spring', stiffness: 120, damping: 20 } as const,
  bouncy: { type: 'spring', stiffness: 300, damping: 20 } as const,
  stiff: { type: 'spring', stiffness: 400, damping: 30 } as const,
  gentle: { type: 'spring', stiffness: 100, damping: 15 } as const,
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: DURATIONS.slow, ease: EASE.smooth } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: DURATIONS.normal, ease: EASE.smooth } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: DURATIONS.slow, ease: EASE.smooth } },
};

export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: STAGGER.fast, delayChildren: 0.1 } },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: DURATIONS.normal, ease: EASE.smooth } },
};
