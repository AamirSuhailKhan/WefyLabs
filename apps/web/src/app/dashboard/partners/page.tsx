'use client';

import React, { useState, useEffect } from 'react';
import {
  Users, UserCheck, Plus, RefreshCw, X, Shield, Lock, CheckCircle2,
  AlertCircle, ArrowRight, DollarSign, Clock, FileText, ChevronRight,
  Search, Filter, MapPin, Tag, Check, Award, Building2, Briefcase,
  Share2, ArrowUpRight, BadgePercent, AlertTriangle, ShieldCheck
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';

const TIER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  platinum: { bg: 'bg-purple-50 dark:bg-purple-950/40', text: 'text-purple-700 dark:text-purple-300', border: 'border-purple-200 dark:border-purple-800' },
  gold: { bg: 'bg-amber-50 dark:bg-amber-950/40', text: 'text-amber-700 dark:text-amber-300', border: 'border-amber-200 dark:border-amber-800' },
  silver: { bg: 'bg-zinc-100 dark:bg-zinc-800', text: 'text-zinc-700 dark:text-zinc-300', border: 'border-zinc-300 dark:border-zinc-700' },
  standard: { bg: 'bg-blue-50 dark:bg-blue-950/40', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-200 dark:border-blue-800' },
};

function formatCurrency(amount?: number | null, currency: string = 'INR'): string {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  if (amount >= 10000000) {
    return `${currency} ${(amount / 10000000).toFixed(2)} Cr`;
  }
  if (amount >= 100000) {
    return `${currency} ${(amount / 100000).toFixed(2)} L`;
  }
  return `${currency} ${Number(amount).toLocaleString('en-IN')}`;
}

export default function ChannelPartnersPage() {
  const [partners, setPartners] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Partner 360 Drawer
  const [activePartnerId, setActivePartnerId] = useState<string | null>(null);
  const [activePartner, setActivePartner] = useState<any>(null);
  const [isLoadingPartner, setIsLoadingPartner] = useState(false);
  const [partnerDrawerTab, setPartnerDrawerTab] = useState<'overview' | 'agreements' | 'commissions'>('overview');

  // Modals
  const [isRegisterCpOpen, setIsRegisterCpOpen] = useState(false);
  const [isRegisterLeadOpen, setIsRegisterLeadOpen] = useState(false);
  const [isAgreementOpen, setIsAgreementOpen] = useState(false);
  const [selectedCpForLead, setSelectedCpForLead] = useState<any>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [leadResult, setLeadResult] = useState<any>(null);

  // CP Form
  const [cpForm, setCpForm] = useState({
    firm_name: 'Apex Realty Advisors',
    contact_name: 'Vikram Malhotra',
    email: 'vikram@apexrealty.in',
    phone: '+919820011223',
    rera_number: 'A51900045678',
    pan_number: 'AABCU9603R',
    gst_number: '27AABCU9603R1ZM',
    city: 'Mumbai',
    tier: 'gold',
    default_commission_pct: 2.5,
  });

  // Partner Lead Form
  const [leadForm, setLeadForm] = useState({
    name: 'Rohit Singhania',
    phone: '+919811223344',
    email: 'rohit.singhania@outlook.com',
    project_id: '',
    budget_min: 30000000,
    budget_max: 50000000,
    property_type: '3 BHK',
  });

  // Agreement Form
  const [agreementForm, setAgreementForm] = useState({
    project_id: '',
    commission_pct: 2.5,
    valid_from: new Date().toISOString().split('T')[0],
    is_exclusive: false,
  });

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [cpRes, projRes] = await Promise.all([
        api.inventoryOS.listChannelPartners({ limit: 100 }).catch(() => ({ items: [] })),
        api.inventoryOS.listProjects({ limit: 50 }).catch(() => ({ items: [] }))
      ]);
      setPartners(cpRes?.items || []);
      const projs = projRes?.items || [];
      setProjects(projs);
      if (projs.length > 0 && !agreementForm.project_id) {
        setAgreementForm(prev => ({ ...prev, project_id: projs[0].id }));
        setLeadForm(prev => ({ ...prev, project_id: projs[0].id }));
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load channel partner network');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openPartner360 = async (cpId: string) => {
    setActivePartnerId(cpId);
    setIsLoadingPartner(true);
    try {
      const res = await api.inventoryOS.getChannelPartner(cpId);
      setActivePartner(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load partner details');
    } finally {
      setIsLoadingPartner(false);
    }
  };

  const handleVerifyKyc = async (cpId: string) => {
    try {
      await api.inventoryOS.verifyKyc(cpId);
      // Refresh partner details & list
      const updated = await api.inventoryOS.getChannelPartner(cpId);
      setActivePartner(updated);
      loadData();
    } catch (err: any) {
      alert(err?.message || 'Failed to verify KYC');
    }
  };

  const handleRegisterCP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cpForm.contact_name.trim() || !cpForm.phone.trim()) {
      setModalError('Contact name and phone are required');
      return;
    }
    setIsSubmitting(true);
    setModalError(null);
    try {
      await api.inventoryOS.registerChannelPartner({
        firm_name: cpForm.firm_name.trim(),
        contact_name: cpForm.contact_name.trim(),
        email: cpForm.email.trim() || undefined,
        phone: cpForm.phone.trim(),
        rera_number: cpForm.rera_number.trim() || undefined,
        pan_number: cpForm.pan_number.trim() || undefined,
        gst_number: cpForm.gst_number.trim() || undefined,
        city: cpForm.city.trim(),
        tier: cpForm.tier,
        default_commission_pct: Number(cpForm.default_commission_pct),
      });
      setIsRegisterCpOpen(false);
      loadData();
    } catch (err: any) {
      setModalError(err?.message || 'Failed to register channel partner');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegisterLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCpForLead) return;
    if (!leadForm.phone.trim()) {
      setModalError('Phone number is required');
      return;
    }
    setIsSubmitting(true);
    setModalError(null);
    setLeadResult(null);
    try {
      const res = await api.inventoryOS.registerPartnerLead(selectedCpForLead.id, {
        name: leadForm.name.trim(),
        phone: leadForm.phone.trim(),
        email: leadForm.email.trim() || undefined,
        project_id: leadForm.project_id || undefined,
        budget_min: Number(leadForm.budget_min),
        budget_max: Number(leadForm.budget_max),
        property_type: leadForm.property_type,
      });
      setLeadResult(res);
    } catch (err: any) {
      setModalError(err?.message || 'Failed to register lead');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateAgreement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activePartnerId || !agreementForm.project_id) return;
    setIsSubmitting(true);
    setModalError(null);
    try {
      await api.inventoryOS.createAgreement(activePartnerId, {
        project_id: agreementForm.project_id,
        commission_pct: Number(agreementForm.commission_pct),
        valid_from: agreementForm.valid_from,
        is_exclusive: agreementForm.is_exclusive,
      });
      setIsAgreementOpen(false);
      // Refresh partner details
      const updated = await api.inventoryOS.getChannelPartner(activePartnerId);
      setActivePartner(updated);
    } catch (err: any) {
      setModalError(err?.message || 'Failed to create project agreement');
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredPartners = partners.filter(p => {
    if (tierFilter !== 'all' && p.tier !== tierFilter) return false;
    if (statusFilter !== 'all' && p.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const codeMatch = p.cp_code?.toLowerCase().includes(q);
      const firmMatch = p.firm_name?.toLowerCase().includes(q);
      const nameMatch = p.contact_name?.toLowerCase().includes(q);
      const emailMatch = p.email?.toLowerCase().includes(q);
      if (!codeMatch && !firmMatch && !nameMatch && !emailMatch) return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-zinc-200 dark:border-zinc-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-300 dark:border-blue-800 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Channel Partner Network OS
              </span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">First-Touch Attribution & KYC Gated</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
              Channel Partner & Broker Network OS
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
              Institutional broker network management, KYC accreditation, exclusive project agreements, and co-broking commission ledgers.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => loadData()}
              className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 text-zinc-600 dark:text-zinc-300 transition-colors"
              title="Refresh Data"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => setIsRegisterCpOpen(true)}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium flex items-center gap-2 shadow-sm transition-all"
            >
              <Users className="w-4 h-4" /> Register Partner
            </button>
          </div>
        </div>

        {/* Global Partner Network KPIs */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 my-6">
          <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/60 shadow-xs">
            <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Total Partners</div>
            <div className="text-2xl font-bold mt-1 text-zinc-900 dark:text-zinc-50">
              {partners.length}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">Accredited brokerage agencies</div>
          </div>

          <div className="p-4 rounded-xl border border-emerald-200/60 dark:border-emerald-800/40 bg-emerald-50/40 dark:bg-emerald-950/20 shadow-xs">
            <div className="text-xs font-medium text-emerald-800 dark:text-emerald-300 uppercase tracking-wider">KYC Verified</div>
            <div className="text-2xl font-bold mt-1 text-emerald-700 dark:text-emerald-400">
              {partners.filter(p => p.kyc_verified).length}
            </div>
            <div className="text-xs text-emerald-600/80 dark:text-emerald-400/60 mt-0.5">Compliant for payouts</div>
          </div>

          <div className="p-4 rounded-xl border border-purple-200/60 dark:border-purple-800/40 bg-purple-50/40 dark:bg-purple-950/20 shadow-xs">
            <div className="text-xs font-medium text-purple-800 dark:text-purple-300 uppercase tracking-wider">Platinum / Gold</div>
            <div className="text-2xl font-bold mt-1 text-purple-700 dark:text-purple-400">
              {partners.filter(p => p.tier === 'platinum' || p.tier === 'gold').length}
            </div>
            <div className="text-xs text-purple-600/80 dark:text-purple-400/60 mt-0.5">High-volume producers</div>
          </div>

          <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/60 shadow-xs">
            <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Active Mandates</div>
            <div className="text-2xl font-bold mt-1 text-zinc-900 dark:text-zinc-50">
              {projects.length} Projects
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">Commission eligible projects</div>
          </div>
        </div>

        {/* Filter Ribbon */}
        <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            {/* Tier Filter */}
            <div className="flex items-center bg-zinc-100 dark:bg-zinc-800 p-1 rounded-lg text-xs font-medium">
              {['all', 'platinum', 'gold', 'silver', 'standard'].map(t => (
                <button
                  key={t}
                  onClick={() => setTierFilter(t)}
                  className={`px-2.5 py-1 rounded-md capitalize transition-colors ${
                    tierFilter === t
                      ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs font-semibold'
                      : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg px-2.5 py-1.5 focus:outline-none"
            >
              <option value="all">All Verification States</option>
              <option value="kyc_verified">KYC Verified Only</option>
              <option value="pending_kyc">Pending KYC</option>
              <option value="active">Active</option>
            </select>
          </div>

          {/* Search Box */}
          <div className="relative w-full md:w-72">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search firm, contact, CP code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Partners Table */}
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-800/40 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  <th className="py-3 px-4">Partner Firm / Contact</th>
                  <th className="py-3 px-4">CP Code</th>
                  <th className="py-3 px-4">Tier</th>
                  <th className="py-3 px-4">Accreditation / KYC</th>
                  <th className="py-3 px-4">Contact Info</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-zinc-500">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                      Loading channel partner network...
                    </td>
                  </tr>
                ) : filteredPartners.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-zinc-500">
                      <Users className="w-8 h-8 mx-auto mb-2 text-zinc-400" />
                      No channel partners found. Click &quot;Register Partner&quot; to onboarding brokers.
                    </td>
                  </tr>
                ) : (
                  filteredPartners.map((p) => {
                    const tierCol = TIER_COLORS[p.tier] || TIER_COLORS.standard;
                    return (
                      <tr
                        key={p.id}
                        className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/30 transition-colors group cursor-pointer"
                        onClick={() => openPartner360(p.id)}
                      >
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-zinc-900 dark:text-zinc-100">
                            {p.firm_name || p.contact_name}
                          </div>
                          {p.firm_name && (
                            <div className="text-xs text-zinc-500 flex items-center gap-1 mt-0.5">
                              <UserCheck className="w-3 h-3 text-zinc-400" /> {p.contact_name}
                            </div>
                          )}
                        </td>

                        <td className="py-3.5 px-4 font-mono text-xs font-semibold text-zinc-600 dark:text-zinc-300">
                          {p.cp_code}
                        </td>

                        <td className="py-3.5 px-4">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize border ${tierCol.bg} ${tierCol.text} ${tierCol.border}`}>
                            <Award className="w-3 h-3" />
                            {p.tier}
                          </span>
                        </td>

                        <td className="py-3.5 px-4">
                          {p.kyc_verified ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                              <CheckCircle2 className="w-3.5 h-3.5" /> KYC Verified
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                              <Clock className="w-3.5 h-3.5" /> Pending KYC
                            </span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 text-xs text-zinc-600 dark:text-zinc-400">
                          <div>{p.phone || '—'}</div>
                          <div className="text-zinc-400">{p.email || '—'}</div>
                        </td>

                        <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="inline-flex items-center gap-2">
                            <button
                              onClick={() => {
                                setSelectedCpForLead(p);
                                setIsRegisterLeadOpen(true);
                              }}
                              className="px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/50 dark:hover:bg-blue-900/60 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800 transition-colors"
                            >
                              + Register Lead
                            </button>
                            <button
                              onClick={() => openPartner360(p.id)}
                              className="px-2 py-1 rounded-md text-xs font-medium border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 transition-colors inline-flex items-center"
                            >
                              Partner 360 <ChevronRight className="w-3 h-3 ml-0.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Partner 360 Drawer */}
      {activePartnerId && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-xl bg-white dark:bg-[#121316] h-full shadow-2xl flex flex-col border-l border-zinc-200 dark:border-zinc-800 overflow-y-auto">
            {/* Header */}
            <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between sticky top-0 bg-white/90 dark:bg-[#121316]/90 backdrop-blur-sm z-10">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800">
                  <Briefcase className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                    {activePartner?.firm_name || activePartner?.contact_name || 'Channel Partner'}
                    {activePartner?.kyc_verified && (
                      <span className="p-1 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                        <Check className="w-3 h-3" />
                      </span>
                    )}
                  </h2>
                  <p className="text-xs text-zinc-500 font-mono">{activePartner?.cp_code}</p>
                </div>
              </div>
              <button
                onClick={() => setActivePartnerId(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Navigation Tabs in Drawer */}
            <div className="px-6 border-b border-zinc-200 dark:border-zinc-800 flex gap-4 text-xs font-semibold">
              <button
                onClick={() => setPartnerDrawerTab('overview')}
                className={`py-3 border-b-2 transition-colors ${partnerDrawerTab === 'overview' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
              >
                Profile & Accreditation
              </button>
              <button
                onClick={() => setPartnerDrawerTab('agreements')}
                className={`py-3 border-b-2 transition-colors ${partnerDrawerTab === 'agreements' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
              >
                Project Mandates ({activePartner?.agreements?.length || 0})
              </button>
              <button
                onClick={() => setPartnerDrawerTab('commissions')}
                className={`py-3 border-b-2 transition-colors ${partnerDrawerTab === 'commissions' ? 'border-blue-600 text-blue-600 dark:text-blue-400' : 'border-transparent text-zinc-500 hover:text-zinc-800'}`}
              >
                Commissions ({activePartner?.commissions?.length || 0})
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6 flex-1">
              {isLoadingPartner ? (
                <div className="py-20 text-center text-zinc-500">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-500" />
                  Loading Partner 360 data...
                </div>
              ) : activePartner ? (
                <>
                  {partnerDrawerTab === 'overview' && (
                    <div className="space-y-4">
                      {/* KYC Card */}
                      <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50 flex items-center justify-between">
                        <div>
                          <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">KYC Status</div>
                          <div className="text-sm font-bold text-zinc-900 dark:text-zinc-100 mt-0.5">
                            {activePartner.kyc_verified ? 'Verified & Authorized' : 'Pending Verification'}
                          </div>
                        </div>
                        {!activePartner.kyc_verified && (
                          <button
                            onClick={() => handleVerifyKyc(activePartner.id)}
                            className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1 shadow-xs"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" /> Approve KYC
                          </button>
                        )}
                      </div>

                      {/* Profile details */}
                      <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
                        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                          Registration & Regulatory Credentials
                        </h3>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div>
                            <div className="text-xs text-zinc-400">RERA Registration</div>
                            <div className="font-semibold text-zinc-900 dark:text-zinc-100 font-mono">{activePartner.rera_number || 'Not Submitted'}</div>
                          </div>
                          <div>
                            <div className="text-xs text-zinc-400">Default Commission</div>
                            <div className="font-semibold text-zinc-900 dark:text-zinc-100">{activePartner.default_commission_pct ? `${activePartner.default_commission_pct}%` : '2.0%'}</div>
                          </div>
                          <div>
                            <div className="text-xs text-zinc-400">Primary Contact</div>
                            <div className="font-semibold text-zinc-900 dark:text-zinc-100">{activePartner.contact_name}</div>
                          </div>
                          <div>
                            <div className="text-xs text-zinc-400">Direct Phone</div>
                            <div className="font-semibold text-zinc-900 dark:text-zinc-100">{activePartner.phone}</div>
                          </div>
                        </div>
                      </div>

                      {/* Quick Action: Register Lead */}
                      <button
                        onClick={() => {
                          setSelectedCpForLead(activePartner);
                          setIsRegisterLeadOpen(true);
                        }}
                        className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-xs transition-all"
                      >
                        <Plus className="w-4 h-4" /> Register Customer Lead for {activePartner.firm_name || activePartner.contact_name}
                      </button>
                    </div>
                  )}

                  {partnerDrawerTab === 'agreements' && (
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                          Active Project Agreements
                        </h3>
                        <button
                          onClick={() => setIsAgreementOpen(true)}
                          className="px-2.5 py-1 rounded-md text-xs font-medium bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-800 dark:text-zinc-200 flex items-center gap-1"
                        >
                          <Plus className="w-3.5 h-3.5" /> Add Agreement
                        </button>
                      </div>

                      {activePartner.agreements?.length > 0 ? (
                        activePartner.agreements.map((a: any) => (
                          <div key={a.id} className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-sm">
                            <div className="flex justify-between items-center">
                              <span className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                                <Building2 className="w-4 h-4 text-blue-500" />
                                Project ID: {a.project_id.slice(0, 8)}...
                              </span>
                              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                {a.commission_pct ? `${a.commission_pct}% Comm.` : 'Standard'}
                              </span>
                            </div>
                            <div className="mt-2 flex items-center gap-2 text-xs text-zinc-500">
                              <span className="px-2 py-0.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
                                {a.is_exclusive ? 'Exclusive Mandate' : 'Open Co-Broker'}
                              </span>
                              <span className="text-emerald-600 font-medium">● Active</span>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-10 text-zinc-400 text-xs">
                          No project marketing agreements active yet. Click &quot;Add Agreement&quot; to authorize this partner.
                        </div>
                      )}
                    </div>
                  )}

                  {partnerDrawerTab === 'commissions' && (
                    <div className="space-y-4">
                      <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                        Payable Commission Ledger
                      </h3>
                      {activePartner.commissions?.length > 0 ? (
                        activePartner.commissions.map((c: any) => (
                          <div key={c.id} className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-sm">
                            <div className="flex justify-between items-center">
                              <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                                {formatCurrency(c.commission_amount)}
                              </span>
                              <span className="px-2 py-0.5 rounded-full text-xs font-semibold capitalize bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                {c.payment_status}
                              </span>
                            </div>
                            <div className="text-xs text-zinc-500 mt-1">
                              Deal Transaction: {c.deal_id ? c.deal_id.slice(0, 8) + '...' : 'Direct Settlement'} · Val: {formatCurrency(c.transaction_value)}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-10 text-zinc-400 text-xs">
                          No commission ledger records for closed transactions yet.
                        </div>
                      )}
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Register Channel Partner Modal */}
      {isRegisterCpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-[#121316] rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-zinc-200 dark:border-zinc-800">
            <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-800">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <Users className="w-5 h-5 text-blue-600" /> Register Channel Partner
              </h2>
              <button onClick={() => setIsRegisterCpOpen(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {modalError && (
              <div className="my-3 p-3 rounded-lg bg-rose-100 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {modalError}
              </div>
            )}

            <form onSubmit={handleRegisterCP} className="space-y-3 mt-4">
              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Brokerage / Firm Name</label>
                <input
                  type="text"
                  required
                  value={cpForm.firm_name}
                  onChange={(e) => setCpForm({ ...cpForm, firm_name: e.target.value })}
                  className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Primary Contact</label>
                  <input
                    type="text"
                    required
                    value={cpForm.contact_name}
                    onChange={(e) => setCpForm({ ...cpForm, contact_name: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Phone</label>
                  <input
                    type="text"
                    required
                    value={cpForm.phone}
                    onChange={(e) => setCpForm({ ...cpForm, phone: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">RERA Number</label>
                  <input
                    type="text"
                    value={cpForm.rera_number}
                    onChange={(e) => setCpForm({ ...cpForm, rera_number: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Tier</label>
                  <select
                    value={cpForm.tier}
                    onChange={(e) => setCpForm({ ...cpForm, tier: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  >
                    <option value="standard">Standard</option>
                    <option value="silver">Silver</option>
                    <option value="gold">Gold</option>
                    <option value="platinum">Platinum</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsRegisterCpOpen(false)}
                  className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Register Partner
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Register Partner Lead Modal (Step 23 & 68) */}
      {isRegisterLeadOpen && selectedCpForLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-[#121316] rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-zinc-200 dark:border-zinc-800">
            <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-800">
              <div>
                <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <Share2 className="w-5 h-5 text-blue-600" /> Register Partner Lead
                </h2>
                <p className="text-xs text-zinc-500 mt-0.5">Attributed to {selectedCpForLead.firm_name || selectedCpForLead.contact_name} ({selectedCpForLead.cp_code})</p>
              </div>
              <button onClick={() => { setIsRegisterLeadOpen(false); setLeadResult(null); }} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Attribution Guard Banner */}
            <div className="my-3 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 text-xs text-blue-800 dark:text-blue-300 flex items-start gap-2">
              <Shield className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>
                <strong>First-Touch Attribution Guard:</strong> If this contact already exists in the CRM, existing attribution is strictly protected to prevent commission disputes.
              </span>
            </div>

            {leadResult && (
              <div className={`my-3 p-3.5 rounded-lg text-xs flex items-start gap-2 ${leadResult.duplicate_detected ? 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200 border border-amber-300' : 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 border border-emerald-300'}`}>
                {leadResult.duplicate_detected ? <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" /> : <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />}
                <div>
                  <div className="font-semibold">{leadResult.message}</div>
                  <div className="text-[11px] opacity-80 mt-0.5">Lead ID: {leadResult.lead_id} · Source: {leadResult.attribution}</div>
                </div>
              </div>
            )}

            {modalError && (
              <div className="my-3 p-3 rounded-lg bg-rose-100 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {modalError}
              </div>
            )}

            <form onSubmit={handleRegisterLead} className="space-y-3 mt-3">
              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Customer Full Name</label>
                <input
                  type="text"
                  required
                  value={leadForm.name}
                  onChange={(e) => setLeadForm({ ...leadForm, name: e.target.value })}
                  className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Phone Number</label>
                  <input
                    type="text"
                    required
                    value={leadForm.phone}
                    onChange={(e) => setLeadForm({ ...leadForm, phone: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Email</label>
                  <input
                    type="email"
                    value={leadForm.email}
                    onChange={(e) => setLeadForm({ ...leadForm, email: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Target Project Interest</label>
                <select
                  value={leadForm.project_id}
                  onChange={(e) => setLeadForm({ ...leadForm, project_id: e.target.value })}
                  className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                >
                  <option value="">Select Project (Optional)</option>
                  {projects.map(p => (
                    <option key={p.id} value={p.id}>{p.project_name} ({p.city})</option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => { setIsRegisterLeadOpen(false); setLeadResult(null); }}
                  className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 text-xs font-medium"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Register & Verify Attribution
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Project Agreement Modal */}
      {isAgreementOpen && activePartner && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-[#121316] rounded-2xl max-w-md w-full p-6 shadow-2xl border border-zinc-200 dark:border-zinc-800">
            <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-800">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-blue-600" /> New Project Mandate
              </h2>
              <button onClick={() => setIsAgreementOpen(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {modalError && (
              <div className="my-3 p-3 rounded-lg bg-rose-100 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {modalError}
              </div>
            )}

            <form onSubmit={handleCreateAgreement} className="space-y-3.5 mt-4">
              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Select Project</label>
                <select
                  required
                  value={agreementForm.project_id}
                  onChange={(e) => setAgreementForm({ ...agreementForm, project_id: e.target.value })}
                  className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                >
                  {projects.map(p => (
                    <option key={p.id} value={p.id}>{p.project_name} ({p.city})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Commission Rate (%)</label>
                <input
                  type="number"
                  step="0.1"
                  required
                  value={agreementForm.commission_pct}
                  onChange={(e) => setAgreementForm({ ...agreementForm, commission_pct: Number(e.target.value) })}
                  className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="exclusive"
                  checked={agreementForm.is_exclusive}
                  onChange={(e) => setAgreementForm({ ...agreementForm, is_exclusive: e.target.checked })}
                  className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="exclusive" className="text-xs text-zinc-700 dark:text-zinc-300">
                  Exclusive Project Marketing Mandate
                </label>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsAgreementOpen(false)}
                  className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Sign Mandate
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
