'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api-client';
import {
  ArrowLeft,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  Compass,
  FileCheck,
  Heart,
  Home,
  Layers,
  MapPin,
  Maximize2,
  MessageSquare,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';

interface PropertyDetails {
  id: string;
  name: string;
  description?: string | null;
  type?: string | null;
  category?: string | null;
  bedrooms?: number | null;
  bathrooms?: number | null;
  area_sqft?: number | null;
  price?: number | null;
  currency?: string | null;
  status?: string | null;
  location?: string | null;
  address?: string | null;
  possession_date?: string | null;
  source_verified?: boolean | null;
  amenities?: string[] | null;
  images?: string[] | null;
  furnishing_status?: string | null;
}

function formatPrice(price?: number | null, currency?: string | null): string {
  if (!price) return 'Price on Request';
  const curr = currency || 'INR';
  if (curr === 'INR' || curr === '₹') {
    if (price >= 10_000_000) return `₹${(price / 10_000_000).toFixed(2)} Cr`;
    if (price >= 100_000) return `₹${(price / 100_000).toFixed(1)} L`;
    return `₹${price.toLocaleString('en-IN')}`;
  }
  if (curr === 'AED' || curr === 'د.إ') {
    if (price >= 1_000_000) return `AED ${(price / 1_000_000).toFixed(2)}M`;
    return `AED ${price.toLocaleString('en-AE')}`;
  }
  return `${curr} ${price.toLocaleString()}`;
}

export default function PropertyDetailPage() {
  const params = useParams();
  const org = String(params?.org || '');
  const id = String(params?.id || '');

  const [property, setProperty] = useState<PropertyDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let isMounted = true;
    setLoading(true);
    setError(null);

    api.properties
      .getById(id)
      .then((data: any) => {
        if (isMounted) {
          setProperty(data);
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          setError(err?.message || 'Unable to load property details');
        }
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="flex flex-col items-center space-y-4 max-w-sm text-center">
          <div className="w-12 h-12 border-4 border-violet-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm font-medium text-slate-600">Loading verified property data…</p>
        </div>
      </div>
    );
  }

  if (error || !property) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl p-8 max-w-md w-full text-center shadow-xl border border-slate-100 space-y-4">
          <div className="w-16 h-16 bg-red-50 text-red-500 rounded-2xl flex items-center justify-center mx-auto">
            <Building2 className="w-8 h-8" />
          </div>
          <h2 className="text-lg font-bold text-slate-900">Property Not Found</h2>
          <p className="text-xs text-slate-500">
            {error || 'This property listing may be unlisted or no longer available.'}
          </p>
          <Link
            href={`/portal/${org}/chat`}
            className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-violet-600 text-white text-xs font-semibold hover:bg-violet-700 transition"
          >
            <ArrowLeft className="w-4 h-4" /> Return to Chat
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      {/* Top Header */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link
            href={`/portal/${org}/chat`}
            className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-slate-900 transition"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Advisor
          </Link>
          <div className="flex items-center gap-2">
            <Link
              href={`/portal/${org}/chat`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-violet-50 hover:bg-violet-100 text-violet-700 text-xs font-semibold border border-violet-200 transition"
            >
              <MessageSquare className="w-3.5 h-3.5" /> Chat about this unit
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 pt-6 space-y-6">
        {/* Hero Visual Card */}
        <div className="relative rounded-3xl overflow-hidden bg-gradient-to-br from-indigo-900 via-violet-900 to-slate-900 text-white min-h-[260px] p-6 sm:p-8 flex flex-col justify-between shadow-lg">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-bold uppercase tracking-wider bg-white/20 backdrop-blur px-3 py-1 rounded-full">
                {property.type || property.category || 'Property'}
              </span>
              {property.source_verified && (
                <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-emerald-500/90 backdrop-blur px-3 py-1 rounded-full text-white">
                  <ShieldCheck className="w-3.5 h-3.5" /> Source Verified
                </span>
              )}
              {property.status && (
                <span className="text-[11px] font-bold capitalize bg-white/10 backdrop-blur px-3 py-1 rounded-full text-slate-200">
                  {property.status}
                </span>
              )}
            </div>
          </div>

          <div className="space-y-2 mt-8">
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight">{property.name}</h1>
            {(property.location || property.address) && (
              <p className="text-xs sm:text-sm text-slate-300 flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-violet-400 flex-shrink-0" />
                {property.address || property.location}
              </p>
            )}
          </div>
        </div>

        {/* Pricing & Key Metrics Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-white p-5 rounded-3xl border border-slate-200/80 shadow-xs">
          <div className="p-3 bg-slate-50/70 rounded-2xl">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Price</span>
            <p className="text-lg sm:text-xl font-black text-violet-700 mt-0.5">
              {formatPrice(property.price, property.currency)}
            </p>
          </div>

          <div className="p-3 bg-slate-50/70 rounded-2xl">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Layout</span>
            <p className="text-sm sm:text-base font-bold text-slate-800 mt-0.5">
              {property.bedrooms ? `${property.bedrooms} BHK` : 'N/A'}
              {property.bathrooms ? ` • ${property.bathrooms} Bath` : ''}
            </p>
          </div>

          <div className="p-3 bg-slate-50/70 rounded-2xl">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Super Built-up</span>
            <p className="text-sm sm:text-base font-bold text-slate-800 mt-0.5">
              {property.area_sqft ? `${property.area_sqft.toLocaleString()} sq.ft` : 'On Request'}
            </p>
          </div>

          <div className="p-3 bg-slate-50/70 rounded-2xl">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Possession</span>
            <p className="text-sm sm:text-base font-bold text-slate-800 mt-0.5">
              {property.possession_date || 'Ready to Move'}
            </p>
          </div>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Info */}
          <div className="lg:col-span-2 space-y-6">
            {/* Overview */}
            <section className="bg-white p-6 rounded-3xl border border-slate-200/80 shadow-xs space-y-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">Overview</h2>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                {property.description ||
                  `Premium ${property.bedrooms ? `${property.bedrooms}-bedroom ` : ''}${property.type || 'property'} located in ${property.location || 'prime locality'}. Verified inventory directly synced with the CRM.`}
              </p>
            </section>

            {/* Amenities */}
            {property.amenities && property.amenities.length > 0 && (
              <section className="bg-white p-6 rounded-3xl border border-slate-200/80 shadow-xs space-y-3">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">Amenities & Features</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 pt-1">
                  {property.amenities.map((amenity, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50 text-xs font-medium text-slate-700"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                      <span className="truncate">{amenity}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Sidebar Info & Action */}
          <div className="space-y-6">
            <div className="bg-gradient-to-br from-violet-600 to-indigo-700 rounded-3xl p-6 text-white space-y-4 shadow-lg">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-300" />
                <h3 className="text-base font-bold">Ask AI Advisor</h3>
              </div>
              <p className="text-xs text-violet-100 leading-relaxed">
                Want to book a viewing or negotiate terms? Our AI sales agent has full verified pricing, payment plans, and slot availability.
              </p>
              <Link
                href={`/portal/${org}/chat`}
                className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-2xl bg-white text-violet-800 text-xs font-bold hover:bg-violet-50 transition shadow-sm"
              >
                <MessageSquare className="w-4 h-4" /> Open Conversation
              </Link>
            </div>

            <div className="bg-white p-5 rounded-3xl border border-slate-200/80 shadow-xs space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Inventory Status</h3>
              <div className="space-y-2 text-xs text-slate-600">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-400">Status</span>
                  <span className="font-semibold capitalize text-slate-800">{property.status || 'Active'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-400">Furnishing</span>
                  <span className="font-semibold capitalize text-slate-800">{property.furnishing_status || 'Standard'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-400">Verification</span>
                  <span className="font-semibold text-emerald-600">
                    {property.source_verified ? 'CRM Verified' : 'Standard Listing'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
