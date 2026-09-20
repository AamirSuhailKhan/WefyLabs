'use client';

import React, { useEffect, useState } from 'react';
import { aiCompareProperties, type AIPropertyComparison } from '@/lib/api-client';

interface ComparisonModalProps {
  sessionId: string;
  propertyIds: string[];
  onClose: () => void;
  onRemove?: (propId: string) => void;
  onSchedule?: (propId: string) => void;
}

function formatPrice(p?: number | null, c?: string | null): string {
  if (!p) return '—';
  if (!c || c === 'INR' || c === '₹') {
    if (p >= 10_000_000) return `₹${(p / 10_000_000).toFixed(2)} Cr`;
    if (p >= 100_000) return `₹${(p / 100_000).toFixed(1)} L`;
    return `₹${p.toLocaleString('en-IN')}`;
  }
  return `${c} ${p.toLocaleString()}`;
}

function Row({
  label,
  values,
}: {
  label: string;
  values: (string | number | null | undefined)[];
}) {
  return (
    <div className="grid gap-px" style={{ gridTemplateColumns: `140px repeat(${values.length}, 1fr)` }}>
      <div className="flex items-center py-3 px-3 bg-slate-50 text-xs font-semibold text-slate-500 border-b border-slate-100">
        {label}
      </div>
      {values.map((v, i) => (
        <div
          key={i}
          className="flex items-center py-3 px-3 bg-white text-xs text-slate-800 font-medium border-b border-slate-100"
        >
          {v != null ? String(v) : <span className="text-slate-300">—</span>}
        </div>
      ))}
    </div>
  );
}

export function ComparisonModal({
  sessionId,
  propertyIds,
  onClose,
  onRemove,
  onSchedule,
}: ComparisonModalProps) {
  const [properties, setProperties] = useState<AIPropertyComparison[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    aiCompareProperties(sessionId, propertyIds)
      .then(r => setProperties(r.properties))
      .catch(() => setError('Could not load comparison data'))
      .finally(() => setLoading(false));
  }, [sessionId, propertyIds.join(',')]);

  return (
    <div
      id="comparison-modal"
      className="absolute inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30 backdrop-blur-sm p-0 sm:p-4"
    >
      <div className="w-full sm:max-w-4xl bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 flex-shrink-0">
          <div>
            <h3 className="text-base font-black text-slate-900">Property Comparison</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Verified data from our listings database
              {properties.some(p => p.source_verified) && (
                <span className="ml-2 text-emerald-600 font-semibold">✓ All data verified</span>
              )}
            </p>
          </div>
          <button
            id="comparison-close-btn"
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          {loading && (
            <div className="flex items-center justify-center h-48">
              <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {error && (
            <div className="text-center text-sm text-red-500 py-12">{error}</div>
          )}
          {!loading && !error && properties.length > 0 && (
            <div className="overflow-x-auto">
              {/* Property Headers */}
              <div
                className="grid gap-px sticky top-0 z-10"
                style={{ gridTemplateColumns: `140px repeat(${properties.length}, 1fr)` }}
              >
                <div className="bg-slate-100 py-3 px-3" />
                {properties.map((p) => (
                  <div key={p.id} className="bg-gradient-to-b from-violet-600 to-indigo-700 py-3 px-3 text-white">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-black leading-tight truncate">{p.name}</p>
                        <p className="text-[10px] opacity-80 truncate mt-0.5">{p.location || p.city || '—'}</p>
                      </div>
                      {onRemove && (
                        <button
                          id={`remove-compare-${p.id}`}
                          onClick={() => onRemove(p.id)}
                          className="flex-shrink-0 w-4 h-4 rounded-full bg-white/20 hover:bg-white/40 flex items-center justify-center transition-colors"
                        >
                          <span className="text-[9px]">✕</span>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Comparison rows */}
              <Row label="Price" values={properties.map(p => formatPrice(p.price, p.currency))} />
              <Row label="Type" values={properties.map(p => p.type)} />
              <Row label="Bedrooms" values={properties.map(p => p.bedrooms ? `${p.bedrooms} BHK` : null)} />
              <Row label="Bathrooms" values={properties.map(p => p.bathrooms)} />
              <Row label="Area (sq ft)" values={properties.map(p => p.area_sqft ? `${p.area_sqft.toLocaleString()} sq ft` : null)} />
              <Row label="Location" values={properties.map(p => p.location || p.city)} />
              <Row label="Developer" values={properties.map(p => p.developer)} />
              <Row label="Possession" values={properties.map(p => p.possession)} />
              <Row label="Status" values={properties.map(p => p.status)} />
              <Row
                label="Amenities"
                values={properties.map(p =>
                  p.amenities && p.amenities.length > 0
                    ? p.amenities.slice(0, 3).join(', ')
                    : null
                )}
              />

              {/* Action row */}
              <div
                className="grid gap-px"
                style={{ gridTemplateColumns: `140px repeat(${properties.length}, 1fr)` }}
              >
                <div className="py-3 px-3 bg-slate-50 text-xs font-semibold text-slate-500">
                  Actions
                </div>
                {properties.map((p) => (
                  <div key={p.id} className="py-3 px-3 bg-white">
                    <button
                      id={`compare-schedule-${p.id}`}
                      onClick={() => onSchedule?.(p.id)}
                      className="w-full py-1.5 text-[11px] font-bold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-xl transition-colors"
                    >
                      Schedule Visit
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
