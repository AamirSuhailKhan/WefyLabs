'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api-client';
import { WefyLabsLogo } from '@/components/shared/WefyLabsLogo';

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const processOAuth = async () => {
      const error = searchParams.get('error');
      if (error) {
        let userFacingError = `Google sign-in failed: ${error}`;
        if (error === 'access_denied') {
          userFacingError = 'Google sign-in was cancelled.';
        } else if (error === 'invalid_client' || error.includes('client')) {
          userFacingError = 'Google OAuth client configuration error. Please verify Google Cloud Client ID.';
        } else if (error === 'redirect_uri_mismatch') {
          userFacingError = 'Google OAuth redirect URI mismatch. Please verify authorized redirect URI in Google Cloud Console.';
        }
        setErrorMessage(userFacingError);
        setTimeout(() => {
          router.push(`/login?error=${encodeURIComponent(userFacingError)}`);
        }, 2000);
        return;
      }

      const code = searchParams.get('code');
      const state = searchParams.get('state') || undefined;

      if (!code) {
        setErrorMessage('No authorization code provided in callback.');
        setTimeout(() => {
          router.push('/login');
        }, 2000);
        return;
      }

      const callbackType = searchParams.get('type');
      const isCalendarCallback = callbackType === 'calendar';

      try {
        if (isCalendarCallback) {
          const redirectUri = `${window.location.origin}/auth/callback?type=calendar`;
          await api.calendar.exchangeGoogleCallback(code, state || '', redirectUri);
          router.push('/dashboard/settings?calendar=connected');
          return;
        }

        const redirectUri = `${window.location.origin}/auth/callback`;
        const res = await api.auth.exchangeGoogleCode({
          code,
          state,
          redirect_uri: redirectUri
        });

        if (res?.broker?.onboarding_status === 'ONBOARDED') {
          router.push('/dashboard');
        } else {
          router.push('/onboarding');
        }
      } catch (err: any) {
        const msg = err?.message || 'Failed to complete Google authentication.';
        setErrorMessage(msg);
        setTimeout(() => {
          if (isCalendarCallback) {
            router.push('/dashboard/settings?calendar_error=failed');
          } else {
            router.push(`/login?error=${encodeURIComponent(msg)}`);
          }
        }, 3000);
      }
    };

    processOAuth();
  }, [router, searchParams]);

  return (
    <div className="min-h-screen bg-[#0A0D14] text-white flex flex-col items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-tr from-blue-600/20 to-purple-600/20 rounded-full blur-[140px] pointer-events-none" />

      <div className="relative z-10 flex flex-col items-center text-center max-w-md bg-white/5 border border-white/10 rounded-2xl p-8 backdrop-blur-xl shadow-2xl">
        <div className="mb-6">
          <WefyLabsLogo dark href="/" iconSize={36} textSize="text-2xl" />
        </div>

        {errorMessage ? (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto text-red-400">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-red-400">Authentication Failed</h2>
            <p className="text-sm text-gray-400">{errorMessage}</p>
            <p className="text-xs text-gray-500">Redirecting you back to login...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-blue-500 border-t-transparent mx-auto" />
            <h2 className="text-lg font-bold text-white">Authenticating with Google...</h2>
            <p className="text-sm text-gray-400">Verifying credentials and securely preparing your workspace.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#0A0D14] flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
