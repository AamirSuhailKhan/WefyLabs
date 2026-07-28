'use client';

import { motion, useMotionValue, useSpring } from 'framer-motion';
import { useEffect } from 'react';

export function CursorGlow() {
  const cursorX = useMotionValue(-300);
  const cursorY = useMotionValue(-300);
  const springX = useSpring(cursorX, { stiffness: 400, damping: 40 });
  const springY = useSpring(cursorY, { stiffness: 400, damping: 40 });

  useEffect(() => {
    const move = (e: MouseEvent) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
    };
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
  }, [cursorX, cursorY]);

  return (
    <motion.div
      className="pointer-events-none fixed w-[300px] h-[300px] rounded-full bg-[#0D9488]/10 blur-[90px] z-0 hidden lg:block"
      style={{ x: springX, y: springY, translateX: '-50%', translateY: '-50%' }}
    />
  );
}
