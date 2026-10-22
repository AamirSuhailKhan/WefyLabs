'use client';

import React, { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api-client';
import { LeadCaptureNav } from '@/components/lead-capture/LeadCaptureNav';
import { PageContainer } from '@/components/ui/PageContainer';
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
    <PageContainer className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#2C4BFB]/10 text-[#2C4BFB] border border-[#2C4BFB]/20 flex items-center justify-center shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-[#1A1A1A]">Bulk Lead Import Wizard</h1>
              <p className="text-xs text-[#6B6B6B]">
                Safely ingest leads at scale with automatic normalization, deduplication, and CRM attribution.
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={downloadSampleCSV}
            className="flex items-center gap-2 px-3.5 py-2 bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A] transition shadow-2xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            Download Sample CSV
          </button>
          <button
            onClick={loadBatches}
            disabled={loadingBatches}
            className="p-2 bg-[#FAF7F2] hover:bg-white border border-[#D4D0C8] rounded-xl text-[#1A1A1A] transition shadow-2xs cursor-pointer"
            title="Refresh Batch History"
          >
            <RefreshCw className={`w-4 h-4 ${loadingBatches ? 'animate-spin text-[#2C4BFB]' : ''}`} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <LeadCaptureNav activeTab="import" />

      {/* Status Messages */}
      {uploadSuccess && (
        <div className="flex items-center gap-3 p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 shadow-2xs">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
          <span>{uploadSuccess}</span>
        </div>
      )}
      {errorMessage && (
        <div className="flex items-center gap-3 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-800 shadow-2xs">
          <AlertCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Ingestion Rules / Feature Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] flex items-start gap-3 shadow-xs">
          <ShieldCheck className="w-5 h-5 text-emerald-700 mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-[#1A1A1A]">Zero Silent Corruptions</h4>
            <p className="text-xs text-[#6B6B6B] mt-1 leading-relaxed">
              Phones and emails are normalized to canonical international standards. Invalid formats are safely isolated to the DLQ.
            </p>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] flex items-start gap-3 shadow-xs">
          <Filter className="w-5 h-5 text-[#2C4BFB] mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-[#1A1A1A]">Identity Resolution & Deduplication</h4>
            <p className="text-xs text-[#6B6B6B] mt-1 leading-relaxed">
              Existing leads are detected by phone/email. Re-engaged sources are attributed without creating duplicate CRM leads.
            </p>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] flex items-start gap-3 shadow-xs">
          <Database className="w-5 h-5 text-purple-700 mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-[#1A1A1A]">Asynchronous Batch Execution</h4>
            <p className="text-xs text-[#6B6B6B] mt-1 leading-relaxed">
              High-throughput queue ensures server stability even with 10,000+ row datasets.
            </p>
          </div>
        </div>
      </div>

      {/* Upload Zone */}
      <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-6 shadow-xs">
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-3 ${
            dragActive
              ? 'border-[#2C4BFB] bg-[#2C4BFB]/5'
              : file
              ? 'border-emerald-500 bg-emerald-50/50'
              : 'border-[#D4D0C8] hover:border-[#1A1A1A] bg-white'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="w-14 h-14 rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] flex items-center justify-center text-[#6B6B6B]">
            {file ? (
              <FileSpreadsheet className="w-7 h-7 text-emerald-700" />
            ) : (
              <UploadCloud className="w-7 h-7 text-[#2C4BFB]" />
            )}
          </div>

          <div>
            {file ? (
              <div>
                <p className="text-sm font-semibold text-emerald-800">{file.name}</p>
                <p className="text-xs text-[#6B6B6B] mt-0.5 font-mono">
                  {(file.size / 1024).toFixed(1)} KB — Click or drag to change file
                </p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-[#1A1A1A]">
                  Drop your CSV or Excel file here, or <span className="text-[#2C4BFB] underline font-semibold">browse</span>
                </p>
                <p className="text-xs text-[#6B6B6B] mt-1">Supports UTF-8 CSV, .xlsx, .xls up to 25 MB</p>
              </div>
            )}
          </div>
        </div>

        {/* CSV Preview Section */}
        {preview && (
          <div className="space-y-3 bg-white border border-[#D4D0C8] rounded-xl p-4 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#2C4BFB]" />
                <h3 className="text-xs font-semibold text-[#1A1A1A]">
                  Pre-flight Preview (~{preview.totalRows} records detected)
                </h3>
              </div>
              <span className="text-xs text-[#6B6B6B]">First 5 rows displayed</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="border-b border-[#D4D0C8] bg-[#FAF7F2] text-[#6B6B6B]">
                    {preview.headers.map((h, i) => (
                      <th key={i} className="py-2 px-3 font-semibold">
                        <span className="inline-block px-1.5 py-0.5 rounded bg-white border border-[#D4D0C8] text-[#1A1A1A] text-[10px] mr-1 font-mono">
                          Col {i + 1}
                        </span>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#D4D0C8]/60">
                  {preview.rows.map((row, rIdx) => (
                    <tr key={rIdx} className="hover:bg-[#FAF7F2]">
                      {row.map((val, cIdx) => (
                        <td key={cIdx} className="py-2 px-3 text-[#1A1A1A] truncate max-w-xs font-mono text-[11px]">
                          {val || <span className="text-[#D4D0C8]">—</span>}
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
              className="px-4 py-2 text-xs font-medium text-[#6B6B6B] hover:text-[#1A1A1A] transition cursor-pointer"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleStartImport}
            disabled={!file || uploading}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold shadow-xs transition cursor-pointer ${
              file && !uploading
                ? 'bg-[#1A1A1A] hover:bg-black text-white'
                : 'bg-[#D4D0C8]/50 text-[#6B6B6B] cursor-not-allowed border border-[#D4D0C8]'
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
      <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#2C4BFB]" />
            <h3 className="text-sm font-semibold text-[#1A1A1A]">Import Batch History</h3>
          </div>
          <span className="text-xs text-[#6B6B6B] font-mono">
            {batches.length} {batches.length === 1 ? 'batch' : 'batches'} recorded
          </span>
        </div>

        {loadingBatches ? (
          <div className="py-12 flex justify-center items-center text-[#6B6B6B] text-xs gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-[#2C4BFB]" />
            Loading import batches...
          </div>
        ) : batches.length === 0 ? (
          <div className="text-center py-10 border border-dashed border-[#D4D0C8] rounded-xl bg-white">
            <FileSpreadsheet className="w-8 h-8 text-[#6B6B6B] mx-auto mb-2" />
            <p className="text-xs text-[#1A1A1A] font-medium">No lead import batches run yet</p>
            <p className="text-[11px] text-[#6B6B6B] mt-1">Upload a CSV or Excel file above to start your first bulk import.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="border-b border-[#D4D0C8] text-[#6B6B6B] bg-[#F0EDE8]/60">
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Filename</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Total Records</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Processed</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Duplicates</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Failed</th>
                  <th className="py-3 px-4 font-semibold uppercase tracking-wider text-[11px]">Started At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#D4D0C8]/60 bg-white">
                {batches.map((b) => {
                  const isSuccess = b.status === 'completed' || b.status === 'success';
                  const isProcessing = b.status === 'processing' || b.status === 'in_progress';
                  const isFailed = b.status === 'failed';

                  return (
                    <tr key={b.id} className="hover:bg-[#FAF7F2] transition">
                      <td className="py-3 px-4 font-medium text-[#1A1A1A] flex items-center gap-2">
                        <FileSpreadsheet className="w-4 h-4 text-[#6B6B6B]" />
                        <span className="truncate max-w-xs">{b.filename}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
                            isSuccess
                              ? 'bg-emerald-500/10 text-emerald-800 border border-emerald-500/20'
                              : isProcessing
                              ? 'bg-blue-500/10 text-blue-800 border border-blue-500/20'
                              : isFailed
                              ? 'bg-rose-500/10 text-rose-800 border border-rose-500/20'
                              : 'bg-black/5 text-[#6B6B6B]'
                          }`}
                        >
                          {isSuccess && <CheckCircle2 className="w-3 h-3" />}
                          {isProcessing && <RefreshCw className="w-3 h-3 animate-spin" />}
                          {isFailed && <AlertCircle className="w-3 h-3" />}
                          {b.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[#1A1A1A] font-mono">{b.total_records}</td>
                      <td className="py-3 px-4 text-emerald-700 font-mono font-semibold">{b.processed_records}</td>
                      <td className="py-3 px-4 text-amber-800 font-mono">{b.duplicate_records || 0}</td>
                      <td className="py-3 px-4 text-rose-700 font-mono">{b.failed_records}</td>
                      <td className="py-3 px-4 text-[#6B6B6B] font-mono">
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
    </PageContainer>
  );
}
