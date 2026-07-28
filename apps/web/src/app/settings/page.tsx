'use client';

import { useEffect, useState } from 'react';
import { Settings, User, Building, Phone, CreditCard, CheckCircle2, MessageSquare, ShieldCheck, Zap } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Broker } from '@/types';

export default function SettingsPage() {
  const [broker, setBroker] = useState<Broker | null>(null);
  const [name, setName] = useState('');
  const [agencyName, setAgencyName] = useState('');
  const [city, setCity] = useState('');
  const [whatsappNumber, setWhatsappNumber] = useState('');
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [submittingPlan, setSubmittingPlan] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      try {
        const b = await api.getBrokerProfile();
        setBroker(b);
        setName(b.name || '');
        setAgencyName(b.agency_name || '');
        setCity(b.city || 'Bengaluru');
        setWhatsappNumber(b.whatsapp_number || b.phone || '');
      } catch (e) {
        console.error('Failed loading profile', e);
      }
    }
    loadProfile();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const updated = await api.updateBrokerProfile({
        name,
        agency_name: agencyName,
        city,
        whatsapp_number: whatsappNumber,
      });
      setBroker(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      alert(e.message || 'Failed saving profile');
    } finally {
      setLoading(false);
    }
  };

  const handleUpgradePlan = async (plan: string) => {
    setSubmittingPlan(true);
    try {
      await api.subscribe(plan);
      alert(`Successfully subscribed to ${plan.toUpperCase()} plan!`);
      const b = await api.getBrokerProfile();
      setBroker(b);
    } catch (e: any) {
      alert(e.message || 'Upgrade failed');
    } finally {
      setSubmittingPlan(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2.5">
          <Settings className="w-7 h-7 text-emerald-400" />
          Broker Profile & Settings
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Manage your real estate agency profile, WhatsApp Business integration & Razorpay subscription.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
        {/* Left Column: Profile Form */}
        <div className="md:col-span-7 glass-panel p-6 rounded-2xl border border-dark-border space-y-6">
          <div className="flex items-center gap-2 font-extrabold text-white text-base border-b border-dark-border pb-3">
            <User className="w-5 h-5 text-emerald-400" />
            <span>Agency & Contact Details</span>
          </div>

          {saved && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Profile updated successfully!</span>
            </div>
          )}

          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase mb-1.5">
                Broker Full Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full bg-dark-card border border-dark-border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase mb-1.5">
                Real Estate Agency Name
              </label>
              <input
                type="text"
                value={agencyName}
                onChange={(e) => setAgencyName(e.target.value)}
                required
                className="w-full bg-dark-card border border-dark-border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase mb-1.5">
                  Operating City
                </label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  required
                  className="w-full bg-dark-card border border-dark-border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 uppercase mb-1.5">
                  WhatsApp Number
                </label>
                <input
                  type="text"
                  value={whatsappNumber}
                  onChange={(e) => setWhatsappNumber(e.target.value)}
                  required
                  className="w-full bg-dark-card border border-dark-border rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold px-6 py-3 rounded-xl text-xs transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Save Profile Changes'}
            </button>
          </form>
        </div>

        {/* Right Column: WhatsApp Connection & Billing */}
        <div className="md:col-span-5 space-y-6">
          {/* WhatsApp Status Card */}
          <div className="glass-panel p-6 rounded-2xl border border-dark-border space-y-4">
            <div className="flex items-center gap-2 font-extrabold text-white text-base">
              <MessageSquare className="w-5 h-5 text-whatsapp-light" />
              <span>WhatsApp Integration</span>
            </div>

            <div className="p-3.5 rounded-xl bg-whatsapp-light/10 border border-whatsapp-light/30 text-xs space-y-1">
              <div className="flex items-center justify-between font-bold text-emerald-400">
                <span>360dialog API: Connected</span>
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
              </div>
              <p className="text-slate-300 text-[11px]">Forward leads to +91 98765 43210 to trigger bot qualification.</p>
            </div>
          </div>

          {/* Subscription Billing Card */}
          <div className="glass-panel p-6 rounded-2xl border border-dark-border space-y-4">
            <div className="flex items-center gap-2 font-extrabold text-white text-base">
              <CreditCard className="w-5 h-5 text-amber-400" />
              <span>Subscription & Billing</span>
            </div>

            <div className="p-4 rounded-xl bg-dark-card border border-dark-border space-y-2 text-xs">
              <div className="flex justify-between font-bold">
                <span className="text-slate-400">Current Plan:</span>
                <span className="text-emerald-400 uppercase font-extrabold">
                  {broker?.subscription_status || 'TRIAL'} ({broker?.subscription_plan || 'Starter'})
                </span>
              </div>
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>Lead Quota Used:</span>
                <span className="text-white font-bold">14 / 100 leads</span>
              </div>
            </div>

            <div className="space-y-2">
              <button
                onClick={() => handleUpgradePlan('starter')}
                disabled={submittingPlan}
                className="w-full bg-white/10 hover:bg-white/20 text-white font-bold py-2.5 rounded-xl text-xs transition-all"
              >
                Renew Starter Plan (₹2,999/mo)
              </button>
              <button
                onClick={() => handleUpgradePlan('pro')}
                disabled={submittingPlan}
                className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-extrabold py-2.5 rounded-xl text-xs transition-all shadow-lg shadow-emerald-500/20"
              >
                Upgrade to Pro Plan (₹4,999/mo)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
