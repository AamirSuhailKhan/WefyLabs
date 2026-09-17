'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, getToken } from '@/lib/api-client';
import {
  OnboardingStatusResponse,
  BusinessProfileSetup,
  TenantActivationResponse,
  ChecklistItem,
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
  const [activationData, setActivationData] = useState<TenantActivationResponse | null>(null);

  // Step 1: Business Profile State
  const [agencyName, setAgencyName] = useState('');
  const [businessType, setBusinessType] = useState('agency');
  const [city, setCity] = useState('Bengaluru');
  const [timezone, setTimezone] = useState('Asia/Kolkata');
  const [currencyCode, setCurrencyCode] = useState('INR');
  const [teamSize, setTeamSize] = useState('1-5');
  const [website, setWebsite] = useState('');

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
    try {
      await api.onboarding.updateStep('ACTIVATED', 'complete');
      router.push('/dashboard');
    } catch (err: any) {
      router.push('/dashboard');
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0d1117] text-white">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent"></div>
          <p className="text-sm font-medium text-slate-400">Initializing your real-estate workspace...</p>
        </div>
      </div>
    );
  }

  const progressPct = statusData?.progress_percentage || 20;

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0B0F17] via-[#111827] to-[#0B0F17] text-slate-100 flex flex-col justify-between py-10 px-4 sm:px-6 lg:px-8">
      {/* Top Header & Progress */}
      <div className="max-w-4xl w-full mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-6 mb-8 gap-4">
          <div className="flex items-center gap-4">
            <WefyLabsLogo theme="dark" size="lg" href={null} />
            <div className="h-8 w-px bg-slate-800 hidden sm:block" />
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="text-[11px] uppercase tracking-widest font-semibold text-emerald-400">Welcome to WefyLabs</span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white mt-0.5">Workspace Onboarding</h1>
            </div>
          </div>
          <div className="text-left sm:text-right">
            <span className="text-xs font-medium text-slate-400">Setup Progress</span>
            <div className="text-lg font-bold text-indigo-400">{progressPct}% Complete</div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden mb-10">
          <div
            className="bg-gradient-to-r from-indigo-500 via-emerald-400 to-teal-400 h-2 transition-all duration-500 ease-out"
            style={{ width: `${progressPct}%` }}
          ></div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="mb-6 rounded-xl bg-rose-950/50 border border-rose-800/80 p-4 text-sm text-rose-300 flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError('')} className="text-rose-400 hover:text-white text-xs">Dismiss</button>
          </div>
        )}
        {successMsg && (
          <div className="mb-6 rounded-xl bg-emerald-950/50 border border-emerald-800/80 p-4 text-sm text-emerald-300 flex items-center justify-between">
            <span>{successMsg}</span>
            <button onClick={() => setSuccessMsg('')} className="text-emerald-400 hover:text-white text-xs">Dismiss</button>
          </div>
        )}

        {/* Step Container Card */}
        <div className="bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-800 shadow-2xl p-6 sm:p-10">

          {/* STEP 1: BUSINESS PROFILE */}
          {currentStep === 'BUSINESS_PROFILE' && (
            <div>
              <div className="mb-6">
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">Step 1 of 5</span>
                <h2 className="text-2xl font-bold text-white mt-1">Configure Your Agency Profile</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Tell us about your organization to personalize your inventory rules, currency formatting, and daily operations.
                </p>
              </div>

              <form onSubmit={handleProfileSubmit} className="space-y-5">
                <div>
                  <label className="block text-xs font-medium uppercase tracking-wider text-slate-300 mb-1.5">
                    Agency / Business Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={agencyName}
                    onChange={(e) => setAgencyName(e.target.value)}
                    placeholder="e.g. Apex Realty Partners"
                    className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium uppercase tracking-wider text-slate-300 mb-1.5">
                      Business Type
                    </label>
                    <select
                      value={businessType}
                      onChange={(e) => setBusinessType(e.target.value)}
                      className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                    >
                      <option value="agency">Real Estate Agency</option>
                      <option value="brokerage">Commercial Brokerage</option>
                      <option value="developer">Builder / Developer</option>
                      <option value="individual">Independent Consultant</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium uppercase tracking-wider text-slate-300 mb-1.5">
                      Operating City *
                    </label>
                    <input
                      type="text"
                      required
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      placeholder="e.g. Bengaluru, Mumbai, Delhi NCR"
                      className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-medium uppercase tracking-wider text-slate-300 mb-1.5">
                      Timezone
                    </label>
                    <select
                      value={timezone}
                      onChange={(e) => setTimezone(e.target.value)}
                      className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                    >
                      <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                      <option value="Asia/Dubai">Asia/Dubai (GST)</option>
                      <option value="Europe/London">Europe/London (GMT)</option>
                      <option value="America/New_York">America/New_York (EST)</option>
                      <option value="Asia/Singapore">Asia/Singapore (SGT)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium uppercase tracking-wider text-slate-300 mb-1.5">
                      Currency
                    </label>
                    <select
                      value={currencyCode}
                      onChange={(e) => setCurrencyCode(e.target.value)}
                      className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                    >
                      <option value="INR">INR (₹)</option>
                      <option value="AED">AED (د.إ)</option>
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium uppercase tracking-wider text-slate-300 mb-1.5">
                      Team Size
                    </label>
                    <select
                      value={teamSize}
                      onChange={(e) => setTeamSize(e.target.value)}
                      className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
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
                    className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition duration-150 shadow-lg shadow-indigo-600/30 flex items-center gap-2"
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
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">Step 2 of 5</span>
                <h2 className="text-2xl font-bold text-white mt-1">Populate Initial Workspace Data</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Experience the AI matching and follow-up engine immediately. Choose how you want to start:
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                {/* Option 1: Demo Mode */}
                <div className="rounded-xl border border-indigo-500/40 bg-indigo-950/20 p-6 flex flex-col justify-between hover:border-indigo-400 transition">
                  <div>
                    <div className="h-10 w-10 rounded-lg bg-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 text-lg">
                      ✨
                    </div>
                    <h3 className="font-bold text-white text-lg">Instant Demo Playground</h3>
                    <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                      Seed 10 realistic Indian properties, 8 buyer leads, and automated AI matches. Perfect for testing without uploading live data.
                    </p>
                  </div>
                  <button
                    onClick={handleStartDemoPlayground}
                    disabled={submitting}
                    className="mt-6 w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold transition"
                  >
                    {submitting ? 'Seeding...' : 'Load Sample Data'}
                  </button>
                </div>

                {/* Option 2: Add Manually */}
                <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-6 flex flex-col justify-between hover:border-slate-500 transition">
                  <div>
                    <div className="h-10 w-10 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300 mb-4 text-lg">
                      ✍️
                    </div>
                    <h3 className="font-bold text-white text-lg">Add Manually</h3>
                    <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                      Enter your first active listing and buyer inquiry using a quick, streamlined 30-second form.
                    </p>
                  </div>
                  <button
                    onClick={() => setCurrentStep('ADD_FIRST_ENTITY')}
                    className="mt-6 w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-semibold transition"
                  >
                    Enter Manually
                  </button>
                </div>

                {/* Option 3: Skip to Dashboard */}
                <div className="rounded-xl border border-slate-700 bg-slate-950/50 p-6 flex flex-col justify-between hover:border-slate-500 transition">
                  <div>
                    <div className="h-10 w-10 rounded-lg bg-slate-800 flex items-center justify-center text-slate-300 mb-4 text-lg">
                      🚀
                    </div>
                    <h3 className="font-bold text-white text-lg">I'll Add Data Later</h3>
                    <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                      Jump straight to the agent command center. You can capture leads and listings any time from the navigation menu.
                    </p>
                  </div>
                  <button
                    onClick={() => setCurrentStep('TEAM_AND_TOOLS')}
                    className="mt-6 w-full py-2.5 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-lg text-sm font-semibold transition"
                  >
                    Skip to Team Setup
                  </button>
                </div>
              </div>

              <div className="flex justify-between items-center pt-4 border-t border-slate-800">
                <button
                  onClick={() => setCurrentStep('BUSINESS_PROFILE')}
                  className="text-sm text-slate-400 hover:text-white"
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
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">Step 3 of 5</span>
                <h2 className="text-2xl font-bold text-white mt-1">Add Your First Record</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Let's create your first property or lead to activate AI matching.
                </p>
              </div>

              <div className="flex gap-4 mb-6">
                <button
                  type="button"
                  onClick={() => setManualMode('property')}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
                    manualMode === 'property'
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300'
                      : 'border-slate-700 text-slate-400 hover:bg-slate-800'
                  }`}
                >
                  Add Property Listing
                </button>
                <button
                  type="button"
                  onClick={() => setManualMode('lead')}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold border ${
                    manualMode === 'lead'
                      ? 'bg-indigo-600/20 border-indigo-500 text-indigo-300'
                      : 'border-slate-700 text-slate-400 hover:bg-slate-800'
                  }`}
                >
                  Add Buyer Lead
                </button>
              </div>

              <form onSubmit={handleCreateManualEntity} className="space-y-4">
                {manualMode === 'property' ? (
                  <>
                    <div>
                      <label className="block text-xs font-medium uppercase text-slate-300 mb-1">
                        Listing Title *
                      </label>
                      <input
                        type="text"
                        required
                        value={propTitle}
                        onChange={(e) => setPropTitle(e.target.value)}
                        placeholder="e.g. Prestige High-Rise 3BHK at Indiranagar"
                        className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-medium uppercase text-slate-300 mb-1">Price ({currencyCode})</label>
                        <input
                          type="number"
                          value={propPrice}
                          onChange={(e) => setPropPrice(e.target.value)}
                          className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium uppercase text-slate-300 mb-1">Bedrooms (BHK)</label>
                        <select
                          value={propBhk}
                          onChange={(e) => setPropBhk(e.target.value)}
                          className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
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
                      <label className="block text-xs font-medium uppercase text-slate-300 mb-1">Lead Client Name</label>
                      <input
                        type="text"
                        value={leadName}
                        onChange={(e) => setLeadName(e.target.value)}
                        placeholder="e.g. Rahul Sharma"
                        className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-medium uppercase text-slate-300 mb-1">Phone Number *</label>
                        <input
                          type="tel"
                          required
                          value={leadPhone}
                          onChange={(e) => setLeadPhone(e.target.value)}
                          placeholder="+91 98765 43210"
                          className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium uppercase text-slate-300 mb-1">Budget Max ({currencyCode})</label>
                        <input
                          type="number"
                          value={leadBudget}
                          onChange={(e) => setLeadBudget(e.target.value)}
                          className="w-full rounded-xl bg-slate-950 border border-slate-700 px-4 py-3 text-white focus:outline-none focus:border-indigo-500"
                        />
                      </div>
                    </div>
                  </>
                )}

                <div className="pt-4 flex justify-between items-center">
                  <button
                    type="button"
                    onClick={() => setCurrentStep('DATA_CHOICE')}
                    className="text-sm text-slate-400 hover:text-white"
                  >
                    ← Back
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition"
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
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">First Value Experience</span>
                <h2 className="text-2xl font-bold text-white mt-1">Lead ↔ Property AI Matching Active</h2>
                <p className="text-sm text-slate-400 mt-1">
                  The AI matching engine has evaluated your inventory against buyer requirements with explainable scoring:
                </p>
              </div>

              <div className="bg-slate-950/70 rounded-xl border border-slate-800 p-6 mb-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">
                      96%
                    </div>
                    <div>
                      <h4 className="font-semibold text-white">Top Match: Indiranagar 3BHK High-Rise</h4>
                      <p className="text-xs text-slate-400">Matched with Buyer: Rahul Sharma (Budget ₹2.45 Cr)</p>
                    </div>
                  </div>
                  <span className="px-3 py-1 bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs font-medium rounded-full">
                    Best Overall Fit
                  </span>
                </div>
                <div className="bg-slate-900 rounded-lg p-3 text-xs text-slate-300 font-mono">
                  💡 AI Reasoning: Exact budget alignment (₹2.45 Cr vs ₹2.5 Cr cap), preferred locality match (Indiranagar), and ready-to-move status.
                </div>
              </div>

              <div className="flex justify-between items-center pt-4 border-t border-slate-800">
                <button
                  onClick={() => setCurrentStep('DATA_CHOICE')}
                  className="text-sm text-slate-400 hover:text-white"
                >
                  ← Back
                </button>
                <button
                  onClick={() => setCurrentStep('TEAM_AND_TOOLS')}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl transition"
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
                <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">Step 4 of 5</span>
                <h2 className="text-2xl font-bold text-white mt-1">Invite Your Teammates (Optional)</h2>
                <p className="text-sm text-slate-400 mt-1">
                  Add agents or managers with secure, role-based permissions. They'll receive a secure single-use access link.
                </p>
              </div>

              <form onSubmit={handleInviteTeam} className="space-y-4 mb-6">
                <div className="flex gap-3">
                  <input
                    type="email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="teammate@agency.com"
                    className="flex-1 rounded-xl bg-slate-950 border border-slate-700 px-4 py-2.5 text-white focus:outline-none focus:border-indigo-500"
                  />
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value as any)}
                    className="rounded-xl bg-slate-950 border border-slate-700 px-4 py-2.5 text-white focus:outline-none focus:border-indigo-500"
                  >
                    <option value="agent">Agent</option>
                    <option value="manager">Manager</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white font-medium rounded-xl text-sm transition"
                  >
                    Send Invite
                  </button>
                </div>
              </form>

              {invitedList.length > 0 && (
                <div className="mb-6 bg-slate-950/40 rounded-xl p-4 border border-slate-800">
                  <span className="text-xs text-slate-400 font-medium">Invited Teammates:</span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {invitedList.map((inv, idx) => (
                      <span key={idx} className="px-3 py-1 bg-slate-800 text-slate-200 text-xs rounded-full border border-slate-700">
                        {inv}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-between items-center pt-4 border-t border-slate-800">
                <button
                  onClick={() => setCurrentStep('DATA_CHOICE')}
                  className="text-sm text-slate-400 hover:text-white"
                >
                  ← Back
                </button>
                <button
                  onClick={() => setCurrentStep('ACTIVATED_SUCCESS')}
                  className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-xl transition shadow-lg shadow-emerald-600/20"
                >
                  Finish Activation →
                </button>
              </div>
            </div>
          )}

          {/* STEP 6: ACTIVATED SUCCESS */}
          {currentStep === 'ACTIVATED_SUCCESS' && (
            <div className="text-center py-6">
              <div className="h-16 w-16 bg-emerald-500/20 text-emerald-400 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl">
                🎉
              </div>
              <h2 className="text-3xl font-bold text-white">Your Workspace is Activated!</h2>
              <p className="text-slate-400 text-sm max-w-md mx-auto mt-2">
                Congratulations! <span className="text-white font-medium">{agencyName || 'Your Agency'}</span> is ready.
                Your real-time inventory, lead tracking, and Daily Command Center are live.
              </p>

              <div className="my-8 max-w-md mx-auto bg-slate-950/70 border border-slate-800 rounded-xl p-4 text-left space-y-2">
                <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
                  <span>✓</span> <span>Agency profile & timezone configured</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
                  <span>✓</span> <span>Initial property inventory & leads initialized</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
                  <span>✓</span> <span>Lead ↔ Property AI matching active</span>
                </div>
                <div className="flex items-center gap-2 text-xs text-emerald-400 font-medium">
                  <span>✓</span> <span>Agent Daily Command Center ready</span>
                </div>
              </div>

              <button
                onClick={handleFinalizeWorkspace}
                className="px-8 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-bold rounded-xl shadow-xl shadow-emerald-500/20 transition transform hover:-translate-y-0.5"
              >
                Launch Daily Command Center →
              </button>
            </div>
          )}

        </div>
      </div>

      {/* Footer Branding Neutral Notice */}
      <footer className="mt-8 text-center text-xs text-slate-500">
        Enterprise Real Estate CRM Platform • End-to-End Multi-Tenant Isolation
      </footer>
    </div>
  );
}
