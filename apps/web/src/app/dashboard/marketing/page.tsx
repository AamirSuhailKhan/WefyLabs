'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Megaphone, Building2, FileText, Link2, Rocket, BarChart3,
  Plus, Target, CheckCircle2, AlertCircle, Clock,
  ChevronRight, ArrowUpRight, Zap, Globe, DollarSign, Users,
  Activity, RefreshCw
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import {
  Button, Card, CardHeader, CardTitle, CardContent,
  PageHeader, KpiCard, StatusBadge, EmptyState, Skeleton
} from '@/components/ui';

/* ─── Types ───────────────────────────────────────────────────────────────── */
type Campaign = {
  id: string;
  campaign_code: string;
  name: string;
  objective: string;
  status: string;
  project_id?: string;
  approval_status: string;
  budget_planned?: string;
  currency?: string;
};

type Listing = {
  id: string;
  slug: string;
  listing_title?: string;
  status: string;
  is_stale: boolean;
  project_id: string;
  stale_reason?: string;
};

type IntelSummary = {
  pending_approvals: number;
  stale_listings_count: number;
  alert: boolean;
};

/* ─── API helpers ─────────────────────────────────────────────────────────── */
const API = '/api/v1/marketing';
const fetchJSON = async (path: string) => {
  try {
    const res = await fetch(path, { credentials: 'include' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
};

/* ─── Sub-Components ─────────────────────────────────────────────────────── */

function CampaignRow({ campaign }: { campaign: Campaign }) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs gap-3">
      <div className="flex items-center gap-3.5 min-w-0">
        <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] shrink-0 text-[#1A1A1A]">
          <Megaphone className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs font-bold text-[#1A1A1A] truncate">
              {campaign.name}
            </span>
            <span className="font-mono text-[10px] text-[#6B6B6B] bg-[#F5F0EB] px-2 py-0.5 rounded border border-[#D4D0C8]">
              {campaign.campaign_code}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#6B6B6B] mt-0.5 font-sans">
            <span className="capitalize">{campaign.objective?.replace(/_/g, ' ')}</span>
            {campaign.budget_planned && (
              <>
                <span>•</span>
                <span className="font-mono font-medium text-[#1A1A1A]">
                  {campaign.currency || 'INR'} {Number(campaign.budget_planned).toLocaleString()}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <StatusBadge status={campaign.status} />
        <Link
          href={`/dashboard/marketing/campaigns`}
          className="p-1.5 text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8] rounded-lg transition-colors"
          title="View Campaign"
        >
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}

function ListingRow({ listing }: { listing: Listing }) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs gap-3">
      <div className="flex items-center gap-3.5 min-w-0">
        <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] shrink-0 text-[#1A1A1A]">
          <Building2 className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <p className="font-mono text-xs font-bold text-[#1A1A1A] truncate">
            {listing.listing_title || listing.slug}
          </p>
          <p className="text-xs text-[#6B6B6B] font-mono mt-0.5">
            Slug: /{listing.slug}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {listing.is_stale ? (
          <StatusBadge status="stale" label="Stale Data" />
        ) : (
          <StatusBadge status={listing.status} />
        )}
        <Link
          href={`/dashboard/marketing/listings`}
          className="p-1.5 text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8] rounded-lg transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}

/* ─── Main Page ───────────────────────────────────────────────────────────── */

export default function MarketingDashboardPage() {
  const [activeTab, setActiveTab] = useState<'campaigns' | 'listings'>('campaigns');
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [listings, setListings] = useState<Listing[]>([]);
  const [intel, setIntel] = useState<IntelSummary>({
    pending_approvals: 0,
    stale_listings_count: 0,
    alert: false,
  });
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [cRes, lRes, aRes, sRes] = await Promise.all([
        fetchJSON(`${API}/campaigns`),
        fetchJSON(`${API}/listings`),
        fetchJSON(`${API}/intelligence/approvals`),
        fetchJSON(`${API}/intelligence/stale-listings`),
      ]);

      if (cRes?.items) setCampaigns(cRes.items);
      else if (Array.isArray(cRes)) setCampaigns(cRes);

      if (lRes?.items) setListings(lRes.items);
      else if (Array.isArray(lRes)) setListings(lRes);

      setIntel({
        pending_approvals: aRes?.pending_approvals_count ?? 0,
        stale_listings_count: sRes?.stale_listings_count ?? 0,
        alert: Boolean(sRes?.alert),
      });
    } catch (e) {
      console.error('Marketing data fetch error', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const activeCampaigns = campaigns.filter((c) => c.status === 'active').length;
  const draftCampaigns = campaigns.filter((c) => c.status === 'draft').length;
  const staleCount = intel.stale_listings_count;
  const pendingApprovals = intel.pending_approvals;

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Unified Page Header with single primary action */}
        <PageHeader
          title="MARKETING OS"
          description="Demand generation, inventory-grounded listing distribution, launch readiness verification, and end-to-end UTM attribution."
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={loadData}
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
              >
                Refresh
              </Button>
              <Link href="/dashboard/marketing/campaigns">
                <Button variant="lime" size="sm" leftIcon={<Plus className="w-3.5 h-3.5" />}>
                  New Campaign
                </Button>
              </Link>
            </div>
          }
        />

        {/* Operational Attention Alerts (Only if relevant) */}
        {(staleCount > 0 || pendingApprovals > 0) && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {staleCount > 0 && (
              <div className="p-3.5 rounded-xl bg-[#FEF2F2] border border-[#FECACA] flex items-center justify-between text-[#991B1B]">
                <div className="flex items-center gap-2.5 text-xs font-semibold">
                  <AlertCircle className="w-4 h-4 shrink-0 text-[#EF4444]" />
                  <span>{staleCount} listing{staleCount > 1 ? 's' : ''} out of sync with Supply OS</span>
                </div>
                <Link
                  href="/dashboard/marketing/listings"
                  className="text-xs font-bold underline hover:text-red-900"
                >
                  Review Listings →
                </Link>
              </div>
            )}
            {pendingApprovals > 0 && (
              <div className="p-3.5 rounded-xl bg-[#FFFBEB] border border-[#FDE68A] flex items-center justify-between text-[#92400E]">
                <div className="flex items-center gap-2.5 text-xs font-semibold">
                  <Clock className="w-4 h-4 shrink-0 text-[#F59E0B]" />
                  <span>{pendingApprovals} campaign{pendingApprovals > 1 ? 's' : ''} awaiting human approval</span>
                </div>
                <Link
                  href="/dashboard/marketing/campaigns"
                  className="text-xs font-bold underline hover:text-amber-900"
                >
                  Approve →
                </Link>
              </div>
            )}
          </div>
        )}

        {/* KPI Metrics Ribbon */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Active Campaigns"
            value={loading ? undefined : activeCampaigns}
            sublabel={`${draftCampaigns} in preparation`}
            icon={Megaphone}
            variant="lime"
            isLoading={loading}
          />
          <KpiCard
            label="Published Listings"
            value={loading ? undefined : listings.filter((l) => l.status === 'published').length}
            sublabel={staleCount > 0 ? `${staleCount} need sync` : 'All inventory synchronized'}
            icon={Building2}
            variant={staleCount > 0 ? 'warning' : 'default'}
            isLoading={loading}
          />
          <KpiCard
            label="Pending Approvals"
            value={loading ? undefined : pendingApprovals}
            sublabel="Human oversight required"
            icon={Clock}
            variant={pendingApprovals > 0 ? 'warning' : 'default'}
            isLoading={loading}
          />
          <KpiCard
            label="Total Campaigns"
            value={loading ? undefined : campaigns.length}
            sublabel="Demand pipelines tracked"
            icon={Globe}
            variant="default"
            isLoading={loading}
          />
        </div>

        {/* 2-Column Main Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Column: Tabbed Lists */}
          <div className="lg:col-span-2 space-y-4">
            {/* View Switcher Tabs */}
            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] w-fit shadow-2xs">
              <button
                onClick={() => setActiveTab('campaigns')}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  activeTab === 'campaigns'
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                <Megaphone className="w-3.5 h-3.5" />
                <span>Campaigns ({campaigns.length})</span>
              </button>
              <button
                onClick={() => setActiveTab('listings')}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  activeTab === 'listings'
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                <Building2 className="w-3.5 h-3.5" />
                <span>Listings ({listings.length})</span>
              </button>
            </div>

            {/* List Body */}
            <div className="space-y-2.5">
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-16 rounded-xl bg-white border border-[#D4D0C8] p-4 flex items-center justify-between animate-pulse"
                  >
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-6 w-20 rounded-full" />
                  </div>
                ))
              ) : activeTab === 'campaigns' ? (
                campaigns.length > 0 ? (
                  campaigns.map((c) => <CampaignRow key={c.id} campaign={c} />)
                ) : (
                  <EmptyState
                    icon={Megaphone}
                    title="No marketing campaigns yet"
                    description="Create demand generation campaigns grounded in your supply inventory to track impressions, clicks, and lead acquisitions."
                    primaryAction={{
                      label: 'Create Campaign',
                      onClick: () => {
                        window.location.href = '/dashboard/marketing/campaigns';
                      },
                      icon: Plus,
                    }}
                  />
                )
              ) : listings.length > 0 ? (
                listings.map((l) => <ListingRow key={l.id} listing={l} />)
              ) : (
                <EmptyState
                  icon={Building2}
                  title="No property listings published"
                  description="Use the Listing Studio to generate grounded, syndicate-ready descriptions from real Supply OS inventory units."
                  primaryAction={{
                    label: 'Open Listing Studio',
                    onClick: () => {
                      window.location.href = '/dashboard/marketing/listings';
                    },
                    icon: Plus,
                  }}
                />
              )}
            </div>
          </div>

          {/* Right Column: Quick Workspace Nav & Funnel Telemetry */}
          <div className="space-y-5">
            {/* Workspaces Sub-navigation */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-[#D97706]" />
                  <CardTitle className="text-sm">Marketing Workspaces</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {[
                  {
                    label: 'Campaign Manager',
                    desc: 'Lifecycle states & budgets',
                    href: '/dashboard/marketing/campaigns',
                    icon: Megaphone,
                  },
                  {
                    label: 'Listing Studio',
                    desc: 'Syndication & AI descriptions',
                    href: '/dashboard/marketing/listings',
                    icon: Building2,
                  },
                  {
                    label: 'Project Launches',
                    desc: '4-gate launch readiness',
                    href: '/dashboard/marketing/launches',
                    icon: Rocket,
                  },
                  {
                    label: 'Landing Pages',
                    desc: 'Branded lead capture pages',
                    href: '/dashboard/marketing/landing-pages',
                    icon: FileText,
                  },
                ].map((ws) => (
                  <Link
                    key={ws.label}
                    href={ws.href}
                    className="flex items-center justify-between p-3 rounded-xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] group-hover:bg-[#E8F5A8] transition-colors">
                        <ws.icon className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-[#1A1A1A] font-mono">{ws.label}</p>
                        <p className="text-[11px] text-[#6B6B6B] font-sans">{ws.desc}</p>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[#A8A29E] group-hover:text-[#1A1A1A] transition-colors" />
                  </Link>
                ))}
              </CardContent>
            </Card>

            {/* Demand-to-Revenue Attribution Map */}
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-[#2C4BFB]" />
                  <CardTitle className="text-sm">Attribution Pipeline</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {[
                  { label: 'Impressions & Clicks', desc: 'Campaign tracking links & UTM' },
                  { label: 'Universal Intake', desc: 'Direct webhook & page capture' },
                  { label: 'AI Lead Qualification', desc: 'Deterministic score & propensity' },
                  { label: 'Appointments & Visits', desc: 'Calendar scheduling' },
                  { label: 'Unit Reservations', desc: 'Supply OS distributed lock' },
                  { label: 'Closing & Commission', desc: 'Deal OS revenue attribution' },
                ].map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-[#FAF7F2] border border-[#D4D0C8] text-[10px] font-mono font-bold flex items-center justify-center text-[#1A1A1A] shrink-0 mt-0.5">
                      {idx + 1}
                    </span>
                    <div>
                      <p className="text-xs font-semibold text-[#1A1A1A]">{step.label}</p>
                      <p className="text-[10px] text-[#6B6B6B] font-mono">{step.desc}</p>
                    </div>
                  </div>
                ))}

                <p className="text-[10px] text-[#8C877D] font-mono pt-3 border-t border-[#E5E1DA]">
                  Mathematical ROI calculated only when verified spend and real closed revenue exist.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
