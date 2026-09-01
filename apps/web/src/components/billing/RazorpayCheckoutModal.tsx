'use client';

/**
 * RazorpayCheckoutModal
 * =====================
 * Production-grade Razorpay Checkout Modal with:
 * - Dynamic script injection & fallback handling
 * - Double-submit prevention with loading lock
 * - Authoritative server-side order generation
 * - Cryptographic backend payment verification before showing success
 * - Full plan discovery & capability checks
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, ShieldCheck, AlertCircle, Loader2, Sparkles, X, CreditCard, ArrowRight } from 'lucide-react';
import { api } from '@/lib/api-client';
import { useCapabilities } from '@/hooks/useCapabilities';

interface RazorpayCheckoutModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  initialPlanId?: string;
}

declare global {
  interface Window {
    Razorpay: any;
  }
}

export default function RazorpayCheckoutModal({
  isOpen,
  onClose,
  onSuccess,
  initialPlanId = 'pro_monthly'
}: RazorpayCheckoutModalProps) {
  const { capabilities } = useCapabilities();
  const [plans, setPlans] = useState<any[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState(initialPlanId);
  const [billingState, setBillingState] = useState<
    'idle' | 'creating_order' | 'checkout_open' | 'verifying' | 'success' | 'failed'
  >('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [scriptLoaded, setScriptLoaded] = useState(false);

  // ── 1. Load Razorpay Checkout Script ───────────────────────────────────────
  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (window.Razorpay) {
      setScriptLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => setScriptLoaded(true);
    script.onerror = () => {
      console.warn('[Razorpay] Failed to load checkout script from CDN');
    };
    document.body.appendChild(script);

    return () => {
      // Keep script in DOM for future modal openings
    };
  }, []);

  // ── 2. Load Plans ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isOpen) return;

    api.billing.getPlans().then((data) => {
      if (data && data.length > 0) {
        setPlans(data);
      } else {
        // Fallback default plans
        setPlans([
          {
            plan_id: 'starter_monthly',
            name: 'Starter Monthly',
            amount_inr: 2999,
            period: 'monthly',
            features: ['100 AI Qualifications/mo', 'WhatsApp Lite', '1 Broker Seat']
          },
          {
            plan_id: 'pro_monthly',
            name: 'Professional Monthly',
            amount_inr: 4999,
            period: 'monthly',
            features: ['500 AI Qualifications/mo', 'Full WhatsApp Bot', 'AVM Valuation', 'Google Calendar Sync', '5 Team Seats']
          },
          {
            plan_id: 'pro_annual',
            name: 'Professional Annual',
            amount_inr: 49999,
            period: 'annual',
            features: ['500 AI Qualifications/mo', 'Full WhatsApp Bot', 'AVM Valuation', '2 Months Free', 'Priority Support']
          }
        ]);
      }
    });
  }, [isOpen]);

  // ── 3. Start Checkout Flow ─────────────────────────────────────────────────
  const handleInitiatePayment = async () => {
    if (billingState === 'creating_order' || billingState === 'verifying') return;

    setErrorMessage(null);
    setBillingState('creating_order');

    try {
      // Step A: Create Order on Backend
      const order = await api.billing.createOrder(selectedPlanId, `idemp_${Date.now()}`);

      // Step B: Check Razorpay Script Availability
      if (!window.Razorpay) {
        throw new Error('Razorpay Checkout SDK is still loading. Please check your network connection.');
      }

      setBillingState('checkout_open');

      // Step C: Initialize Razorpay Checkout
      const options = {
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        name: 'BeetleLabs AI',
        description: `Upgrade to ${order.plan_name}`,
        order_id: order.razorpay_order_id,
        image: '/icon.svg',
        theme: {
          color: '#1A1A1A'
        },
        modal: {
          ondismiss: () => {
            setBillingState('idle');
          }
        },
        handler: async (response: {
          razorpay_payment_id: string;
          razorpay_order_id: string;
          razorpay_signature: string;
        }) => {
          // Step D: Cryptographic Verification on Backend
          setBillingState('verifying');
          try {
            const verifyRes = await api.billing.verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature
            });

            if (verifyRes.success) {
              setBillingState('success');
              if (onSuccess) onSuccess();
            } else {
              setBillingState('failed');
              setErrorMessage('Payment verification failed on server. Please contact support.');
            }
          } catch (err: any) {
            setBillingState('failed');
            setErrorMessage(err.message || 'Payment verification failed. Please contact support.');
          }
        }
      };

      const rzp = new window.Razorpay(options);
      rzp.on('payment.failed', (resp: any) => {
        setBillingState('failed');
        setErrorMessage(resp.error?.description || 'Payment was declined or failed.');
      });
      rzp.open();
    } catch (err: any) {
      setBillingState('failed');
      setErrorMessage(err.message || 'Failed to create payment order. Please retry.');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        className="w-full max-w-xl bg-white border border-[#D4D0C8] rounded-2xl shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="p-6 bg-[#FAF7F2] border-b border-[#D4D0C8] flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#B45309]" />
              <h2 className="text-xl font-bold text-[#1A1A1A] tracking-tight">Upgrade Your Broker Plan</h2>
            </div>
            <p className="text-xs text-[#6B6B6B] mt-0.5">
              Secure, instant activation via Razorpay Payments & Subscriptions.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#EAE6DF] rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Mode banner */}
          {capabilities.billing.mode === 'test' && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-2.5 text-xs text-amber-800 font-medium">
              <ShieldCheck className="w-4 h-4 shrink-0 text-amber-600" />
              <span>
                <strong>Razorpay Test Sandbox Active</strong> — Use Razorpay test cards/UPI to simulate payments safely.
              </span>
            </div>
          )}

          {/* Success State */}
          {billingState === 'success' ? (
            <div className="py-8 text-center space-y-4">
              <div className="w-14 h-14 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
                <Check className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-bold text-[#1A1A1A]">Payment Successful & Verified!</h3>
              <p className="text-sm text-[#6B6B6B] max-w-sm mx-auto">
                Your broker plan has been upgraded and premium lead qualification features are now unlocked.
              </p>
              <button
                onClick={() => {
                  onClose();
                  window.location.reload();
                }}
                className="px-6 py-2.5 bg-[#1A1A1A] text-white rounded-xl font-semibold hover:bg-black transition-colors"
              >
                Go to Dashboard
              </button>
            </div>
          ) : (
            <>
              {/* Plan Selection */}
              <div className="space-y-3">
                <label className="text-xs font-bold text-[#6B6B6B] uppercase tracking-wider">
                  Select Subscription Tier
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {plans.map((p) => {
                    const isSelected = selectedPlanId === p.plan_id;
                    return (
                      <div
                        key={p.plan_id}
                        onClick={() => setSelectedPlanId(p.plan_id)}
                        className={`p-4 rounded-xl border cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-[#E8F5A8]/30 border-[#1A1A1A] ring-2 ring-[#1A1A1A]'
                            : 'bg-white border-[#D4D0C8] hover:border-[#A0A0A0]'
                        }`}
                      >
                        <p className="text-xs font-bold text-[#1A1A1A]">{p.name}</p>
                        <p className="text-lg font-extrabold text-[#1A1A1A] mt-1">
                          ₹{(p.amount_inr || p.amount_paise / 100).toLocaleString('en-IN')}
                          <span className="text-[10px] font-normal text-[#6B6B6B]">/{p.period === 'annual' ? 'yr' : 'mo'}</span>
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Error Message */}
              {errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2.5 text-xs text-red-800">
                  <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {/* Action Button */}
              <div className="pt-2">
                <button
                  onClick={handleInitiatePayment}
                  disabled={billingState === 'creating_order' || billingState === 'verifying'}
                  className="w-full py-3.5 px-6 rounded-xl bg-[#1A1A1A] text-white font-bold flex items-center justify-center gap-2 hover:bg-black transition-all disabled:opacity-50 shadow-md cursor-pointer"
                >
                  {billingState === 'creating_order' ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Creating Order...</span>
                    </>
                  ) : billingState === 'verifying' ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Verifying Payment Signature...</span>
                    </>
                  ) : (
                    <>
                      <CreditCard className="w-4 h-4" />
                      <span>Proceed to Razorpay Checkout</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>

              {/* Security Badges */}
              <div className="flex items-center justify-center gap-4 text-[11px] text-[#6B6B6B] pt-2">
                <span className="flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> 256-bit Encrypted
                </span>
                <span>•</span>
                <span>Instant Activation</span>
                <span>•</span>
                <span>GST Invoiced</span>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}
