'use client';

import { motion, HTMLMotionProps } from 'framer-motion';
import { EASE, SPRING } from '@/lib/animations';

export interface AnimatedButtonProps extends HTMLMotionProps<'button'> {
  variant?: 'primary' | 'secondary' | 'ghost';
  children: React.ReactNode;
}

export function AnimatedButton({
  children,
  variant = 'primary',
  className = '',
  ...props
}: AnimatedButtonProps) {
  const base =
    'relative overflow-hidden rounded-xl font-semibold text-sm inline-flex items-center justify-center gap-2';
  const variants = {
    primary: 'bg-[#E8F5A8] text-[#1A1A1A] hover:bg-[#D4E894]',
    secondary: 'border border-[#D4D0C8] text-[#1A1A1A] hover:bg-[#FAF7F2]',
    ghost: 'text-[#6B6B6B] hover:text-[#1A1A1A]',
  };

  return (
    <motion.button
      className={`${base} ${variants[variant]} px-6 py-3 ${className}`}
      whileHover={{ scale: 1.03, y: -1 }}
      whileTap={{ scale: 0.97 }}
      transition={SPRING.stiff}
      {...props}
    >
      <motion.span
        className="absolute inset-0 bg-white/30"
        initial={{ x: '-100%', opacity: 0 }}
        whileHover={{ x: '100%', opacity: 0.3 }}
        transition={{ duration: 0.6, ease: EASE.smooth }}
      />
      <span className="relative z-10 flex items-center justify-center gap-2">{children}</span>
    </motion.button>
  );
}
