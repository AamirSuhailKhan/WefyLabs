'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Building2, Plus, RefreshCw, AlertCircle, CheckCircle2,
  ExternalLink, Sparkles, Clock, ChevronRight
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import {
  Button, Card, CardHeader, CardTitle, CardContent,
  PageHeader, KpiCard, StatusBadge, EmptyState, Skeleton
} from '@/components/ui';

const API = '/api/v1/marketing';

interface Listing {
  id: string;
  slug: string;
  listing_title?: string;
  status: string;
  is_stale: boolean;
  project_id: string;
  stale_reason?: string;
  canonical_unit_id?: string;
  headline?: string;
  description_copy?: string;
  version: number;
  last_inventory_sync?: string;
}

export default function MarketingListingsPage() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);

  const loadListings = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/listings`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setListings(data.items || data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadListings();
  }, []);

  const publishedCount = listings.filter((l) => l.status === 'published').length;
  const staleCount = listings.filter((l) => l.is_stale).length;

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="LISTING STUDIO"
          description="Marketing publications backed by Supply OS physical inventory records. Automatically flagged as stale upon unit reservation or price mutation."
          breadcrumbs={[
            { label: 'Marketing', href: '/dashboard/marketing' },
            { label: 'Listing Studio' },
          ]}
          actions={
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={loadListings}
                leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
              >
                Refresh
              </Button>
            </div>
          }
        />

        {/* Feature Highlights Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                <Building2 className="w-5 h-5 text-[#2C4BFB]" />
              </div>
              <div>
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">
                  Grounded in Canonical Supply Data
                </h3>
                <p className="text-xs text-[#6B6B6B] mt-1 font-sans leading-relaxed">
                  Listing attributes (carpet area, tower, floor, price per sqft, and possession date) are directly sourced from Supply OS inventory records to prevent false advertising.
                </p>
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                <AlertCircle className="w-5 h-5 text-[#EF4444]" />
              </div>
              <div>
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">
                  Automated Stale State Detection
                </h3>
                <p className="text-xs text-[#6B6B6B] mt-1 font-sans leading-relaxed">
                  When a unit transitions to RESERVED, BOOKED, or SOLD in Deal OS, published syndications are automatically flagged as stale and queued for unpublishing.
                </p>
              </div>
            </div>
          </Card>
        </div>

        {/* Listings Directory */}
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
          ) : listings.length > 0 ? (
            listings.map((listing) => (
              <div
                key={listing.id}
                className="p-5 rounded-2xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                  <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                    <Building2 className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-bold text-[#1A1A1A]">
                        {listing.listing_title || listing.slug}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#FAF7F2] border border-[#D4D0C8] text-[#6B6B6B]">
                        v{listing.version}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[#6B6B6B] mt-1 font-sans flex-wrap">
                      <span>Slug: /{listing.slug}</span>
                      {listing.canonical_unit_id && (
                        <>
                          <span>•</span>
                          <span>Unit ID: {listing.canonical_unit_id.slice(0, 8)}...</span>
                        </>
                      )}
                      {listing.last_inventory_sync && (
                        <>
                          <span>•</span>
                          <span>Synced: {new Date(listing.last_inventory_sync).toLocaleDateString()}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                  {listing.is_stale ? (
                    <StatusBadge status="stale" label="Stale" />
                  ) : (
                    <StatusBadge status={listing.status} />
                  )}
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon={Building2}
              title="No property listings created yet"
              description="Listing Studio syndicates your Supply OS inventory units into public listings, microsites, and marketing campaigns."
              primaryAction={{
                label: 'View Inventory Supply',
                onClick: () => {
                  window.location.href = '/dashboard/inventory';
                },
                icon: Building2,
              }}
            />
          )}
        </div>
      </main>
    </div>
  );
}
