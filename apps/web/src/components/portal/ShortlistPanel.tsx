'use client';

import React, { useEffect, useState } from 'react';
import { aiGetShortlist, type AIShortlistItem } from '@/lib/api-client';

interface ShortlistPanelProps {
  sessionId: string;
  organizationId: string;
  onClose: () => void;
  onSchedule?: (propId: string) => void;
  onCompare?: (propId: string) => void;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    shortlisted: 'bg-violet-50 text-violet-700',
    liked: 'bg-emerald-50 text-emerald-700',
    rejected: 'bg-red-50 text-red-600',
    visit_requested: 'bg-blue-50 text-blue-700',
    visited: 'bg-teal-50 text-teal-700',
  };
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${colors[status] || 'bg-slate-50 text-slate-500'}`}>
      {status.replace('_', ' ')}
    </span>
  );
}

export function ShortlistPanel({
  sessionId,
  organizationId,
  onClose,
  onSchedule,
  onCompare,
}: ShortlistPanelProps) {
  const [items, setItems] = useState<AIShortlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    aiGetShortlist(sessionId)
      .then(r => setItems(r.items))
      .catch(() => setError('Could not load shortlist'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  return (
    /* Slide-in overlay */
    <div className="absolute inset-0 z-40 flex" id="shortlist-panel">
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/20 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="w-80 sm:w-96 h-full bg-white flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-slate-100">
          <div>
            <h3 className="text-sm font-bold text-slate-800">My Shortlist</h3>
            <p className="text-xs text-slate-400">{items.length} propert{items.length === 1 ? 'y' : 'ies'} saved</p>
          </div>
          <button
            id="shortlist-close-btn"
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && (
            <div className="flex items-center justify-center h-32">
              <div className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {error && (
            <div className="text-center text-sm text-red-500 py-8">{error}</div>
          )}
          {!loading && !error && items.length === 0 && (
            <div className="text-center py-12">
              <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-violet-50 flex items-center justify-center">
                <svg className="w-7 h-7 text-violet-300" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.86L12 17.77l-6.18 3.23L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                </svg>
              </div>
              <p className="text-sm font-medium text-slate-600">No properties saved yet</p>
              <p className="text-xs text-slate-400 mt-1">Tap "Save" on any property card</p>
            </div>
          )}
          {items.map((item) => (
            <div
              key={item.property_id}
              id={`shortlist-item-${item.property_id}`}
              className="bg-slate-50 border border-slate-100 rounded-2xl p-3 space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-800 truncate">{item.name}</p>
                  <p className="text-xs text-slate-500 truncate">{item.location || 'Location TBD'}</p>
                </div>
                <StatusBadge status={item.status} />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  {item.bedrooms && (
                    <span className="text-xs text-slate-600">{item.bedrooms} BHK</span>
                  )}
                  {item.price && (
                    <span className="text-xs font-bold text-violet-700 ml-2">
                      {item.price >= 10_000_000
                        ? `₹${(item.price / 10_000_000).toFixed(2)} Cr`
                        : `₹${(item.price / 100_000).toFixed(1)} L`}
                    </span>
                  )}
                </div>
                {item.source_verified && (
                  <span className="text-[9px] font-bold text-emerald-600">✓ VERIFIED</span>
                )}
              </div>
              <div className="flex gap-1.5">
                <button
                  id={`shortlist-schedule-${item.property_id}`}
                  onClick={() => onSchedule?.(item.property_id)}
                  className="flex-1 py-1.5 text-[11px] font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-xl transition-colors"
                >
                  Schedule Visit
                </button>
                <button
                  id={`shortlist-compare-${item.property_id}`}
                  onClick={() => onCompare?.(item.property_id)}
                  className="flex-1 py-1.5 text-[11px] font-semibold bg-teal-50 hover:bg-teal-100 text-teal-700 rounded-xl transition-colors"
                >
                  Compare
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
