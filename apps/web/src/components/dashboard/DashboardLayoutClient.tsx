'use client';

import { usePathname, useRouter } from 'next/navigation';
import { AnimatePresence } from 'framer-motion';
import PageTransition from '@/components/shared/PageTransition';
import { useEffect, useState } from 'react';
import { api, getToken } from '@/lib/api-client';

export default function DashboardLayoutClient({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [suspended, setSuspended] = useState(false);

  useEffect(() => {
    let active = true;

    async function checkAuth() {
      const token = getToken();
      if (!token) {
        if (active) router.push('/login');
        return;
      }

      try {
        const broker = await api.auth.me();
        if (!active) return;

        if (broker.onboarding_status === 'SUSPENDED') {
          setSuspended(true);
          setLoading(false);
          return;
        }

        if (broker.onboarding_status === 'AUTHENTICATED_NOT_ONBOARDED') {
          router.push('/onboarding');
          return;
        }

        setLoading(false);
      } catch (err) {
        console.error('Auth verification failed', err);
        if (active) {
          router.push('/login');
        }
      }
    }

    checkAuth();

    return () => {
      active = false;
    };
  }, [router, pathname]);

  if (suspended) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#F0EDE8] p-4 text-center">
        <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl border border-red-100">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-50 text-red-500 mb-6">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-8 w-8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight mb-2">Account Suspended</h2>
          <p className="text-gray-500 mb-6">
            Your broker account has been suspended by the administrator. Please contact support at support@beetlelabs.ai for resolution.
          </p>
          <button
            onClick={() => {
              api.auth.logout();
              router.push('/login');
            }}
            className="w-full py-3 px-4 bg-gray-950 text-white font-medium rounded-xl hover:bg-gray-800 transition-colors shadow-sm"
          >
            Return to Login
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F0EDE8]">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-gray-900 border-t-transparent"></div>
          <p className="text-sm font-medium text-gray-600">Verifying session...</p>
        </div>
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <PageTransition key={pathname}>
        {children}
      </PageTransition>
    </AnimatePresence>
  );
}
