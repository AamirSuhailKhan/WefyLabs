'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import {
  CreditCard,
  Zap,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  Shield,
  FileText,
  Clock,
  ChevronRight,
  RefreshCw,
  Gift,
  HelpCircle,
  XCircle,
  TrendingUp,
  Cpu,
  MessageSquare,
  Users,
  Building,
  Sliders,
  Download,
} from 'lucide-react';
import RazorpayCheckoutModal from '@/components/billing/RazorpayCheckoutModal';

export default function BillingPortalPage() {
  const [loading, setLoading] = useState(true);
  const [subscription, setSubscription] = useState<any>(null);
  const [usage, setUsage] = useState<any>(null);
  const [entitlements, setEntitlements] = useState<any>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [credits, setCredits] = useState<any>({ balance: '0.00', currency: 'INR', entries: [] });
  const [catalog, setCatalog] = useState<any[]>([]);
  const [billingInterval, setBillingInterval] = useState<'MONTHLY' | 'ANNUAL'>('MONTHLY');
  const [checkoutModalOpen, setCheckoutModalOpen] = useState(false);
  const [selectedPlanForCheckout, setSelectedPlanForCheckout] = useState('pro_monthly');
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchBillingData = async () => {
    setLoading(true);
    try {
      const [subData, usageData, entData, invData, credData, catData] = await Promise.all([
        api.billing.portal.getSubscription(),
        api.billing.portal.getUsage(),
        api.billing.portal.getEntitlements(),
        api.billing.portal.getInvoices(),
        api.billing.portal.getCredits(),
        api.billing.portal.getCatalog(),
      ]);

      setSubscription(subData);
      setUsage(usageData);
      setEntitlements(entData);
      setInvoices(invData);
      setCredits(credData);
      setCatalog(catData);
    } catch (err: any) {
      console.error('Failed to load billing portal data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBillingData();
  }, []);

  const handleUpgrade = async (planCode: string) => {
    try {
      setActionMessage(null);
      const res = await api.billing.portal.upgradePlan(planCode, billingInterval);
      setActionMessage({
        type: 'success',
        text: `Plan successfully changed to ${planCode.toUpperCase()} (${billingInterval}).`,
      });
      await fetchBillingData();
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err?.message || 'Upgrade request failed. Please try again.',
      });
    }
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel your subscription? It will remain active until the end of your billing cycle.')) {
      return;
    }
    try {
      await api.billing.portal.cancelSubscription(false, 'User requested cancellation in portal');
      setActionMessage({
        type: 'success',
        text: 'Subscription scheduled for cancellation at the end of the billing period.',
      });
      await fetchBillingData();
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err?.message || 'Cancellation request failed.',
      });
    }
  };

  const getMeterIcon = (key: string) => {
    if (key.includes('ai')) return <Cpu className="w-4 h-4 text-purple-400" />;
    if (key.includes('whatsapp') || key.includes('message')) return <MessageSquare className="w-4 h-4 text-emerald-400" />;
    if (key.includes('team') || key.includes('member')) return <Users className="w-4 h-4 text-blue-400" />;
    if (key.includes('property')) return <Building className="w-4 h-4 text-amber-400" />;
    if (key.includes('workflow') || key.includes('execution')) return <Sliders className="w-4 h-4 text-cyan-400" />;
    return <Zap className="w-4 h-4 text-indigo-400" />;
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 lg:p-10 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Navigation & Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
          <div>
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-1">
              <Link href="/settings" className="hover:text-slate-200 transition-colors">Settings</Link>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
              <span className="text-indigo-400 font-medium">Billing & Subscriptions</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              Billing &amp; Revenue OS
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Enterprise
              </span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Manage your commercial plan, monitor metered consumption, review invoices, and view credit balances.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchBillingData}
              disabled={loading}
              className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm font-medium hover:bg-slate-800 text-slate-300 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
              Refresh Data
            </button>
            <button
              onClick={() => {
                setSelectedPlanForCheckout('pro_monthly');
                setCheckoutModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-medium hover:from-indigo-500 hover:to-violet-500 shadow-lg shadow-indigo-600/20 transition-all"
            >
              <CreditCard className="w-4 h-4" />
              Payment Gateway
            </button>
          </div>
        </div>

        {/* Action Alert Banner */}
        {actionMessage && (
          <div className={`p-4 rounded-xl border flex items-center justify-between gap-3 text-sm ${
            actionMessage.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-950/40 border-rose-500/30 text-rose-300'
          }`}>
            <div className="flex items-center gap-2.5">
              {actionMessage.type === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" /> : <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />}
              <span>{actionMessage.text}</span>
            </div>
            <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-white">✕</button>
          </div>
        )}

        {/* Top Summary Row: Active Subscription + Available Credits */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Active Plan Card */}
          <div className="md:col-span-2 p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 via-slate-900/60 to-slate-950 border border-slate-800/80 shadow-xl relative overflow-hidden">
            <div className="absolute -right-8 -top-8 w-40 h-40 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
              <div>
                <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">Current Plan</span>
                <div className="flex items-center gap-3 mt-1">
                  <h2 className="text-2xl font-bold text-white capitalize">
                    {subscription?.plan?.name || 'Free Tier'}
                  </h2>
                  <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${
                    subscription?.status === 'ACTIVE'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : subscription?.status === 'TRIALING'
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : 'bg-slate-800 border-slate-700 text-slate-400'
                  }`}>
                    {subscription?.status || 'TRIAL'}
                  </span>
                </div>
              </div>

              <div className="text-right">
                <span className="text-2xl font-bold text-white">
                  ₹{subscription?.plan?.price ? Number(subscription.plan.price).toLocaleString('en-IN') : '0'}
                </span>
                <span className="text-xs text-slate-400"> / {subscription?.plan?.interval?.toLowerCase() || 'month'}</span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-4 border-y border-slate-800/60 mb-6 text-sm">
              <div>
                <span className="text-xs text-slate-500 block">Cycle Start</span>
                <span className="text-slate-300 font-medium">
                  {subscription?.current_period_start ? new Date(subscription.current_period_start).toLocaleDateString() : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Renewal / Next Bill</span>
                <span className="text-slate-300 font-medium">
                  {subscription?.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Cancellation Status</span>
                <span className={`font-medium ${subscription?.cancel_at_period_end ? 'text-amber-400' : 'text-slate-400'}`}>
                  {subscription?.cancel_at_period_end ? 'Cancels at period end' : 'Auto-renew active'}
                </span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Payment Method</span>
                <span className="text-slate-300 font-medium flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-indigo-400" /> Razorpay Verified
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => handleUpgrade('pro')}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
              >
                Upgrade to Professional
              </button>
              {subscription?.has_subscription && !subscription?.cancel_at_period_end && (
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors"
                >
                  Cancel Plan
                </button>
              )}
            </div>
          </div>

          {/* Credits Balance Card */}
          <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 via-slate-900/60 to-slate-950 border border-slate-800/80 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">Available Credits</span>
                <Gift className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-extrabold text-white tracking-tight">
                ₹{Number(credits.balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Promotional credits and invoice adjustments automatically reduce your upcoming bill.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-800/60">
              <span className="text-xs text-slate-500 block mb-2">Recent Credit Activity</span>
              {credits.entries && credits.entries.length > 0 ? (
                <div className="space-y-1.5 text-xs text-slate-300">
                  {credits.entries.slice(0, 2).map((e: any) => (
                    <div key={e.id} className="flex items-center justify-between">
                      <span className="truncate max-w-[140px] text-slate-400">{e.reason}</span>
                      <span className={e.entry_type === 'CREDIT_ISSUED' ? 'text-emerald-400 font-semibold' : 'text-slate-400'}>
                        {e.entry_type === 'CREDIT_ISSUED' ? '+' : '-'}₹{Number(e.amount).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-xs text-slate-500 italic">No credit adjustments applied yet.</span>
              )}
            </div>
          </div>
        </div>

        {/* Metered Usage Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-indigo-400" />
                Current Period Metered Consumption
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Authoritative server-side consumption tracking against plan quotas for the current billing cycle.
              </p>
            </div>
            {usage?.period_end && (
              <span className="text-xs text-slate-400">
                Resets on {new Date(usage.period_end).toLocaleDateString()}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {usage?.meters && usage.meters.length > 0 ? (
              usage.meters.map((m: any) => (
                <div
                  key={m.entitlement_key}
                  className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 hover:border-slate-700/80 transition-all flex flex-col justify-between"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 font-medium text-sm text-slate-200">
                      {getMeterIcon(m.entitlement_key)}
                      <span className="capitalize">{m.entitlement_key.replace(/_/g, ' ')}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                      m.warning_level === 'CRITICAL'
                        ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        : m.warning_level === 'WARNING'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-slate-800 text-slate-400'
                    }`}>
                      {m.limit ? `${m.percentage}%` : 'Unlimited'}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-baseline justify-between text-xs mb-1.5">
                      <span className="text-slate-400">
                        {m.used.toLocaleString()} consumed
                      </span>
                      <span className="text-slate-500">
                        {m.limit ? `Limit: ${m.limit.toLocaleString()}` : 'No hard cap'}
                      </span>
                    </div>

                    {m.limit && (
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            m.warning_level === 'CRITICAL'
                              ? 'bg-rose-500'
                              : m.warning_level === 'WARNING'
                              ? 'bg-amber-500'
                              : 'bg-indigo-500'
                          }`}
                          style={{ width: `${Math.min(100, m.percentage)}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="col-span-3 p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400 text-sm">
                No metered usage recorded yet for the current billing cycle.
              </div>
            )}
          </div>
        </div>

        {/* Dynamic Plan Comparison Cards */}
        <div className="space-y-4 pt-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-indigo-400" />
                Available Subscription Plans
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Database-driven commercial catalog. Transparent pricing, no hidden fees.
              </p>
            </div>

            {/* Monthly / Annual Toggle */}
            <div className="flex items-center self-start sm:self-auto bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-medium">
              <button
                onClick={() => setBillingInterval('MONTHLY')}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  billingInterval === 'MONTHLY' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingInterval('ANNUAL')}
                className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                  billingInterval === 'ANNUAL' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>Annual</span>
                <span className="bg-emerald-500/20 text-emerald-400 text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                  Save ~17%
                </span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {catalog.map((plan: any) => {
              const matchedVersion = plan.versions?.find((v: any) => v.interval === billingInterval) || plan.versions?.[0];
              const isCurrent = subscription?.plan?.code === plan.code;
              const priceDisplay = matchedVersion ? `₹${Number(matchedVersion.price).toLocaleString('en-IN')}` : 'Contact';

              return (
                <div
                  key={plan.id}
                  className={`p-6 rounded-2xl border transition-all flex flex-col justify-between ${
                    isCurrent
                      ? 'bg-slate-900/90 border-indigo-500/50 shadow-lg shadow-indigo-500/10'
                      : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-bold text-white capitalize">{plan.name}</h3>
                      {isCurrent && (
                        <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                          Active Plan
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mb-5 leading-relaxed">{plan.description}</p>

                    <div className="mb-6">
                      <span className="text-3xl font-extrabold text-white">{priceDisplay}</span>
                      <span className="text-xs text-slate-400"> / {billingInterval.toLowerCase()}</span>
                    </div>

                    <div className="space-y-2.5 text-xs text-slate-300 border-t border-slate-800/80 pt-4 mb-6">
                      {matchedVersion?.entitlements && Object.entries(matchedVersion.entitlements).map(([k, v]: [string, any]) => (
                        <div key={k} className="flex items-center gap-2">
                          <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                          <span>
                            {v.limit ? `${v.limit.toLocaleString()} ` : ''}
                            <span className="capitalize">{k.replace(/_/g, ' ')}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <button
                    disabled={isCurrent}
                    onClick={() => handleUpgrade(plan.code)}
                    className={`w-full py-2.5 rounded-xl text-xs font-semibold transition-all ${
                      isCurrent
                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                        : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20'
                    }`}
                  >
                    {isCurrent ? 'Current Plan' : `Switch to ${plan.name}`}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Invoices History Table */}
        <div className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                Invoices &amp; Billing History
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Deterministic invoice ledger with recomputable subtotal, tax, credits, and payment provenance.
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-lg">
            {invoices.length > 0 ? (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-800/60 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Invoice #</th>
                    <th className="py-3 px-4">Due Date</th>
                    <th className="py-3 px-4">Subtotal</th>
                    <th className="py-3 px-4">Tax (18%)</th>
                    <th className="py-3 px-4">Credits</th>
                    <th className="py-3 px-4">Total</th>
                    <th className="py-3 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  {invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-medium text-white">{inv.invoice_number}</td>
                      <td className="py-3.5 px-4 text-slate-400">{new Date(inv.due_date).toLocaleDateString()}</td>
                      <td className="py-3.5 px-4">₹{Number(inv.subtotal).toFixed(2)}</td>
                      <td className="py-3.5 px-4">₹{Number(inv.tax_amount).toFixed(2)}</td>
                      <td className="py-3.5 px-4 text-emerald-400">
                        {Number(inv.credit_amount) > 0 ? `-₹${Number(inv.credit_amount).toFixed(2)}` : '—'}
                      </td>
                      <td className="py-3.5 px-4 font-bold text-white">₹{Number(inv.total).toFixed(2)}</td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          inv.status === 'PAID'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : inv.status === 'OPEN'
                            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            : 'bg-slate-800 text-slate-400'
                        }`}>
                          {inv.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-8 text-center text-slate-400 text-xs">
                No invoices generated yet for this organization.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Razorpay Checkout Modal Integration */}
      <RazorpayCheckoutModal
        isOpen={checkoutModalOpen}
        onClose={() => setCheckoutModalOpen(false)}
        initialPlanId={selectedPlanForCheckout}
        onSuccess={() => {
          fetchBillingData();
          setActionMessage({
            type: 'success',
            text: 'Payment captured and subscription entitlements activated successfully.',
          });
        }}
      />
    </div>
  );
}
