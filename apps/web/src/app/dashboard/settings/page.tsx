'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, CreditCard, MessageSquare, CheckCircle2, Copy, Calendar } from 'lucide-react';
import { api } from '@/lib/api-client';
import { useBroker } from '@/lib/auth-context';
import { Broker } from '@/types';
import DashboardNav from '@/components/shared/DashboardNav';
import RazorpayCheckoutModal from '@/components/billing/RazorpayCheckoutModal';

export default function SettingsPage() {
  const { broker, updateProfile } = useBroker();
  const [billingStatus, setBillingStatus] = useState<any>(null);
  const [calendarStatus, setCalendarStatus] = useState<any>(null);
  const [calendarConnecting, setCalendarConnecting] = useState(false);
  const [name, setName] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [city, setCity] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [submittingPlan, setSubmittingPlan] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [checkoutPlanId, setCheckoutPlanId] = useState('pro_monthly');


  useEffect(() => {
    if (broker) {
      setName(broker.name || '');
      setAgencyName(broker.agency_name || '');
      setCity(broker.city || 'Bengaluru');
      setWhatsappNumber(broker.whatsapp_number || broker.phone || '');
    }
  }, [broker]);

  useEffect(() => {
    async function loadSettings() {
      try {
        const [statusRes, calRes] = await Promise.all([
          api.billing.getStatus().catch(() => null),
          api.calendar.getGoogleStatus().catch(() => null),
        ]);
        if (statusRes) setBillingStatus(statusRes);
        if (calRes) setCalendarStatus(calRes);
      } catch (e) {
        console.warn('Could not load settings metadata', e);
      }
    }
    loadSettings();
  }, []);

  const handleConnectCalendar = async () => {
    setCalendarConnecting(true);
    try {
      const redirectUri = `${window.location.origin}/auth/callback?type=calendar`;
      const res = await api.calendar.getGoogleConnectUrl(redirectUri);
      if (res && res.auth_url) {
        window.location.href = res.auth_url;
      }
    } catch (err: any) {
      alert(err.message || 'Failed to initiate Google Calendar connection.');
    } finally {
      setCalendarConnecting(false);
    }
  };

  const handleDisconnectCalendar = async () => {
    if (!confirm('Are you sure you want to disconnect Google Calendar?')) return;
    setCalendarConnecting(true);
    try {
      await api.calendar.disconnectGoogle();
      setCalendarStatus({ is_connected: false, account_email: null, status: 'NOT_CONNECTED' });
    } catch (err: any) {
      alert(err.message || 'Failed to disconnect Google Calendar.');
    } finally {
      setCalendarConnecting(false);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await updateProfile({ name, agency_name: agencyName, city, whatsapp_number: whatsappNumber });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      alert(err.message || 'Failed updating profile');
    } finally {
      setLoading(false);
    }
  };

  const handleUpgradePlan = (planId: string) => {
    setCheckoutPlanId(planId);
    setIsCheckoutOpen(true);
  };

  const getWebhookUrl = () => {
    if (typeof window !== 'undefined') {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || `${window.location.origin}/api/v1`;
      return `${apiBase.replace(/\/+$/, '')}/whatsapp/webhook`;
    }
    return '/api/v1/whatsapp/webhook';
  };

  const handleCopyWebhook = () => {
    navigator.clipboard.writeText(getWebhookUrl());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fieldLabel = (text: string) => (
    <label className="block text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
      {text}
    </label>
  );

  const inputClass = "w-full bg-white border border-[#D4D0C8] rounded-xl h-12 px-4 text-[14px] text-[#1A1A1A] placeholder:text-[#A0A0A0] focus:outline-none focus:border-[#1A1A1A] transition-colors";

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">

          {/* Page Header */}
          <div className="py-8 border-b border-[#D4D0C8]">
            <h1
              className="text-[28px] sm:text-[32px] font-bold text-[#1A1A1A] tracking-tight"
              style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
            >
              Broker Profile &amp;{' '}
              <span className="bg-[#E8F5A8]/70 px-2 rounded">Settings</span>
            </h1>
            <p className="text-[14px] text-[#6B6B6B] mt-2" style={{ fontFamily: 'Inter, sans-serif' }}>
              Manage your real estate agency profile, WhatsApp Business integration &amp; Razorpay subscription.
            </p>
          </div>

          {/* Layout */}
          <div className="py-8 grid grid-cols-1 md:grid-cols-[55fr_45fr] gap-8">

            {/* LEFT: Agency Details */}
            <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-8 shadow-sm">
              <div className="flex items-center gap-2.5 mb-6 pb-4 border-b border-[#D4D0C8]">
                <Settings className="w-5 h-5 text-[#1A1A1A]" />
                <span className="text-[16px] font-semibold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Agency &amp; Contact Details
                </span>
              </div>

              {saved && (
                <div className="mb-5 flex items-center gap-2.5 p-3.5 rounded-xl bg-[#DCFCE7] border border-[#BBF7D0] text-[#15803D]">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span className="text-[13px] font-semibold" style={{ fontFamily: 'Inter, sans-serif' }}>
                    Profile updated successfully!
                  </span>
                </div>
              )}

              <form onSubmit={handleSaveProfile} className="space-y-5">
                <div>
                  {fieldLabel('Broker Full Name')}
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Rahul Sharma"
                    required
                    className={inputClass}
                  />
                </div>

                <div>
                  {fieldLabel('Real Estate Agency Name')}
                  <input
                    type="text"
                    value={agencyName}
                    onChange={(e) => setAgencyName(e.target.value)}
                    placeholder="e.g. Apex Realty Bengaluru"
                    required
                    className={inputClass}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    {fieldLabel('Operating City')}
                    <input
                      type="text"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      placeholder="Bengaluru"
                      required
                      className={inputClass}
                    />
                  </div>
                  <div>
                    {fieldLabel('WhatsApp Number')}
                    <input
                      type="text"
                      value={whatsappNumber}
                      onChange={(e) => setWhatsappNumber(e.target.value)}
                      placeholder="+919876543210"
                      required
                      className={inputClass}
                    />
                  </div>
                </div>

                <div className="pt-2 border-t border-[#D4D0C8]" />

                <motion.button
                  whileHover={{ y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  type="submit"
                  disabled={loading}
                  className="bg-[#1A1A1A] hover:bg-[#333333] text-white font-semibold px-6 h-12 rounded-xl text-[13px] transition-all disabled:opacity-50 w-full sm:w-auto shadow-sm"
                  style={{ fontFamily: 'Inter, sans-serif' }}
                >
                  {loading ? 'Saving...' : 'Save Profile Changes'}
                </motion.button>
              </form>
            </div>

            {/* RIGHT: Calendar + WhatsApp + Billing */}
            <div className="space-y-6">

              {/* Google Calendar Integration Card */}
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-8 shadow-sm">
                <div className="flex items-center justify-between mb-5 pb-4 border-b border-[#D4D0C8]">
                  <div className="flex items-center gap-2.5">
                    <Calendar className="w-5 h-5 text-[#1A1A1A]" />
                    <span className="text-[16px] font-semibold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                      Google Calendar
                    </span>
                  </div>
                  {calendarStatus?.is_connected ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#DCFCE7] text-[#15803D] border border-[#BBF7D0]">
                      <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                      Connected
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#F3F4F6] text-[#6B7280] border border-[#E5E7EB]">
                      <span className="w-2 h-2 rounded-full bg-[#9CA3AF]" />
                      Not Connected
                    </span>
                  )}
                </div>

                <p className="text-[13px] text-[#6B6B6B] mb-5 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Sync meeting schedules, check broker free/busy availability, and automatically generate Google Meet links for property viewings.
                </p>

                {calendarStatus?.is_connected ? (
                  <div className="space-y-4">
                    <div className="bg-white border border-[#D4D0C8] rounded-xl p-4 flex items-center justify-between">
                      <div>
                        <span className="text-[11px] font-bold uppercase tracking-widest text-[#6B6B6B] block mb-0.5" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                          Connected Account
                        </span>
                        <span className="text-[14px] font-semibold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                          {calendarStatus.account_email || 'broker@gmail.com'}
                        </span>
                      </div>
                      <span className="text-[12px] text-[#10B981] font-medium">OAuth 2.0 Active</span>
                    </div>

                    <div className="flex items-center gap-3">
                      <motion.button
                        whileHover={{ y: -1 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleDisconnectCalendar}
                        disabled={calendarConnecting}
                        className="px-4 h-10 rounded-xl text-[12px] font-semibold text-[#EF4444] bg-white border border-[#FCA5A5] hover:bg-[#FEF2F2] transition-colors disabled:opacity-50"
                        style={{ fontFamily: 'Inter, sans-serif' }}
                      >
                        Disconnect Calendar
                      </motion.button>

                      <motion.button
                        whileHover={{ y: -1 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={handleConnectCalendar}
                        disabled={calendarConnecting}
                        className="px-4 h-10 rounded-xl text-[12px] font-semibold text-[#1A1A1A] bg-white border border-[#D4D0C8] hover:bg-[#F5F0EB] transition-colors disabled:opacity-50"
                        style={{ fontFamily: 'Inter, sans-serif' }}
                      >
                        Reauthorize
                      </motion.button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <motion.button
                      whileHover={{ y: -2 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={handleConnectCalendar}
                      disabled={calendarConnecting}
                      className="w-full bg-[#1A1A1A] hover:bg-[#333333] text-white h-11 rounded-xl text-[13px] font-semibold transition-colors disabled:opacity-50 shadow-sm flex items-center justify-center gap-2"
                      style={{ fontFamily: 'Inter, sans-serif' }}
                    >
                      <Calendar className="w-4 h-4 text-[#E8F5A8]" />
                      <span>{calendarConnecting ? 'Redirecting to Google...' : 'Connect Google Calendar'}</span>
                    </motion.button>
                    <p className="text-[11px] text-[#9CA3AF] text-center" style={{ fontFamily: 'Inter, sans-serif' }}>
                      Requires calendar.events &amp; calendar.readonly permissions.
                    </p>
                  </div>
                )}

                {/* Notion Calendar Client Guidance */}
                <div className="mt-6 pt-5 border-t border-[#D4D0C8]">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[12px] font-bold text-[#1A1A1A]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      NOTION CALENDAR USER EXPERIENCE
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#E8F5A8] text-[#1A1A1A]">
                      Recommended Client
                    </span>
                  </div>
                  <p className="text-[12px] text-[#6B6B6B] mb-3 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                    Your CRM uses Google Calendar for backend scheduling, Free/Busy availability, and Google Meet generation. You can view and manage all appointments in Notion Calendar.
                  </p>
                  <div className="bg-white/80 border border-[#D4D0C8] rounded-xl p-3.5 space-y-2 text-[12px] text-[#4A4A4A]">
                    <div className="font-semibold text-[#1A1A1A] text-[11px] uppercase tracking-wider" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      Recommended Setup:
                    </div>
                    <ol className="list-decimal list-inside space-y-1 text-[12px] text-[#555555]">
                      <li>Connect your Google Calendar account above.</li>
                      <li>Open <span className="font-semibold text-[#1A1A1A]">Notion Calendar</span> (web or desktop app).</li>
                      <li>Connect the <span className="font-semibold text-[#1A1A1A]">same Google account</span> in Notion Calendar.</li>
                      <li>All CRM site visits, viewings &amp; consultations will sync and display automatically.</li>
                    </ol>
                  </div>
                </div>
              </div>

              {/* WhatsApp Integration Card */}
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-8 shadow-sm">
                <div className="flex items-center gap-2.5 mb-5 pb-4 border-b border-[#D4D0C8]">
                  <MessageSquare className="w-5 h-5 text-[#1A1A1A]" />
                  <span className="text-[16px] font-semibold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    360dialog WhatsApp API
                  </span>
                </div>

                <div className="flex items-center gap-2.5 mb-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#EAB308] shrink-0" />
                  <span className="text-[14px] font-semibold text-[#B45309]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    Status: Disabled (Launch Standby)
                  </span>
                </div>

                <p className="text-[13px] text-[#6B6B6B] mb-5 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                  WhatsApp integration is disabled for this launch stage. Inbound webhooks are inactive.
                </p>

                <div>
                  {fieldLabel('Webhook URL (Configured Endpoint)')}
                  <div className="relative">
                    <div className="bg-[#1A1A1A] text-[#E8F5A8] font-mono text-[12px] p-4 rounded-lg break-all leading-relaxed pr-12">
                      {getWebhookUrl()}
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={handleCopyWebhook}
                      title="Copy webhook URL"
                      className="absolute top-3 right-3 p-1.5 rounded-md bg-[#E8F5A8]/20 hover:bg-[#E8F5A8]/40 text-[#E8F5A8] transition-colors"
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </motion.button>
                    {copied && (
                      <span className="absolute -top-7 right-0 text-[11px] font-semibold text-[#10B981] bg-[#FAF7F2] border border-[#D4D0C8] px-2 py-0.5 rounded-lg">
                        Copied!
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Razorpay Subscription */}
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-8 shadow-sm">
                <div className="flex items-center gap-2.5 mb-5 pb-4 border-b border-[#D4D0C8]">
                  <CreditCard className="w-5 h-5 text-[#1A1A1A]" />
                  <span className="text-[16px] font-semibold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    Razorpay Subscription &amp; Billing
                  </span>
                </div>

                <div className="space-y-3 mb-5" style={{ fontFamily: 'Inter, sans-serif' }}>
                  <div className="flex items-center justify-between">
                    <span className="text-[14px] text-[#6B6B6B]">Status:</span>
                    <span className="text-[14px] font-bold text-[#10B981] uppercase">
                      {billingStatus?.subscription_status || broker?.subscription_status || 'TRIAL'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-[14px] text-[#6B6B6B]">Trial Days Remaining:</span>
                    <span className="text-[14px] font-bold text-[#1A1A1A]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {billingStatus?.trial_days_remaining ?? broker?.trial_days_remaining ?? 7} Days
                    </span>
                  </div>
                </div>

                <div className="space-y-3">
                  <motion.button
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleUpgradePlan('starter_monthly')}
                    disabled={submittingPlan}
                    className="w-full bg-white border border-[#D4D0C8] text-[#1A1A1A] h-11 rounded-xl text-[13px] font-medium hover:bg-[#F5F0EB] transition-colors disabled:opacity-50"
                  >
                    Subscribe Starter Monthly (₹2,999/mo)
                  </motion.button>

                  <motion.button
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => handleUpgradePlan('pro_monthly')}
                    disabled={submittingPlan}
                    className="w-full bg-[#1A1A1A] hover:bg-[#333333] text-white h-11 rounded-xl text-[13px] font-semibold transition-colors disabled:opacity-50 shadow-sm"
                  >
                    Subscribe Pro Monthly (₹4,999/mo)
                  </motion.button>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>

      {/* In-App Razorpay Checkout Modal */}
      <RazorpayCheckoutModal
        isOpen={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        initialPlanId={checkoutPlanId}
        onSuccess={() => {
          api.billing.getStatus().then((st) => setBillingStatus(st));
        }}
      />
    </div>
  );
}
