'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Megaphone, Plus, RefreshCw, ChevronRight, AlertCircle,
  Clock, DollarSign, Target, CheckCircle2, X
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import {
  Button, Card, CardHeader, CardTitle, CardContent,
  PageHeader, KpiCard, StatusBadge, EmptyState, Skeleton
} from '@/components/ui';

const API = '/api/v1/marketing';

interface Campaign {
  id: string;
  campaign_code: string;
  name: string;
  objective: string;
  status: string;
  approval_status: string;
  budget_planned?: string;
  budget_spent?: string;
  currency?: string;
  created_at: string;
}

export default function MarketingCampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: '',
    objective: 'LEAD_GENERATION',
    budget_planned: '50000',
    currency: 'INR',
    description: '',
  });

  const loadCampaigns = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/campaigns`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data.items || data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCampaigns();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) return;

    setIsSubmitting(true);
    setCreateError(null);
    try {
      const res = await fetch(`${API}/campaigns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          name: form.name.trim(),
          objective: form.objective,
          budget_planned: Number(form.budget_planned),
          currency: form.currency,
          description: form.description.trim(),
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to create campaign');
      }

      setIsCreateOpen(false);
      setForm({
        name: '',
        objective: 'LEAD_GENERATION',
        budget_planned: '50000',
        currency: 'INR',
        description: '',
      });
      loadCampaigns();
    } catch (err: any) {
      setCreateError(err?.message || 'Error creating campaign');
    } finally {
      setIsSubmitting(false);
    }
  };

  const filtered = campaigns.filter((c) => {
    if (filter === 'all') return true;
    return c.status?.toLowerCase() === filter.toLowerCase();
  });

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="CAMPAIGN MANAGER"
          description="Demand generation campaigns with strict state machine validation, human approval gates, and multi-touch ROI attribution."
          breadcrumbs={[
            { label: 'Marketing', href: '/dashboard/marketing' },
            { label: 'Campaigns' },
          ]}
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={loadCampaigns}
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
              >
                Refresh
              </Button>
              <Button
                variant="lime"
                size="sm"
                onClick={() => setIsCreateOpen(true)}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                New Campaign
              </Button>
            </div>
          }
        />

        {/* Filter Chips */}
        <div className="flex items-center gap-1.5 p-1 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl w-fit flex-wrap">
          {['all', 'draft', 'in_review', 'approved', 'active', 'completed'].map((st) => (
            <button
              key={st}
              onClick={() => setFilter(st)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono uppercase transition-all ${
                filter === st
                  ? 'bg-[#1A1A1A] text-white shadow-xs'
                  : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Campaign List */}
        <div className="space-y-3">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-20 bg-white border border-[#D4D0C8] rounded-2xl p-4 flex items-center justify-between animate-pulse"
              >
                <div className="space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
                <Skeleton className="h-6 w-20 rounded-full" />
              </div>
            ))
          ) : filtered.length > 0 ? (
            filtered.map((c) => (
              <div
                key={c.id}
                className="p-4 sm:p-5 rounded-2xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                  <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                    <Megaphone className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-bold text-[#1A1A1A]">
                        {c.name}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#FAF7F2] border border-[#D4D0C8] text-[#6B6B6B]">
                        {c.campaign_code}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[#6B6B6B] mt-1 font-sans flex-wrap">
                      <span className="capitalize">{c.objective?.replace(/_/g, ' ')}</span>
                      <span>•</span>
                      <span>Budget: {c.currency || 'INR'} {Number(c.budget_planned || 0).toLocaleString()}</span>
                      {c.budget_spent && (
                        <>
                          <span>•</span>
                          <span>Spent: {c.currency || 'INR'} {Number(c.budget_spent).toLocaleString()}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                  <StatusBadge status={c.status} />
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon={Megaphone}
              title={filter === 'all' ? 'No campaigns created yet' : `No ${filter} campaigns`}
              description="Define target audiences, set financial budgets with Decimal precision, and attach canonical inventory to launch demand generation."
              primaryAction={{
                label: 'Create Campaign',
                onClick: () => setIsCreateOpen(true),
                icon: Plus,
              }}
            />
          )}
        </div>

        {/* Create Campaign Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
              className="fixed inset-0 bg-[#1A1A1A]/40 backdrop-blur-xs"
              onClick={() => !isSubmitting && setIsCreateOpen(false)}
            />
            <div className="relative w-full max-w-lg bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 shadow-xl z-10 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#E5E1DA]">
                <h3 className="text-base font-bold font-mono text-[#1A1A1A]">
                  New Marketing Campaign
                </h3>
                <button
                  onClick={() => setIsCreateOpen(false)}
                  disabled={isSubmitting}
                  className="p-1.5 rounded-lg text-[#6B6B6B] hover:text-[#1A1A1A]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {createError && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
                  {createError}
                </div>
              )}

              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Campaign Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g. Palm Heights Q4 Digital Showcase"
                    className="w-full text-xs font-sans p-2.5 rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] focus:outline-none focus:ring-2 focus:ring-[#1A1A1A]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                      Objective
                    </label>
                    <select
                      value={form.objective}
                      onChange={(e) => setForm({ ...form, objective: e.target.value })}
                      className="w-full text-xs font-sans p-2.5 rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] focus:outline-none focus:ring-2 focus:ring-[#1A1A1A]"
                    >
                      <option value="LEAD_GENERATION">Lead Generation</option>
                      <option value="PROJECT_LAUNCH">Project Launch</option>
                      <option value="INVENTORY_SALES">Inventory Sales</option>
                      <option value="REMARKETING">Remarketing</option>
                      <option value="SITE_VISIT">Site Visit Drive</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                      Planned Budget
                    </label>
                    <input
                      type="number"
                      required
                      min={1000}
                      value={form.budget_planned}
                      onChange={(e) => setForm({ ...form, budget_planned: e.target.value })}
                      className="w-full text-xs font-sans p-2.5 rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] focus:outline-none focus:ring-2 focus:ring-[#1A1A1A]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Description & Target Audience
                  </label>
                  <textarea
                    rows={3}
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    placeholder="Campaign goals, ad channels (Meta/Google), target demographic..."
                    className="w-full text-xs font-sans p-2.5 rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] focus:outline-none focus:ring-2 focus:ring-[#1A1A1A] resize-none"
                  />
                </div>

                <div className="pt-3 border-t border-[#E5E1DA] flex items-center justify-end gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    disabled={isSubmitting}
                    onClick={() => setIsCreateOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="lime"
                    size="sm"
                    isLoading={isSubmitting}
                    loadingText="Creating..."
                  >
                    Create Campaign
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
