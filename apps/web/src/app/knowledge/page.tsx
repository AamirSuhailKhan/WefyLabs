'use client';

/**
 * Knowledge Intelligence Platform — Broker & Admin Page
 * ======================================================
 * Full knowledge management workflow matching the WefyLabs Broker Dashboard design system:
 * Ingest → Process → Review → Verify → Publish → Monitor
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BookOpen, Upload, Search, AlertTriangle, CheckCircle2, Clock,
  FileText, Trash2, RefreshCw, Eye, ChevronRight, X, Filter,
  Database, Zap, Shield, BarChart3, GitBranch, ArrowUpCircle,
  Archive, Loader2, CheckSquare, Activity, FileSearch,
} from 'lucide-react';
import { api, KnowledgeDocument } from '@/lib/api-client';
import DashboardNav from '@/components/shared/DashboardNav';

// ─── Status badge helper ──────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  UPLOADED:       'bg-blue-100 text-blue-800 border-blue-200',
  PROCESSING:     'bg-amber-100 text-amber-800 border-amber-200',
  PARSED:         'bg-purple-100 text-purple-800 border-purple-200',
  EXTRACTED:      'bg-indigo-100 text-indigo-800 border-indigo-200',
  INDEXING:       'bg-cyan-100 text-cyan-800 border-cyan-200',
  INDEXED:        'bg-sky-100 text-sky-800 border-sky-200',
  PUBLISHED:      'bg-emerald-100 text-emerald-800 border-emerald-200',
  FAILED:         'bg-red-100 text-red-800 border-red-200',
  ARCHIVED:       'bg-gray-100 text-gray-700 border-gray-200',
  EXPIRED:        'bg-orange-100 text-orange-800 border-orange-200',
  PENDING_REVIEW: 'bg-yellow-100 text-yellow-800 border-yellow-200',
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-700 border-gray-200';
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase border inline-flex items-center gap-1 ${cls}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

// ─── Knowledge type pills ─────────────────────────────────────────────────────

const KNOWLEDGE_TYPES = [
  'PROJECT', 'PROPERTY', 'DEVELOPER', 'UNIT', 'PRICE', 'AVAILABILITY',
  'PAYMENT_PLAN', 'AMENITY', 'LOCATION', 'FAQ', 'POLICY', 'LEGAL',
  'SALES_GUIDE', 'MARKETING', 'INTERNAL', 'OTHER',
];

const TYPE_COLORS: Record<string, string> = {
  PRICE:        'text-[#0D9488]',
  AVAILABILITY: 'text-[#2563EB]',
  PAYMENT_PLAN: 'text-[#7C3AED]',
  FAQ:          'text-[#D97706]',
  POLICY:       'text-[#DC2626]',
  LEGAL:        'text-[#EA580C]',
  PROJECT:      'text-[#0891B2]',
  PROPERTY:     'text-[#4F46E5]',
};

// ─── Tab definitions ──────────────────────────────────────────────────────────

type Tab = 'overview' | 'documents' | 'search' | 'conflicts' | 'settings';

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: 'overview',   label: 'Overview',   icon: BarChart3   },
  { id: 'documents',  label: 'Documents',  icon: FileText    },
  { id: 'search',     label: 'Search',     icon: FileSearch  },
  { id: 'conflicts',  label: 'Conflicts',  icon: GitBranch   },
  { id: 'settings',   label: 'Settings',   icon: Shield      },
];

// ─── Main component ───────────────────────────────────────────────────────────

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [health, setHealth] = useState<any>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [totalDocs, setTotalDocs] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [conflicts, setConflicts] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [policies, setPolicies] = useState<any[]>([]);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingConflicts, setLoadingConflicts] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Search tab state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchLatency, setSearchLatency] = useState(0);

  // Upload form state
  const [uploadForm, setUploadForm] = useState({
    title: '',
    knowledge_type: 'PROJECT',
    language: 'en',
    visibility: 'INTERNAL',
    description: '',
  });

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const h = await api.knowledge.getHealth();
      setHealth(h);
    } catch {
      setHealth(null);
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const res = await api.knowledge.listDocuments({
        status: statusFilter || undefined,
        knowledge_type: typeFilter || undefined,
        page,
        limit: 20,
      });
      setDocuments(res.documents);
      setTotalDocs(res.total);
      setTotalPages(res.total_pages);
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  }, [statusFilter, typeFilter, page]);

  const loadConflicts = useCallback(async () => {
    setLoadingConflicts(true);
    try {
      const res = await api.knowledge.listConflicts({ resolution_status: 'OPEN' });
      setConflicts(res);
    } catch {
      setConflicts([]);
    } finally {
      setLoadingConflicts(false);
    }
  }, []);

  const loadPolicies = useCallback(async () => {
    try {
      const res = await api.knowledge.listFreshnessPolicies();
      setPolicies(res);
    } catch {
      setPolicies([]);
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const res = await api.knowledge.listJobs({ status: 'failed' });
      setJobs(res);
    } catch {
      setJobs([]);
    }
  }, []);

  useEffect(() => { loadHealth(); }, [loadHealth]);
  useEffect(() => { if (activeTab === 'documents') { loadDocuments(); } }, [activeTab, loadDocuments, statusFilter, typeFilter, page]);
  useEffect(() => { if (activeTab === 'conflicts') { loadConflicts(); } }, [activeTab, loadConflicts]);
  useEffect(() => { if (activeTab === 'settings') { loadPolicies(); loadJobs(); } }, [activeTab, loadPolicies, loadJobs]);

  // ── Upload handler ────────────────────────────────────────────────────────

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    if (!uploadForm.title.trim()) { setUploadMsg('Title is required.'); return; }

    setUploading(true);
    setUploadMsg('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', uploadForm.title);
      fd.append('knowledge_type', uploadForm.knowledge_type);
      fd.append('language', uploadForm.language);
      fd.append('visibility', uploadForm.visibility);
      fd.append('description', uploadForm.description);

      const res = await api.knowledge.uploadDocument(fd);
      setUploadMsg(
        res.is_duplicate
          ? `⚠ Duplicate detected. Existing ID: ${res.document_id}`
          : `✓ Uploaded! Processing job: ${res.job_id || 'queued'}`
      );
      if (!res.is_duplicate) {
        setUploadForm({ title: '', knowledge_type: 'PROJECT', language: 'en', visibility: 'INTERNAL', description: '' });
        if (fileRef.current) fileRef.current.value = '';
        loadHealth();
        if (activeTab === 'documents') loadDocuments();
      }
    } catch (err: any) {
      setUploadMsg(`✗ Upload failed: ${err.message || 'Unknown error'}`);
    } finally {
      setUploading(false);
    }
  };

  // ── Document actions ──────────────────────────────────────────────────────

  const handlePublish = async (docId: string) => {
    setActionLoading(docId + ':publish');
    try {
      await api.knowledge.publishDocument(docId);
      await loadDocuments();
      setSelectedDoc(null);
    } catch { } finally { setActionLoading(null); }
  };

  const handleReindex = async (docId: string) => {
    setActionLoading(docId + ':reindex');
    try {
      await api.knowledge.reindexDocument(docId);
    } catch { } finally { setActionLoading(null); }
  };

  const handleArchive = async (docId: string) => {
    setActionLoading(docId + ':archive');
    try {
      await api.knowledge.archiveDocument(docId);
      await loadDocuments();
      setSelectedDoc(null);
    } catch { } finally { setActionLoading(null); }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document? This will remove all embeddings and index entries.')) return;
    setActionLoading(docId + ':delete');
    try {
      await api.knowledge.deleteDocument(docId, 'admin_delete');
      await loadDocuments();
      setSelectedDoc(null);
    } catch { } finally { setActionLoading(null); }
  };

  const handleFullReindex = async () => {
    if (!confirm('Queue a full reindex for all published documents? This may take time.')) return;
    try {
      const res = await api.knowledge.fullReindex();
      alert(`Full reindex queued: ${res.documents_queued} documents`);
    } catch { }
  };

  // ── Search handler ────────────────────────────────────────────────────────

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults([]);
    try {
      const res = await api.knowledge.search({
        query: searchQuery,
        top_k: 10,
        rerank_top_n: 5,
        channel: 'internal',
      });
      setSearchResults(res.results);
      setSearchLatency(res.retrieval_latency_ms);
    } catch { } finally { setSearching(false); }
  };

  // ── Conflict resolution ───────────────────────────────────────────────────

  const handleResolveConflict = async (conflictId: string, winningFactId: string) => {
    try {
      await api.knowledge.resolveConflict(conflictId, winningFactId, 'Resolved via admin UI');
      await loadConflicts();
    } catch { }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      {/* Fixed Navigation Bar */}
      <DashboardNav />

      <div className="pt-16">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

          {/* ── Page Header ── */}
          <div className="py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
            <div>
              <h1
                className="text-[28px] font-bold text-[#1A1A1A] tracking-tight flex items-center gap-2.5"
                style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
              >
                <BookOpen className="w-7 h-7 text-[#0D9488]" />
                KNOWLEDGE INTELLIGENCE PLATFORM
              </h1>
              <p className="text-[14px] text-[#6B6B6B] mt-1" style={{ fontFamily: 'Inter, sans-serif' }}>
                Ingest, process, verify, publish, and monitor real estate documents for AI qualification.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {health && (
                <span className={`flex items-center gap-1.5 text-xs font-bold px-3 py-1.5 rounded-full border ${
                  health.status === 'healthy'
                    ? 'bg-[#CCFBF1] text-[#0F766E] border-[#99F6E4]'
                    : 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]'
                }`}>
                  <Activity className="w-3.5 h-3.5" />
                  {health.status?.toUpperCase()}
                </span>
              )}
              <button
                id="knowledge-full-reindex-btn"
                onClick={handleFullReindex}
                className="flex items-center gap-1.5 text-xs bg-[#FAF7F2] hover:bg-[#F0EDE8] text-[#1A1A1A] px-3.5 py-2 rounded-lg border border-[#D4D0C8] font-semibold transition-all shadow-sm"
              >
                <RefreshCw className="w-3.5 h-3.5 text-[#6B6B6B]" />
                Full Reindex
              </button>
            </div>
          </div>

          {/* ── Health Banner ── */}
          {!loadingHealth && health && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              {[
                { label: 'TOTAL DOCS',     value: health.total_documents,     icon: Database,      color: '#1A1A1A' },
                { label: 'PUBLISHED',      value: health.published_documents, icon: CheckCircle2, color: '#0D9488' },
                { label: 'INDEXED CHUNKS', value: health.indexed_chunks,      icon: Zap,           color: '#4338CA' },
                { label: 'FAILED',         value: health.failed_documents,    icon: AlertTriangle, color: '#DC2626' },
                { label: 'CONFLICTS',      value: health.open_conflicts,      icon: GitBranch,     color: '#B45309' },
                { label: 'EMBEDDING',      value: health.embedding_provider,  icon: Activity,      color: '#2563EB' },
              ].map(({ label, value, icon: Icon, color }, idx) => (
                <motion.div
                  key={label}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: idx * 0.03 }}
                  className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-4 shadow-sm"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-[#6B6B6B] font-bold uppercase tracking-wider" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {label}
                    </span>
                    <Icon className="w-4 h-4" style={{ color }} />
                  </div>
                  <div className="text-xl font-extrabold capitalize" style={{ color, fontFamily: 'JetBrains Mono, monospace' }}>
                    {typeof value === 'number' ? value.toLocaleString() : value || '—'}
                  </div>
                </motion.div>
              ))}
            </div>
          )}

          {/* ── Tabs ── */}
          <div className="flex gap-2 border-b border-[#D4D0C8] pb-0 overflow-x-auto">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                id={`knowledge-tab-${id}`}
                onClick={() => setActiveTab(id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-t-lg whitespace-nowrap transition-all ${
                  activeTab === id
                    ? 'bg-[#1A1A1A] text-white shadow-sm'
                    : 'bg-[#FAF7F2] border border-[#D4D0C8] border-b-0 text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]'
                }`}
                style={{ fontFamily: 'Inter, sans-serif' }}
              >
                <Icon className="w-4 h-4" />
                {label}
                {id === 'conflicts' && conflicts.length > 0 && (
                  <span className="bg-[#FEF3C7] text-[#B45309] text-[10px] font-extrabold px-2 py-0.5 rounded-full border border-[#FDE68A]">
                    {conflicts.length}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB: OVERVIEW                                                     */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          <AnimatePresence mode="wait">
            {activeTab === 'overview' && (
              <motion.div
                key="overview"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="grid grid-cols-1 lg:grid-cols-2 gap-6"
              >
                {/* Upload Panel */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-sm">
                  <h2 className="font-bold text-[#1A1A1A] text-base flex items-center gap-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                    <Upload className="w-4 h-4 text-[#0D9488]" />
                    Upload Knowledge Document
                  </h2>
                  <form id="knowledge-upload-form" onSubmit={handleUpload} className="space-y-3.5">
                    <div>
                      <label className="text-[11px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 block" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                        Title *
                      </label>
                      <input
                        id="knowledge-upload-title"
                        type="text"
                        value={uploadForm.title}
                        onChange={e => setUploadForm(f => ({ ...f, title: e.target.value }))}
                        placeholder="e.g., Emaar Creek Harbour Brochure v2"
                        className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3.5 py-2 text-sm text-[#1A1A1A] placeholder:text-[#A0A0A0] focus:outline-none focus:border-[#1A1A1A]"
                        required
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[11px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 block" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                          Knowledge Type
                        </label>
                        <select
                          id="knowledge-upload-type"
                          value={uploadForm.knowledge_type}
                          onChange={e => setUploadForm(f => ({ ...f, knowledge_type: e.target.value }))}
                          className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3.5 py-2 text-sm text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A]"
                        >
                          {KNOWLEDGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 block" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                          Visibility
                        </label>
                        <select
                          id="knowledge-upload-visibility"
                          value={uploadForm.visibility}
                          onChange={e => setUploadForm(f => ({ ...f, visibility: e.target.value }))}
                          className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3.5 py-2 text-sm text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A]"
                        >
                          {['INTERNAL', 'PUBLIC', 'CUSTOMER', 'MANAGER_ONLY', 'ADMIN_ONLY'].map(v => (
                            <option key={v} value={v}>{v}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="text-[11px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 block" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                        Description
                      </label>
                      <textarea
                        id="knowledge-upload-description"
                        value={uploadForm.description}
                        onChange={e => setUploadForm(f => ({ ...f, description: e.target.value }))}
                        placeholder="Optional: describe this document's content and scope"
                        rows={2}
                        className="w-full bg-white border border-[#D4D0C8] rounded-lg px-3.5 py-2 text-sm text-[#1A1A1A] placeholder:text-[#A0A0A0] resize-none focus:outline-none focus:border-[#1A1A1A]"
                      />
                    </div>

                    <div>
                      <label className="text-[11px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 block" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                        File (PDF, DOCX, TXT, CSV, MD, HTML)
                      </label>
                      <input
                        id="knowledge-upload-file"
                        ref={fileRef}
                        type="file"
                        accept=".pdf,.docx,.doc,.txt,.csv,.xlsx,.md,.html,.htm"
                        className="w-full text-sm text-[#4A4A4A] file:mr-3 file:py-2 file:px-3.5 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-[#1A1A1A] file:text-white hover:file:bg-[#333333] cursor-pointer"
                      />
                    </div>

                    {uploadMsg && (
                      <p className={`text-xs font-semibold ${uploadMsg.startsWith('✓') ? 'text-[#0D9488]' : 'text-[#B45309]'}`}>
                        {uploadMsg}
                      </p>
                    )}

                    <button
                      id="knowledge-upload-submit"
                      type="submit"
                      disabled={uploading}
                      className="w-full flex items-center justify-center gap-2 bg-[#1A1A1A] hover:bg-[#333333] disabled:opacity-60 text-white text-sm font-semibold py-2.5 rounded-lg transition-all shadow-sm"
                    >
                      {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {uploading ? 'Uploading…' : 'Upload & Process'}
                    </button>
                  </form>
                </div>

                {/* Admin Pipeline Guide */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-sm">
                  <h2 className="font-bold text-[#1A1A1A] text-base flex items-center gap-2" style={{ fontFamily: 'Inter, sans-serif' }}>
                    <ChevronRight className="w-4 h-4 text-[#0D9488]" />
                    Admin Workflow & Pipeline
                  </h2>
                  <div className="space-y-2">
                    {[
                      { step: '1', label: 'Upload Document', desc: 'PDF, DOCX, TXT, CSV, MD, HTML', state: 'completed' },
                      { step: '2', label: 'Parse & OCR',     desc: 'Text extraction with confidence scoring', state: 'completed' },
                      { step: '3', label: 'Extract Facts',    desc: 'Price, area, bedrooms, payment plans', state: 'completed' },
                      { step: '4', label: 'Chunk & Embed',   desc: 'Semantic chunks + vector embeddings', state: 'completed' },
                      { step: '5', label: 'Review Conflicts', desc: 'Resolve conflicting price/fact claims', state: 'pending' },
                      { step: '6', label: 'Publish',         desc: 'Make live for customer-facing AI', state: 'pending' },
                      { step: '7', label: 'Monitor',         desc: 'Track freshness, usage, feedback', state: 'pending' },
                    ].map(({ step, label, desc, state }) => (
                      <div key={step} className="flex items-start gap-3 p-3 rounded-xl bg-white border border-[#D4D0C8]">
                        <span className={`text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center shrink-0 ${
                          state === 'completed' ? 'bg-[#CCFBF1] text-[#0F766E]' :
                          state === 'current' ? 'bg-[#0D9488] text-white' :
                          state === 'warning' ? 'bg-[#FEF3C7] text-[#B45309]' :
                          state === 'error' ? 'bg-[#FEE2E2] text-[#DC2626]' :
                          'bg-[#F0EDE8] text-[#6B6B6B]'
                        }`}>
                          {state === 'completed' ? '✓' : step}
                        </span>
                        <div>
                          <p className="text-xs font-bold text-[#1A1A1A]">{label}</p>
                          <p className="text-[12px] text-[#6B6B6B]">{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 p-3.5 rounded-xl bg-[#FEF3C7] border border-[#FDE68A]">
                    <p className="text-[12px] text-[#B45309] font-semibold">
                      ⚠ Only PUBLISHED documents serve customer-facing AI.
                      Internal uploaded documents require explicit publish action.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* ══════════════════════════════════════════════════════════════════ */}
            {/* TAB: DOCUMENTS                                                    */}
            {/* ══════════════════════════════════════════════════════════════════ */}
            {activeTab === 'documents' && (
              <motion.div
                key="documents"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="space-y-4"
              >
                {/* Filters */}
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-1.5 text-xs text-[#6B6B6B] font-bold">
                    <Filter className="w-3.5 h-3.5" />
                    <span>Filters:</span>
                  </div>
                  <select
                    id="knowledge-filter-status"
                    value={statusFilter}
                    onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
                    className="bg-white border border-[#D4D0C8] rounded-lg px-3 py-1.5 text-xs text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A]"
                  >
                    <option value="">All Statuses</option>
                    {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <select
                    id="knowledge-filter-type"
                    value={typeFilter}
                    onChange={e => { setTypeFilter(e.target.value); setPage(1); }}
                    className="bg-white border border-[#D4D0C8] rounded-lg px-3 py-1.5 text-xs text-[#1A1A1A] focus:outline-none focus:border-[#1A1A1A]"
                  >
                    <option value="">All Types</option>
                    {KNOWLEDGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <button
                    id="knowledge-refresh-docs"
                    onClick={loadDocuments}
                    className="flex items-center gap-1.5 text-xs text-[#4A4A4A] bg-[#FAF7F2] hover:bg-[#F0EDE8] px-3 py-1.5 rounded-lg border border-[#D4D0C8] font-semibold transition-colors shadow-sm"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingDocs ? 'animate-spin' : ''}`} />
                    Refresh
                  </button>
                  <span className="ml-auto text-xs text-[#6B6B6B] font-mono">{totalDocs} documents</span>
                </div>

                {/* Document Table */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl overflow-hidden shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#F5F0EB] text-[#6B6B6B] uppercase font-bold border-b border-[#D4D0C8]" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                        <tr>
                          <th className="py-3 px-4">Title</th>
                          <th className="py-3 px-4">Type</th>
                          <th className="py-3 px-4">Status</th>
                          <th className="py-3 px-4">Pages</th>
                          <th className="py-3 px-4">Chunks</th>
                          <th className="py-3 px-4">Facts</th>
                          <th className="py-3 px-4">Conflicts</th>
                          <th className="py-3 px-4">Uploaded</th>
                          <th className="py-3 px-4">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F0EDE8]">
                        {loadingDocs ? (
                          <tr>
                            <td colSpan={9} className="py-10 text-center">
                              <Loader2 className="w-5 h-5 animate-spin text-[#0D9488] mx-auto" />
                            </td>
                          </tr>
                        ) : documents.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="py-10 text-center text-[#6B6B6B]">
                              No documents found. Upload your first document above.
                            </td>
                          </tr>
                        ) : documents.map(doc => (
                          <tr key={doc.id} className="hover:bg-[#F5F0EB]/60 transition-colors">
                            <td className="py-3 px-4">
                              <div className="font-semibold text-[#1A1A1A] max-w-[200px] truncate" title={doc.title}>
                                {doc.title}
                              </div>
                              {doc.file_name && (
                                <div className="text-[#6B6B6B] text-[10px] truncate max-w-[200px]">{doc.file_name}</div>
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <span className={`font-bold ${TYPE_COLORS[doc.knowledge_type] || 'text-[#4A4A4A]'}`}>
                                {doc.knowledge_type}
                              </span>
                            </td>
                            <td className="py-3 px-4"><StatusBadge status={doc.status} /></td>
                            <td className="py-3 px-4 text-[#4A4A4A] font-mono">{doc.total_pages || '—'}</td>
                            <td className="py-3 px-4 text-[#4A4A4A] font-mono">{doc.total_chunks || '—'}</td>
                            <td className="py-3 px-4 text-[#4A4A4A] font-mono">{doc.total_facts || '—'}</td>
                            <td className="py-3 px-4">
                              {doc.total_conflicts > 0 ? (
                                <span className="text-[#B45309] font-bold">{doc.total_conflicts}</span>
                              ) : <span className="text-[#A0A0A0]">0</span>}
                            </td>
                            <td className="py-3 px-4 text-[#6B6B6B]">
                              {new Date(doc.created_at).toLocaleDateString()}
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-1">
                                <button
                                  id={`knowledge-view-${doc.id}`}
                                  onClick={() => setSelectedDoc(doc)}
                                  className="p-1.5 rounded hover:bg-[#EAE6DF] text-[#6B6B6B] hover:text-[#1A1A1A] transition-colors"
                                  title="View details"
                                >
                                  <Eye className="w-3.5 h-3.5" />
                                </button>
                                {['INDEXED', 'PENDING_REVIEW'].includes(doc.status) && (
                                  <button
                                    id={`knowledge-publish-${doc.id}`}
                                    onClick={() => handlePublish(doc.id)}
                                    disabled={actionLoading === doc.id + ':publish'}
                                    className="p-1.5 rounded hover:bg-[#CCFBF1] text-[#0D9488] hover:text-[#0F766E] transition-colors disabled:opacity-50"
                                    title="Publish"
                                  >
                                    {actionLoading === doc.id + ':publish'
                                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                      : <ArrowUpCircle className="w-3.5 h-3.5" />}
                                  </button>
                                )}
                                <button
                                  id={`knowledge-reindex-${doc.id}`}
                                  onClick={() => handleReindex(doc.id)}
                                  disabled={actionLoading === doc.id + ':reindex'}
                                  className="p-1.5 rounded hover:bg-purple-100 text-purple-700 transition-colors disabled:opacity-50"
                                  title="Reindex"
                                >
                                  {actionLoading === doc.id + ':reindex'
                                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    : <RefreshCw className="w-3.5 h-3.5" />}
                                </button>
                                <button
                                  id={`knowledge-delete-${doc.id}`}
                                  onClick={() => handleDelete(doc.id)}
                                  disabled={actionLoading === doc.id + ':delete'}
                                  className="p-1.5 rounded hover:bg-red-100 text-red-600 transition-colors disabled:opacity-50"
                                  title="Delete"
                                >
                                  {actionLoading === doc.id + ':delete'
                                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                    : <Trash2 className="w-3.5 h-3.5" />}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between px-4 py-3 border-t border-[#D4D0C8]">
                      <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="text-xs text-[#4A4A4A] hover:text-[#1A1A1A] disabled:opacity-40 px-3 py-1.5 rounded border border-[#D4D0C8] bg-white"
                      >
                        Previous
                      </button>
                      <span className="text-xs text-[#6B6B6B]">Page {page} of {totalPages}</span>
                      <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="text-xs text-[#4A4A4A] hover:text-[#1A1A1A] disabled:opacity-40 px-3 py-1.5 rounded border border-[#D4D0C8] bg-white"
                      >
                        Next
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* ══════════════════════════════════════════════════════════════════ */}
            {/* TAB: SEARCH                                                       */}
            {/* ══════════════════════════════════════════════════════════════════ */}
            {activeTab === 'search' && (
              <motion.div
                key="search"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="space-y-4"
              >
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-sm">
                  <h2 className="font-bold text-[#1A1A1A] text-base flex items-center gap-2">
                    <Search className="w-4 h-4 text-[#0D9488]" />
                    Hybrid Knowledge Search
                    <span className="text-xs text-[#6B6B6B] font-normal">
                      (Vector + Keyword + RRF fusion + Reranking)
                    </span>
                  </h2>

                  <form id="knowledge-search-form" onSubmit={handleSearch} className="flex gap-3">
                    <input
                      id="knowledge-search-input"
                      type="text"
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      placeholder='e.g., "payment plan for 3 BHK in Creek Harbour" or "handover date"'
                      className="flex-1 bg-white border border-[#D4D0C8] rounded-lg px-4 py-2.5 text-sm text-[#1A1A1A] placeholder:text-[#A0A0A0] focus:outline-none focus:border-[#1A1A1A]"
                    />
                    <button
                      id="knowledge-search-submit"
                      type="submit"
                      disabled={searching}
                      className="flex items-center gap-2 bg-[#1A1A1A] hover:bg-[#333333] disabled:opacity-60 text-white text-sm font-bold px-5 py-2.5 rounded-lg transition-all shadow-sm"
                    >
                      {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      Search
                    </button>
                  </form>

                  {searchResults.length > 0 && (
                    <div className="space-y-3 pt-2">
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-[#6B6B6B] font-mono">
                          {searchResults.length} results · {searchLatency}ms retrieval
                        </p>
                      </div>
                      {searchResults.map((r, i) => (
                        <div key={r.chunk_id} className="p-4 rounded-xl bg-white border border-[#D4D0C8] shadow-sm space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-[#0D9488]">#{i + 1}</span>
                              <span className="text-[11px] text-[#6B6B6B] bg-[#F5F0EB] px-2 py-0.5 rounded font-mono">{r.retrieval_method}</span>
                              <span className="text-xs text-[#0D9488] font-bold">
                                {(r.score * 100).toFixed(1)}% match
                              </span>
                            </div>
                            <span className="text-[10px] text-[#A0A0A0] font-mono">{r.chunk_id?.slice(0, 12)}…</span>
                          </div>
                          <p className="text-sm text-[#1A1A1A] leading-relaxed">{r.text}</p>
                          {r.metadata?.source_title && (
                            <p className="text-[11px] text-[#6B6B6B] font-medium pt-1">
                              Source: <span className="font-semibold text-[#1A1A1A]">{r.metadata.source_title}</span>
                              {r.metadata.page_number && ` · Page ${r.metadata.page_number}`}
                              {r.metadata.heading && ` · ${r.metadata.heading}`}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {!searching && searchQuery && searchResults.length === 0 && (
                    <div className="text-center py-8 text-[#6B6B6B] text-sm">
                      No results found. Try a different query or upload more documents.
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* ══════════════════════════════════════════════════════════════════ */}
            {/* TAB: CONFLICTS                                                    */}
            {/* ══════════════════════════════════════════════════════════════════ */}
            {activeTab === 'conflicts' && (
              <motion.div
                key="conflicts"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="space-y-4"
              >
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h2 className="font-bold text-[#1A1A1A] text-base flex items-center gap-2">
                      <GitBranch className="w-4 h-4 text-[#B45309]" />
                      Open Knowledge Conflicts
                    </h2>
                    <button
                      id="knowledge-refresh-conflicts"
                      onClick={loadConflicts}
                      className="text-xs text-[#6B6B6B] hover:text-[#1A1A1A] flex items-center gap-1 font-semibold"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${loadingConflicts ? 'animate-spin' : ''}`} />
                      Refresh
                    </button>
                  </div>

                  {loadingConflicts ? (
                    <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin text-[#B45309] mx-auto" /></div>
                  ) : conflicts.length === 0 ? (
                    <div className="py-10 text-center">
                      <CheckCircle2 className="w-8 h-8 text-[#0D9488] mx-auto mb-2" />
                      <p className="text-sm text-[#6B6B6B]">No open conflicts. Knowledge base is consistent.</p>
                    </div>
                  ) : conflicts.map(c => (
                    <div key={c.id} className="p-4 rounded-xl bg-white border border-[#FDE68A] shadow-sm space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[#B45309] uppercase tracking-wide font-mono">{c.fact_type} CONFLICT</span>
                        <span className="text-[10px] text-[#6B6B6B]">{new Date(c.created_at).toLocaleDateString()}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-[#EFF6FF] border border-[#BFDBFE]">
                          <p className="text-[10px] text-[#1E40AF] font-bold mb-1">FACT A</p>
                          <p className="text-sm font-bold text-[#1E3A8A]">{c.fact_a_value || '—'}</p>
                          <p className="text-[10px] text-[#3B82F6] font-semibold mt-1">Confidence: {(c.fact_a_confidence * 100).toFixed(0)}%</p>
                        </div>
                        <div className="p-3 rounded-lg bg-[#F5F3FF] border border-[#DDD6FE]">
                          <p className="text-[10px] text-[#5B21B6] font-bold mb-1">FACT B</p>
                          <p className="text-sm font-bold text-[#4C1D95]">{c.fact_b_value || '—'}</p>
                          <p className="text-[10px] text-[#7C3AED] font-semibold mt-1">Confidence: {(c.fact_b_confidence * 100).toFixed(0)}%</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          id={`knowledge-resolve-a-${c.id}`}
                          onClick={() => handleResolveConflict(c.id, c.fact_a_id)}
                          className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold py-2 rounded-lg bg-[#2563EB] hover:bg-[#1D4ED8] text-white transition-colors shadow-sm"
                        >
                          <CheckSquare className="w-3.5 h-3.5" />
                          Accept A
                        </button>
                        <button
                          id={`knowledge-resolve-b-${c.id}`}
                          onClick={() => handleResolveConflict(c.id, c.fact_b_id)}
                          className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold py-2 rounded-lg bg-[#7C3AED] hover:bg-[#6D28D9] text-white transition-colors shadow-sm"
                        >
                          <CheckSquare className="w-3.5 h-3.5" />
                          Accept B
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* ══════════════════════════════════════════════════════════════════ */}
            {/* TAB: SETTINGS                                                     */}
            {/* ══════════════════════════════════════════════════════════════════ */}
            {activeTab === 'settings' && (
              <motion.div
                key="settings"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="space-y-4"
              >
                {/* Freshness Policies */}
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-sm">
                  <h2 className="font-bold text-[#1A1A1A] text-base flex items-center gap-2">
                    <Clock className="w-4 h-4 text-[#0891B2]" />
                    Knowledge Freshness Policies
                  </h2>
                  {policies.length === 0 ? (
                    <p className="text-xs text-[#6B6B6B]">
                      No custom policies configured. Default system policies are active.
                    </p>
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-[#D4D0C8]">
                      <table className="w-full text-xs text-left bg-white">
                        <thead className="bg-[#F5F0EB] border-b border-[#D4D0C8] text-[#6B6B6B] uppercase font-bold font-mono">
                          <tr>
                            <th className="py-2.5 px-3">Knowledge Type</th>
                            <th className="py-2.5 px-3">Max Age (days)</th>
                            <th className="py-2.5 px-3">Warn At (days)</th>
                            <th className="py-2.5 px-3">Auto Expire</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#F0EDE8]">
                          {policies.map(p => (
                            <tr key={p.id} className="hover:bg-[#F5F0EB]/60">
                              <td className="py-2.5 px-3 font-bold text-[#0891B2]">{p.knowledge_type}</td>
                              <td className="py-2.5 px-3 text-[#1A1A1A] font-mono">{p.max_age_days}</td>
                              <td className="py-2.5 px-3 text-[#B45309] font-mono">{p.warn_at_days}</td>
                              <td className="py-2.5 px-3">
                                {p.auto_expire
                                  ? <span className="text-[#0D9488] font-bold">Yes</span>
                                  : <span className="text-[#A0A0A0]">No</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className="text-[11px] text-[#6B6B6B]">
                    Default policies: PRICE=30d · AVAILABILITY=7d · PAYMENT_PLAN=90d · FAQ=365d
                  </div>
                </div>

                {/* Provider Info */}
                {health && (
                  <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-3 shadow-sm">
                    <h2 className="font-bold text-[#1A1A1A] text-base flex items-center gap-2">
                      <Database className="w-4 h-4 text-[#7C3AED]" />
                      Provider Configuration
                    </h2>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        { label: 'Embedding Provider', value: health.embedding_provider },
                        { label: 'Vector Store',        value: health.vector_store_provider },
                      ].map(({ label, value }) => (
                        <div key={label} className="p-3 rounded-lg bg-white border border-[#D4D0C8]">
                          <p className="text-[10px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 font-mono">{label}</p>
                          <p className="text-sm font-bold text-[#7C3AED] capitalize">{value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Failed Jobs */}
                {jobs.length > 0 && (
                  <div className="bg-[#FAF7F2] border border-[#FCA5A5] rounded-2xl p-6 space-y-3 shadow-sm">
                    <h2 className="font-bold text-[#DC2626] text-base flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-[#DC2626]" />
                      Failed Processing Jobs ({jobs.length})
                    </h2>
                    {jobs.slice(0, 5).map(j => (
                      <div key={j.id} className="p-3.5 rounded-xl bg-[#FEE2E2] border border-[#FCA5A5]">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-[#B91C1C]">{j.job_type}</span>
                          <span className="text-[10px] text-[#6B6B6B]">{new Date(j.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-[11px] text-[#7F1D1D] mt-1 truncate">{j.last_error || 'Unknown error'}</p>
                        <p className="text-[10px] text-[#991B1B] font-mono">Document: {j.document_id?.slice(0, 12)}… · Retry #{j.retry_count}</p>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Document Detail Drawer ── */}
          <AnimatePresence>
            {selectedDoc && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-start justify-end"
                onClick={() => setSelectedDoc(null)}
              >
                <motion.div
                  initial={{ x: '100%' }}
                  animate={{ x: 0 }}
                  exit={{ x: '100%' }}
                  transition={{ type: 'spring', damping: 30, stiffness: 300 }}
                  className="w-full max-w-md h-full bg-[#FAF7F2] border-l border-[#D4D0C8] overflow-y-auto shadow-2xl"
                  onClick={e => e.stopPropagation()}
                >
                  <div className="p-6 space-y-5">
                    <div className="flex items-center justify-between border-b border-[#D4D0C8] pb-4">
                      <h3 className="font-bold text-[#1A1A1A] text-lg">Document Details</h3>
                      <button onClick={() => setSelectedDoc(null)} className="text-[#6B6B6B] hover:text-[#1A1A1A]">
                        <X className="w-5 h-5" />
                      </button>
                    </div>

                    <div className="space-y-2">
                      <p className="text-lg font-bold text-[#1A1A1A]">{selectedDoc.title}</p>
                      <StatusBadge status={selectedDoc.status} />
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {[
                        ['Knowledge Type', selectedDoc.knowledge_type],
                        ['Language',       selectedDoc.language],
                        ['Visibility',     selectedDoc.visibility],
                        ['Pages',          String(selectedDoc.total_pages || '—')],
                        ['Chunks',         String(selectedDoc.total_chunks || '—')],
                        ['Facts',          String(selectedDoc.total_facts || '—')],
                        ['Conflicts',      String(selectedDoc.total_conflicts || '—')],
                        ['OCR Used',       selectedDoc.ocr_used ? 'Yes' : 'No'],
                        ['AI Allowed',     selectedDoc.ai_allowed ? 'Yes' : 'No'],
                        ['Customer Facing', selectedDoc.customer_facing_allowed ? 'Yes' : 'No'],
                        ['Uploaded',       new Date(selectedDoc.created_at).toLocaleString()],
                        ['Published',      selectedDoc.published_at ? new Date(selectedDoc.published_at).toLocaleString() : '—'],
                      ].map(([label, value]) => (
                        <div key={label} className="p-2.5 rounded-lg bg-white border border-[#D4D0C8]">
                          <p className="text-[#6B6B6B] text-[10px] font-bold uppercase tracking-wider font-mono">{label}</p>
                          <p className="text-[#1A1A1A] font-semibold mt-0.5 truncate">{value}</p>
                        </div>
                      ))}
                    </div>

                    {selectedDoc.description && (
                      <div className="p-3.5 rounded-lg bg-white border border-[#D4D0C8]">
                        <p className="text-[10px] text-[#6B6B6B] font-bold uppercase tracking-wider mb-1 font-mono">DESCRIPTION</p>
                        <p className="text-xs text-[#4A4A4A] leading-relaxed">{selectedDoc.description}</p>
                      </div>
                    )}

                    {selectedDoc.processing_error && (
                      <div className="p-3.5 rounded-lg bg-[#FEE2E2] border border-[#FCA5A5]">
                        <p className="text-[10px] text-[#B91C1C] font-bold uppercase tracking-wider mb-1 font-mono">PROCESSING ERROR</p>
                        <p className="text-xs text-[#7F1D1D]">{selectedDoc.processing_error}</p>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-2 pt-2">
                      {['INDEXED', 'PENDING_REVIEW'].includes(selectedDoc.status) && (
                        <button
                          id={`knowledge-drawer-publish-${selectedDoc.id}`}
                          onClick={() => handlePublish(selectedDoc.id)}
                          disabled={!!actionLoading}
                          className="col-span-2 flex items-center justify-center gap-2 bg-[#0D9488] hover:bg-[#0F766E] disabled:opacity-50 text-white text-xs font-bold py-2.5 rounded-lg shadow-sm transition-all"
                        >
                          <ArrowUpCircle className="w-4 h-4" />
                          Publish Document
                        </button>
                      )}
                      <button
                        id={`knowledge-drawer-reindex-${selectedDoc.id}`}
                        onClick={() => handleReindex(selectedDoc.id)}
                        disabled={!!actionLoading}
                        className="flex items-center justify-center gap-1.5 bg-white hover:bg-[#F5F0EB] border border-[#D4D0C8] text-[#1A1A1A] text-xs font-bold py-2 rounded-lg transition-colors"
                      >
                        <RefreshCw className="w-3.5 h-3.5 text-[#6B6B6B]" /> Reindex
                      </button>
                      <button
                        id={`knowledge-drawer-archive-${selectedDoc.id}`}
                        onClick={() => handleArchive(selectedDoc.id)}
                        disabled={!!actionLoading}
                        className="flex items-center justify-center gap-1.5 bg-white hover:bg-[#F5F0EB] border border-[#D4D0C8] text-[#6B6B6B] text-xs font-bold py-2 rounded-lg transition-colors"
                      >
                        <Archive className="w-3.5 h-3.5" /> Archive
                      </button>
                      <button
                        id={`knowledge-drawer-delete-${selectedDoc.id}`}
                        onClick={() => handleDelete(selectedDoc.id)}
                        disabled={!!actionLoading}
                        className="col-span-2 flex items-center justify-center gap-1.5 bg-[#FEE2E2] hover:bg-[#FCA5A5]/40 border border-[#FCA5A5] text-[#B91C1C] text-xs font-bold py-2.5 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Delete (GDPR Pipeline)
                      </button>
                    </div>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

        </div>
      </div>
    </div>
  );
}
