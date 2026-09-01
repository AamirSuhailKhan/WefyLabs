'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Mail, Lock, Phone, User, Building, MapPin, ArrowRight, MessageSquare } from 'lucide-react';
import { api } from '@/lib/api-client';
import { BeetleLabsLogo } from '@/components/shared/BeetleLabsLogo';

const EXPO = [0.22, 1, 0.36, 1] as const;

function RegisterContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    phone: '',
    agency_name: '',
    city: '',
    whatsapp_number: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const errorParam = searchParams.get('error');
    if (errorParam) {
      setError(decodeURIComponent(errorParam));
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.password || !formData.phone) {
      setError('Please fill in all required fields.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await api.auth.register(formData);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err?.message || 'Registration failed. Please check your inputs.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignUp = async () => {
    setIsGoogleLoading(true);
    setError(null);

    try {
      const redirectUri = `${window.location.origin}/auth/callback`;
      const data = await api.auth.getGoogleAuthUrl(redirectUri);
      if (data?.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error('Google OAuth configuration unavailable.');
      }
    } catch (err: any) {
      setError(err?.message || 'Unable to connect to Google OAuth service.');
      setIsGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col items-center justify-center p-4 relative py-12 overflow-hidden">
      <style>{`
        @keyframes drift {
          0% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
          100% { transform: translate(0, 0) scale(1); }
        }
        .animate-drift {
          animation: drift 25s ease-in-out infinite;
        }
        @keyframes pulse-slow {
          0%, 100% { opacity: 0.15; transform: scale(1); }
          50% { opacity: 0.3; transform: scale(1.05); }
        }
        .animate-pulse-slow {
          animation: pulse-slow 15s ease-in-out infinite;
        }
        @media (prefers-reduced-motion: reduce) {
          .animate-drift, .animate-pulse-slow {
            animation: none !important;
          }
        }
      `}</style>

      {/* Ambient Background Elements */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden flex items-center justify-center">
        <div className="absolute top-[-20%] left-[-10%] w-[70vw] h-[70vw] max-w-[800px] max-h-[800px] bg-[#E8F5A8] opacity-20 blur-[120px] rounded-full animate-pulse-slow mix-blend-multiply" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] max-w-[700px] max-h-[700px] bg-[#d4f5a4] opacity-20 blur-[100px] rounded-full animate-drift mix-blend-multiply" />
        {/* Subtle grid/texture overlay */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPgo8cmVjdCB3aWR0aD0iNCIgaGVpZ2h0PSI0IiBmaWxsPSIjZmZmIiBmaWxsLW9wYWNpdHk9IjAuMCIvPgo8cGF0aCBkPSJNMCAwTDRgME0wIDRMNCw0TTAgMEw0LDRNMCA0TDQsMCIgc3Ryb2tlPSIjMDAwIiBzdHJva2Utd2lkdGg9IjAuMDUiIHN0cm9rZS1vcGFjaXR5PSIwLjAyIi8+Cjwvc3ZnPg==')] opacity-50 mix-blend-multiply" />
      </div>

      {/* Logo Outside Card */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EXPO }}
        className="relative z-10 mb-8"
      >
        <BeetleLabsLogo dark={false} href="/" iconSize={36} textSize="text-3xl" />
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: EXPO, delay: 0.1 }}
        className="w-full max-w-[540px] bg-white border border-[#D4D0C8] rounded-3xl p-8 md:p-12 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative z-10"
      >
        <div className="text-center mb-8">
          <h1 className="text-2xl md:text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight">
            Create Your Broker Account
          </h1>
          <p className="text-[15px] text-[#6B6B6B] mt-3" style={{ fontFamily: 'Inter, sans-serif' }}>
            Start your 7-day free trial. Qualify real estate leads on WhatsApp automatically.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-[#FEE2E2] border border-[#FCA5A5] text-[#DC2626] text-sm font-medium flex items-center justify-center text-center">
            {error}
          </div>
        )}

        {/* Google Sign Up Button */}
        <button
          type="button"
          disabled={isGoogleLoading || isLoading}
          onClick={handleGoogleSignUp}
          className="w-full py-3.5 px-4 bg-white border border-[#D4D0C8] rounded-xl hover:bg-[#FAF7F2] text-[#1A1A1A] font-semibold flex items-center justify-center gap-3 shadow-sm hover:shadow transition-all mb-7 disabled:opacity-60 group"
        >
          {isGoogleLoading ? (
            <span className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-[#1A1A1A] border-t-transparent" />
          ) : (
            <svg className="w-5 h-5 shrink-0 group-hover:scale-105 transition-transform" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              />
            </svg>
          )}
          <span className="text-[15px] font-semibold" style={{ fontFamily: 'Inter, sans-serif' }}>
            {isGoogleLoading ? 'Connecting to Google...' : 'Sign up with Google'}
          </span>
        </button>

        {/* Divider */}
        <div className="relative mb-7 flex items-center justify-center">
          <div className="border-t border-[#E8E4DE] w-full" />
          <span className="bg-white px-4 text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono absolute">
            OR REGISTER WITH EMAIL
          </span>
        </div>

        <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div className="sm:col-span-2">
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              Full Name <span className="text-[#DC2626]">*</span>
            </label>
            <div className="relative group">
              <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="First Last"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              Email Address <span className="text-[#DC2626]">*</span>
            </label>
            <div className="relative group">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="you@example.com"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              Password <span className="text-[#DC2626]">*</span>
            </label>
            <div className="relative group">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="••••••••"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              Phone Number <span className="text-[#DC2626]">*</span>
            </label>
            <div className="relative group">
              <Phone className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="tel"
                required
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+91 XXXXX XXXXX"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              WhatsApp
            </label>
            <div className="relative group">
              <MessageSquare className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="tel"
                value={formData.whatsapp_number}
                onChange={(e) => setFormData({ ...formData, whatsapp_number: e.target.value })}
                placeholder="+91 XXXXX XXXXX"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              Agency Name
            </label>
            <div className="relative group">
              <Building className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="text"
                value={formData.agency_name}
                onChange={(e) => setFormData({ ...formData, agency_name: e.target.value })}
                placeholder="Company Name"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
              City
            </label>
            <div className="relative group">
              <MapPin className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#A0A0A0] group-focus-within:text-[#1A1A1A] transition-colors" />
              <input
                type="text"
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                placeholder="City Name"
                className="w-full pl-10 pr-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
              />
            </div>
          </div>

          <div className="sm:col-span-2 mt-5">
            <motion.button
              type="submit"
              disabled={isLoading || isGoogleLoading}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              className="group w-full py-4 px-4 bg-[#E8F5A8] hover:bg-[#E1F099] border border-[#D4D0C8] rounded-xl flex items-center justify-center gap-2 disabled:opacity-50 transition-colors shadow-sm"
            >
              {isLoading ? (
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-2 border-[#1A1A1A] border-t-transparent" />
              ) : (
                <>
                  <span className="font-bold text-[13px] tracking-wide text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    CREATE FREE ACCOUNT & START TRIAL
                  </span>
                  <ArrowRight className="w-4 h-4 text-[#1A1A1A] group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </motion.button>
          </div>
        </form>

        <div className="mt-8 pt-6 border-t border-[#E8E4DE] text-center text-[15px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
          Already registered?{' '}
          <Link href="/login" className="text-[#1A1A1A] font-semibold hover:text-[#4A4A4A] transition-colors">
            Sign In Here
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#F0EDE8] flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#1A1A1A] border-t-transparent" />
        </div>
      }
    >
      <RegisterContent />
    </Suspense>
  );
}
