'use client';

import React from 'react';
import Link from 'next/link';
import type { PropertyResult } from './AISalesChat';

interface PropertyCardInlineProps {
  property: PropertyResult;
  organizationId?: string;
  inCompareList?: boolean;
  onShortlist?: () => void;
  onCompare?: () => void;
  onSchedule?: () => void;
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

function PropertyTypeBadge({ type }: { type?: string | null }) {
  const colors: Record<string, string> = {
    apartment: 'bg-blue-50 text-blue-700',
    villa: 'bg-emerald-50 text-emerald-700',
    townhouse: 'bg-amber-50 text-amber-700',
    plot: 'bg-orange-50 text-orange-700',
    penthouse: 'bg-purple-50 text-purple-700',
  };
  const label = type || 'Property';
  const color = colors[label.toLowerCase()] || 'bg-slate-50 text-slate-600';
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${color} capitalize`}>
      {label}
    </span>
  );
}

export function PropertyCardInline({
  property,
  organizationId,
  inCompareList,
  onShortlist,
  onCompare,
  onSchedule,
}: PropertyCardInlineProps) {
  const price = formatPrice(property.price, property.currency);

  return (
    <div
      id={`property-card-${property.id}`}
      className="
        group bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm
        hover:shadow-md hover:border-violet-200 transition-all duration-200
      "
    >
      {/* Image placeholder — premium gradient */}
      <div className="relative h-28 bg-gradient-to-br from-indigo-100 via-violet-100 to-purple-200 overflow-hidden">
        <div className="absolute inset-0 flex items-center justify-center">
          <svg className="w-12 h-12 text-violet-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
        </div>
        {/* Verified badge */}
        {property.source_verified && (
          <div className="absolute top-2 right-2 flex items-center gap-1 bg-emerald-500/90 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
            <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
            VERIFIED
          </div>
        )}
        {property.status === 'available' && (
          <div className="absolute top-2 left-2 bg-emerald-400/90 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
            Available
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3 space-y-2">
        {/* Name + type */}
        <div className="flex items-start justify-between gap-2">
          <h4 className="text-sm font-bold text-slate-800 leading-tight line-clamp-1">
            {property.name}
          </h4>
          <PropertyTypeBadge type={property.type} />
        </div>

        {/* Location + bedrooms */}
        <div className="flex items-center gap-3 text-xs text-slate-500">
          {property.location && (
            <div className="flex items-center gap-1 min-w-0">
              <svg className="w-3 h-3 text-violet-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
              </svg>
              <span className="truncate">{property.location}</span>
            </div>
          )}
          {property.bedrooms && (
            <div className="flex items-center gap-1 flex-shrink-0">
              <svg className="w-3 h-3 text-violet-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M7 13c1.66 0 3-1.34 3-3S8.66 7 7 7s-3 1.34-3 3 1.34 3 3 3zm12-6h-8v7H3V5H1v15h2v-3h18v3h2v-9c0-2.21-1.79-4-4-4z" />
              </svg>
              <span>{property.bedrooms} BHK</span>
            </div>
          )}
        </div>

        {/* Price */}
        <div className="flex items-baseline justify-between">
          <span className="text-base font-black bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
            {price}
          </span>
          {!property.source_verified && (
            <span className="text-[9px] text-amber-500 font-medium">Indicative</span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1.5 pt-1">
          {organizationId && (
            <Link
              id={`view-prop-${property.id}`}
              href={`/portal/${organizationId}/property/${property.id}`}
              className="flex-1 flex items-center justify-center gap-1 py-1.5 text-[11px] font-semibold
                bg-slate-50 hover:bg-slate-100 text-slate-700 rounded-xl transition-colors"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              View
            </Link>
          )}
          <button
            id={`shortlist-prop-${property.id}`}
            onClick={onShortlist}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 text-[11px] font-semibold
              bg-violet-50 hover:bg-violet-100 text-violet-700 rounded-xl transition-colors"
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.86L12 17.77l-6.18 3.23L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            Save
          </button>
          <button
            id={`compare-prop-${property.id}`}
            onClick={onCompare}
            className={`flex-1 flex items-center justify-center gap-1 py-1.5 text-[11px] font-semibold
              rounded-xl transition-colors
              ${inCompareList
                ? 'bg-teal-100 text-teal-800'
                : 'bg-teal-50 hover:bg-teal-100 text-teal-700'
              }`}
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            {inCompareList ? 'Added' : 'Compare'}
          </button>
          <button
            id={`schedule-prop-${property.id}`}
            onClick={onSchedule}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 text-[11px] font-semibold
              bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-xl transition-colors"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            Visit
          </button>
        </div>
      </div>
    </div>
  );
}
