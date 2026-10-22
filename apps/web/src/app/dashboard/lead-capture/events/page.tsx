'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api-client';
import { LeadCaptureNav } from '@/components/lead-capture/LeadCaptureNav';
import { PageContainer } from '@/components/ui/PageContainer';
import {
  Activity,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Filter,
  Layers,
  Eye,
  RotateCcw,
  Copy,
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
      await api.leadCapture.retryEvent(eventId);
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
    <PageContainer className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-700 border border-amber-500/20 flex items-center justify-center shrink-0">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-[#1A1A1A]">Lead Ingestion Feed & DLQ</h1>
              <p className="text-xs text-[#6B6B6B]">
                Audited ingestion log, duplicate tracking, and dead-letter queue with safe idempotent replay.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadEvents}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A] transition shadow-2xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#2C4BFB]' : ''}`} />
            Refresh Feed
          </button>
        </div>
      </div>

      {/* Navigation */}
      <LeadCaptureNav activeTab="events" />

      {/* Notification Banner */}
      {notification && (
        <div
          className={`flex items-center justify-between p-4 rounded-xl text-sm border shadow-2xs ${
            notification.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <div className="flex items-center gap-3">
            {notification.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
          <button
            onClick={() => setNotification(null)}
            className="text-xs opacity-70 hover:opacity-100 ml-4 font-semibold cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* KPI Highlights */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 shadow-xs">
          <p className="text-[11px] font-mono text-[#6B6B6B] uppercase font-semibold">Fetched Events</p>
          <p className="text-2xl font-bold text-[#1A1A1A] mt-1 font-mono">{totalCount}</p>
        </div>
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 shadow-xs">
          <p className="text-[11px] font-mono text-emerald-700 uppercase font-semibold">Processed to Leads</p>
          <p className="text-2xl font-bold text-emerald-700 mt-1 font-mono">{processedCount}</p>
        </div>
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 shadow-xs">
          <p className="text-[11px] font-mono text-amber-800 uppercase font-semibold">Duplicates Caught</p>
          <p className="text-2xl font-bold text-amber-800 mt-1 font-mono">{duplicateCount}</p>
        </div>
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-4 shadow-xs">
          <p className="text-[11px] font-mono text-rose-700 uppercase font-semibold">DLQ / Failed</p>
          <p className="text-2xl font-bold text-rose-700 mt-1 font-mono">{failedCount}</p>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-3 shadow-xs">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[#6B6B6B]" />
          <span className="text-xs font-semibold text-[#1A1A1A]">Filter Status:</span>
          {['all', 'processed', 'duplicate', 'failed', 'pending'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition cursor-pointer ${
                statusFilter === s
                  ? 'bg-[#1A1A1A] text-white shadow-xs font-semibold'
                  : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl overflow-hidden shadow-xs">
        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center gap-3 text-[#6B6B6B] text-xs">
            <RefreshCw className="w-6 h-6 animate-spin text-[#2C4BFB]" />
            Loading real-time ingestion log...
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-16">
            <Layers className="w-10 h-10 text-[#6B6B6B] mx-auto mb-3" />
            <h4 className="text-sm font-semibold text-[#1A1A1A]">No Ingestion Events Found</h4>
            <p className="text-xs text-[#6B6B6B] mt-1 max-w-sm mx-auto">
              {statusFilter !== 'all'
                ? `No events matching status "${statusFilter}". Try selecting "All" or submit a test lead.`
                : 'Inbound events from forms, webhooks, or imports will stream here automatically.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] bg-[#F0EDE8]/60">
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Event ID</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Source</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Type</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Attempts</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Failure / Info</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Received</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px] text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#D4D0C8]/60 bg-white">
                {events.map((evt) => {
                  const isProcessed = evt.processing_status === 'processed' || evt.processing_status === 'success';
                  const isDup = evt.processing_status === 'duplicate';
                  const isFailed = evt.processing_status === 'failed' || evt.processing_status === 'rejected';

                  return (
                    <tr key={evt.id} className="hover:bg-[#FAF7F2] transition">
                      <td className="py-3 px-4 font-mono text-[11px] text-[#1A1A1A]">
                        <div className="flex items-center gap-1.5">
                          <span>{evt.id.slice(0, 10)}...</span>
                          <button
                            onClick={() => copyToClipboard(evt.id, evt.id)}
                            className="text-[#6B6B6B] hover:text-[#1A1A1A] cursor-pointer"
                            title="Copy full Event ID"
                          >
                            {copiedId === evt.id ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-[#1A1A1A]">{evt.source_name || 'System / Direct'}</span>
                        {evt.source_channel && (
                          <span className="block text-[10px] text-[#6B6B6B] uppercase tracking-wider mt-0.5 font-mono">
                            {evt.source_channel}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-[#1A1A1A] font-mono text-[11px]">{evt.event_type}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                            isProcessed
                              ? 'bg-emerald-500/10 text-emerald-800 border border-emerald-500/20'
                              : isDup
                              ? 'bg-amber-500/10 text-amber-800 border border-amber-500/20'
                              : isFailed
                              ? 'bg-rose-500/10 text-rose-800 border border-rose-500/20'
                              : 'bg-blue-500/10 text-blue-800 border border-blue-500/20'
                          }`}
                        >
                          {isProcessed && <CheckCircle2 className="w-2.5 h-2.5" />}
                          {isDup && <Layers className="w-2.5 h-2.5" />}
                          {isFailed && <AlertCircle className="w-2.5 h-2.5" />}
                          {evt.processing_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[#6B6B6B] font-mono">{evt.processing_attempts ?? 1}</td>
                      <td className="py-3 px-4 text-[#6B6B6B] max-w-xs truncate">
                        {evt.failure_reason ? (
                          <span className="text-rose-700 text-[11px] flex items-center gap-1">
                            <AlertCircle className="w-3 h-3 shrink-0" />
                            <span className="truncate">{evt.failure_reason}</span>
                          </span>
                        ) : (
                          <span className="text-[#D4D0C8]">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-[#6B6B6B] text-[11px] whitespace-nowrap font-mono">
                        {evt.received_at ? new Date(evt.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setSelectedEvent(evt)}
                            className="p-1.5 rounded-lg bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] text-[#1A1A1A] transition cursor-pointer shadow-2xs"
                            title="Inspect Raw Event"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          {isFailed && (
                            <button
                              onClick={() => handleRetry(evt.id)}
                              disabled={retryingId === evt.id}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700 text-[10px] font-semibold transition cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between p-5 border-b border-[#D4D0C8]">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-[#2C4BFB]" />
                <h3 className="text-sm font-semibold text-[#1A1A1A]">Event Inspector</h3>
                <span className="px-2 py-0.5 rounded bg-white border border-[#D4D0C8] text-[#6B6B6B] text-[10px] font-mono">
                  {selectedEvent.id}
                </span>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-[#6B6B6B] hover:text-[#1A1A1A] text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
                  <span className="text-[#6B6B6B]">Status</span>
                  <p className="font-semibold text-[#1A1A1A] uppercase mt-0.5">
                    {selectedEvent.processing_status}
                  </p>
                </div>
                <div className="bg-white p-3 rounded-xl border border-[#D4D0C8]">
                  <span className="text-[#6B6B6B]">Received At</span>
                  <p className="font-semibold text-[#1A1A1A] mt-0.5 font-mono">
                    {new Date(selectedEvent.received_at).toLocaleString()}
                  </p>
                </div>
                {selectedEvent.failure_reason && (
                  <div className="col-span-2 bg-rose-50 border border-rose-200 p-3 rounded-xl">
                    <span className="text-rose-700 font-medium">Failure Reason:</span>
                    <p className="text-rose-800 mt-0.5">{selectedEvent.failure_reason}</p>
                  </div>
                )}
              </div>

              <div>
                <span className="text-xs font-semibold text-[#1A1A1A]">Sanitized Payload View:</span>
                <pre className="mt-1.5 p-3 rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] font-mono text-xs overflow-x-auto max-h-64">
                  {JSON.stringify(selectedEvent.raw_payload || {}, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 border-t border-[#D4D0C8] bg-white">
              <span className="text-[11px] text-[#6B6B6B]">
                Untrusted payloads are sanitized against XSS, script execution, and prompt injection.
              </span>
              <div className="flex items-center gap-2">
                {selectedEvent.processing_status === 'failed' && (
                  <button
                    onClick={() => handleRetry(selectedEvent.id)}
                    disabled={retryingId === selectedEvent.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold transition cursor-pointer"
                  >
                    <RotateCcw className={`w-3 h-3 ${retryingId === selectedEvent.id ? 'animate-spin' : ''}`} />
                    Retry Ingestion
                  </button>
                )}
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="px-4 py-1.5 rounded-lg bg-[#FAF7F2] hover:bg-[#F0EDE8] text-[#1A1A1A] border border-[#D4D0C8] text-xs font-medium transition cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
