'use client';

import React, { useState, useEffect } from 'react';
import { DealRiskCard } from '@/components/deals/DealRiskCard';
import { Briefcase, Plus, Trash2, X, RefreshCw } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { formatCurrencyINR } from '@/lib/utils';
import { api } from '@/lib/api-client';

export default function DealsPage() {
  const [selectedStageFilter, setSelectedStageFilter] = useState<string>('all');
  const [deals, setDeals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    deal_name: '',
    agreed_price: 28500000,
    commission_percentage: 2.0,
    current_stage: 'booking',
    lead_name: 'Rahul Sharma',
    property_title: 'Luxury 3BHK Penthouse in Marina Gate'
  });

  const stages = [
    'lead', 'qualified', 'property_visit', 'offer', 'negotiation',
    'booking', 'documents', 'loan', 'legal', 'registration',
    'closing', 'commission', 'after_sales'
  ];

  const fetchDeals = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.deals.list({
        stage: selectedStageFilter !== 'all' ? selectedStageFilter : undefined
      });
      setDeals(data.items || data.data || data || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load deals');
      setDeals([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDeals();
  }, [selectedStageFilter]);

  const handleCreateDeal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.deal_name.trim()) {
      setFormError('Deal name is required');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.deals.create({
        deal_name: formData.deal_name.trim(),
        agreed_price: Number(formData.agreed_price),
        commission_percentage: Number(formData.commission_percentage),
        current_stage: formData.current_stage,
        currency: 'INR',
        lead_name: formData.lead_name.trim() || undefined,
        property_title: formData.property_title.trim() || undefined
      });
      setIsModalOpen(false);
      setFormData({
        deal_name: '',
        agreed_price: 28500000,
        commission_percentage: 2.0,
        current_stage: 'booking',
        lead_name: 'Rahul Sharma',
        property_title: 'Luxury 3BHK Penthouse in Marina Gate'
      });
      fetchDeals();
    } catch (err: any) {
      setFormError(err?.message || 'Failed to create deal');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdvanceStage = async (dealId: string, nextStage: string) => {
    try {
      await api.deals.advanceStage(dealId, nextStage);
      setDeals(prev => prev.map(d => d.id === dealId ? { ...d, current_stage: nextStage } : d));
    } catch (err: any) {
      alert(err?.message || 'Failed to update deal stage');
    }
  };

  const handleDeleteDeal = async (dealId: string, dealName: string) => {
    if (!confirm(`Are you sure you want to delete transaction "${dealName}"?`)) return;
    try {
      await api.deals.delete(dealId);
      setDeals(prev => prev.filter(d => d.id !== dealId));
    } catch (err: any) {
      alert(err?.message || 'Failed to delete deal');
    }
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
          <div>
            <h1
              className="text-[26px] sm:text-[28px] font-bold text-[#1A1A1A] tracking-tight leading-tight"
              style={{ fontFamily: 'JetBrains Mono, monospace' }}
            >
              TRANSACTION LIFECYCLE &amp; AI RISK
            </h1>
            <p className="text-[13px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
              Manage 13-stage customer journey, payment milestones, legal checklists &amp; AI Deal Risk closing probability.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchDeals}
              disabled={isLoading}
              title="Refresh transactions"
              className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[#0D9488]' : ''}`} />
            </button>
            <button
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[11px] font-bold transition-all shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>+ New Transaction Deal</span>
            </button>
          </div>
        </div>

        {/* 13-Stage Journey Stepper */}
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-3 rounded-2xl overflow-x-auto shadow-xs">
          <div className="flex items-center gap-2 min-w-max">
            <button
              onClick={() => setSelectedStageFilter('all')}
              className={`px-3 py-1.5 text-[11px] font-mono font-bold rounded-xl uppercase transition-all ${
                selectedStageFilter === 'all'
                  ? 'bg-[#1A1A1A] text-white shadow-xs'
                  : 'bg-white text-gray-700 border border-[#D4D0C8] hover:bg-gray-100'
              }`}
            >
              All ({deals.length})
            </button>
            {stages.map((stg, idx) => (
              <button
                key={stg}
                onClick={() => setSelectedStageFilter(stg)}
                className={`px-3 py-1.5 text-[11px] font-mono font-bold rounded-xl capitalize transition-all flex items-center gap-1.5 ${
                  selectedStageFilter === stg
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'bg-white text-gray-700 border border-[#D4D0C8] hover:bg-gray-100'
                }`}
              >
                <span className="w-4 h-4 rounded-full bg-[#E8F5A8] text-[#1A1A1A] flex items-center justify-center text-[10px] font-extrabold">
                  {idx + 1}
                </span>
                <span>{stg.replace('_', ' ')}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Deal Pipeline Grid */}
        {isLoading ? (
          <div className="text-center py-20 text-sm text-[#6B6B6B]">Loading transaction deals...</div>
        ) : error ? (
          <div className="text-center py-20 text-sm text-red-500">{error}</div>
        ) : deals.length === 0 ? (
          <div className="text-center py-20 bg-white border border-[#D4D0C8] rounded-2xl p-8">
            <Briefcase className="w-12 h-12 text-[#9CA3AF] mx-auto mb-3" />
            <h3 className="text-sm font-bold text-[#1A1A1A] mb-1 font-mono">No transaction deals in this stage</h3>
            <p className="text-xs text-[#6B6B6B] max-w-sm mx-auto mb-4 font-sans">
              Create a new transaction deal to track contract milestones, commission and AI deal risk.
            </p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-xs font-bold"
            >
              + Create Transaction Deal
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {deals.map((deal) => (
              <div key={deal.id} className="bg-white border border-[#D4D0C8] rounded-2xl p-5 shadow-xs space-y-4 hover:border-[#B0ACA4] transition-all">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase bg-indigo-100 text-indigo-900 px-2 py-0.5 rounded font-bold">
                      Stage: {deal.current_stage ? deal.current_stage.replace('_', ' ') : 'Booking'}
                    </span>
                    <h3 className="text-base font-bold font-mono text-[#1A1A1A] mt-1.5 leading-tight">{deal.deal_name}</h3>
                    <div className="text-xs text-gray-500 font-sans mt-0.5">
                      Client: <span className="font-semibold text-gray-800">{deal.lead_name}</span> • Property: <span className="font-semibold text-gray-800">{deal.property_title}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleDeleteDeal(deal.id, deal.deal_name)}
                      title="Delete Deal"
                      className="p-1.5 text-gray-400 hover:text-red-600 rounded-md transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Financial Summary */}
                <div className="grid grid-cols-2 gap-3 bg-[#FAF7F2] p-3 rounded-xl border border-[#F0EDE8] font-mono">
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase block">Agreed Price</span>
                    <span className="text-sm font-bold text-[#1A1A1A]">{formatCurrencyINR(deal.agreed_price || 0)}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-500 uppercase block">Est. Commission ({deal.commission_percentage || 2}%)</span>
                    <span className="text-sm font-bold text-[#0D9488]">{formatCurrencyINR(deal.estimated_commission_amount || 0)}</span>
                  </div>
                </div>

                {/* AI Risk Card Component */}
                <DealRiskCard
                  dealName={deal.deal_name}
                  stage={deal.current_stage || 'booking'}
                  riskLevel={deal.risk_level === 'critical_stalled' || deal.risk_level === 'high_risk' || deal.risk_level === 'medium' ? deal.risk_level : 'low'}
                  closingProbability={deal.closing_probability_pct || 85}
                  missingDocs={deal.missing_documents || []}
                  recommendedAction={deal.recommended_action || 'Proceed with transaction milestones.'}
                />

                {/* Stage Progression Selector */}
                <div className="pt-2 border-t border-[#F0EDE8] flex items-center justify-between">
                  <span className="text-xs text-gray-500 font-sans">Advance Stage:</span>
                  <select
                    value={deal.current_stage || 'booking'}
                    onChange={(e) => handleAdvanceStage(deal.id, e.target.value)}
                    className="text-xs bg-[#FAF7F2] border border-[#D4D0C8] rounded-md px-2.5 py-1 text-[#1A1A1A] font-bold font-mono focus:outline-none cursor-pointer"
                  >
                    {stages.map((s) => (
                      <option key={s} value={s}>{s.replace('_', ' ').toUpperCase()}</option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New Deal Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
              <h2 className="text-base font-bold font-mono text-[#1A1A1A]">CREATE TRANSACTION DEAL</h2>
              <button onClick={() => setIsModalOpen(false)} className="p-1 hover:bg-gray-100 rounded-md">
                <X className="w-4 h-4 text-gray-500" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg font-sans">
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateDeal} className="space-y-3.5 font-sans">
              <div>
                <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                  Deal Name *
                </label>
                <input
                  type="text"
                  required
                  value={formData.deal_name}
                  onChange={(e) => setFormData({ ...formData, deal_name: e.target.value })}
                  placeholder="e.g. Marina Gate Penthouse Purchase"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none focus:border-[#1A1A1A]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Agreed Price (INR ₹) *
                  </label>
                  <input
                    type="number"
                    required
                    min={100000}
                    value={formData.agreed_price}
                    onChange={(e) => setFormData({ ...formData, agreed_price: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Commission % *
                  </label>
                  <input
                    type="number"
                    required
                    step="0.1"
                    min={0.1}
                    max={20}
                    value={formData.commission_percentage}
                    onChange={(e) => setFormData({ ...formData, commission_percentage: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                  Starting Stage
                </label>
                <select
                  value={formData.current_stage}
                  onChange={(e) => setFormData({ ...formData, current_stage: e.target.value })}
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none font-mono"
                >
                  {stages.map((s) => (
                    <option key={s} value={s}>{s.replace('_', ' ').toUpperCase()}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Buyer / Lead Name
                  </label>
                  <input
                    type="text"
                    value={formData.lead_name}
                    onChange={(e) => setFormData({ ...formData, lead_name: e.target.value })}
                    placeholder="e.g. Rahul Sharma"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-[#4A4A4A] uppercase mb-1">
                    Property Title
                  </label>
                  <input
                    type="text"
                    value={formData.property_title}
                    onChange={(e) => setFormData({ ...formData, property_title: e.target.value })}
                    placeholder="e.g. Marina Gate 3BHK"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-lg focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-4 border-t border-[#F0EDE8]">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2 text-xs font-bold bg-[#1A1A1A] text-white rounded-lg hover:bg-black disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Deal'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
