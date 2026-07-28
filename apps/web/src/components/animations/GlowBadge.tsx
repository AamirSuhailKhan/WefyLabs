'use client';

import { motion } from 'framer-motion';

export function GlowBadge({
  children,
  color = '#F59E0B',
}: {
  children: React.ReactNode;
  color?: string;
}) {
  return (
    <motion.span
      className="relative inline-flex items-center"
      animate={{
        boxShadow: [
          `0 0 0px ${color}00`,
          `0 0 12px ${color}40`,
          `0 0 0px ${color}00`,
        ],
      }}
      transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
      style={{ borderRadius: 9999 }}
    >
      {children}
    </motion.span>
  );
}
