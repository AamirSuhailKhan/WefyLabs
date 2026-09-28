'use client';

import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Flame,
  Layers,
  LineChart,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from 'lucide-react';

interface DependencyStatus {
  name: string;
  category: string;
  status: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE';
  latency_ms: number;
  critical: boolean;
}

interface SLOItem {
  name: string;
  target: string;
  current: string;
  budget_remaining_pct: number;
  status: 'MEETING' | 'AT_RISK' | 'BREACHED';
}

interface IncidentItem {
  id: string;
  title: string;
  severity: 'P0' | 'P1' | 'P2' | 'P3';
  status: 'OPEN' | 'INVESTIGATING' | 'MITIGATED' | 'RESOLVED';
  service: string;
  ttd: string;
  runbook: string;
}

export default function OperationsCenterPage() {
  const [activeTab, setActiveTab] = useState<'health' | 'slos' | 'ai' | 'incidents' | 'capacity'>('health');
  const [lastRefreshed, setLastRefreshed] = useState<string>('');
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  useEffect(() => {
    setLastRefreshed(new Date().toLocaleTimeString());
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setLastRefreshed(new Date().toLocaleTimeString());
      setIsRefreshing(false);
    }, 600);
  };

  const dependencies: DependencyStatus[] = [
    { name: 'PostgreSQL Relational DB', category: 'Core Database', status: 'HEALTHY', latency_ms: 2.4, critical: true },
    { name: 'Redis Cache & PubSub', category: 'In-Memory Store', status: 'HEALTHY', latency_ms: 0.8, critical: true },
    { name: 'Google Gemini AI Gateway', category: 'AI Intelligence', status: 'HEALTHY', latency_ms: 820.0, critical: false },
    { name: 'WhatsApp Cloud API', category: 'Omnichannel Comm', status: 'HEALTHY', latency_ms: 195.0, critical: false },
    { name: 'Celery Distributed Queue', category: 'Async Workers', status: 'HEALTHY', latency_ms: 12.0, critical: true },
    { name: 'Transactional Outbox Lag', category: 'Event Bus', status: 'HEALTHY', latency_ms: 4.5, critical: true },
    { name: 'pgvector Search Engine', category: 'Semantic RAG', status: 'HEALTHY', latency_ms: 45.0, critical: false },
    { name: 'Razorpay Payment Gateway', category: 'Financials', status: 'HEALTHY', latency_ms: 180.0, critical: false },
  ];

  const slos: SLOItem[] = [
    { name: 'API Availability (30d)', target: '≥ 99.9%', current: '99.98%', budget_remaining_pct: 82.0, status: 'MEETING' },
    { name: 'API Latency p99', target: '≤ 500 ms', current: '215 ms', budget_remaining_pct: 57.0, status: 'MEETING' },
    { name: 'AI Response Latency p95', target: '≤ 3,000 ms', current: '1,420 ms', budget_remaining_pct: 52.6, status: 'MEETING' },
    { name: 'Database Query p99', target: '≤ 100 ms', current: '24 ms', budget_remaining_pct: 76.0, status: 'MEETING' },
    { name: 'Queue Processing p95', target: '≤ 5,000 ms', current: '1,120 ms', budget_remaining_pct: 77.6, status: 'MEETING' },
    { name: 'API Error Rate', target: '< 1.0%', current: '0.04%', budget_remaining_pct: 96.0, status: 'MEETING' },
  ];

  const incidents: IncidentItem[] = [
    {
      id: 'INC-2026-089',
      title: 'WhatsApp Cloud API Webhook Spike Auto-Throttled',
      severity: 'P2',
      status: 'RESOLVED',
      service: 'omnichannel-ingest',
      ttd: '28s',
      runbook: '/docs/operations/runbooks/whatsapp-outage.md',
    },
    {
      id: 'INC-2026-074',
      title: 'Celery Outbox Catch-up After Database Migration',
      severity: 'P3',
      status: 'RESOLVED',
      service: 'outbox-processor',
      ttd: '45s',
      runbook: '/docs/operations/runbooks/outbox-backlog.md',
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-10 font-sans">
      {/* Top Banner / Header */}
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between pb-8 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                WefyLabs Operations Center
                <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  Build 12 Live
                </span>
              </h1>
              <p className="text-sm text-slate-400">
                Observability, Reliability, SLO Error Budgets & Production Health
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-right text-xs text-slate-400">
            <div>Telemetry Synced</div>
            <div className="font-mono text-slate-300">{lastRefreshed}</div>
          </div>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-900 border border-slate-700 hover:border-slate-600 text-xs font-medium text-slate-200 hover:text-white transition-all shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Primary KPI Strip */}
      <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4 my-8">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Overall Health</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">NOMINAL</div>
          <div className="text-xs text-emerald-400 mt-1 font-mono">0 Core Outages</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>API p99 Latency</span>
            <Zap className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white">215 ms</div>
          <div className="text-xs text-cyan-400 mt-1 font-mono">Target: ≤ 500 ms</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>AI Inference p95</span>
            <Cpu className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white">1.42 s</div>
          <div className="text-xs text-indigo-400 mt-1 font-mono">Budget: ≤ 3.00 s</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 backdrop-blur">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Active Incidents</span>
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">0 Active</div>
          <div className="text-xs text-slate-400 mt-1 font-mono">P0/P1 Clear</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto flex border-b border-slate-800 mb-6 gap-2">
        <button
          onClick={() => setActiveTab('health')}
          className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'health'
              ? 'border-cyan-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Dependency Health
        </button>
        <button
          onClick={() => setActiveTab('slos')}
          className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'slos'
              ? 'border-cyan-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          SLOs & Error Budgets
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'ai'
              ? 'border-cyan-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          AI Evaluation & Grounding
        </button>
        <button
          onClick={() => setActiveTab('incidents')}
          className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'incidents'
              ? 'border-cyan-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Incident Intelligence
        </button>
        <button
          onClick={() => setActiveTab('capacity')}
          className={`pb-3 px-4 text-sm font-medium transition-colors border-b-2 ${
            activeTab === 'capacity'
              ? 'border-cyan-500 text-white'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Capacity Forecast
        </button>
      </div>

      {/* Tab Content */}
      <div className="max-w-7xl mx-auto">
        {activeTab === 'health' && (
          <div className="rounded-xl bg-slate-900/50 border border-slate-800 overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Dependency Health Registry</h2>
              <span className="text-xs text-slate-400">Auto-cached 10s TTL</span>
            </div>
            <div className="divide-y divide-slate-800/60">
              {dependencies.map((dep, idx) => (
                <div key={idx} className="p-4 flex items-center justify-between hover:bg-slate-800/20 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
                    <div>
                      <div className="text-sm font-medium text-white flex items-center gap-2">
                        {dep.name}
                        {dep.critical && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                            Critical
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-400">{dep.category}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <div className="text-xs font-mono text-slate-300">{dep.latency_ms} ms</div>
                      <div className="text-[10px] text-slate-500">Latency</div>
                    </div>
                    <span className="px-2.5 py-1 text-xs font-medium rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {dep.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'slos' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {slos.map((slo, idx) => (
              <div key={idx} className="p-5 rounded-xl bg-slate-900/50 border border-slate-800 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-white">{slo.name}</h3>
                    <span className="text-xs px-2 py-0.5 rounded font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {slo.status}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between text-xs text-slate-400 my-2">
                    <span>Current: <strong className="text-white font-mono">{slo.current}</strong></span>
                    <span>Target: <strong className="text-slate-300 font-mono">{slo.target}</strong></span>
                  </div>
                </div>
                <div className="mt-4">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">Remaining Error Budget</span>
                    <span className="font-mono text-emerald-400 font-medium">{slo.budget_remaining_pct}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full"
                      style={{ width: `${slo.budget_remaining_pct}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'ai' && (
          <div className="space-y-6">
            <div className="p-6 rounded-xl bg-slate-900/50 border border-slate-800">
              <h2 className="text-base font-semibold text-white mb-4">Golden Dataset Evaluation (v1.4)</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-xs text-slate-400">Relevance Score</div>
                  <div className="text-xl font-bold text-white mt-1">94.2%</div>
                  <div className="text-[10px] text-emerald-400">Threshold: ≥ 75%</div>
                </div>
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-xs text-slate-400">Context Faithfulness</div>
                  <div className="text-xl font-bold text-white mt-1">91.8%</div>
                  <div className="text-[10px] text-emerald-400">Threshold: ≥ 80%</div>
                </div>
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-xs text-slate-400">Zero-Hallucination Rate</div>
                  <div className="text-xl font-bold text-white mt-1">96.5%</div>
                  <div className="text-[10px] text-emerald-400">Threshold: ≥ 90%</div>
                </div>
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-xs text-slate-400">Safety & Injection Defense</div>
                  <div className="text-xl font-bold text-white mt-1">99.4%</div>
                  <div className="text-[10px] text-emerald-400">Threshold: ≥ 95%</div>
                </div>
              </div>
              <div className="text-xs text-slate-400 bg-slate-950/40 p-3 rounded-lg border border-slate-800/80 flex items-center justify-between">
                <span>Active Model: <strong className="text-slate-200">Google Gemini 2.0 Flash</strong></span>
                <span>Eval Samples: <strong className="text-slate-200">100 Ground Truth Cases</strong></span>
                <span className="text-emerald-400 font-medium">Promotion Gate: APPROVED</span>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'incidents' && (
          <div className="rounded-xl bg-slate-900/50 border border-slate-800 overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Recent Operational Incidents</h2>
              <span className="text-xs text-slate-400">P0-P4 Lifecycle Engine</span>
            </div>
            <div className="divide-y divide-slate-800/60">
              {incidents.map((inc) => (
                <div key={inc.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        {inc.severity}
                      </span>
                      <span className="font-mono text-xs text-slate-400">{inc.id}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {inc.status}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-white">{inc.title}</div>
                    <div className="text-xs text-slate-400 mt-1">Service: {inc.service} • Time to Detect: {inc.ttd}</div>
                  </div>
                  <div>
                    <span className="text-xs font-mono text-cyan-400 bg-cyan-950/30 px-3 py-1.5 rounded border border-cyan-800/50">
                      Runbook: {inc.runbook.split('/').pop()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'capacity' && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">Database Storage</span>
                <Database className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="text-2xl font-bold text-white">45.2 GB / 500 GB</div>
              <div className="text-xs text-slate-400 mt-1 font-mono">620 Days to Exhaustion</div>
              <div className="w-full h-1.5 rounded-full bg-slate-800 mt-4 overflow-hidden">
                <div className="h-full bg-cyan-400 rounded-full" style={{ width: '9%' }} />
              </div>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">Redis Memory</span>
                <Layers className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="text-2xl font-bold text-white">210 MB / 2,048 MB</div>
              <div className="text-xs text-slate-400 mt-1 font-mono">450 Days to Exhaustion</div>
              <div className="w-full h-1.5 rounded-full bg-slate-800 mt-4 overflow-hidden">
                <div className="h-full bg-indigo-400 rounded-full" style={{ width: '10.2%' }} />
              </div>
            </div>

            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">AI Tokens (Monthly)</span>
                <Flame className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold text-white">1.5M / 10.0M</div>
              <div className="text-xs text-slate-400 mt-1 font-mono">180 Days to Cap</div>
              <div className="w-full h-1.5 rounded-full bg-slate-800 mt-4 overflow-hidden">
                <div className="h-full bg-emerald-400 rounded-full" style={{ width: '15%' }} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
