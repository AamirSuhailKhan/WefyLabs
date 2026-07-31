'use client';

import { ReactNode, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import Lenis from 'lenis';

import { RegionProvider } from '@/lib/i18n/region-context';
import { GlobalAICopilot } from '@/components/copilot/GlobalAICopilot';

export function Providers({ children }: { children: ReactNode }) {
  useEffect(() => {
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    });
    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
    return () => lenis.destroy();
  }, []);

  return (
    <RegionProvider>
      <AnimatePresence mode="wait">{children}</AnimatePresence>
      <GlobalAICopilot />
    </RegionProvider>
  );
}
