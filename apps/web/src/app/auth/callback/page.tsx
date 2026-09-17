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
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Ambient background matching login */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden flex items-center justify-center">
        <div className="absolute top-[-20%] left-[-10%] w-[70vw] h-[70vw] max-w-[800px] max-h-[800px] bg-[#E8F5A8] opacity-20 blur-[120px] rounded-full mix-blend-multiply" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] max-w-[700px] max-h-[700px] bg-[#d4f5a4] opacity-20 blur-[100px] rounded-full mix-blend-multiply" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPgo8cmVjdCB3aWR0aD0iNCIgaGVpZ2h0PSI0IiBmaWxsPSIjZmZmIiBmaWxsLW9wYWNpdHk9IjAuMCIvPgo8cGF0aCBkPSJNMCAwTDRgME0wIDRMNCw0TTAgMEw0LDRNMCA0TDQsMCIgc3Ryb2tlPSIjMDAwIiBzdHJva2Utd2lkdGg9IjAuMDUiIHN0cm9rZS1vcGFjaXR5PSIwLjAyIi8+Cjwvc3ZnPg==')] opacity-50 mix-blend-multiply" />
      </div>

      <div className="relative z-10 flex flex-col items-center text-center w-full max-w-md bg-white border border-[#D4D0C8] rounded-3xl p-8 md:p-10 shadow-[0_8px_30px_rgb(0,0,0,0.04)]">
        <div className="mb-6">
          <WefyLabsLogo dark={false} href="/" iconSize={36} textSize="text-2xl" />
        </div>

        {errorMessage ? (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-full bg-[#FEE2E2] border border-[#FCA5A5] flex items-center justify-center mx-auto text-[#DC2626]">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-lg font-bold mono-headline text-[#DC2626]">Authentication Failed</h2>
            <p className="text-sm text-[#6B6B6B]">{errorMessage}</p>
            <p className="text-xs text-[#A0A0A0] font-mono">Redirecting you back to login...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-[#1A1A1A] border-t-transparent mx-auto" />
            <h2 className="text-lg font-bold mono-headline text-[#1A1A1A]">Authenticating with Google...</h2>
            <p className="text-sm text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
              Verifying credentials and securely preparing your workspace.
            </p>
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
        <div className="min-h-screen bg-[#F0EDE8] flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#1A1A1A] border-t-transparent" />
        </div>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
