'use client';

import React, { useState } from 'react';
import { Sparkles, Search, Send, BarChart2, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api-client';

interface Props {
  onExecuteQuery?: (query: string) => void;
}

export function TableauNLQueryBar({ onExecuteQuery }: Props) {
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const sampleQueries = [
    "What is the breakdown of hot vs warm leads?",
    "Summarize current pipeline conversion health",
    "Identify bottleneck stages in lead pipeline",
    "Forecast quarterly revenue from qualified leads"
  ];

  const handleSend = async (qStr?: string) => {
    const q = qStr || inputQuery;
    if (!q.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await api.bi.askQuery(q);
      setResult({
        query: res.query,
        summary: "Executive Analytics Root-Cause Analysis",
        explanation: res.explanation_markdown,
        dataPoints: (res.data_points || []).map((dp: any) => ({
          label: dp.category || dp.label || 'Metric',
          value: dp.count !== undefined ? String(dp.count) : dp.value || '--'
        }))
      });
      onExecuteQuery?.(q);
    } catch (err: any) {
      setError(err?.message || 'Unable to process analytics query at this time.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-5 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-indigo-600 fill-indigo-200" />
          <span>Tableau AI Natural Language Analytics Engine</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          Ask Any Business Question
        </span>
      </div>

      {/* Query Input */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask any question e.g. What is the breakdown of hot vs warm leads?"
            className="w-full pl-9 pr-3.5 py-2.5 bg-white border border-[#D4D0C8] rounded-2xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none"
          />
        </div>

        <button onClick={() => handleSend()} disabled={loading} className="btn-lime px-4 py-2.5 text-xs flex items-center gap-1.5">
          {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          <span>Query</span>
        </button>
      </div>

      {/* Sample Quick Action Chips */}
      <div className="flex flex-wrap gap-1.5">
        {sampleQueries.map((sq, idx) => (
          <button
            key={idx}
            onClick={() => {
              setInputQuery(sq);
              handleSend(sq);
            }}
            className="text-[10px] font-mono bg-white hover:bg-[#E8F5A8] text-gray-700 border border-[#D4D0C8] px-2.5 py-1 rounded-lg transition-colors"
          >
            {sq}
          </button>
        ))}
      </div>

      {/* Error Panel */}
      {error && (
        <div className="bg-red-50 text-red-800 text-xs font-mono p-3 rounded-xl border border-red-200">
          {error}
        </div>
      )}

      {/* Result Panel */}
      {result && (
        <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 space-y-3 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#1A1A1A]">
            <BarChart2 className="w-4 h-4 text-emerald-600" />
            <span>{result.summary}</span>
          </div>

          <div className="text-xs text-gray-800 font-sans leading-relaxed bg-[#FAF7F2] p-3 rounded-xl border border-[#D4D0C8] whitespace-pre-wrap">
            {result.explanation}
          </div>

          {result.dataPoints && result.dataPoints.length > 0 && (
            <div className="grid grid-cols-3 gap-2">
              {result.dataPoints.map((dp: any, i: number) => (
                <div key={i} className="bg-[#FAF7F2] p-2 rounded-xl text-center border border-[#EAE7E1]">
                  <span className="text-[10px] font-mono text-gray-500 block">{dp.label}</span>
                  <span className="text-xs font-bold font-mono text-[#1A1A1A]">{dp.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
