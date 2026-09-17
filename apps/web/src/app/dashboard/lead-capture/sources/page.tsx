'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { 
  Radio, 
  Plus, 
  RefreshCw, 
  Copy, 
  Check, 
  Play, 
  Key, 
  Code2, 
  Globe, 
  Webhook, 
  Share2, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle,
  ExternalLink
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import LeadCaptureNav from '@/components/lead-capture/LeadCaptureNav';
import { api } from '@/lib/api-client';

export default function LeadCaptureSourcesPage() {
  const [sources, setSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [embedModalSource, setEmbedModalSource] = useState<any | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [actionInProgressId, setActionInProgressId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // New source form state
  const [name, setName] = useState('');
  const [channel, setChannel] = useState('WEBSITE');
  const [provider, setProvider] = useState('');
  const [description, setDescription] = useState('');

  const fetchSources = async () => {
    setLoading(true);
    try {
      const data = await api.leadCapture.listSources();
      setSources(data || []);
    } catch (err) {
      console.error('Failed to fetch lead sources', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, []);

  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.leadCapture.createSource({
        name,
        channel,
        provider: provider || undefined,
        description: description || undefined,
      });
      setCreateModalOpen(false);
      setName('');
      setDescription('');
      setProvider('');
      fetchSources();
      showToast('New lead source created successfully!');
    } catch (err: any) {
      alert(`Error creating source: ${err.message || err}`);
    }
  };

  const handleTestLead = async (sourceId: string) => {
    setActionInProgressId(sourceId);
    try {
      const res = await api.leadCapture.sendTestLead(sourceId);
      showToast(`Test lead "${res.lead_name}" (${res.lead_phone}) created and assigned!`);
      fetchSources();
    } catch (err: any) {
      alert(`Test lead failed: ${err.message || err}`);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleRotateToken = async (sourceId: string) => {
    if (!confirm('Are you sure you want to rotate this token? Any external website or webhook using the old token will need to be updated.')) {
      return;
    }
    setActionInProgressId(sourceId);
    try {
      const res = await api.leadCapture.rotateToken(sourceId);
      showToast('Public capture token rotated successfully!');
      fetchSources();
    } catch (err: any) {
      alert(`Token rotation failed: ${err.message || err}`);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleOpenEmbedModal = async (source: any) => {
    try {
      const res = await api.leadCapture.getEmbedCode(source.id);
      setEmbedModalSource(res);
    } catch (err: any) {
      alert(`Failed to load embed snippet: ${err.message || err}`);
    }
  };

  const copyToClipboard = (text: string, fieldKey: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldKey);
    setTimeout(() => setCopiedField(null), 2500);
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 5000);
  };

  const getChannelIcon = (ch: string) => {
    switch (ch.toUpperCase()) {
      case 'WEBSITE':
        return <Globe className="w-4 h-4 text-blue-500" />;
      case 'WEBHOOK':
        return <Webhook className="w-4 h-4 text-purple-500" />;
      case 'META':
      case 'GOOGLE':
        return <Share2 className="w-4 h-4 text-indigo-500" />;
      default:
        return <Radio className="w-4 h-4 text-gray-500" />;
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-gray-900 pb-16">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto pt-20 px-4 sm:px-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 py-6 border-b border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-widest bg-gray-900 text-white">
                Part 26
              </span>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-gray-900">
                Source Management
              </h1>
            </div>
            <p className="text-xs sm:text-sm text-gray-500">
              Configure and test lead capture endpoints, rotate public tokens, and copy website embed code.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchSources}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 transition shadow-sm"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              onClick={() => setCreateModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800 transition shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              New Source
            </button>
          </div>
        </div>

        {/* Lead Capture Sub Navigation */}
        <div className="my-4 rounded-xl overflow-hidden border border-gray-200 shadow-sm">
          <LeadCaptureNav />
        </div>

        {/* Toast */}
        {toastMessage && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between text-emerald-800 text-xs font-semibold animate-in fade-in">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>{toastMessage}</span>
            </div>
          </div>
        )}

        {/* Sources Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-8">
          {sources.map((src) => (
            <div
              key={src.id}
              className="bg-white rounded-2xl border border-gray-200/80 shadow-sm p-5 flex flex-col justify-between hover:shadow-md transition-shadow"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-gray-50 border border-gray-100">
                      {getChannelIcon(src.channel)}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-gray-900 leading-tight">{src.name}</h3>
                      <span className="text-[11px] text-gray-500 font-mono">{src.channel}</span>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    src.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {src.is_active ? 'Active' : 'Disabled'}
                  </span>
                </div>

                {src.description && (
                  <p className="text-xs text-gray-600 mb-4 line-clamp-2">{src.description}</p>
                )}

                {/* Token Box */}
                <div className="p-2.5 rounded-lg bg-gray-50 border border-gray-200/60 mb-4 flex items-center justify-between text-[11px]">
                  <div className="truncate mr-2">
                    <span className="text-gray-400 block text-[9px] font-bold uppercase tracking-wider">Public Token</span>
                    <span className="font-mono text-gray-700 font-semibold truncate block">
                      {src.webhook_url_token || 'No token assigned'}
                    </span>
                  </div>
                  {src.webhook_url_token && (
                    <button
                      onClick={() => copyToClipboard(src.webhook_url_token, `token-${src.id}`)}
                      title="Copy Token"
                      className="p-1.5 hover:bg-gray-200 rounded text-gray-600 transition"
                    >
                      {copiedField === `token-${src.id}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-gray-100 flex items-center justify-between gap-2">
                <button
                  onClick={() => handleTestLead(src.id)}
                  disabled={actionInProgressId === src.id}
                  className="flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 px-3 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg text-xs font-semibold transition"
                >
                  <Play className={`w-3 h-3 ${actionInProgressId === src.id ? 'animate-spin' : ''}`} />
                  {actionInProgressId === src.id ? 'Testing...' : 'Test Lead'}
                </button>

                <button
                  onClick={() => handleOpenEmbedModal(src)}
                  className="inline-flex items-center gap-1 py-1.5 px-3 bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg text-xs font-semibold transition"
                  title="View Embed Code"
                >
                  <Code2 className="w-3.5 h-3.5" />
                  Embed
                </button>

                <button
                  onClick={() => handleRotateToken(src.id)}
                  disabled={actionInProgressId === src.id}
                  className="p-1.5 bg-white border border-gray-200 hover:bg-rose-50 hover:border-rose-200 hover:text-rose-600 text-gray-500 rounded-lg transition"
                  title="Rotate Token"
                >
                  <Key className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}

          {sources.length === 0 && !loading && (
            <div className="col-span-full py-16 text-center bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
              <Radio className="w-10 h-10 text-gray-300 mx-auto mb-3" />
              <h3 className="text-base font-bold text-gray-900 mb-1">No Lead Sources Configured</h3>
              <p className="text-xs text-gray-500 max-w-md mx-auto mb-5">
                Connect your first lead source to start capturing prospects from websites, webhooks, or advertising campaigns.
              </p>
              <button
                onClick={() => setCreateModalOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800 transition"
              >
                <Plus className="w-4 h-4" /> Create First Source
              </button>
            </div>
          )}
        </div>

        {/* Create Source Modal */}
        {createModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-md p-6 animate-in zoom-in-95">
              <h3 className="text-lg font-bold text-gray-900 mb-1">Create Lead Source</h3>
              <p className="text-xs text-gray-500 mb-4">Set up a named origin for incoming prospects.</p>

              <form onSubmit={handleCreateSource} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Source Name *</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Website Contact Form or FB Dubai Campaign"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Channel *</label>
                  <select
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-gray-900 bg-white"
                  >
                    <option value="WEBSITE">WEBSITE — Embeddable Form & Landing Page</option>
                    <option value="WEBHOOK">WEBHOOK — Inbound Webhook Endpoint</option>
                    <option value="META">META — Facebook / Instagram Lead Ads</option>
                    <option value="GOOGLE">GOOGLE — Google Ads Lead Forms</option>
                    <option value="API">API — Custom REST Ingestion</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Description (Optional)</label>
                  <textarea
                    rows={2}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Context or internal notes about this channel"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-gray-900"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-4 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={() => setCreateModalOpen(false)}
                    className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-900"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800"
                  >
                    Create Source
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Embed Code Modal */}
        {embedModalSource && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-200 w-full max-w-lg p-6 animate-in zoom-in-95">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-base font-bold text-gray-900">Integration Snippets</h3>
                <button
                  onClick={() => setEmbedModalSource(null)}
                  className="text-gray-400 hover:text-gray-600 text-sm font-bold"
                >
                  ✕
                </button>
              </div>
              <p className="text-xs text-gray-500 mb-4">
                Embed this form on your customer website or send leads programmatically via cURL / REST API.
              </p>

              {/* Script Snippet */}
              <div className="mb-4">
                <div className="flex items-center justify-between text-xs font-semibold text-gray-700 mb-1.5">
                  <span>HTML Embed Code (Script)</span>
                  <button
                    onClick={() => copyToClipboard(embedModalSource.script_snippet, 'snippet')}
                    className="text-[11px] text-gray-900 font-bold hover:underline inline-flex items-center gap-1"
                  >
                    {copiedField === 'snippet' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    {copiedField === 'snippet' ? 'Copied' : 'Copy Snippet'}
                  </button>
                </div>
                <pre className="p-3 bg-gray-950 text-emerald-400 font-mono text-[11px] rounded-lg overflow-x-auto whitespace-pre-wrap">
                  {embedModalSource.script_snippet}
                </pre>
              </div>

              {/* cURL Example */}
              <div className="mb-5">
                <div className="flex items-center justify-between text-xs font-semibold text-gray-700 mb-1.5">
                  <span>Direct REST Ingestion (cURL)</span>
                  <button
                    onClick={() => copyToClipboard(embedModalSource.curl_example, 'curl')}
                    className="text-[11px] text-gray-900 font-bold hover:underline inline-flex items-center gap-1"
                  >
                    {copiedField === 'curl' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    {copiedField === 'curl' ? 'Copied' : 'Copy cURL'}
                  </button>
                </div>
                <pre className="p-3 bg-gray-950 text-gray-200 font-mono text-[11px] rounded-lg overflow-x-auto whitespace-pre-wrap">
                  {embedModalSource.curl_example}
                </pre>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={() => setEmbedModalSource(null)}
                  className="px-4 py-2 bg-gray-900 text-white rounded-lg text-xs font-semibold hover:bg-gray-800"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
