'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X, Send, Sparkles, ArrowRight } from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';
import { FlagIcon } from '@/components/shared/FlagIcon';
import SectionLabel from '@/components/shared/SectionLabel';

export default function GlobalPricing() {
  const router = useRouter();
  const { region } = useRegion();
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);
  const [contactSubmitted, setContactSubmitted] = useState(false);
  const [contactForm, setContactForm] = useState({
    name: '',
    email: '',
    phone: '',
    company: '',
    leadsPerMonth: '1000+',
    message: '',
  });

  const discountFactor = billingCycle === 'annual' ? 0.83 : 1.0;
  const starterPrice = Math.round(region.starterPrice * discountFactor);
  const proPrice = Math.round(region.proPrice * discountFactor);

  const handleSelectStarter = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    router.push('/register?plan=starter');
  };

  const handleSelectPro = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    router.push('/register?plan=pro');
  };

  const handleOpenCustomModal = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setIsContactModalOpen(true);
  };

  const handleContactSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setContactSubmitted(true);
    setTimeout(() => {
      setIsContactModalOpen(false);
      setContactSubmitted(false);
      setContactForm({
        name: '',
        email: '',
        phone: '',
        company: '',
        leadsPerMonth: '1000+',
        message: '',
      });
    }, 2500);
  };

  return (
    <section id="pricing" className="py-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto relative z-20">
      {/* Section Header */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="text-center mb-12"
      >
        <SectionLabel variant="pill">
          <span>PRICING FOR {region.name.toUpperCase()}</span>
          <FlagIcon code={region.code} className="w-4 h-3 rounded-[2px] shadow-2xs border border-black/10 inline-block shrink-0" />
        </SectionLabel>

        <h2 className="text-3xl md:text-5xl font-mono text-gray-900 font-bold tracking-tight mb-4">
          Simple pricing. Enterprise power.
        </h2>
        <p className="text-base md:text-lg text-gray-600 font-sans leading-relaxed max-w-2xl mx-auto">
          Select a plan below to start your free 15-day trial or request custom enterprise pricing.
        </p>

        {/* Billing Cycle Toggle */}
        <div className="flex items-center justify-center mt-8">
          <div className="inline-flex items-center gap-2 p-1.5 bg-gray-100 border border-gray-200 rounded-2xl">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                billingCycle === 'monthly'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle('annual')}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                billingCycle === 'annual'
                  ? 'bg-[#d4f5a4] text-black shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Annual
              <span className="bg-black text-white text-[9px] px-1.5 py-0.5 rounded-full uppercase">17% OFF</span>
            </button>
          </div>
        </div>
      </motion.div>

      {/* 3 Pricing Cards Grid */}
      <div className="grid lg:grid-cols-3 md:grid-cols-2 gap-8 items-stretch">
        
        {/* 1. STARTER PLAN */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          onClick={handleSelectStarter}
          className="bg-white rounded-3xl p-8 shadow-sm flex flex-col justify-between cursor-pointer transition-all border-2 border-gray-200 hover:border-gray-900 hover:shadow-xl hover:-translate-y-1 relative"
        >
          <div>
            <div className="text-center mb-6">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-widest font-mono mb-2">STARTER</h3>
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-5xl font-extrabold font-mono text-gray-900">
                  {formatCurrency(starterPrice, region)}
                </span>
                <span className="text-sm font-sans text-gray-500">/month</span>
              </div>
              <div className="mt-4">
                <span className="inline-block bg-emerald-50 text-emerald-700 text-xs font-medium px-3 py-1 rounded-full border border-emerald-200">
                  15 day free trial · No credit card required
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-4 font-sans leading-relaxed">
                Perfect for individuals and small teams getting started with AI agents.
              </p>
            </div>

            <div className="border-t border-gray-100 pt-6">
              <h4 className="text-xs font-bold text-gray-900 uppercase font-mono mb-4">What's Included</h4>
              <ul className="space-y-3 text-sm text-gray-600 font-sans mb-6">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Whatsapp, Telegram, Web widget</span>
                </li>
                <li className="flex items-center gap-2.5 font-semibold text-gray-900">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>150 Monthly AI Leads</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Up to 2 Specialised AI Agents</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Up to 2 Team Members</span>
                </li>
              </ul>

              <h4 className="text-xs font-bold text-gray-900 uppercase font-mono mb-3">Key Features</h4>
              <ul className="space-y-2.5 text-xs text-gray-600 font-sans mb-8">
                <li className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>Knowledge Base & Universal Ingestion</span>
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>AI Lead Enrichment Baseline</span>
                </li>
              </ul>
            </div>
          </div>

          <button
            onClick={handleSelectStarter}
            className="w-full py-3.5 px-4 border border-gray-900 bg-white text-gray-900 hover:bg-gray-900 hover:text-white transition-all font-bold text-sm rounded-xl cursor-pointer shadow-xs flex items-center justify-center gap-2"
          >
            SELECT STARTER PLAN →
          </button>
        </motion.div>

        {/* 2. PROFESSIONAL PLAN */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.1 }}
          onClick={handleSelectPro}
          className="bg-white rounded-3xl p-8 shadow-xl flex flex-col justify-between relative cursor-pointer transition-all border-2 border-gray-900 ring-2 ring-black/5 hover:shadow-2xl hover:-translate-y-1"
        >
          <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-[#d4f5a4] text-black text-xs font-bold font-mono px-4 py-1 rounded-full uppercase tracking-wider border border-gray-900 shadow-sm">
            MOST POPULAR
          </div>

          <div>
            <div className="text-center mb-6 mt-2">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-widest font-mono mb-2">PROFESSIONAL</h3>
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-5xl font-extrabold font-mono text-gray-900">
                  {formatCurrency(proPrice, region)}
                </span>
                <span className="text-sm font-sans text-gray-500">/month</span>
              </div>
              <div className="mt-4">
                <span className="inline-block bg-emerald-50 text-emerald-700 text-xs font-medium px-3 py-1 rounded-full border border-emerald-200">
                  15 day free trial · No credit card required
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-4 font-sans leading-relaxed">
                For growing businesses that need advanced features and higher limits.
              </p>
            </div>

            <div className="border-t border-gray-100 pt-6">
              <h4 className="text-xs font-bold text-gray-900 uppercase font-mono mb-4">What's Included</h4>
              <ul className="space-y-3 text-sm text-gray-600 font-sans mb-6">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Web widget, Telegram, Whatsapp, Api</span>
                </li>
                <li className="flex items-center gap-2.5 font-semibold text-gray-900">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>500 Monthly AI Leads</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Up to 15 Specialised AI Agents</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Up to 10 Team Members</span>
                </li>
              </ul>

              <h4 className="text-xs font-bold text-gray-900 uppercase font-mono mb-3">Key Features</h4>
              <ul className="space-y-2.5 text-xs text-gray-600 font-sans mb-8">
                <li className="flex items-center gap-2 font-medium text-gray-900">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>Buyer Identity Verification (Identity Graph)</span>
                </li>
                <li className="flex items-center gap-2 font-medium text-gray-900">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>AI Lead Scoring & Intent Prediction</span>
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>Automated Follow-ups & Task Reminders</span>
                </li>
              </ul>
            </div>
          </div>

          <button
            onClick={handleSelectPro}
            className="w-full py-3.5 px-4 bg-[#d4f5a4] text-black hover:bg-[#c5e894] transition-colors font-bold text-sm rounded-xl cursor-pointer shadow-sm flex items-center justify-center gap-2"
          >
            SELECT PROFESSIONAL PLAN →
          </button>
        </motion.div>

        {/* 3. PREMIUM / CUSTOM PLAN */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          onClick={handleOpenCustomModal}
          className="bg-white rounded-3xl p-8 shadow-sm flex flex-col justify-between cursor-pointer transition-all border-2 border-gray-200 hover:border-gray-900 hover:shadow-xl hover:-translate-y-1 relative"
        >
          <div>
            <div className="text-center mb-6">
              <h3 className="text-sm font-bold text-gray-500 uppercase tracking-widest font-mono mb-2">PREMIUM</h3>
              <div className="flex items-baseline justify-center gap-1">
                <span className="text-4xl font-extrabold font-mono text-gray-900">Custom</span>
              </div>
              <p className="text-xs text-gray-500 mt-2 font-sans">Contact us for pricing</p>
              <p className="text-xs text-gray-500 mt-4 font-sans leading-relaxed">
                Custom solutions for large organizations with dedicated support.
              </p>
            </div>

            <div className="border-t border-gray-100 pt-6">
              <h4 className="text-xs font-bold text-gray-900 uppercase font-mono mb-4">What's Included</h4>
              <ul className="space-y-3 text-sm text-gray-600 font-sans mb-6">
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Api, Web widget, Telegram, Whatsapp</span>
                </li>
                <li className="flex items-center gap-2.5 font-semibold text-gray-900">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Unlimited Monthly AI Leads</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Unlimited Specialised AI Agents</span>
                </li>
                <li className="flex items-center gap-2.5">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Unlimited Team Members</span>
                </li>
              </ul>

              <h4 className="text-xs font-bold text-gray-900 uppercase font-mono mb-3">Key Features</h4>
              <ul className="space-y-2.5 text-xs text-gray-600 font-sans mb-8">
                <li className="flex items-center gap-2 font-medium text-gray-900">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>24/7 Dedicated Support</span>
                </li>
                <li className="flex items-center gap-2 font-medium text-gray-900">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>99.9% SLA Guarantee</span>
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>Custom AI Model Fine-tuning & Workflows</span>
                </li>
              </ul>
            </div>
          </div>

          <button
            onClick={handleOpenCustomModal}
            className="w-full py-3.5 px-4 border border-gray-900 bg-gray-900 text-white hover:bg-gray-800 transition-colors font-bold text-sm rounded-xl cursor-pointer shadow-sm flex items-center justify-center gap-2"
          >
            CONTACT SALES →
          </button>
        </motion.div>

      </div>

      <p className="text-center text-xs text-gray-500 mt-8 font-sans">
        All prices in {region.currency} ({region.currencySymbol.trim()}). Local taxes may apply.
      </p>

      {/* Contact Sales Interactive Modal */}
      <AnimatePresence>
        {isContactModalOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-3xl p-8 max-w-lg w-full shadow-2xl relative border border-gray-200 text-gray-900"
            >
              <button
                onClick={() => setIsContactModalOpen(false)}
                className="absolute top-6 right-6 text-gray-400 hover:text-gray-700 cursor-pointer p-1 rounded-full hover:bg-gray-100"
              >
                <X className="w-5 h-5" />
              </button>

              {contactSubmitted ? (
                <div className="text-center py-8">
                  <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Check className="w-6 h-6" />
                  </div>
                  <h3 className="text-xl font-bold font-mono text-gray-900 mb-2">Request Received!</h3>
                  <p className="text-sm text-gray-600 font-sans">
                    Thank you for reaching out. Our enterprise team will contact you within 2 hours with a custom pricing proposal.
                  </p>
                </div>
              ) : (
                <>
                  <div className="mb-6">
                    <div className="inline-flex items-center gap-2 bg-[#d4f5a4] text-black text-xs font-bold font-mono px-3 py-1 rounded-full uppercase mb-3">
                      <Sparkles className="w-3.5 h-3.5" />
                      ENTERPRISE CUSTOM PLAN
                    </div>
                    <h3 className="text-2xl font-bold font-mono text-gray-900">Request Custom Pricing</h3>
                    <p className="text-xs text-gray-600 mt-1 font-sans">
                      Get a tailored package for your agency in {region.name}.
                    </p>
                  </div>

                  <form onSubmit={handleContactSubmit} className="space-y-4 font-sans text-sm">
                    <div>
                      <label className="block text-xs font-bold text-gray-700 mb-1 uppercase font-mono">Full Name *</label>
                      <input
                        type="text"
                        required
                        value={contactForm.name}
                        onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                        placeholder="e.g. Sarah Jenkins"
                        className="w-full px-3.5 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-black focus:outline-none text-gray-900"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-gray-700 mb-1 uppercase font-mono">Email *</label>
                        <input
                          type="email"
                          required
                          value={contactForm.email}
                          onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                          placeholder="sarah@agency.com"
                          className="w-full px-3.5 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-black focus:outline-none text-gray-900"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-gray-700 mb-1 uppercase font-mono">Phone *</label>
                        <input
                          type="tel"
                          required
                          value={contactForm.phone}
                          onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
                          placeholder="+1 (555) 000-0000"
                          className="w-full px-3.5 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-black focus:outline-none text-gray-900"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-gray-700 mb-1 uppercase font-mono">Agency / Company</label>
                        <input
                          type="text"
                          value={contactForm.company}
                          onChange={(e) => setContactForm({ ...contactForm, company: e.target.value })}
                          placeholder="Apex Real Estate"
                          className="w-full px-3.5 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-black focus:outline-none text-gray-900"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-gray-700 mb-1 uppercase font-mono">Expected Monthly Leads</label>
                        <select
                          value={contactForm.leadsPerMonth}
                          onChange={(e) => setContactForm({ ...contactForm, leadsPerMonth: e.target.value })}
                          className="w-full px-3.5 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-black focus:outline-none text-gray-900 bg-white"
                        >
                          <option value="1000-2500">1,000 – 2,500 leads/mo</option>
                          <option value="2500-5000">2,500 – 5,000 leads/mo</option>
                          <option value="5000-10000">5,000 – 10,000 leads/mo</option>
                          <option value="10000+">10,000+ leads/mo</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-gray-700 mb-1 uppercase font-mono">Custom Requirements</label>
                      <textarea
                        rows={3}
                        value={contactForm.message}
                        onChange={(e) => setContactForm({ ...contactForm, message: e.target.value })}
                        placeholder="Tell us about your team size, custom AI integration needs, or regional requirements..."
                        className="w-full px-3.5 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-black focus:outline-none text-gray-900"
                      />
                    </div>

                    <button
                      type="submit"
                      className="w-full py-3.5 px-4 bg-gray-900 text-white font-bold text-sm rounded-xl hover:bg-gray-800 transition-colors shadow-md cursor-pointer flex items-center justify-center gap-2"
                    >
                      <Send className="w-4 h-4" />
                      SUBMIT CUSTOM QUOTE REQUEST
                    </button>
                  </form>
                </>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </section>
  );
}
