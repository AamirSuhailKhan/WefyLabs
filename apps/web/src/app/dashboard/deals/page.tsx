'use client';

import React, { useState, useEffect } from 'react';
import {
  Briefcase, Plus, RefreshCw, X, Shield, Lock, CheckCircle2,
  AlertCircle, ArrowRight, DollarSign, Clock, FileText, UserCheck,
  Award, Star, Sparkles, ChevronRight, History, Layers
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { ConfirmDialog } from '@/components/ui';
import { api } from '@/lib/api-client';

const ORDERED_STAGES = [
  'opportunity', 'negotiation', 'offer', 'reservation',
  'booking', 'transaction', 'commission', 'closing', 'post_sale'
];

const IRREVERSIBLE_STAGES = new Set(['reservation', 'booking', 'closing']);

function formatCurrency(amount?: number | null, currency: string = 'AED'): string {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  return `${currency} ${Number(amount).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

export default function DealsPage() {
  const [selectedStageFilter, setSelectedStageFilter] = useState<string>('all');
  const [deals, setDeals] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Deal Detail Modal / Workspace
  const [activeDealId, setActiveDealId] = useState<string | null>(null);
  const [activeDealDetail, setActiveDealDetail] = useState<any>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailTab, setDetailTab] = useState<'overview' | 'negotiation' | 'reservation' | 'booking' | 'commission' | 'closing' | 'post_sale' | 'audit'>('overview');

  // Create Deal Modal
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    deal_title: '',
    lead_id: '',
    property_id: '',
    current_stage: 'opportunity',
    agreed_price: 3500000,
    currency: 'AED',
    commission_percentage: 2.0,
    tags: 'luxury, waterfront',
    notes: 'High net-worth buyer interested in prime beachfront property.'
  });

  // Action Sub-Forms State
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Offer Form
  const [offerForm, setOfferForm] = useState({
    offer_price: 3400000,
    listing_price: 3500000,
    currency: 'AED',
    token_amount: 100000,
    payment_plan: '10% on booking, 40% during construction, 50% on handover'
  });

  // Reservation Form
  const [reservationForm, setReservationForm] = useState({
    reservation_amount: 50000,
    currency: 'AED',
    reserved_price: 3450000,
    customer_name: 'Ahmed Al Mansoori',
    customer_phone: '+971501234567',
    hold_hours: 48
  });

  // Booking Form
  const [bookingForm, setBookingForm] = useState({
    booking_reference: '',
    booked_price: 3450000,
    currency: 'AED',
    token_amount: 345000
  });

  // Commission Form
  const [commissionForm, setCommissionForm] = useState({
    transaction_price: 3450000,
    commission_percentage: 2.0,
    currency: 'AED',
    invoice_reference: 'INV-2026-001'
  });

  // Closing Form
  const [closingForm, setClosingForm] = useState({
    registration_authority: 'Dubai Land Department (DLD)',
    registration_number: 'REG-DLD-89421',
    title_deed_number: 'TD-9901428',
    handover_date: '2026-10-15'
  });

  // Post Sale Form
  const [postSaleForm, setPostSaleForm] = useState({
    customer_satisfaction_score: 5,
    nps_score: 9,
    feedback_text: 'Flawless closing experience, transparent escrow and swift handover!',
    referral_given: true
  });

  // Fetch summary and deals
  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [sumRes, dealsRes] = await Promise.all([
        api.dealOS.getSummary().catch(() => null),
        api.dealOS.list({ stage: selectedStageFilter !== 'all' ? selectedStageFilter : undefined })
      ]);
      setSummary(sumRes);
      setDeals(Array.isArray(dealsRes) ? dealsRes : (dealsRes as any)?.data || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load deals data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedStageFilter]);

  // Load Deal Detail Workspace
  const openDealWorkspace = async (dealId: string) => {
    setActiveDealId(dealId);
    setIsLoadingDetail(true);
    setActionSuccess(null);
    setActionError(null);
    try {
      const detail = await api.dealOS.get(dealId);
      setActiveDealDetail(detail);
      // Prepopulate forms
      if (detail) {
        setOfferForm(prev => ({
          ...prev,
          offer_price: detail.agreed_price || detail.offer_price || 3400000,
          currency: detail.currency || 'AED'
        }));
        setReservationForm(prev => ({
          ...prev,
          reserved_price: detail.agreed_price || 3450000,
          currency: detail.currency || 'AED',
          customer_name: detail.lead_name || 'Client'
        }));
        setBookingForm(prev => ({
          ...prev,
          booked_price: detail.agreed_price || 3450000,
          currency: detail.currency || 'AED',
          token_amount: Math.round((detail.agreed_price || 3450000) * 0.1)
        }));
        setCommissionForm(prev => ({
          ...prev,
          transaction_price: detail.agreed_price || 3450000,
          currency: detail.currency || 'AED',
          commission_percentage: detail.commission_percentage || 2.0
        }));
      }
    } catch (err: any) {
      setActionError(err?.message || 'Failed to load deal detail');
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const closeDealWorkspace = () => {
    setActiveDealId(null);
    setActiveDealDetail(null);
    setDetailTab('overview');
  };

  // Create Deal Handler
  const handleCreateDeal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.deal_title.trim()) {
      setCreateError('Deal title is required');
      return;
    }
    if (!createForm.lead_id.trim()) {
      setCreateError('Valid Lead ID is required');
      return;
    }
    setIsSubmitting(true);
    setCreateError(null);
    try {
      await api.dealOS.create({
        deal_title: createForm.deal_title.trim(),
        lead_id: createForm.lead_id.trim(),
        property_id: createForm.property_id.trim() || undefined,
        current_stage: createForm.current_stage,
        agreed_price: Number(createForm.agreed_price),
        currency: createForm.currency,
        commission_percentage: Number(createForm.commission_percentage),
        tags: createForm.tags.split(',').map(t => t.trim()).filter(Boolean),
        notes: createForm.notes
      });
      setIsCreateOpen(false);
      setCreateForm({
        deal_title: '',
        lead_id: '',
        property_id: '',
        current_stage: 'opportunity',
        agreed_price: 3500000,
        currency: 'AED',
        commission_percentage: 2.0,
        tags: 'luxury, waterfront',
        notes: 'High net-worth buyer interested in prime beachfront property.'
      });
      loadData();
    } catch (err: any) {
      setCreateError(err?.message || 'Failed to create deal');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Advance Stage Modal State & Handlers
  const [advanceModal, setAdvanceModal] = useState<{
    isOpen: boolean;
    dealId: string;
    targetStage: string;
    isSubmitting: boolean;
  }>({ isOpen: false, dealId: '', targetStage: '', isSubmitting: false });

  const handleAdvanceStage = (dealId: string, targetStage: string) => {
    setAdvanceModal({ isOpen: true, dealId, targetStage, isSubmitting: false });
  };

  const handleConfirmAdvance = async (reason?: string) => {
    if (!advanceModal.dealId) return;
    setAdvanceModal(prev => ({ ...prev, isSubmitting: true }));
    try {
      await api.dealOS.advanceStage(advanceModal.dealId, {
        target_stage: advanceModal.targetStage,
        reason: reason || `Advancing deal workflow to ${advanceModal.targetStage}`
      });
      await loadData();
      if (activeDealId === advanceModal.dealId) {
        await openDealWorkspace(advanceModal.dealId);
      }
      setAdvanceModal({ isOpen: false, dealId: '', targetStage: '', isSubmitting: false });
    } catch (err: any) {
      alert(`Stage transition failed: ${err?.message || 'Error occurred'}`);
      setAdvanceModal(prev => ({ ...prev, isSubmitting: false }));
    }
  };

  // Negotiation Offer Submission
  const handleSubmitOffer = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.submitOffer(activeDealId, {
        offer_price: Number(offerForm.offer_price),
        listing_price: Number(offerForm.listing_price),
        currency: offerForm.currency,
        token_amount: Number(offerForm.token_amount),
        payment_plan: offerForm.payment_plan
      });
      setActionSuccess('Offer version submitted and logged to audit trail.');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to submit offer');
    }
  };

  // Unit Reservation Hold
  const handleCreateReservation = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.createReservation(activeDealId, {
        reservation_amount: Number(reservationForm.reservation_amount),
        currency: reservationForm.currency,
        reserved_price: Number(reservationForm.reserved_price),
        customer_name: reservationForm.customer_name,
        customer_phone: reservationForm.customer_phone,
        hold_hours: Number(reservationForm.hold_hours)
      });
      setActionSuccess('Unit reservation placed with distributed concurrency lock!');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Reservation failed');
    }
  };

  // Booking Gate Request & Confirm
  const handleRequestBooking = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.requestBooking(activeDealId, {
        reason: 'Client paid deposit; requesting human authorization to confirm booking.'
      });
      setActionSuccess('Booking authorization requested (Human-in-the-loop gate pending).');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Booking request failed');
    }
  };

  const handleConfirmBooking = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.confirmBooking(activeDealId, {
        booking_reference: bookingForm.booking_reference || `BK-${Date.now().toString().slice(-6)}`,
        booked_price: Number(bookingForm.booked_price),
        currency: bookingForm.currency,
        token_amount: Number(bookingForm.token_amount)
      });
      setActionSuccess('Booking confirmed and token deposit recorded!');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Booking confirmation failed');
    }
  };

  // Commission Ledger
  const handleRecordCommission = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.recordCommission(activeDealId, {
        transaction_price: Number(commissionForm.transaction_price),
        commission_percentage: Number(commissionForm.commission_percentage),
        currency: commissionForm.currency,
        invoice_reference: commissionForm.invoice_reference
      });
      setActionSuccess('Commission ledger calculated with split breakdown!');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to record commission');
    }
  };

  // Closing Handover
  const handleCreateClosing = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.createClosing(activeDealId, {
        registration_authority: closingForm.registration_authority,
        registration_number: closingForm.registration_number,
        title_deed_number: closingForm.title_deed_number,
        handover_date: closingForm.handover_date
      });
      setActionSuccess('Closing registration and checklist created!');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Closing creation failed');
    }
  };

  const handleCompleteClosing = async () => {
    if (!activeDealId) return;
    if (!confirm('Complete closing and transition deal to CLOSED_WON? This action is permanent.')) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.completeClosing(activeDealId);
      setActionSuccess('Closing completed! Deal marked CLOSED_WON.');
      await openDealWorkspace(activeDealId);
      await loadData();
    } catch (err: any) {
      setActionError(err?.message || 'Closing completion failed');
    }
  };

  // Post Sale NPS
  const handleRecordPostSale = async () => {
    if (!activeDealId) return;
    setActionError(null);
    setActionSuccess(null);
    try {
      await api.dealOS.recordPostSale(activeDealId, {
        customer_satisfaction_score: Number(postSaleForm.customer_satisfaction_score),
        nps_score: Number(postSaleForm.nps_score),
        feedback_text: postSaleForm.feedback_text,
        referral_given: postSaleForm.referral_given
      });
      setActionSuccess('Post-sale NPS and revenue learning signals recorded!');
      await openDealWorkspace(activeDealId);
    } catch (err: any) {
      setActionError(err?.message || 'Failed to record post-sale feedback');
    }
  };

  const getStageColor = (stage: string) => {
    switch (stage) {
      case 'opportunity': return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'negotiation': return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'offer': return 'bg-cyan-50 text-cyan-700 border-cyan-200';
      case 'reservation': return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'booking': return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'transaction': return 'bg-sky-50 text-sky-700 border-sky-200';
      case 'commission': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'closing': return 'bg-green-50 text-green-700 border-green-200';
      case 'post_sale': return 'bg-teal-50 text-teal-700 border-teal-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16 max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-[#1A1A1A] text-[#E8F5A8]">
                PART 18 COMMERCIAL PIPELINE
              </span>
              <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                <Shield className="w-3 h-3" /> Concurrency &amp; Audit Guard Active
              </span>
            </div>
            <h1
              className="text-[26px] sm:text-[30px] font-bold text-[#1A1A1A] tracking-tight mt-1"
              style={{ fontFamily: 'JetBrains Mono, monospace' }}
            >
              DEAL, BOOKING &amp; TRANSACTION OS
            </h1>
            <p className="text-[13px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
              Deterministic 9-stage commercial execution: Offers, Unit Reservations, Human-gated Bookings, Commission Ledger &amp; Closings.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={isLoading}
              title="Refresh Pipeline"
              className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[#0D9488]' : ''}`} />
            </button>
            <button
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[12px] font-bold font-mono transition-all shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>+ Create Canonical Deal</span>
            </button>
          </div>
        </div>

        {/* Commercial Pipeline KPI Cards */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-xl shadow-xs">
              <span className="text-[11px] font-mono uppercase text-[#6B6B6B] block">Active Deals</span>
              <div className="text-[24px] font-bold font-mono text-[#1A1A1A] mt-1">
                {summary.total_active_deals || 0}
              </div>
              <span className="text-[10px] text-emerald-700 font-mono">100% Tenant Isolated</span>
            </div>

            <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-xl shadow-xs">
              <span className="text-[11px] font-mono uppercase text-[#6B6B6B] block">Gross Pipeline Value</span>
              <div className="text-[20px] sm:text-[22px] font-bold font-mono text-emerald-800 mt-1">
                {formatCurrency(summary.total_pipeline_value, 'AED')}
              </div>
              <span className="text-[10px] text-[#6B6B6B] font-mono">Agreed / Offer Total</span>
            </div>

            <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-xl shadow-xs">
              <span className="text-[11px] font-mono uppercase text-[#6B6B6B] block">Weighted Value</span>
              <div className="text-[20px] sm:text-[22px] font-bold font-mono text-indigo-800 mt-1">
                {formatCurrency(summary.weighted_pipeline_value, 'AED')}
              </div>
              <span className="text-[10px] text-[#6B6B6B] font-mono">Probability Adjusted</span>
            </div>

            <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-xl shadow-xs">
              <span className="text-[11px] font-mono uppercase text-[#6B6B6B] block">Projected Commission</span>
              <div className="text-[20px] sm:text-[22px] font-bold font-mono text-[#0D9488] mt-1">
                {formatCurrency(summary.total_commission_projected, 'AED')}
              </div>
              <span className="text-[10px] text-[#6B6B6B] font-mono">Ledger Calculated</span>
            </div>
          </div>
        )}

        {/* 9-Stage Filter Ribbon */}
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-2.5 rounded-2xl overflow-x-auto shadow-xs">
          <div className="flex items-center gap-1.5 min-w-max">
            <button
              onClick={() => setSelectedStageFilter('all')}
              className={`px-3 py-1.5 rounded-lg text-[11px] font-mono font-bold transition-all ${
                selectedStageFilter === 'all'
                  ? 'bg-[#1A1A1A] text-[#FAF7F2]'
                  : 'bg-white text-[#4A4A4A] border border-[#D4D0C8] hover:bg-[#F0EDE8]'
              }`}
            >
              All Stages ({deals.length})
            </button>

            {ORDERED_STAGES.map((stg) => {
              const count = summary?.deals_by_stage?.[stg] || 0;
              const isLocked = IRREVERSIBLE_STAGES.has(stg);
              return (
                <button
                  key={stg}
                  onClick={() => setSelectedStageFilter(stg)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-mono capitalize transition-all ${
                    selectedStageFilter === stg
                      ? 'bg-[#1A1A1A] text-[#FAF7F2] font-bold'
                      : 'bg-white text-[#4A4A4A] border border-[#D4D0C8] hover:bg-[#F0EDE8]'
                  }`}
                >
                  {isLocked && <Lock className="w-3 h-3 text-amber-500" />}
                  <span>{stg.replace('_', ' ')}</span>
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-[#EAE7E1] text-[#1A1A1A] font-bold">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Deals Grid List */}
        {isLoading ? (
          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-12 text-center">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-[#0D9488]" />
            <p className="mt-3 text-[13px] font-mono text-[#6B6B6B]">Loading real estate transaction deals...</p>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl text-sm font-mono">
            {error}
          </div>
        ) : deals.length === 0 ? (
          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-12 text-center space-y-3">
            <Briefcase className="w-12 h-12 mx-auto text-[#8C887B]" />
            <h3 className="text-base font-bold text-[#1A1A1A] font-mono">No Deals in Stage "{selectedStageFilter}"</h3>
            <p className="text-xs text-[#6B6B6B] max-w-md mx-auto">
              Create a new canonical deal to advance commercial opportunities through negotiation, unit reservations, and closing.
            </p>
            <button
              onClick={() => setIsCreateOpen(true)}
              className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-xs font-mono font-bold"
            >
              + Create First Deal
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {deals.map((deal) => {
              const currIdx = ORDERED_STAGES.indexOf(deal.current_stage);
              const nextStage = currIdx >= 0 && currIdx < ORDERED_STAGES.length - 1 ? ORDERED_STAGES[currIdx + 1] : null;
              const isLocked = IRREVERSIBLE_STAGES.has(deal.current_stage);

              return (
                <div
                  key={deal.id}
                  className="bg-[#FAF7F2] border border-[#D4D0C8] hover:border-[#1A1A1A] rounded-2xl p-5 space-y-4 transition-all shadow-xs flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    {/* Top Row: Ref & Stage Badge */}
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-[#6B6B6B] tracking-wide">
                        {deal.deal_reference || 'REF-PENDING'}
                      </span>
                      <span
                        className={`flex items-center gap-1 text-[11px] font-mono font-bold px-2.5 py-1 rounded-full border ${getStageColor(
                          deal.current_stage
                        )}`}
                      >
                        {isLocked && <Lock className="w-3 h-3 text-amber-600" />}
                        <span className="capitalize">{deal.current_stage.replace('_', ' ')}</span>
                      </span>
                    </div>

                    {/* Deal Title */}
                    <div>
                      <h3 className="text-[16px] font-bold text-[#1A1A1A] font-mono leading-tight hover:text-[#0D9488] cursor-pointer" onClick={() => openDealWorkspace(deal.id)}>
                        {deal.deal_title}
                      </h3>
                      {deal.property_title && (
                        <p className="text-[12px] text-[#6B6B6B] truncate mt-0.5 font-sans">
                          📍 {deal.property_title}
                        </p>
                      )}
                    </div>

                    {/* Financials & Probability */}
                    <div className="bg-white p-3 rounded-xl border border-[#D4D0C8] space-y-2">
                      <div className="flex justify-between items-baseline">
                        <span className="text-[10px] font-mono text-[#6B6B6B] uppercase font-bold">Agreed Price</span>
                        <span className="text-[15px] font-bold font-mono text-[#1A1A1A]">
                          {formatCurrency(deal.agreed_price, deal.currency)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center text-[11px] font-mono pt-1 border-t border-[#F0EDE8]">
                        <span className="text-[#6B6B6B]">Commission ({deal.commission_percentage || 2.0}%)</span>
                        <span className="font-bold text-emerald-800">
                          {formatCurrency(deal.commission_amount, deal.currency)}
                        </span>
                      </div>
                    </div>

                    {/* Sub-Entity Indicators */}
                    <div className="flex flex-wrap gap-1.5 text-[10px] font-mono">
                      {deal.has_offer && (
                        <span className="px-2 py-0.5 rounded bg-cyan-50 text-cyan-800 border border-cyan-200">
                          ✓ Offer
                        </span>
                      )}
                      {deal.has_reservation && (
                        <span className="px-2 py-0.5 rounded bg-indigo-50 text-indigo-800 border border-indigo-200">
                          ✓ Reserved
                        </span>
                      )}
                      {deal.has_booking && (
                        <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200">
                          ✓ Booked
                        </span>
                      )}
                      {deal.has_commission && (
                        <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
                          ✓ Commission
                        </span>
                      )}
                      {deal.has_closing && (
                        <span className="px-2 py-0.5 rounded bg-green-50 text-green-800 border border-green-200">
                          ✓ Closing
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Actions Bar */}
                  <div className="pt-3 border-t border-[#EAE7E1] flex items-center justify-between gap-2">
                    <button
                      onClick={() => openDealWorkspace(deal.id)}
                      className="px-3 py-1.5 bg-[#FAF7F2] hover:bg-[#EAE7E1] border border-[#D4D0C8] text-[#1A1A1A] rounded-lg text-[11px] font-mono font-bold transition-all flex items-center gap-1"
                    >
                      <span>Workspace</span>
                      <ChevronRight className="w-3 h-3" />
                    </button>

                    {nextStage && deal.status === 'ACTIVE' && (
                      <button
                        onClick={() => handleAdvanceStage(deal.id, nextStage)}
                        className="px-3 py-1.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[11px] font-mono font-bold transition-all flex items-center gap-1"
                        title={`Advance to ${nextStage}`}
                      >
                        <span>Advance → {nextStage}</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ───────────────────────────────────────────────────────────────────────────── */}
      {/* Create Deal Modal */}
      {/* ───────────────────────────────────────────────────────────────────────────── */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#D4D0C8] pb-3">
              <div className="flex items-center gap-2">
                <Briefcase className="w-5 h-5 text-[#0D9488]" />
                <h2 className="text-[17px] font-bold font-mono text-[#1A1A1A]">Create Real Estate Deal</h2>
              </div>
              <button onClick={() => setIsCreateOpen(false)} className="text-[#6B6B6B] hover:text-[#1A1A1A]">
                <X className="w-5 h-5" />
              </button>
            </div>

            {createError && (
              <div className="bg-red-50 border border-red-200 text-red-800 p-3 rounded-xl text-xs font-mono">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateDeal} className="space-y-4">
              <div>
                <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Deal Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Palm Jumeirah Signature Villa 4BHK"
                  value={createForm.deal_title}
                  onChange={(e) => setCreateForm({ ...createForm, deal_title: e.target.value })}
                  className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Lead ID (UUID) *</label>
                  <input
                    type="text"
                    required
                    placeholder="Existing Lead UUID"
                    value={createForm.lead_id}
                    onChange={(e) => setCreateForm({ ...createForm, lead_id: e.target.value })}
                    className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Property ID (Optional)</label>
                  <input
                    type="text"
                    placeholder="Listing UUID"
                    value={createForm.property_id}
                    onChange={(e) => setCreateForm({ ...createForm, property_id: e.target.value })}
                    className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Agreed Price</label>
                  <input
                    type="number"
                    value={createForm.agreed_price}
                    onChange={(e) => setCreateForm({ ...createForm, agreed_price: Number(e.target.value) })}
                    className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Currency</label>
                  <select
                    value={createForm.currency}
                    onChange={(e) => setCreateForm({ ...createForm, currency: e.target.value })}
                    className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                  >
                    <option value="AED">AED (Dirhams)</option>
                    <option value="INR">INR (Rupees)</option>
                    <option value="USD">USD (Dollars)</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Comm %</label>
                  <input
                    type="number"
                    step="0.1"
                    value={createForm.commission_percentage}
                    onChange={(e) => setCreateForm({ ...createForm, commission_percentage: Number(e.target.value) })}
                    className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Tags (Comma-separated)</label>
                <input
                  type="text"
                  value={createForm.tags}
                  onChange={(e) => setCreateForm({ ...createForm, tags: e.target.value })}
                  className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                />
              </div>

              <div>
                <label className="text-[11px] font-mono uppercase text-[#6B6B6B] block mb-1">Commercial Notes</label>
                <textarea
                  rows={2}
                  value={createForm.notes}
                  onChange={(e) => setCreateForm({ ...createForm, notes: e.target.value })}
                  className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3 py-2 text-xs font-mono text-[#1A1A1A] focus:outline-hidden focus:border-[#1A1A1A]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-[#D4D0C8]">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 bg-white border border-[#D4D0C8] text-[#1A1A1A] rounded-lg text-xs font-mono hover:bg-[#F0EDE8]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-xs font-mono font-bold"
                >
                  {isSubmitting ? 'Creating...' : 'Create Canonical Deal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ───────────────────────────────────────────────────────────────────────────── */}
      {/* Interactive Deal OS Workspace Drawer / Modal */}
      {/* ───────────────────────────────────────────────────────────────────────────── */}
      {activeDealId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-[#D4D0C8] bg-white flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-[#6B6B6B]">
                    {activeDealDetail?.deal_reference || 'REF-LOAD'}
                  </span>
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${getStageColor(
                      activeDealDetail?.current_stage || 'opportunity'
                    )}`}
                  >
                    {activeDealDetail?.current_stage?.replace('_', ' ').toUpperCase()}
                  </span>
                  {activeDealDetail?.status === 'CLOSED_WON' && (
                    <span className="text-[10px] font-mono bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded">
                      🎉 CLOSED WON
                    </span>
                  )}
                </div>
                <h2 className="text-[20px] font-bold font-mono text-[#1A1A1A] mt-1">
                  {activeDealDetail?.deal_title || 'Deal Workspace'}
                </h2>
              </div>

              <button
                onClick={closeDealWorkspace}
                className="p-2 text-[#6B6B6B] hover:text-[#1A1A1A] rounded-lg hover:bg-[#F0EDE8]"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Lifecycle Progress Bar */}
            <div className="bg-[#F0EDE8] border-b border-[#D4D0C8] px-6 py-3 overflow-x-auto">
              <div className="flex items-center gap-2 min-w-max">
                {ORDERED_STAGES.map((s, idx) => {
                  const currentIdx = ORDERED_STAGES.indexOf(activeDealDetail?.current_stage || 'opportunity');
                  const isCurrent = s === activeDealDetail?.current_stage;
                  const isCompleted = idx < currentIdx;
                  return (
                    <div key={s} className="flex items-center gap-1.5">
                      <div
                        className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-mono capitalize transition-all ${
                          isCurrent
                            ? 'bg-[#1A1A1A] text-[#FAF7F2] font-bold shadow-xs'
                            : isCompleted
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                            : 'bg-white/60 text-gray-400 border border-gray-200'
                        }`}
                      >
                        {isCompleted ? <CheckCircle2 className="w-3 h-3 text-emerald-600" /> : <span>{idx + 1}.</span>}
                        <span>{s.replace('_', ' ')}</span>
                      </div>
                      {idx < ORDERED_STAGES.length - 1 && <span className="text-[#A09D94] text-xs">→</span>}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Sub-Workspace Tab Navigation */}
            <div className="bg-white border-b border-[#D4D0C8] px-6 flex items-center gap-4 overflow-x-auto">
              {[
                { key: 'overview', label: 'Overview & Stages' },
                { key: 'negotiation', label: 'Offers & Negotiation' },
                { key: 'reservation', label: 'Unit Reservation' },
                { key: 'booking', label: 'Booking & Gate' },
                { key: 'commission', label: 'Commission Ledger' },
                { key: 'closing', label: 'Closing & Handover' },
                { key: 'post_sale', label: 'Post-Sale NPS' },
                { key: 'audit', label: 'Audit Trail' }
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setDetailTab(tab.key as any)}
                  className={`py-3 text-[11px] font-mono font-bold border-b-2 transition-all shrink-0 ${
                    detailTab === tab.key
                      ? 'border-[#1A1A1A] text-[#1A1A1A]'
                      : 'border-transparent text-[#6B6B6B] hover:text-[#1A1A1A]'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Feedback Notifications */}
            {actionSuccess && (
              <div className="mx-6 mt-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-mono flex items-center justify-between">
                <span>{actionSuccess}</span>
                <button onClick={() => setActionSuccess(null)} className="text-emerald-700 font-bold">×</button>
              </div>
            )}
            {actionError && (
              <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs font-mono flex items-center justify-between">
                <span>{actionError}</span>
                <button onClick={() => setActionError(null)} className="text-red-700 font-bold">×</button>
              </div>
            )}

            {/* Tab Contents */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              {isLoadingDetail ? (
                <div className="py-12 text-center font-mono text-sm text-[#6B6B6B]">
                  Loading detailed workspace...
                </div>
              ) : !activeDealDetail ? (
                <div className="py-12 text-center font-mono text-sm text-red-600">
                  Failed to load deal detail.
                </div>
              ) : (
                <>
                  {/* TAB 1: OVERVIEW */}
                  {detailTab === 'overview' && (
                    <div className="space-y-5">
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-white p-3.5 rounded-xl border border-[#D4D0C8]">
                          <span className="text-[10px] font-mono uppercase text-[#6B6B6B] block">Agreed Price</span>
                          <span className="text-[16px] font-bold font-mono text-[#1A1A1A]">
                            {formatCurrency(activeDealDetail.agreed_price, activeDealDetail.currency)}
                          </span>
                        </div>
                        <div className="bg-white p-3.5 rounded-xl border border-[#D4D0C8]">
                          <span className="text-[10px] font-mono uppercase text-[#6B6B6B] block">Commission Amount</span>
                          <span className="text-[16px] font-bold font-mono text-emerald-800">
                            {formatCurrency(activeDealDetail.commission_amount, activeDealDetail.currency)}
                          </span>
                        </div>
                        <div className="bg-white p-3.5 rounded-xl border border-[#D4D0C8]">
                          <span className="text-[10px] font-mono uppercase text-[#6B6B6B] block">Closing Probability</span>
                          <span className="text-[16px] font-bold font-mono text-indigo-700">
                            {activeDealDetail.closing_probability_pct}%
                          </span>
                        </div>
                      </div>

                      {/* Stage History Timeline */}
                      <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#1A1A1A]">
                          <History className="w-4 h-4 text-[#0D9488]" />
                          <span>Stage History &amp; Transition Log</span>
                        </div>
                        <div className="space-y-2">
                          {activeDealDetail.stage_history?.map((h: any, i: number) => (
                            <div key={h.id || i} className="flex items-center justify-between text-xs font-mono p-2 bg-[#FAF7F2] rounded-lg border border-[#EAE7E1]">
                              <div>
                                <span className="text-[#6B6B6B]">{h.from_stage ? `${h.from_stage} → ` : 'Created at '}</span>
                                <strong className="text-[#1A1A1A] capitalize">{h.to_stage}</strong>
                                {h.reason && <span className="text-gray-500 block text-[11px]">Reason: {h.reason}</span>}
                              </div>
                              <div className="text-right text-[11px] text-[#6B6B6B]">
                                {new Date(h.transitioned_at).toLocaleString()}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* AI Recommendations */}
                      {activeDealDetail.ai_recommendations && (
                        <div className="bg-indigo-50 border border-indigo-200 p-4 rounded-xl space-y-2">
                          <div className="flex items-center gap-2 text-xs font-mono font-bold text-indigo-950">
                            <Sparkles className="w-4 h-4 text-indigo-600" />
                            <span>AI Deal Risk &amp; Governance Recommendations</span>
                          </div>
                          <ul className="text-xs text-indigo-900 font-sans list-disc list-inside space-y-1">
                            {activeDealDetail.ai_recommendations.map((rec: string, i: number) => (
                              <li key={i}>{rec}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 2: NEGOTIATION & OFFERS */}
                  {detailTab === 'negotiation' && (
                    <div className="space-y-5">
                      {activeDealDetail.offer ? (
                        <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                          <div className="flex justify-between items-center border-b border-[#EAE7E1] pb-2">
                            <span className="text-xs font-mono font-bold text-[#1A1A1A]">
                              Active Offer Version {activeDealDetail.offer.version}
                            </span>
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                              Status: {activeDealDetail.offer.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                            <div>
                              <span className="text-[#6B6B6B] block">Offer Price</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.offer.offer_price, activeDealDetail.offer.currency)}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Listing Price</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.offer.listing_price, activeDealDetail.offer.currency)}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Token Amount</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.offer.token_amount, activeDealDetail.offer.currency)}</strong>
                            </div>
                          </div>
                          {activeDealDetail.offer.payment_plan && (
                            <div className="text-xs font-mono bg-[#FAF7F2] p-2.5 rounded-lg border border-[#EAE7E1]">
                              <span className="text-[#6B6B6B] block font-bold">Payment Plan:</span>
                              <span>{activeDealDetail.offer.payment_plan}</span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs font-mono text-amber-900">
                          No active commercial offer logged yet for this deal.
                        </div>
                      )}

                      {/* Submit / Revise Offer Form */}
                      <div className="bg-[#FAF7F2] p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <h4 className="text-xs font-mono font-bold text-[#1A1A1A] uppercase">
                          Submit Counter-Offer / Negotiation Version
                        </h4>
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Offer Price</label>
                            <input
                              type="number"
                              value={offerForm.offer_price}
                              onChange={(e) => setOfferForm({ ...offerForm, offer_price: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Listing Price</label>
                            <input
                              type="number"
                              value={offerForm.listing_price}
                              onChange={(e) => setOfferForm({ ...offerForm, listing_price: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Token Amount</label>
                            <input
                              type="number"
                              value={offerForm.token_amount}
                              onChange={(e) => setOfferForm({ ...offerForm, token_amount: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-[10px] font-mono text-[#6B6B6B] block">Payment Plan Terms</label>
                          <input
                            type="text"
                            value={offerForm.payment_plan}
                            onChange={(e) => setOfferForm({ ...offerForm, payment_plan: e.target.value })}
                            className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                          />
                        </div>
                        <button
                          onClick={handleSubmitOffer}
                          className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-xs font-mono font-bold"
                        >
                          Submit Offer Revision
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 3: UNIT RESERVATION */}
                  {detailTab === 'reservation' && (
                    <div className="space-y-5">
                      {activeDealDetail.reservation ? (
                        <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                          <div className="flex justify-between items-center border-b border-[#EAE7E1] pb-2">
                            <span className="text-xs font-mono font-bold text-[#1A1A1A] flex items-center gap-1.5">
                              <Lock className="w-3.5 h-3.5 text-indigo-600" />
                              Unit Reservation Lock Active
                            </span>
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">
                              Status: {activeDealDetail.reservation.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                            <div>
                              <span className="text-[#6B6B6B] block">Reserved Price</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.reservation.reserved_price, activeDealDetail.reservation.currency)}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Reservation Deposit</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.reservation.reservation_amount, activeDealDetail.reservation.currency)}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Reserved At</span>
                              <span>{new Date(activeDealDetail.reservation.reserved_at).toLocaleString()}</span>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Expires At</span>
                              <span>{activeDealDetail.reservation.expires_at ? new Date(activeDealDetail.reservation.expires_at).toLocaleString() : 'Permanent'}</span>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-xs font-mono text-amber-900">
                          No active unit reservation currently locks this property.
                        </div>
                      )}

                      {/* Create Reservation Hold Form */}
                      <div className="bg-[#FAF7F2] p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <h4 className="text-xs font-mono font-bold text-[#1A1A1A] uppercase flex items-center gap-1.5">
                          <Shield className="w-3.5 h-3.5 text-indigo-600" />
                          Place Concurrency-Safe Unit Reservation Hold
                        </h4>
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Deposit Amount</label>
                            <input
                              type="number"
                              value={reservationForm.reservation_amount}
                              onChange={(e) => setReservationForm({ ...reservationForm, reservation_amount: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Reserved Price</label>
                            <input
                              type="number"
                              value={reservationForm.reserved_price}
                              onChange={(e) => setReservationForm({ ...reservationForm, reserved_price: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Hold Duration (Hours)</label>
                            <input
                              type="number"
                              value={reservationForm.hold_hours}
                              onChange={(e) => setReservationForm({ ...reservationForm, hold_hours: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Customer Name</label>
                            <input
                              type="text"
                              value={reservationForm.customer_name}
                              onChange={(e) => setReservationForm({ ...reservationForm, customer_name: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Customer Phone</label>
                            <input
                              type="text"
                              value={reservationForm.customer_phone}
                              onChange={(e) => setReservationForm({ ...reservationForm, customer_phone: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <button
                          onClick={handleCreateReservation}
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-mono font-bold"
                        >
                          Acquire Reservation Lock
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 4: BOOKING & GATE */}
                  {detailTab === 'booking' && (
                    <div className="space-y-5">
                      {activeDealDetail.booking ? (
                        <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                          <div className="flex justify-between items-center border-b border-[#EAE7E1] pb-2">
                            <span className="text-xs font-mono font-bold text-[#1A1A1A]">
                              Booking Reference: {activeDealDetail.booking.booking_reference}
                            </span>
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800">
                              Status: {activeDealDetail.booking.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                            <div>
                              <span className="text-[#6B6B6B] block">Booked Price</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.booking.booked_price, activeDealDetail.booking.currency)}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Token Amount Paid</span>
                              <strong className="text-[15px]">{formatCurrency(activeDealDetail.booking.token_amount, activeDealDetail.booking.currency)}</strong>
                            </div>
                          </div>
                          {activeDealDetail.booking.payment_schedule && (
                            <div className="space-y-1.5 pt-2">
                              <span className="text-[11px] font-mono font-bold text-[#1A1A1A] block">Payment Schedule Milestones</span>
                              {activeDealDetail.booking.payment_schedule.map((milestone: any, idx: number) => (
                                <div key={idx} className="flex justify-between text-xs font-mono bg-[#FAF7F2] p-2 rounded border border-[#EAE7E1]">
                                  <span>{milestone.milestone} ({milestone.percentage}%)</span>
                                  <strong>{formatCurrency(milestone.amount, activeDealDetail.booking.currency)}</strong>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="p-4 bg-purple-50 border border-purple-200 rounded-xl space-y-3">
                          <div className="flex items-center gap-2 text-xs font-mono font-bold text-purple-950">
                            <Lock className="w-4 h-4 text-purple-700" />
                            <span>Booking Stage Gate (Human Authorization Required)</span>
                          </div>
                          <p className="text-xs text-purple-900 font-sans">
                            Advancing to the Booking stage requires an explicit human authorization check. AI agents cannot irreversibly mutate transaction booking state without approval.
                          </p>
                          <button
                            onClick={handleRequestBooking}
                            className="px-4 py-2 bg-purple-700 hover:bg-purple-800 text-white rounded-lg text-xs font-mono font-bold"
                          >
                            Request Human Authorization
                          </button>
                        </div>
                      )}

                      {/* Confirm Booking Form */}
                      <div className="bg-[#FAF7F2] p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <h4 className="text-xs font-mono font-bold text-[#1A1A1A] uppercase">
                          Confirm Final Booking &amp; Milestone Schedule
                        </h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Final Booked Price</label>
                            <input
                              type="number"
                              value={bookingForm.booked_price}
                              onChange={(e) => setBookingForm({ ...bookingForm, booked_price: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Token Amount Paid</label>
                            <input
                              type="number"
                              value={bookingForm.token_amount}
                              onChange={(e) => setBookingForm({ ...bookingForm, token_amount: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <button
                          onClick={handleConfirmBooking}
                          className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-xs font-mono font-bold"
                        >
                          Confirm Booking Record
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 5: COMMISSION LEDGER */}
                  {detailTab === 'commission' && (
                    <div className="space-y-5">
                      {activeDealDetail.commission ? (
                        <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                          <div className="flex justify-between items-center border-b border-[#EAE7E1] pb-2">
                            <span className="text-xs font-mono font-bold text-[#1A1A1A]">
                              Invoice Ref: {activeDealDetail.commission.invoice_reference || 'LEDGER-ACTIVE'}
                            </span>
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
                              Status: {activeDealDetail.commission.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                            <div>
                              <span className="text-[#6B6B6B] block">Gross Commission</span>
                              <strong className="text-[16px] text-emerald-800">{formatCurrency(activeDealDetail.commission.gross_commission, activeDealDetail.commission.currency)}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Rate %</span>
                              <strong className="text-[16px]">{activeDealDetail.commission.commission_percentage}%</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Transaction Price</span>
                              <strong className="text-[16px]">{formatCurrency(activeDealDetail.commission.transaction_price, activeDealDetail.commission.currency)}</strong>
                            </div>
                          </div>
                          {activeDealDetail.commission.commission_splits && (
                            <div className="space-y-1.5 pt-2">
                              <span className="text-[11px] font-mono font-bold text-[#1A1A1A] block">Commission Split Allocation</span>
                              {activeDealDetail.commission.commission_splits.map((split: any, idx: number) => (
                                <div key={idx} className="flex justify-between text-xs font-mono bg-[#FAF7F2] p-2 rounded border border-[#EAE7E1]">
                                  <span>{split.role} ({split.percentage}%)</span>
                                  <strong>{formatCurrency(split.amount, activeDealDetail.commission.currency)}</strong>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs font-mono text-emerald-900">
                          Commission ledger record has not yet been computed for this deal.
                        </div>
                      )}

                      {/* Record Commission Form */}
                      <div className="bg-[#FAF7F2] p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <h4 className="text-xs font-mono font-bold text-[#1A1A1A] uppercase">
                          Calculate / Update Commission Ledger
                        </h4>
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Transaction Price</label>
                            <input
                              type="number"
                              value={commissionForm.transaction_price}
                              onChange={(e) => setCommissionForm({ ...commissionForm, transaction_price: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Commission Rate %</label>
                            <input
                              type="number"
                              step="0.1"
                              value={commissionForm.commission_percentage}
                              onChange={(e) => setCommissionForm({ ...commissionForm, commission_percentage: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Invoice Ref</label>
                            <input
                              type="text"
                              value={commissionForm.invoice_reference}
                              onChange={(e) => setCommissionForm({ ...commissionForm, invoice_reference: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <button
                          onClick={handleRecordCommission}
                          className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-mono font-bold"
                        >
                          Calculate Ledger
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 6: CLOSING & HANDOVER */}
                  {detailTab === 'closing' && (
                    <div className="space-y-5">
                      {activeDealDetail.closing ? (
                        <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                          <div className="flex justify-between items-center border-b border-[#EAE7E1] pb-2">
                            <span className="text-xs font-mono font-bold text-[#1A1A1A]">
                              Land Registry: {activeDealDetail.closing.registration_authority}
                            </span>
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-green-100 text-green-800">
                              Status: {activeDealDetail.closing.status}
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                            <div>
                              <span className="text-[#6B6B6B] block">Reg Number</span>
                              <strong>{activeDealDetail.closing.registration_number || 'N/A'}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Title Deed</span>
                              <strong>{activeDealDetail.closing.title_deed_number || 'N/A'}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Handover Date</span>
                              <strong>{activeDealDetail.closing.handover_date ? new Date(activeDealDetail.closing.handover_date).toLocaleDateString() : 'Pending'}</strong>
                            </div>
                          </div>
                          {activeDealDetail.closing.closing_checklist && (
                            <div className="space-y-1.5 pt-2">
                              <span className="text-[11px] font-mono font-bold text-[#1A1A1A] block">Closing Checklist</span>
                              {activeDealDetail.closing.closing_checklist.map((item: any, idx: number) => (
                                <div key={idx} className="flex items-center gap-2 text-xs font-mono bg-[#FAF7F2] p-2 rounded border border-[#EAE7E1]">
                                  <CheckCircle2 className={`w-4 h-4 ${item.completed ? 'text-emerald-600' : 'text-gray-300'}`} />
                                  <span className={item.completed ? 'line-through text-gray-400' : 'text-[#1A1A1A]'}>{item.item}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="pt-3 border-t border-[#EAE7E1]">
                            <button
                              onClick={handleCompleteClosing}
                              className="px-4 py-2 bg-green-700 hover:bg-green-800 text-white rounded-lg text-xs font-mono font-bold"
                            >
                              Finalize Closing &amp; Mark Deal Won
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="p-4 bg-green-50 border border-green-200 rounded-xl text-xs font-mono text-green-900">
                          Title transfer &amp; closing record has not yet been registered.
                        </div>
                      )}

                      {/* Create Closing Registration Form */}
                      <div className="bg-[#FAF7F2] p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <h4 className="text-xs font-mono font-bold text-[#1A1A1A] uppercase">
                          Register Title Deed &amp; Handover Checklist
                        </h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Registration Authority</label>
                            <input
                              type="text"
                              value={closingForm.registration_authority}
                              onChange={(e) => setClosingForm({ ...closingForm, registration_authority: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Registration Number</label>
                            <input
                              type="text"
                              value={closingForm.registration_number}
                              onChange={(e) => setClosingForm({ ...closingForm, registration_number: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Title Deed Number</label>
                            <input
                              type="text"
                              value={closingForm.title_deed_number}
                              onChange={(e) => setClosingForm({ ...closingForm, title_deed_number: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">Handover Date</label>
                            <input
                              type="date"
                              value={closingForm.handover_date}
                              onChange={(e) => setClosingForm({ ...closingForm, handover_date: e.target.value })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <button
                          onClick={handleCreateClosing}
                          className="px-4 py-2 bg-green-700 hover:bg-green-800 text-white rounded-lg text-xs font-mono font-bold"
                        >
                          Initiate Title Closing
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 7: POST-SALE NPS */}
                  {detailTab === 'post_sale' && (
                    <div className="space-y-5">
                      {activeDealDetail.post_sale ? (
                        <div className="bg-white p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                          <div className="flex justify-between items-center border-b border-[#EAE7E1] pb-2">
                            <span className="text-xs font-mono font-bold text-[#1A1A1A] flex items-center gap-1.5">
                              <Star className="w-4 h-4 text-amber-500 fill-amber-400" />
                              Customer Satisfaction &amp; NPS Signals
                            </span>
                            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-teal-100 text-teal-800">
                              NPS: {activeDealDetail.post_sale.nps_score} / 10
                            </span>
                          </div>
                          <div className="grid grid-cols-3 gap-3 text-xs font-mono">
                            <div>
                              <span className="text-[#6B6B6B] block">CSAT Rating</span>
                              <strong className="text-[15px]">{activeDealDetail.post_sale.customer_satisfaction_score} / 5 Stars</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Referral Given</span>
                              <strong>{activeDealDetail.post_sale.referral_given ? '✅ Yes' : '❌ No'}</strong>
                            </div>
                            <div>
                              <span className="text-[#6B6B6B] block">Days to Close</span>
                              <strong>{activeDealDetail.post_sale.days_to_close || 'N/A'} Days</strong>
                            </div>
                          </div>
                          {activeDealDetail.post_sale.feedback_text && (
                            <div className="p-3 bg-[#FAF7F2] rounded-lg border border-[#EAE7E1] text-xs italic font-serif">
                              "{activeDealDetail.post_sale.feedback_text}"
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="p-4 bg-teal-50 border border-teal-200 rounded-xl text-xs font-mono text-teal-900">
                          Post-sale feedback and NPS signals not yet recorded.
                        </div>
                      )}

                      {/* Record Post Sale Form */}
                      <div className="bg-[#FAF7F2] p-4 rounded-xl border border-[#D4D0C8] space-y-3">
                        <h4 className="text-xs font-mono font-bold text-[#1A1A1A] uppercase">
                          Record Post-Sale NPS &amp; Learning Signals
                        </h4>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">CSAT Score (1 to 5)</label>
                            <input
                              type="number"
                              min="1"
                              max="5"
                              value={postSaleForm.customer_satisfaction_score}
                              onChange={(e) => setPostSaleForm({ ...postSaleForm, customer_satisfaction_score: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-mono text-[#6B6B6B] block">NPS Score (1 to 10)</label>
                            <input
                              type="number"
                              min="1"
                              max="10"
                              value={postSaleForm.nps_score}
                              onChange={(e) => setPostSaleForm({ ...postSaleForm, nps_score: Number(e.target.value) })}
                              className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                            />
                          </div>
                        </div>
                        <div>
                          <label className="text-[10px] font-mono text-[#6B6B6B] block">Buyer Feedback Quote</label>
                          <textarea
                            rows={2}
                            value={postSaleForm.feedback_text}
                            onChange={(e) => setPostSaleForm({ ...postSaleForm, feedback_text: e.target.value })}
                            className="w-full bg-white border border-[#D4D0C8] rounded px-2.5 py-1.5 text-xs font-mono"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id="referralCheck"
                            checked={postSaleForm.referral_given}
                            onChange={(e) => setPostSaleForm({ ...postSaleForm, referral_given: e.target.checked })}
                            className="rounded border-[#D4D0C8]"
                          />
                          <label htmlFor="referralCheck" className="text-xs font-mono text-[#1A1A1A]">
                            Customer consented to provide new referrals
                          </label>
                        </div>
                        <button
                          onClick={handleRecordPostSale}
                          className="px-4 py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-lg text-xs font-mono font-bold"
                        >
                          Record Feedback Signals
                        </button>
                      </div>
                    </div>
                  )}

                  {/* TAB 8: AUDIT TRAIL */}
                  {detailTab === 'audit' && (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#1A1A1A]">
                        <Shield className="w-4 h-4 text-emerald-600" />
                        <span>Immutable Commercial Audit Trail</span>
                      </div>
                      <div className="space-y-2">
                        {activeDealDetail.commercial_audit && activeDealDetail.commercial_audit.length > 0 ? (
                          activeDealDetail.commercial_audit.map((aud: any) => (
                            <div key={aud.id} className="p-3 bg-white rounded-xl border border-[#D4D0C8] text-xs font-mono space-y-1">
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="font-bold text-[#1A1A1A]">{aud.event_type}</span>
                                <span className="text-[#6B6B6B]">{new Date(aud.created_at).toLocaleString()}</span>
                              </div>
                              <p className="text-[#4A4A4A]">{aud.change_summary || 'Commercial mutation logged.'}</p>
                            </div>
                          ))
                        ) : (
                          <div className="p-4 bg-white rounded-xl border border-[#D4D0C8] text-xs font-mono text-[#6B6B6B] text-center">
                            Audit events for this deal are written to transactional outbox and commercial audit log.
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Confirm Stage Advance Modal */}
      <ConfirmDialog
        isOpen={advanceModal.isOpen}
        title={`Advance Deal to ${advanceModal.targetStage?.toUpperCase()}`}
        description={`Are you sure you want to transition this deal to the "${advanceModal.targetStage}" stage? Please provide operational justification for the audit trail.`}
        confirmLabel="Advance Stage"
        requireReason={true}
        reasonPlaceholder={`e.g. Buyer submitted offer / approved term sheet for ${advanceModal.targetStage}`}
        isLoading={advanceModal.isSubmitting}
        onConfirm={handleConfirmAdvance}
        onCancel={() => setAdvanceModal(prev => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
}
