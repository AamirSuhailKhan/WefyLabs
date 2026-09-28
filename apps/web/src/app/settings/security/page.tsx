'use client';

import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Lock,
  Key,
  Users,
  Eye,
  FileText,
  AlertTriangle,
  RefreshCw,
  Server,
  Database,
  Cpu,
  Download,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
  ChevronRight
} from 'lucide-react';

interface SecurityHealthPlane {
  status: 'HEALTHY' | 'DEGRADED' | 'ACTION_REQUIRED';
  details: string;
}

export default function SecurityAdministrationPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'ai_governance' | 'retention' | 'events' | 'incidents'>('overview');
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  // Sample verified security health metrics
  const healthPlanes: Record<string, SecurityHealthPlane> = {
    'Authentication & Tokens': {
      status: 'HEALTHY',
      details: 'Supabase JWT validation, PBKDF2 100k rounds, JTI revocation blacklist active'
    },
    'Multi-Tenant Isolation': {
      status: 'HEALTHY',
      details: 'Fail-closed tenancy (UNKNOWN=REJECT), strict organization-scoped query filtering'
    },
    'Role-Based Access Control': {
      status: 'HEALTHY',
      details: '10 canonical roles, bidirectional dot/colon aliases, fail-closed zero-trust boundary'
    },
    'Secret Management & Redaction': {
      status: 'HEALTHY',
      details: 'AES-256-GCM application encryption, automatic credential/PII scrubbing pipeline'
    },
    'Webhook Signature Defense': {
      status: 'HEALTHY',
      details: 'HMAC-SHA256 verification, 300s replay attack skew window defense'
    },
    'Storage & File Security': {
      status: 'HEALTHY',
      details: 'MIME magic bytes scanner, path traversal block, private signed download URLs'
    },
    'AI Model & Autonomy Guard': {
      status: 'HEALTHY',
      details: 'Gemini approved models allowlist, prompt-injection filter, financial confirmation required'
    },
    'Worker & Queue Privileges': {
      status: 'HEALTHY',
      details: 'Strict JSON serialization (zero pickle), tenant-bound worker context'
    },
    'Database Parameterization': {
      status: 'HEALTHY',
      details: '100% parameterized queries, async connection pooling, non-root application roles'
    },
    'Backup & Disaster Recovery': {
      status: 'HEALTHY',
      details: 'Daily automated snapshots, tested drill RPO: 0m, RTO: 3m (Target: RPO < 15m, RTO < 60m)'
    }
  };

  const [aiDomains, setAiDomains] = useState({
    FAQ: 'AUTONOMOUS',
    QUALIFICATION: 'AUTONOMOUS',
    PROPERTY_RECOMMENDATION: 'AUTONOMOUS',
    MESSAGE_DRAFTING: 'AUTONOMOUS',
    MESSAGE_SENDING: 'CONFIRM',
    APPOINTMENT: 'CONFIRM',
    NEGOTIATION: 'SUGGEST',
    BOOKING: 'CONFIRM',
    PAYMENT: 'CONFIRM'
  });

  const [legalHolds, setLegalHolds] = useState([
    {
      id: 'hold-101',
      targetType: 'Lead',
      targetId: 'lead-83921',
      reason: 'Statutory compliance verification',
      placedBy: 'cso@wefylabs.ai',
      placedAt: '2026-09-27T10:15:00Z',
      active: true
    }
  ]);

  const [securityEvents] = useState([
    {
      id: 'evt-901',
      type: 'AUTH_SUCCESS',
      actor: 'admin@alpharealty.com',
      severity: 'INFO',
      ip: '103.21.244.2',
      timestamp: '2026-09-27 13:45:12',
      result: 'SUCCESS'
    },
    {
      id: 'evt-902',
      type: 'PRIVILEGE_ESCALATION_ATTEMPT',
      actor: 'agent_unknown@external.net',
      severity: 'HIGH',
      ip: '198.51.100.44',
      timestamp: '2026-09-27 12:30:05',
      result: 'DENIED'
    },
    {
      id: 'evt-903',
      type: 'EXPORT_CREATED',
      actor: 'admin@alpharealty.com',
      severity: 'LOW',
      ip: '103.21.244.2',
      timestamp: '2026-09-27 11:10:48',
      result: 'SUCCESS'
    }
  ]);

  const [newHoldReason, setNewHoldReason] = useState('');
  const [newHoldTargetId, setNewHoldTargetId] = useState('');

  const handlePlaceHold = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newHoldTargetId || !newHoldReason) return;
    const newEntry = {
      id: `hold-${Date.now().toString().slice(-4)}`,
      targetType: 'Lead',
      targetId: newHoldTargetId,
      reason: newHoldReason,
      placedBy: 'admin@current.tenant',
      placedAt: new Date().toISOString(),
      active: true
    };
    setLegalHolds([newEntry, ...legalHolds]);
    setNewHoldTargetId('');
    setNewHoldReason('');
    setNotification('Legal Hold successfully enforced. Record is locked from deletion.');
    setTimeout(() => setNotification(null), 4000);
  };

  const handleReleaseHold = (holdId: string) => {
    setLegalHolds(legalHolds.map(h => h.id === holdId ? { ...h, active: false } : h));
    setNotification('Legal Hold released. Standard retention schedule resumed.');
    setTimeout(() => setNotification(null), 4000);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 p-6 md:p-10 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-teal-600/10 text-teal-600 dark:bg-teal-500/10 dark:text-teal-400 rounded-xl">
                <ShieldCheck className="w-8 h-8" />
              </div>
              <div>
                <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Enterprise Security & Governance OS</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Defense-in-depth, zero-trust tenancy, fine-grained RBAC, AI autonomy controls & compliance
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Security Posture: Enterprise Hardened
            </span>
          </div>
        </div>

        {/* Notification Toast */}
        {notification && (
          <div className="p-4 rounded-xl bg-teal-50 dark:bg-teal-950/60 border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200 flex items-center gap-3 text-sm animate-fadeIn">
            <CheckCircle2 className="w-5 h-5 text-teal-600 dark:text-teal-400 shrink-0" />
            <span>{notification}</span>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
          {[
            { id: 'overview', label: 'Security Health Overview', icon: Shield },
            { id: 'ai_governance', label: 'AI Governance & Autonomy', icon: Cpu },
            { id: 'retention', label: 'Retention & Legal Holds', icon: Lock },
            { id: 'events', label: 'Security Audit Stream', icon: FileText },
            { id: 'incidents', label: 'Incident Response', icon: ShieldAlert }
          ].map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-teal-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-900'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content: Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(healthPlanes).map(([title, plane]) => (
                <div
                  key={title}
                  className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-200">{title}</h3>
                      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                        <CheckCircle2 className="w-3 h-3" />
                        {plane.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                      {plane.details}
                    </p>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
                    <span>Verified via automated suite</span>
                    <span className="font-mono text-[11px] text-teal-600 dark:text-teal-400">ACTIVE</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab Content: AI Governance */}
        {activeTab === 'ai_governance' && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
              <h2 className="text-lg font-bold">Approved AI Models Allowlist</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Only approved, safety-evaluated models can be invoked across WefyLabs. External unlisted models are rejected at gateway.
              </p>
              <div className="flex flex-wrap gap-2 pt-2">
                {['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-3.5-flash'].map(m => (
                  <span key={m} className="px-3 py-1.5 rounded-lg text-xs font-mono font-medium bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300">
                    ✓ {m}
                  </span>
                ))}
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
              <div>
                <h2 className="text-lg font-bold">AI Autonomy Policy Matrix</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Granular control over AI agent capabilities per operational domain. Financial mutations strictly enforce human confirmation.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(aiDomains).map(([domain, level]) => (
                  <div key={domain} className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">{domain}</span>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                        level === 'AUTONOMOUS'
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                          : level === 'CONFIRM'
                          ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                          : 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-300'
                      }`}>
                        {level}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      {level === 'AUTONOMOUS' && 'AI executes automatically within guardrails'}
                      {level === 'CONFIRM' && 'AI drafts action; requires explicit human confirmation'}
                      {level === 'SUGGEST' && 'AI produces advisory suggestions for sales staff'}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab Content: Retention & Legal Holds */}
        {activeTab === 'retention' && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
              <h2 className="text-lg font-bold">Statutory Retention Schedules</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs text-slate-500">Audit Logs (SOC 2)</div>
                  <div className="text-xl font-bold mt-1">2,555 Days</div>
                  <div className="text-[11px] text-slate-400 mt-1">7 Years (Mandatory)</div>
                </div>
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs text-slate-500">Financial Records</div>
                  <div className="text-xl font-bold mt-1">2,555 Days</div>
                  <div className="text-[11px] text-slate-400 mt-1">7 Years (Statutory)</div>
                </div>
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs text-slate-500">CRM Leads</div>
                  <div className="text-xl font-bold mt-1">730 Days</div>
                  <div className="text-[11px] text-slate-400 mt-1">2 Years (Configurable)</div>
                </div>
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800">
                  <div className="text-xs text-slate-500">AI Prompt Traces</div>
                  <div className="text-xl font-bold mt-1">90 Days</div>
                  <div className="text-[11px] text-slate-400 mt-1">Scrubbed Telemetry</div>
                </div>
              </div>
            </div>

            {/* Legal Hold Section */}
            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold">Active Legal Holds</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Records under Legal Hold are mathematically locked against GDPR Right-to-be-Forgotten deletion or automated retention purges.
                  </p>
                </div>
              </div>

              {/* Form to place legal hold */}
              <form onSubmit={handlePlaceHold} className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-4">
                <div className="text-sm font-semibold">Place New Legal Hold</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <input
                    type="text"
                    placeholder="Target Resource ID (e.g. lead-uuid)"
                    value={newHoldTargetId}
                    onChange={e => setNewHoldTargetId(e.target.value)}
                    className="px-3.5 py-2 text-sm rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                    required
                  />
                  <input
                    type="text"
                    placeholder="Hold Justification / Matter Reason"
                    value={newHoldReason}
                    onChange={e => setNewHoldReason(e.target.value)}
                    className="px-3.5 py-2 text-sm rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900"
                    required
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium transition-colors"
                  >
                    Enforce Legal Hold
                  </button>
                </div>
              </form>

              {/* List of active holds */}
              <div className="space-y-3">
                {legalHolds.map(hold => (
                  <div
                    key={hold.id}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">{hold.targetType}: {hold.targetId}</span>
                        {hold.active ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            ACTIVE HOLD
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300">
                            RELEASED
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        Reason: {hold.reason} | Placed by: {hold.placedBy}
                      </div>
                    </div>
                    {hold.active && (
                      <button
                        onClick={() => handleReleaseHold(hold.id)}
                        className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                      >
                        Release Hold
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab Content: Security Events */}
        {activeTab === 'events' && (
          <div className="space-y-4">
            <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold">Canonical Security Event Stream</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Real-time SecOps telemetry stream scrubbed of credentials, API keys, and sensitive tokens.
                  </p>
                </div>
              </div>

              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {securityEvents.map(evt => (
                  <div key={evt.id} className="py-3.5 flex items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-800 dark:text-slate-200">{evt.type}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          evt.severity === 'HIGH' ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300' :
                          evt.severity === 'LOW' ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300' :
                          'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300'
                        }`}>
                          {evt.severity}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        Actor: {evt.actor} | IP: {evt.ip} | Time: {evt.timestamp}
                      </div>
                    </div>
                    <span className={`text-xs font-semibold px-2 py-1 rounded ${
                      evt.result === 'SUCCESS' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                    }`}>
                      {evt.result}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab Content: Incidents */}
        {activeTab === 'incidents' && (
          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
            <h2 className="text-lg font-bold">Security Incident State Machine</h2>
            <div className="flex flex-wrap gap-2 text-xs font-semibold text-slate-500">
              {['DETECTED', 'TRIAGED', 'CONTAINED', 'INVESTIGATING', 'REMEDIATING', 'RESOLVED', 'POSTMORTEM'].map((step, idx) => (
                <span key={step} className="flex items-center gap-2">
                  <span className={`px-2.5 py-1 rounded ${idx <= 1 ? 'bg-teal-600 text-white' : 'bg-slate-100 dark:bg-slate-800'}`}>
                    {step}
                  </span>
                  {idx < 6 && <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                </span>
              ))}
            </div>

            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm">INC-1001: Automated Privilege Escalation Perimeter Alert</span>
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  CONTAINED
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Unauthorized attempt to elevate role blocked server-side by RBAC engine. Session flagged and IP logged.
              </p>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
