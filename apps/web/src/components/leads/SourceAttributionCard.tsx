'use client';

import { useState, useEffect } from 'react';
import { 
  Compass, Link2, Globe, Tag, Calendar, 
  Layers, ExternalLink, ShieldCheck, Clock, ArrowUpRight
} from 'lucide-react';
import { LeadDetail } from '@/types';
import { api } from '@/lib/api-client';

interface SourceAttributionCardProps {
  lead: LeadDetail;
}

interface AttributionData {
  id?: string;
  lead_id?: string;
  channel?: string;
  provider?: string;
  external_id?: string;
  landing_page?: string;
  referrer?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
  first_touch_at?: string;
  last_touch_at?: string;
}

export default function SourceAttributionCard({ lead }: SourceAttributionCardProps) {
  const [attribution, setAttribution] = useState<AttributionData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let mounted = true;
    async function loadAttribution() {
      try {
        const data = await api.getLeadAttribution(lead.id);
        if (mounted && data) {
          setAttribution(data);
        }
      } catch (err) {
        console.warn('Could not load attribution details', err);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    loadAttribution();
    return () => {
      mounted = false;
    };
  }, [lead.id]);

  const channelDisplay = attribution?.channel || lead.source || 'Direct / Manual';
  const providerDisplay = attribution?.provider || (attribution?.channel === 'csv_import' ? 'CSV Uploader' : 'WefyLabs Engine');

  const hasUTMs = !!(
    attribution?.utm_source ||
    attribution?.utm_medium ||
    attribution?.utm_campaign ||
    attribution?.utm_term ||
    attribution?.utm_content
  );

  return (
    <div className="glass-panel p-5 rounded-2xl border border-dark-border space-y-4 bg-slate-950/60 shadow-lg">
      <div className="flex items-center justify-between border-b border-dark-border/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-white">Source & Attribution</h3>
            <p className="text-[11px] text-slate-400">Canonical acquisition provenance & UTM tracking</p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <ShieldCheck className="w-3 h-3" />
          Immutable
        </span>
      </div>

      {loading ? (
        <div className="py-4 text-center text-xs text-slate-400 font-mono animate-pulse">
          Loading acquisition provenance...
        </div>
      ) : (
        <div className="space-y-3.5">
          {/* Channel & Provider */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 flex items-center gap-1 mb-1">
                <Globe className="w-3 h-3 text-sky-400" /> Channel
              </span>
              <span className="text-xs font-bold text-white capitalize font-mono block truncate">
                {channelDisplay.replace('_', ' ')}
              </span>
            </div>
            <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 flex items-center gap-1 mb-1">
                <Layers className="w-3 h-3 text-violet-400" /> Provider
              </span>
              <span className="text-xs font-bold text-white capitalize font-mono block truncate">
                {providerDisplay.replace('_', ' ')}
              </span>
            </div>
          </div>

          {/* External ID if available */}
          {attribution?.external_id && (
            <div className="bg-slate-900/40 px-3 py-2 rounded-xl border border-slate-800/80 flex items-center justify-between text-[11px]">
              <span className="text-slate-400 font-mono">External Lead ID:</span>
              <span className="text-sky-300 font-mono font-semibold truncate max-w-[200px]">
                {attribution.external_id}
              </span>
            </div>
          )}

          {/* UTM Parameters */}
          {hasUTMs && (
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] uppercase font-bold text-slate-400 flex items-center gap-1">
                <Tag className="w-3 h-3 text-amber-400" /> Campaign & UTM Data
              </span>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                {attribution?.utm_source && (
                  <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-800/60">
                    <span className="text-slate-500 block text-[9px] uppercase font-mono">Source</span>
                    <span className="text-slate-200 font-semibold font-mono truncate block">{attribution.utm_source}</span>
                  </div>
                )}
                {attribution?.utm_medium && (
                  <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-800/60">
                    <span className="text-slate-500 block text-[9px] uppercase font-mono">Medium</span>
                    <span className="text-slate-200 font-semibold font-mono truncate block">{attribution.utm_medium}</span>
                  </div>
                )}
                {attribution?.utm_campaign && (
                  <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-800/60 col-span-2">
                    <span className="text-slate-500 block text-[9px] uppercase font-mono">Campaign</span>
                    <span className="text-emerald-300 font-semibold font-mono truncate block">{attribution.utm_campaign}</span>
                  </div>
                )}
                {attribution?.utm_content && (
                  <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-800/60">
                    <span className="text-slate-500 block text-[9px] uppercase font-mono">Content</span>
                    <span className="text-slate-200 font-semibold font-mono truncate block">{attribution.utm_content}</span>
                  </div>
                )}
                {attribution?.utm_term && (
                  <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-800/60">
                    <span className="text-slate-500 block text-[9px] uppercase font-mono">Term</span>
                    <span className="text-slate-200 font-semibold font-mono truncate block">{attribution.utm_term}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Landing page & Referrer */}
          {(attribution?.landing_page || attribution?.referrer) && (
            <div className="space-y-1.5 pt-1 text-[11px]">
              {attribution?.landing_page && (
                <div className="flex items-center gap-1.5 text-slate-400 bg-slate-900/40 p-2 rounded-lg border border-slate-800/50 truncate">
                  <Link2 className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                  <span className="font-mono text-[10px] text-slate-300 truncate">{attribution.landing_page}</span>
                </div>
              )}
            </div>
          )}

          {/* Touchpoint Timestamps */}
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-dark-border/40 text-[10px] font-mono text-slate-400">
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3 text-slate-500" />
              <span>First: {attribution?.first_touch_at ? new Date(attribution.first_touch_at).toLocaleDateString() : new Date(lead.created_at).toLocaleDateString()}</span>
            </div>
            <div className="flex items-center gap-1 justify-end">
              <ArrowUpRight className="w-3 h-3 text-slate-500" />
              <span>Last: {attribution?.last_touch_at ? new Date(attribution.last_touch_at).toLocaleDateString() : new Date(lead.created_at).toLocaleDateString()}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
