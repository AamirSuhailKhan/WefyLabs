'use client';

import { usePathname } from 'next/navigation';
import { AnimatePresence } from 'framer-motion';
import PageTransition from '@/components/shared/PageTransition';

export default function DashboardLayoutClient({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <AnimatePresence mode="wait">
      <PageTransition key={pathname}>
        {children}
      </PageTransition>
    </AnimatePresence>
  );
}
