'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, CreditCard, MessageSquare, CheckCircle2, Copy } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Broker } from '@/types';
import DashboardNav from '@/components/shared/DashboardNav';

export default function SettingsPage() {
  const [broker, setBroker] = useState<Broker | null>(null);
  const [billingStatus, setBillingStatus] = useState<any>(null);
  const [name, setName] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [city, setCity] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [submittingPlan, setSubmittingPlan] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const b = await api.getBrokerProfile();
        setBroker(b);
        setName(b.name || '');
        setAgencyName(b.agency_name || '');
        setCity(b.city || 'Bengaluru');
        setWhatsappNumber(b.whatsapp_number || b.phone || '');

        const statusRes = await api.billing.getStatus();
        setBillingStatus(statusRes);
      } catch (e) {
        console.warn('Could not load profile or billing status', e);
      }
    }
    loadData();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const updated = await api.updateBrokerProfile({ name, agency_name: agencyName, city, whatsapp_number: whatsappNumber });
      setBroker(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      alert(err.message || 'Failed updating profile');
    } finally {
      setLoading(false);
    }
  };

  const handleUpgradePlan = async (planId: string) => {
    setSubmittingPlan(true);
    try {
      const res = await api.billing.subscribe(planId);
      if (res && res.short_url) {
        window.location.href = res.short_url;
      } else {
        alert(`Subscription created for ${planId.toUpperCase()}. Check your account for activation.`);
      }
    } catch (err: any) {
      alert(err.message || 'Subscription failed. Please try again.');
    } finally {
      setSubmittingPlan(false);
    }
  };

  const handleCopyWebhook = () => {
    navigator.clipboard.writeText('https://api.beetlelabs.ai/api/v1/whatsapp/webhook');
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

            {/* RIGHT: WhatsApp + Billing */}
            <div className="space-y-6">

              {/* WhatsApp Integration Card */}
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-8 shadow-sm">
                <div className="flex items-center gap-2.5 mb-5 pb-4 border-b border-[#D4D0C8]">
                  <MessageSquare className="w-5 h-5 text-[#1A1A1A]" />
                  <span className="text-[16px] font-semibold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    360dialog WhatsApp API
                  </span>
                </div>

                <div className="flex items-center gap-2.5 mb-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] shrink-0" />
                  <span className="text-[14px] font-semibold text-[#10B981]" style={{ fontFamily: 'Inter, sans-serif' }}>
                    Status: Webhook Online
                  </span>
                </div>

                <p className="text-[13px] text-[#6B6B6B] mb-5 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                  Forward lead phone numbers to your registered WhatsApp number to automatically trigger AI qualification.
                </p>

                <div>
                  {fieldLabel('Webhook URL')}
                  <div className="relative">
                    <div className="bg-[#1A1A1A] text-[#E8F5A8] font-mono text-[12px] p-4 rounded-lg break-all leading-relaxed pr-12">
                      https://api.beetlelabs.ai/api/v1/whatsapp/webhook
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
    </div>
  );
}
