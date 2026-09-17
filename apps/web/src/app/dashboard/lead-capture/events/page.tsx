'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api-client';
import { LeadCaptureNav } from '@/components/lead-capture/LeadCaptureNav';
import {
  Activity,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
  Filter,
  Layers,
  ChevronRight,
  Eye,
  RotateCcw,
  Copy,
  ExternalLink,
  ShieldAlert,
  Search,
  Check
} from 'lucide-react';

interface CaptureEvent {
  id: string;
  source_id?: string;
  source_name?: string;
  source_channel?: string;
  event_type: string;
  external_event_id?: string;
  processing_status: string;
  processing_attempts?: number;
  failure_reason?: string;
  received_at: string;
  processed_at?: string;
  raw_payload?: any;
}

export default function LeadCaptureEventsPage() {
  const [events, setEvents] = useState<CaptureEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<CaptureEvent | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    loadEvents();
  }, [statusFilter]);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 50 };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const res = await api.leadCapture.listEvents(params);
      setEvents(res?.items || []);
    } catch (err: any) {
      console.error('Failed to load events:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async (eventId: string) => {
    setRetryingId(eventId);
    setNotification(null);
    try {
      const res = await api.leadCapture.retryEvent(eventId);
      setNotification({
        type: 'success',
        message: `Event ${eventId.slice(0, 8)} successfully re-queued for processing.`
      });
      await loadEvents();
      if (selectedEvent && selectedEvent.id === eventId) {
        setSelectedEvent(null);
      }
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || `Failed to retry event ${eventId.slice(0, 8)}.`
      });
    } finally {
      setRetryingId(null);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // Metrics
  const totalCount = events.length;
  const processedCount = events.filter(e => e.processing_status === 'processed' || e.processing_status === 'success').length;
  const duplicateCount = events.filter(e => e.processing_status === 'duplicate').length;
  const failedCount = events.filter(e => e.processing_status === 'failed' || e.processing_status === 'rejected').length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-rose-500 flex items-center justify-center shadow-lg shadow-rose-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Lead Ingestion Feed & DLQ</h1>
              <p className="text-sm text-slate-400">
                Audited ingestion log, duplicate tracking, and dead-letter queue with safe idempotent replay.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadEvents}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs font-semibold text-slate-300 hover:text-white transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
            Refresh Feed
          </button>
        </div>
      </div>

      {/* Navigation */}
      <LeadCaptureNav activeTab="events" />

      {/* Notification Banner */}
      {notification && (
        <div
          className={`flex items-center justify-between p-4 rounded-xl text-sm border ${
            notification.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-3">
            {notification.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs opacity-70 hover:opacity-100 ml-4 font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* KPI Highlights */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <p className="text-xs text-slate-400 font-medium">Fetched Events</p>
          <p className="text-2xl font-bold text-white mt-1">{totalCount}</p>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <p className="text-xs text-emerald-400 font-medium">Processed to Leads</p>
          <p className="text-2xl font-bold text-emerald-400 mt-1">{processedCount}</p>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <p className="text-xs text-amber-400 font-medium">Duplicates Caught</p>
          <p className="text-2xl font-bold text-amber-400 mt-1">{duplicateCount}</p>
        </div>
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
          <p className="text-xs text-rose-400 font-medium">DLQ / Failed</p>
          <p className="text-2xl font-bold text-rose-400 mt-1">{failedCount}</p>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-900/60 border border-slate-800 rounded-xl p-3">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs font-semibold text-slate-300">Filter Status:</span>
          {['all', 'processed', 'duplicate', 'failed', 'pending'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium capitalize transition ${
                statusFilter === s
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-semibold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin text-cyan-400" />
            Loading real-time ingestion log...
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-16">
            <Layers className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <h4 className="text-sm font-semibold text-slate-300">No Ingestion Events Found</h4>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              {statusFilter !== 'all'
                ? `No events matching status "${statusFilter}". Try selecting "All" or submit a test lead.`
                : 'Inbound events from forms, webhooks, or imports will stream here automatically.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                  <th className="py-3 px-4 font-semibold">Event ID</th>
                  <th className="py-3 px-4 font-semibold">Source</th>
                  <th className="py-3 px-4 font-semibold">Type</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Attempts</th>
                  <th className="py-3 px-4 font-semibold">Failure / Info</th>
                  <th className="py-3 px-4 font-semibold">Received</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {events.map((evt) => {
                  const isProcessed = evt.processing_status === 'processed' || evt.processing_status === 'success';
                  const isDup = evt.processing_status === 'duplicate';
                  const isFailed = evt.processing_status === 'failed' || evt.processing_status === 'rejected';

                  return (
                    <tr key={evt.id} className="hover:bg-slate-900/40 transition">
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-300">
                        <div className="flex items-center gap-1.5">
                          <span>{evt.id.slice(0, 10)}...</span>
                          <button
                            onClick={() => copyToClipboard(evt.id, evt.id)}
                            className="text-slate-500 hover:text-slate-300"
                            title="Copy full Event ID"
                          >
                            {copiedId === evt.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-slate-200">{evt.source_name || 'System / Direct'}</span>
                        {evt.source_channel && (
                          <span className="block text-[10px] text-slate-500 uppercase tracking-wider mt-0.5">
                            {evt.source_channel}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-300 font-mono text-[11px]">{evt.event_type}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                            isProcessed
                              ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/80'
                              : isDup
                              ? 'bg-amber-950/80 text-amber-300 border border-amber-800/80'
                              : isFailed
                              ? 'bg-rose-950/80 text-rose-300 border border-rose-800/80'
                              : 'bg-cyan-950/80 text-cyan-300 border border-cyan-800/80'
                          }`}
                        >
                          {isProcessed && <CheckCircle2 className="w-2.5 h-2.5" />}
                          {isDup && <Layers className="w-2.5 h-2.5" />}
                          {isFailed && <AlertCircle className="w-2.5 h-2.5" />}
                          {evt.processing_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-400 font-mono">{evt.processing_attempts ?? 1}</td>
                      <td className="py-3 px-4 text-slate-400 max-w-xs truncate">
                        {evt.failure_reason ? (
                          <span className="text-rose-400 text-[11px] flex items-center gap-1">
                            <AlertCircle className="w-3 h-3 flex-shrink-0" />
                            <span className="truncate">{evt.failure_reason}</span>
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-500 text-[11px] whitespace-nowrap">
                        {evt.received_at ? new Date(evt.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setSelectedEvent(evt)}
                            className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition"
                            title="Inspect Raw Event"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          {isFailed && (
                            <button
                              onClick={() => handleRetry(evt.id)}
                              disabled={retryingId === evt.id}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-950/60 hover:bg-rose-900 border border-rose-800 text-rose-300 hover:text-white text-[10px] font-semibold transition"
                              title="Safe Idempotent Replay"
                            >
                              <RotateCcw className={`w-3 h-3 ${retryingId === evt.id ? 'animate-spin' : ''}`} />
                              Retry
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Raw Event Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">Event Inspector</h3>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono">
                  {selectedEvent.id}
                </span>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500">Status</span>
                  <p className="font-semibold text-slate-200 uppercase mt-0.5">
                    {selectedEvent.processing_status}
                  </p>
                </div>
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-500">Received At</span>
                  <p className="font-semibold text-slate-200 mt-0.5">
                    {new Date(selectedEvent.received_at).toLocaleString()}
                  </p>
                </div>
                {selectedEvent.failure_reason && (
                  <div className="col-span-2 bg-rose-950/40 border border-rose-800/60 p-3 rounded-xl">
                    <span className="text-rose-400 font-medium">Failure Reason:</span>
                    <p className="text-rose-200 mt-0.5">{selectedEvent.failure_reason}</p>
                  </div>
                )}
              </div>

              <div>
                <span className="text-xs font-semibold text-slate-300">Sanitized Payload View:</span>
                <pre className="mt-1.5 p-3 rounded-xl bg-slate-950 border border-slate-800 text-cyan-300 font-mono text-xs overflow-x-auto max-h-64">
                  {JSON.stringify(selectedEvent.raw_payload || {}, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 border-t border-slate-800 bg-slate-950/50">
              <span className="text-[11px] text-slate-500">
                Untrusted payloads are sanitized against XSS, script execution, and prompt injection.
              </span>
              <div className="flex items-center gap-2">
                {selectedEvent.processing_status === 'failed' && (
                  <button
                    onClick={() => handleRetry(selectedEvent.id)}
                    disabled={retryingId === selectedEvent.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition"
                  >
                    <RotateCcw className={`w-3 h-3 ${retryingId === selectedEvent.id ? 'animate-spin' : ''}`} />
                    Retry Ingestion
                  </button>
                )}
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
