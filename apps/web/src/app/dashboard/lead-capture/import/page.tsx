'use client';

import React, { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api-client';
import { LeadCaptureNav } from '@/components/lead-capture/LeadCaptureNav';
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Clock,
  Download,
  RefreshCw,
  ArrowRight,
  Database,
  Filter,
  Users,
  ShieldCheck,
  FileText
} from 'lucide-react';

interface ImportBatch {
  id: string;
  filename: string;
  total_records: number;
  processed_records: number;
  failed_records: number;
  duplicate_records?: number;
  status: string;
  started_at?: string;
  completed_at?: string;
}

interface ColumnPreview {
  headers: string[];
  rows: string[][];
  totalRows: number;
}

export default function LeadImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ColumnPreview | null>(null);
  const [uploading, setUploading] = useState(false);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadBatches();
  }, []);

  const loadBatches = async () => {
    setLoadingBatches(true);
    try {
      const res = await api.leadCapture.listImportBatches();
      setBatches(Array.isArray(res) ? res : []);
    } catch (err: any) {
      console.error('Failed to load batches:', err);
    } finally {
      setLoadingBatches(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (selectedFile: File) => {
    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    if (!['csv', 'xlsx', 'xls'].includes(ext || '')) {
      setErrorMessage('Please upload a valid CSV or Excel (.xlsx, .xls) file.');
      return;
    }
    setFile(selectedFile);
    setErrorMessage(null);
    setUploadSuccess(null);

    // If CSV, parse first few lines for preview
    if (ext === 'csv') {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result as string;
        if (!text) return;
        const lines = text.split(/\r?\n/).filter(line => line.trim().length > 0);
        if (lines.length > 0) {
          const headers = lines[0].split(',').map(h => h.trim().replace(/^["']|["']$/g, ''));
          const rows = lines.slice(1, 6).map(line =>
            line.split(',').map(col => col.trim().replace(/^["']|["']$/g, ''))
          );
          setPreview({
            headers,
            rows,
            totalRows: lines.length - 1
          });
        }
      };
      reader.readAsText(selectedFile.slice(0, 50000));
    } else {
      // Excel files can be uploaded directly
      setPreview(null);
    }
  };

  const handleStartImport = async () => {
    if (!file) return;
    setUploading(true);
    setErrorMessage(null);
    setUploadSuccess(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await api.leadCapture.uploadImportFile(formData);
      setUploadSuccess(`Batch "${res.filename}" accepted with ${res.total_records} records. Ingestion queued successfully.`);
      setFile(null);
      setPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadBatches();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to upload and initiate batch import.');
    } finally {
      setUploading(false);
    }
  };

  const downloadSampleCSV = () => {
    const csvContent =
      'Name,Phone,Email,Budget,Location,Property Type,Requirement,Source,Notes\n' +
      'Rahul Sharma,+919876543210,rahul.sharma@example.com,₹1.2 Cr,Whitefield,3 BHK,East facing high rise,Google Ads,Looking to buy in 30 days\n' +
      'Priya Nair,9876543211,priya.nair@example.com,75L,HSR Layout,2 BHK,Gated community,Property Portal,Prefers ready to move\n' +
      'Amit Verma,9876543212,amit.verma@example.com,2.5 Crore,Indiranagar,Villa,Independent plot,Referral,Wants site visit this weekend\n';

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'crm_leads_import_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <FileSpreadsheet className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Bulk Lead Import Wizard</h1>
              <p className="text-sm text-slate-400">
                Safely ingest leads at scale with automatic normalization, deduplication, and CRM attribution.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={downloadSampleCSV}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs font-semibold text-slate-300 hover:text-white transition"
          >
            <Download className="w-3.5 h-3.5" />
            Download Sample CSV
          </button>
          <button
            onClick={loadBatches}
            disabled={loadingBatches}
            className="p-2 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-400 hover:text-white transition"
            title="Refresh Batch History"
          >
            <RefreshCw className={`w-4 h-4 ${loadingBatches ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <LeadCaptureNav activeTab="import" />

      {/* Status Messages */}
      {uploadSuccess && (
        <div className="flex items-center gap-3 p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-xl text-sm text-emerald-300">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
          <span>{uploadSuccess}</span>
        </div>
      )}
      {errorMessage && (
        <div className="flex items-center gap-3 p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl text-sm text-rose-300">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Ingestion Rules / Feature Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-cyan-400 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-slate-200">Zero Silent Corruptions</h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Phones and emails are normalized to canonical international standards. Invalid formats are safely isolated to the DLQ.
            </p>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 flex items-start gap-3">
          <Filter className="w-5 h-5 text-indigo-400 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-slate-200">Identity Resolution & Deduplication</h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Existing leads are detected by phone/email. Re-engaged sources are attributed without creating duplicate CRM leads.
            </p>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800/80 flex items-start gap-3">
          <Database className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-slate-200">Asynchronous Batch Execution</h4>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              High-throughput queue ensures server stability even with 10,000+ row datasets.
            </p>
          </div>
        </div>
      </div>

      {/* Upload Zone */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-6">
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3 ${
            dragActive
              ? 'border-cyan-500 bg-cyan-500/10'
              : file
              ? 'border-emerald-500/50 bg-emerald-950/20'
              : 'border-slate-800 hover:border-slate-700 bg-slate-950/50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400">
            {file ? (
              <FileSpreadsheet className="w-7 h-7 text-emerald-400" />
            ) : (
              <UploadCloud className="w-7 h-7 text-cyan-400" />
            )}
          </div>

          <div>
            {file ? (
              <div>
                <p className="text-sm font-semibold text-emerald-300">{file.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {(file.size / 1024).toFixed(1)} KB — Click or drag to change file
                </p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-slate-200">
                  Drop your CSV or Excel file here, or <span className="text-cyan-400 underline">browse</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">Supports UTF-8 CSV, .xlsx, .xls up to 25 MB</p>
              </div>
            )}
          </div>
        </div>

        {/* CSV Preview Section */}
        {preview && (
          <div className="space-y-3 bg-slate-950/70 border border-slate-800/80 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-semibold text-slate-200">
                  Pre-flight Preview (~{preview.totalRows} records detected)
                </h3>
              </div>
              <span className="text-xs text-slate-500">First 5 rows displayed</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/40 text-slate-400">
                    {preview.headers.map((h, i) => (
                      <th key={i} className="py-2 px-3 font-semibold">
                        <span className="inline-block px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] mr-1">
                          Col {i + 1}
                        </span>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {preview.rows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-slate-900/30">
                      {row.map((val, cIdx) => (
                        <td key={cIdx} className="py-2 px-3 text-slate-300 truncate max-w-xs font-mono text-[11px]">
                          {val || <span className="text-slate-600">—</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="flex justify-end items-center gap-3">
          {file && (
            <button
              onClick={() => {
                setFile(null);
                setPreview(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleStartImport}
            disabled={!file || uploading}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold shadow-lg transition ${
              file && !uploading
                ? 'bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-cyan-500/20'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
            }`}
          >
            {uploading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Ingesting File & Dispatching Pipeline...
              </>
            ) : (
              <>
                <UploadCloud className="w-4 h-4" />
                Start Lead Import
                <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Batch Ingestion History */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200">Import Batch History</h3>
          </div>
          <span className="text-xs text-slate-500">
            {batches.length} {batches.length === 1 ? 'batch' : 'batches'} recorded
          </span>
        </div>

        {loadingBatches ? (
          <div className="py-12 flex justify-center items-center text-slate-500 text-xs gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
            Loading import batches...
          </div>
        ) : batches.length === 0 ? (
          <div className="text-center py-10 border border-dashed border-slate-800 rounded-xl">
            <FileSpreadsheet className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-xs text-slate-400 font-medium">No lead import batches run yet</p>
            <p className="text-[11px] text-slate-500 mt-1">Upload a CSV or Excel file above to start your first bulk import.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                  <th className="py-3 px-4 font-semibold">Filename</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Total Records</th>
                  <th className="py-3 px-4 font-semibold">Processed</th>
                  <th className="py-3 px-4 font-semibold">Duplicates</th>
                  <th className="py-3 px-4 font-semibold">Failed</th>
                  <th className="py-3 px-4 font-semibold">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {batches.map((b) => {
                  const isSuccess = b.status === 'completed' || b.status === 'success';
                  const isProcessing = b.status === 'processing' || b.status === 'in_progress';
                  const isFailed = b.status === 'failed';

                  return (
                    <tr key={b.id} className="hover:bg-slate-900/40 transition">
                      <td className="py-3 px-4 font-medium text-slate-200 flex items-center gap-2">
                        <FileSpreadsheet className="w-4 h-4 text-slate-400" />
                        <span className="truncate max-w-xs">{b.filename}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                            isSuccess
                              ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-800/80'
                              : isProcessing
                              ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-800/80'
                              : isFailed
                              ? 'bg-rose-950/80 text-rose-300 border border-rose-800/80'
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {isSuccess && <CheckCircle2 className="w-3 h-3" />}
                          {isProcessing && <RefreshCw className="w-3 h-3 animate-spin" />}
                          {isFailed && <AlertCircle className="w-3 h-3" />}
                          {b.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-300 font-mono">{b.total_records}</td>
                      <td className="py-3 px-4 text-emerald-400 font-mono">{b.processed_records}</td>
                      <td className="py-3 px-4 text-amber-400 font-mono">{b.duplicate_records || 0}</td>
                      <td className="py-3 px-4 text-rose-400 font-mono">{b.failed_records}</td>
                      <td className="py-3 px-4 text-slate-500">
                        {b.started_at ? new Date(b.started_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
