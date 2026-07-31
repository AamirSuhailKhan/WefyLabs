'use client';

import React, { useState } from 'react';
import { Sparkles, Search, Send, BarChart2, TrendingUp, AlertCircle, RefreshCw } from 'lucide-react';

interface Props {
  onExecuteQuery?: (query: string) => void;
}

export function TableauNLQueryBar({ onExecuteQuery }: Props) {
  const [inputQuery, setInputQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const sampleQueries = [
    "Why did Dubai Marina conversions drop 12% last week?",
    "Show top 5 marketing campaigns by ROI",
    "Which agent has the highest deal closing speed?",
    "Forecast Q4 revenue across UAE and India"
  ];

  const handleSend = (qStr?: string) => {
    const q = qStr || inputQuery;
    if (!q.trim()) return;

    setLoading(true);
    setResult(null);

    setTimeout(() => {
      setResult({
        query: q,
        summary: "Tableau AI Root-Cause Analysis",
        explanation: "**Root Cause Identified:** WhatsApp response speed in Dubai Marina spiked from 2.1m to 14.5m over the past 48 hours due to simultaneous lead distribution. CAC dropped from $580 to $420 following AI bot integration.",
        dataPoints: [
          { label: 'May 2026', value: '$1.8M (22.4% Conv)' },
          { label: 'Jun 2026', value: '$2.4M (28.1% Conv)' },
          { label: 'Jul 2026', value: '$2.85M (34.8% Conv)' }
        ]
      });
      setLoading(false);
      onExecuteQuery?.(q);
    }, 600);
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
            placeholder="Ask any question e.g. Why did Dubai Marina conversions drop 12% last week?"
            className="w-full pl-9 pr-3.5 py-2.5 bg-white border border-[#D4D0C8] rounded-2xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none"
          />
        </div>

        <button onClick={() => handleSend()} className="btn-lime px-4 py-2.5 text-xs flex items-center gap-1.5">
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

          <div className="grid grid-cols-3 gap-2">
            {result.dataPoints.map((dp: any, i: number) => (
              <div key={i} className="bg-[#FAF7F2] p-2 rounded-xl text-center border border-[#EAE7E1]">
                <span className="text-[10px] font-mono text-gray-500 block">{dp.label}</span>
                <span className="text-xs font-bold font-mono text-[#1A1A1A]">{dp.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
