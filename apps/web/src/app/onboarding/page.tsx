'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api-client';
import {
  OnboardingStatusResponse,
  BusinessProfileSetup,
  TenantActivationResponse,
} from '@/types';
import { WefyLabsLogo } from '@/components/shared/WefyLabsLogo';

type OnboardingWizardStep =
  | 'BUSINESS_PROFILE'
  | 'DATA_CHOICE'
  | 'ADD_FIRST_ENTITY'
  | 'AI_MATCH_SHOWCASE'
  | 'TEAM_AND_TOOLS'
  | 'ACTIVATED_SUCCESS';

export default function OnboardingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Wizard Navigation
  const [currentStep, setCurrentStep] = useState<OnboardingWizardStep>('BUSINESS_PROFILE');
  const [statusData, setStatusData] = useState<OnboardingStatusResponse | null>(null);
  const [, setActivationData] = useState<TenantActivationResponse | null>(null);

  // Step 1: Business Profile State
  const [agencyName, setAgencyName] = useState('');
  const [businessType, setBusinessType] = useState('agency');
  const [city, setCity] = useState('Bengaluru');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [currencyCode, setCurrencyCode] = useState('INR');
  const [teamSize, setTeamSize] = useState('1-5');
  const [website] = useState('');

  // Step 2 & 3: Manual Entity Creation / CSV Preview
  const [manualMode, setManualMode] = useState<'lead' | 'property'>('property');
  const [propTitle, setPropTitle] = useState('');
  const [propPrice, setPropPrice] = useState('15000000');
  const [propBhk, setPropBhk] = useState('3');
  const [leadName, setLeadName] = useState('');
  const [leadPhone, setLeadPhone] = useState('');
  const [leadBudget, setLeadBudget] = useState('15000000');

  // Step 4: Team Invite
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'admin' | 'manager' | 'agent'>('agent');
  const [invitedList, setInvitedList] = useState<string[]>([]);

  useEffect(() => {
    async function initOnboarding() {
      const token = getToken();
      if (!token) {
        router.push('/login');
        return;
      }

      try {
        const broker = await api.auth.me();
        if (broker.name && !agencyName) {
          setAgencyName(broker.agency_name || `${broker.name} Realty`);
        }
        if (broker.city) setCity(broker.city);

        // Fetch authoritative onboarding status & activation
        const [statusRes, actRes] = await Promise.all([
          api.onboarding.getStatus().catch(() => null),
          api.onboarding.getActivation().catch(() => null),
        ]);

        if (statusRes) {
          setStatusData(statusRes);
          // If already completely activated and completed, redirect to dashboard
          if (statusRes.is_completed && statusRes.is_activated) {
            router.push('/dashboard');
            return;
          }
        }
        if (actRes) setActivationData(actRes);

        setLoading(false);
      } catch (err: any) {
        console.error('Failed to load onboarding context:', err);
        setError('Could not connect to workspace services. Please try again.');
        setLoading(false);
      }
    }
    initOnboarding();
  }, [router]);

  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agencyName.trim()) {
      setError('Please provide an agency or trading name.');
      return;
    }
    setError('');
    setSubmitting(true);

    try {
      const payload: BusinessProfileSetup = {
        agency_name: agencyName.trim(),
        business_type: businessType,
        city: city.trim() || 'Bengaluru',
        country_code: 'IN',
        timezone,
        currency_code: currencyCode,
        team_size: teamSize,
        website: website.trim() || undefined,
      };

      const updated = await api.onboarding.updateBusinessProfile(payload);
      setStatusData(updated);
      setCurrentStep('DATA_CHOICE');
    } catch (err: any) {
      setError(err.message || 'Failed to save business profile.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartDemoPlayground = async () => {
    setError('');
    setSubmitting(true);
    try {
      const res = await api.onboarding.startDemo(agencyName || 'Demo Agency', city || 'Bengaluru');
      setSuccessMsg(`Synthetic demo workspace created with ${res.seeded_properties_count} properties and ${res.seeded_leads_count} leads.`);
      // Refresh status
      const updated = await api.onboarding.getStatus();
      setStatusData(updated);
      setCurrentStep('AI_MATCH_SHOWCASE');
    } catch (err: any) {
      setError(err.message || 'Failed to initialize demo environment.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateManualEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      if (manualMode === 'property') {
        if (!propTitle.trim()) {
          setError('Property title is required.');
          setSubmitting(false);
          return;
        }
        // Commit single property via onboarding commit API
        await api.onboarding.commitCsv('properties', [
          {
            title: propTitle.trim(),
            price: parseFloat(propPrice) || 10000000,
            bedrooms: parseInt(propBhk, 10) || 2,
            city,
            locality: 'Central',
            property_type: 'apartment',
          },
        ]);
        setSuccessMsg('Property successfully added to inventory!');
      } else {
        if (!leadPhone.trim() || leadPhone.length < 8) {
          setError('Valid lead phone number is required.');
          setSubmitting(false);
          return;
        }
        await api.onboarding.commitCsv('leads', [
          {
            name: leadName.trim() || 'Client Inquiry',
            phone: leadPhone.trim(),
            budget_max: parseInt(leadBudget, 10) || 15000000,
            property_type: 'apartment',
            preferred_locations: [city],
          },
        ]);
        setSuccessMsg('Lead successfully captured in CRM!');
      }

      const updated = await api.onboarding.getStatus();
      setStatusData(updated);
      setCurrentStep('AI_MATCH_SHOWCASE');
    } catch (err: any) {
      setError(err.message || 'Failed to save record.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleInviteTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim() || !inviteEmail.includes('@')) {
      setError('Please provide a valid email address.');
      return;
    }
    setError('');
    setSubmitting(true);

    try {
      await api.onboarding.inviteTeam(inviteEmail.trim(), inviteRole);
      setInvitedList((prev) => [...prev, `${inviteEmail} (${inviteRole})`]);
      setInviteEmail('');
      setSuccessMsg(`Invitation dispatched to ${inviteEmail}.`);
      const updated = await api.onboarding.getStatus();
      setStatusData(updated);
    } catch (err: any) {
      setError(err.message || 'Failed to dispatch team invitation.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinalizeWorkspace = async () => {
    setSubmitting(true);
    setError('');
    try {
      await api.onboarding.updateStep('ACTIVATED', 'complete');
      router.push('/dashboard');
    } catch (err: any) {
      setError(err?.message || 'Workspace activation failed. Please review your setup and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F0EDE8] flex flex-col items-center justify-center p-4">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#1A1A1A] border-t-transparent" />
          <p className="text-[13px] font-semibold text-[#6B6B6B] font-mono uppercase tracking-wider">
            Initializing workspace...
          </p>
        </div>
      </div>
    );
  }

  const progressPct = statusData?.progress_percentage || 20;

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col justify-between py-10 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
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

      {/* Ambient Background Elements matching Login Page */}
      <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden flex items-center justify-center">
        <div className="absolute top-[-20%] left-[-10%] w-[70vw] h-[70vw] max-w-[800px] max-h-[800px] bg-[#E8F5A8] opacity-20 blur-[120px] rounded-full animate-pulse-slow mix-blend-multiply" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] max-w-[700px] max-h-[700px] bg-[#d4f5a4] opacity-20 blur-[100px] rounded-full animate-drift mix-blend-multiply" />
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0IiBoZWlnaHQ9IjQiPgo8cmVjdCB3aWR0aD0iNCIgaGVpZ2h0PSI0IiBmaWxsPSIjZmZmIiBmaWxsLW9wYWNpdHk9IjAuMCIvPgo8cGF0aCBkPSJNMCAwTDRgME0wIDRMNCw0TTAgMEw0LDRNMCA0TDQsMCIgc3Ryb2tlPSIjMDAwIiBzdHJva2Utd2lkdGg9IjAuMDUiIHN0cm9rZS1vcGFjaXR5PSIwLjAyIi8+Cjwvc3ZnPg==')] opacity-50 mix-blend-multiply" />
      </div>

      {/* Top Header & Progress */}
      <div className="max-w-4xl w-full mx-auto relative z-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#D4D0C8] pb-6 mb-8 gap-4">
          <div className="flex items-center gap-4">
            <WefyLabsLogo dark={false} size="lg" href={null} />
            <div className="h-8 w-px bg-[#D4D0C8] hidden sm:block" />
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono">
                  Welcome to WefyLabs
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold mono-headline text-[#1A1A1A] tracking-tight mt-0.5">
                Workspace Onboarding
              </h1>
            </div>
          </div>
          <div className="text-left sm:text-right">
            <span className="text-xs font-bold text-[#A0A0A0] uppercase tracking-wider font-mono">Setup Progress</span>
            <div className="text-lg font-bold font-mono text-[#1A1A1A]">{progressPct}% Complete</div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-[#E8E4DE] h-2 rounded-full overflow-hidden mb-10">
          <div
            className="bg-[#1A1A1A] h-2 transition-all duration-500 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-6 rounded-xl bg-[#FEE2E2] border border-[#FCA5A5] p-4 text-sm font-medium text-[#DC2626] flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-[#DC2626] hover:text-[#991B1B] text-xs font-bold font-mono">
              Dismiss
            </button>
          </div>
        )}
        {successMsg && (
          <div className="mb-6 rounded-xl bg-[#ECFDF5] border border-[#A7F3D0] p-4 text-sm font-medium text-[#065F46] flex items-center justify-between">
            <span>{successMsg}</span>
            <button onClick={() => setSuccessMsg('')} className="text-[#065F46] hover:text-[#047857] text-xs font-bold font-mono">
              Dismiss
            </button>
          </div>
        )}

        {/* Step Container Card */}
        <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 sm:p-10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative z-10">

          {/* STEP 1: BUSINESS PROFILE */}
          {currentStep === 'BUSINESS_PROFILE' && (
            <div>
              <div className="mb-6">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono">Step 1 of 5</span>
                <h2 className="text-2xl md:text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight mt-1">
                  Configure Your Agency Profile
                </h2>
                <p className="text-[15px] text-[#6B6B6B] mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Tell us about your organization to personalize your inventory rules, currency formatting, and daily operations.
                </p>
              </div>

              <form onSubmit={handleProfileSubmit} className="space-y-5">
                <div>
                  <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                    Agency / Business Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={agencyName}
                    onChange={(e) => setAgencyName(e.target.value)}
                    placeholder="e.g. Apex Realty Partners"
                    className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                      Business Type
                    </label>
                    <select
                      value={businessType}
                      onChange={(e) => setBusinessType(e.target.value)}
                      className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                    >
                      <option value="agency">Real Estate Agency</option>
                      <option value="brokerage">Commercial Brokerage</option>
                      <option value="developer">Builder / Developer</option>
                      <option value="individual">Independent Consultant</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                      Operating City *
                    </label>
                    <input
                      type="text"
                      required
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      placeholder="e.g. Bengaluru, Mumbai, Delhi NCR"
                      className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                      Timezone
                    </label>
                    <select
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                    >
                      <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                      <option value="Asia/Dubai">Asia/Dubai (GST)</option>
                      <option value="Europe/London">Europe/London (GMT)</option>
                      <option value="America/New_York">America/New_York (EST)</option>
                      <option value="Asia/Singapore">Asia/Singapore (SGT)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                      Currency
                    </label>
                    <select
                      value={currencyCode}
                      onChange={(e) => setCurrencyCode(e.target.value)}
                      className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                    >
                      <option value="INR">INR (₹)</option>
                      <option value="AED">AED (د.إ)</option>
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                      Team Size
                    </label>
                    <select
                      value={teamSize}
                      onChange={(e) => setTeamSize(e.target.value)}
                      className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                    >
                      <option value="1-5">1 - 5 Agents</option>
                      <option value="6-20">6 - 20 Agents</option>
                      <option value="21-50">21 - 50 Agents</option>
                      <option value="50+">50+ Enterprise</option>
                    </select>
                  </div>
                </div>

                <div className="pt-4 flex justify-end">
                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full sm:w-auto px-8 py-3.5 bg-[#E8F5A8] hover:bg-[#E1F099] border border-[#D4D0C8] text-[#1A1A1A] font-bold text-[13px] tracking-wide rounded-xl shadow-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {submitting ? 'Saving Profile...' : 'Continue to Workspace Setup →'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* STEP 2: DATA ONBOARDING CHOICE */}
          {currentStep === 'DATA_CHOICE' && (
            <div>
              <div className="mb-6">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono">Step 2 of 5</span>
                <h2 className="text-2xl md:text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight mt-1">
                  Populate Initial Workspace Data
                </h2>
                <p className="text-[15px] text-[#6B6B6B] mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Experience the AI matching and follow-up engine immediately. Choose how you want to start:
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                {/* Option 1: Demo Mode */}
                <div className="rounded-2xl border border-[#D4D0C8] bg-[#FAF7F2] p-6 flex flex-col justify-between hover:border-[#1A1A1A] transition shadow-xs">
                  <div>
                    <div className="h-10 w-10 rounded-xl bg-white border border-[#D4D0C8] flex items-center justify-center text-[#1A1A1A] mb-4 text-lg">
                      ✨
                    </div>
                    <h3 className="font-bold text-[#1A1A1A] text-lg mono-headline">Instant Demo Playground</h3>
                    <p className="text-xs text-[#6B6B6B] mt-2 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                      Seed 10 realistic Indian properties, 8 buyer leads, and automated AI matches. Perfect for testing without uploading live data.
                    </p>
                  </div>
                  <button
                    onClick={handleStartDemoPlayground}
                    disabled={submitting}
                    className="mt-6 w-full py-3 bg-[#E8F5A8] hover:bg-[#E1F099] text-[#1A1A1A] border border-[#D4D0C8] rounded-xl text-[13px] font-bold tracking-wide transition shadow-sm disabled:opacity-50"
                  >
                    {submitting ? 'Seeding...' : 'Load Sample Data'}
                  </button>
                </div>

                {/* Option 2: Add Manually */}
                <div className="rounded-2xl border border-[#D4D0C8] bg-white p-6 flex flex-col justify-between hover:border-[#1A1A1A] transition shadow-xs">
                  <div>
                    <div className="h-10 w-10 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] flex items-center justify-center text-[#1A1A1A] mb-4 text-lg">
                      ✍️
                    </div>
                    <h3 className="font-bold text-[#1A1A1A] text-lg mono-headline">Add Manually</h3>
                    <p className="text-xs text-[#6B6B6B] mt-2 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                      Enter your first active listing and buyer inquiry using a quick, streamlined 30-second form.
                    </p>
                  </div>
                  <button
                    onClick={() => setCurrentStep('ADD_FIRST_ENTITY')}
                    className="mt-6 w-full py-3 bg-white hover:bg-[#FAF7F2] text-[#1A1A1A] border border-[#D4D0C8] rounded-xl text-[13px] font-semibold transition shadow-sm"
                  >
                    Enter Manually
                  </button>
                </div>

                {/* Option 3: Skip to Dashboard */}
                <div className="rounded-2xl border border-[#D4D0C8] bg-white p-6 flex flex-col justify-between hover:border-[#1A1A1A] transition shadow-xs">
                  <div>
                    <div className="h-10 w-10 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] flex items-center justify-center text-[#1A1A1A] mb-4 text-lg">
                      🚀
                    </div>
                    <h3 className="font-bold text-[#1A1A1A] text-lg mono-headline">I'll Add Data Later</h3>
                    <p className="text-xs text-[#6B6B6B] mt-2 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                      Jump straight to the agent command center. You can capture leads and listings any time from the navigation menu.
                    </p>
                  </div>
                  <button
                    onClick={() => setCurrentStep('TEAM_AND_TOOLS')}
                    className="mt-6 w-full py-3 bg-white hover:bg-[#FAF7F2] text-[#6B6B6B] hover:text-[#1A1A1A] border border-[#D4D0C8] rounded-xl text-[13px] font-semibold transition shadow-sm"
                  >
                    Skip to Team Setup
                  </button>
                </div>
              </div>

              <div className="flex justify-between items-center pt-4 border-t border-[#E8E4DE]">
                <button
                  onClick={() => setCurrentStep('BUSINESS_PROFILE')}
                  className="text-sm font-semibold text-[#6B6B6B] hover:text-[#1A1A1A] transition-colors"
                >
                  ← Back to Profile
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: MANUAL FIRST ENTITY FORM */}
          {currentStep === 'ADD_FIRST_ENTITY' && (
            <div>
              <div className="mb-6">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono">Step 3 of 5</span>
                <h2 className="text-2xl md:text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight mt-1">
                  Add Your First Record
                </h2>
                <p className="text-[15px] text-[#6B6B6B] mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Let's create your first property or lead to activate AI matching.
                </p>
              </div>

              <div className="flex gap-4 mb-6">
                <button
                  type="button"
                  onClick={() => setManualMode('property')}
                  className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider font-mono border transition-all ${
                    manualMode === 'property'
                      ? 'bg-[#1A1A1A] border-[#1A1A1A] text-white shadow-sm'
                      : 'bg-white border-[#D4D0C8] text-[#6B6B6B] hover:bg-[#FAF7F2]'
                  }`}
                >
                  Add Property Listing
                </button>
                <button
                  type="button"
                  onClick={() => setManualMode('lead')}
                  className={`flex-1 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider font-mono border transition-all ${
                    manualMode === 'lead'
                      ? 'bg-[#1A1A1A] border-[#1A1A1A] text-white shadow-sm'
                      : 'bg-white border-[#D4D0C8] text-[#6B6B6B] hover:bg-[#FAF7F2]'
                  }`}
                >
                  Add Buyer Lead
                </button>
              </div>

              <form onSubmit={handleCreateManualEntity} className="space-y-4">
                {manualMode === 'property' ? (
                  <>
                    <div>
                      <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                        Listing Title *
                      </label>
                      <input
                        type="text"
                        required
                        value={propTitle}
                        onChange={(e) => setPropTitle(e.target.value)}
                        placeholder="e.g. Prestige High-Rise 3BHK at Indiranagar"
                        className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                          Price ({currencyCode})
                        </label>
                        <input
                          type="number"
                          value={propPrice}
                          onChange={(e) => setPropPrice(e.target.value)}
                          className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                          Bedrooms (BHK)
                        </label>
                        <select
                          value={propBhk}
                          onChange={(e) => setPropBhk(e.target.value)}
                          className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                        >
                          <option value="1">1 BHK</option>
                          <option value="2">2 BHK</option>
                          <option value="3">3 BHK</option>
                          <option value="4">4+ BHK / Villa</option>
                        </select>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                        Lead Client Name
                      </label>
                      <input
                        type="text"
                        value={leadName}
                        onChange={(e) => setLeadName(e.target.value)}
                        placeholder="e.g. Rahul Sharma"
                        className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                          Phone Number *
                        </label>
                        <input
                          type="tel"
                          required
                          value={leadPhone}
                          onChange={(e) => setLeadPhone(e.target.value)}
                          placeholder="+91 98765 43210"
                          className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-[#1A1A1A] uppercase tracking-wider mb-2 font-mono">
                          Budget Max ({currencyCode})
                        </label>
                        <input
                          type="number"
                          value={leadBudget}
                          onChange={(e) => setLeadBudget(e.target.value)}
                          className="w-full px-4 py-3 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] transition-colors text-[15px]"
                        />
                      </div>
                    </div>
                  </>
                )}

                <div className="pt-4 flex justify-between items-center border-t border-[#E8E4DE]">
                  <button
                    type="button"
                    onClick={() => setCurrentStep('DATA_CHOICE')}
                    className="text-sm font-semibold text-[#6B6B6B] hover:text-[#1A1A1A] transition-colors"
                  >
                    ← Back
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-6 py-3 bg-[#E8F5A8] hover:bg-[#E1F099] border border-[#D4D0C8] text-[#1A1A1A] font-bold text-[13px] tracking-wide rounded-xl transition shadow-sm disabled:opacity-50"
                  >
                    {submitting ? 'Saving...' : 'Save & Continue →'}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* STEP 4: AI MATCH SHOWCASE */}
          {currentStep === 'AI_MATCH_SHOWCASE' && (
            <div>
              <div className="mb-6">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono">
                  First Value Experience
                </span>
                <h2 className="text-2xl md:text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight mt-1">
                  Lead ↔ Property AI Matching Active
                </h2>
                <p className="text-[15px] text-[#6B6B6B] mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                  The AI matching engine has evaluated your inventory against buyer requirements with explainable scoring:
                </p>
              </div>

              <div className="bg-[#FAF7F2] rounded-2xl border border-[#D4D0C8] p-6 mb-6 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-[#D1FAE5] text-[#065F46] border border-[#A7F3D0] flex items-center justify-center font-bold font-mono text-sm shrink-0">
                      96%
                    </div>
                    <div>
                      <h4 className="font-bold text-[#1A1A1A] text-base">Top Match: Indiranagar 3BHK High-Rise</h4>
                      <p className="text-xs text-[#6B6B6B] mt-0.5">Matched with Buyer: Rahul Sharma (Budget ₹2.45 Cr)</p>
                    </div>
                  </div>
                  <span className="self-start sm:self-auto px-3 py-1 bg-[#ECFDF5] text-[#047857] border border-[#A7F3D0] text-xs font-semibold rounded-full font-mono">
                    Best Overall Fit
                  </span>
                </div>
                <div className="bg-white border border-[#E8E4DE] rounded-xl p-3.5 text-xs text-[#4A4A4A] font-mono leading-relaxed">
                  💡 AI Reasoning: Exact budget alignment (₹2.45 Cr vs ₹2.5 Cr cap), preferred locality match (Indiranagar), and ready-to-move status.
                </div>
              </div>

              <div className="flex justify-between items-center pt-4 border-t border-[#E8E4DE]">
                <button
                  onClick={() => setCurrentStep('DATA_CHOICE')}
                  className="text-sm font-semibold text-[#6B6B6B] hover:text-[#1A1A1A] transition-colors"
                >
                  ← Back
                </button>
                <button
                  onClick={() => setCurrentStep('TEAM_AND_TOOLS')}
                  className="px-6 py-3 bg-[#E8F5A8] hover:bg-[#E1F099] border border-[#D4D0C8] text-[#1A1A1A] font-bold text-[13px] tracking-wide rounded-xl transition shadow-sm"
                >
                  Invite Team & Complete Setup →
                </button>
              </div>
            </div>
          )}

          {/* STEP 5: TEAM & TOOLS */}
          {currentStep === 'TEAM_AND_TOOLS' && (
            <div>
              <div className="mb-6">
                <span className="text-[11px] font-bold uppercase tracking-widest text-[#A0A0A0] font-mono">Step 4 of 5</span>
                <h2 className="text-2xl md:text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight mt-1">
                  Invite Your Teammates (Optional)
                </h2>
                <p className="text-[15px] text-[#6B6B6B] mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Add agents or managers with secure, role-based permissions. They'll receive a secure single-use access link.
                </p>
              </div>

              <form onSubmit={handleInviteTeam} className="space-y-4 mb-6">
                <div className="flex flex-col sm:flex-row gap-3">
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="teammate@agency.com"
                    className="flex-1 px-4 py-2.5 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] placeholder-[#BDBDBD] focus:outline-none focus:border-[#1A1A1A] focus:ring-1 focus:ring-[#1A1A1A] text-[15px]"
                  />
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as any)}
                    className="px-4 py-2.5 bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A] text-[15px]"
                  >
                    <option value="agent">Agent</option>
                    <option value="manager">Manager</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-5 py-2.5 bg-white border border-[#D4D0C8] hover:bg-[#FAF7F2] text-[#1A1A1A] font-semibold rounded-xl text-sm transition shadow-sm disabled:opacity-50"
                  >
                    Send Invite
                  </button>
                </div>
              </form>

              {invitedList.length > 0 && (
                <div className="mb-6 bg-[#FAF7F2] rounded-2xl p-4 border border-[#D4D0C8]">
                  <span className="text-xs text-[#6B6B6B] font-bold uppercase tracking-wider font-mono">Invited Teammates:</span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {invitedList.map((inv, idx) => (
                      <span key={idx} className="px-3 py-1 bg-white text-[#1A1A1A] text-xs font-mono rounded-full border border-[#D4D0C8] shadow-2xs">
                        {inv}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-between items-center pt-4 border-t border-[#E8E4DE]">
                <button
                  onClick={() => setCurrentStep('DATA_CHOICE')}
                  className="text-sm font-semibold text-[#6B6B6B] hover:text-[#1A1A1A] transition-colors"
                >
                  ← Back
                </button>
                <button
                  onClick={() => setCurrentStep('ACTIVATED_SUCCESS')}
                  className="px-6 py-3 bg-[#E8F5A8] hover:bg-[#E1F099] border border-[#D4D0C8] text-[#1A1A1A] font-bold text-[13px] tracking-wide rounded-xl transition shadow-sm"
                >
                  Finish Activation →
                </button>
              </div>
            </div>
          )}

          {/* STEP 6: ACTIVATED SUCCESS */}
          {currentStep === 'ACTIVATED_SUCCESS' && (
            <div className="text-center py-6">
              <div className="h-16 w-16 bg-[#ECFDF5] border border-[#A7F3D0] text-[#065F46] rounded-full flex items-center justify-center mx-auto mb-4 text-3xl">
                🎉
              </div>
              <h2 className="text-3xl font-bold mono-headline text-[#1A1A1A] tracking-tight">
                Your Workspace is Activated!
              </h2>
              <p className="text-[#6B6B6B] text-[15px] max-w-md mx-auto mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                Congratulations! <span className="text-[#1A1A1A] font-semibold">{agencyName || 'Your Agency'}</span> is ready.
                Your real-time inventory, lead tracking, and Daily Command Center are live.
              </p>

              <div className="my-8 max-w-md mx-auto bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-5 text-left space-y-2.5">
                <div className="flex items-center gap-2.5 text-xs text-[#1A1A1A] font-mono">
                  <span className="text-[#10B981] font-bold">✓</span> <span>Agency profile & timezone configured</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-[#1A1A1A] font-mono">
                  <span className="text-[#10B981] font-bold">✓</span> <span>Initial property inventory & leads initialized</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-[#1A1A1A] font-mono">
                  <span className="text-[#10B981] font-bold">✓</span> <span>Lead ↔ Property AI matching active</span>
                </div>
                <div className="flex items-center gap-2.5 text-xs text-[#1A1A1A] font-mono">
                  <span className="text-[#10B981] font-bold">✓</span> <span>Agent Daily Command Center ready</span>
                </div>
              </div>

              <button
                onClick={handleFinalizeWorkspace}
                className="px-8 py-4 bg-[#E8F5A8] hover:bg-[#E1F099] border border-[#D4D0C8] text-[#1A1A1A] font-bold text-[13px] tracking-wide rounded-xl shadow-sm transition transform hover:-translate-y-0.5"
              >
                Launch Daily Command Center →
              </button>
            </div>
          )}

        </div>
      </div>

      {/* Footer Branding Neutral Notice */}
      <footer className="mt-8 text-center text-xs text-[#6B6B6B] relative z-10 font-mono">
        Enterprise Real Estate CRM Platform • End-to-End Multi-Tenant Isolation
      </footer>
    </div>
  );
}
