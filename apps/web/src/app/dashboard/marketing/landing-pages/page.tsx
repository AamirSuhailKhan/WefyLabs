'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  FileText, Plus, RefreshCw, ExternalLink, Globe,
  CheckCircle2, Clock, ChevronRight
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import {
  Button, Card, CardHeader, CardTitle, CardContent,
  PageHeader, KpiCard, StatusBadge, EmptyState, Skeleton
} from '@/components/ui';

const API = '/api/v1/marketing';

interface LandingPageItem {
  id: string;
  slug: string;
  title: string;
  project_id: string;
  campaign_id?: string;
  is_published: boolean;
  published_at?: string;
  views_count?: number;
  leads_count?: number;
}

export default function MarketingLandingPagesPage() {
  const [pages, setPages] = useState<LandingPageItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadPages = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/landing-pages`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setPages(data.items || data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPages();
  }, []);

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="LANDING PAGES & TRACKING"
          description="High-converting project microsites, lead capture funnels, and UTM-attributed destination URLs."
          breadcrumbs={[
            { label: 'Marketing', href: '/dashboard/marketing' },
            { label: 'Landing Pages' },
          ]}
          actions={
            <Button
              variant="secondary"
              size="sm"
              onClick={loadPages}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          }
        />

        {/* Landing Pages List */}
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
          ) : pages.length > 0 ? (
            pages.map((p) => (
              <div
                key={p.id}
                className="p-5 rounded-2xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                  <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                    <Globe className="w-5 h-5 text-[#2C4BFB]" />
                  </div>
                  <div className="min-w-0">
                    <span className="font-mono text-sm font-bold text-[#1A1A1A]">
                      {p.title || p.slug}
                    </span>
                    <div className="flex items-center gap-2 text-xs text-[#6B6B6B] mt-1 font-sans">
                      <span className="font-mono text-[#0F766E]">/{p.slug}</span>
                      <span>•</span>
                      <span>Project: {p.project_id}</span>
                      {p.views_count !== undefined && (
                        <>
                          <span>•</span>
                          <span>{p.views_count} views</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                  <StatusBadge
                    status={p.is_published ? 'published' : 'draft'}
                    label={p.is_published ? 'Published' : 'Draft'}
                  />
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon={FileText}
              title="No landing pages created yet"
              description="Project landing pages provide fast mobile-responsive microsites connected directly to your WefyLabs lead capture pipeline."
              primaryAction={{
                label: 'View Active Campaigns',
                onClick: () => {
                  window.location.href = '/dashboard/marketing/campaigns';
                },
                icon: FileText,
              }}
            />
          )}
        </div>
      </main>
    </div>
  );
}
