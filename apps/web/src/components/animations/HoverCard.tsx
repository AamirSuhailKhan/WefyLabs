'use client';

import { motion } from 'framer-motion';
import { EASE } from '@/lib/animations';

export function HoverCard({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      whileHover={{
        y: -6,
        borderColor: 'rgba(13, 148, 136, 0.3)',
        transition: { duration: 0.3, ease: EASE.smooth },
      }}
      whileTap={{ scale: 0.98 }}
    >
      {children}
    </motion.div>
  );
}
