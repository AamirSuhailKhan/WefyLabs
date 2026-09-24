'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Image as ImageIcon, Plus, RefreshCw, FileText, CheckCircle2,
  Clock, Shield, ChevronRight
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import {
  Button, Card, CardHeader, CardTitle, CardContent,
  PageHeader, KpiCard, StatusBadge, EmptyState, Skeleton
} from '@/components/ui';

const API = '/api/v1/marketing';

interface MarketingAsset {
  id: string;
  name: string;
  asset_type: string;
  storage_url: string;
  status: string;
  version: number;
  is_ai_generated: boolean;
  project_id?: string;
  campaign_id?: string;
  created_at: string;
}

export default function MarketingAssetsPage() {
  const [assets, setAssets] = useState<MarketingAsset[]>([]);
  const [loading, setLoading] = useState(true);

  const loadAssets = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/assets`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAssets(data.items || data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssets();
  }, []);

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="MARKETING ASSET LIBRARY"
          description="Approved digital collateral, floor plans, verified brochures, and price sheets. Never silently overwritten — version controlled with audit trail."
          breadcrumbs={[
            { label: 'Marketing', href: '/dashboard/marketing' },
            { label: 'Assets' },
          ]}
          actions={
            <Button
              variant="secondary"
              size="sm"
              onClick={loadAssets}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          }
        />

        {/* Asset Cards Grid */}
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
          ) : assets.length > 0 ? (
            assets.map((asset) => (
              <div
                key={asset.id}
                className="p-5 rounded-2xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                  <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                    <ImageIcon className="w-5 h-5 text-[#2C4BFB]" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-bold text-[#1A1A1A]">
                        {asset.name}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#FAF7F2] border border-[#D4D0C8] text-[#6B6B6B]">
                        v{asset.version}
                      </span>
                      {asset.is_ai_generated && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
                          AI Assisted
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[#6B6B6B] mt-1 font-sans">
                      <span className="capitalize">{asset.asset_type?.replace(/_/g, ' ')}</span>
                      {asset.project_id && (
                        <>
                          <span>•</span>
                          <span>Project: {asset.project_id}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                  <StatusBadge status={asset.status} />
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon={ImageIcon}
              title="No marketing assets uploaded yet"
              description="Upload brochures, project photos, and floor plans to syndicate them across listings and landing pages."
              primaryAction={{
                label: 'View Listing Studio',
                onClick: () => {
                  window.location.href = '/dashboard/marketing/listings';
                },
                icon: ImageIcon,
              }}
            />
          )}
        </div>
      </main>
    </div>
  );
}
