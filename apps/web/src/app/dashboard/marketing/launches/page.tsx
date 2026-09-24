'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Rocket, Plus, RefreshCw, CheckCircle2, XCircle, AlertCircle,
  Shield, Check, Clock, ChevronRight
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import {
  Button, Card, CardHeader, CardTitle, CardContent,
  PageHeader, KpiCard, StatusBadge, EmptyState, Skeleton
} from '@/components/ui';

const API = '/api/v1/marketing';

const LAUNCH_GATES = [
  { key: 'gate_project_configured', label: 'Project Configured', desc: 'Master developer, project attributes, and towers configured in Supply OS' },
  { key: 'gate_inventory_ready', label: 'Inventory Ready', desc: 'All physical units, BHK topologies, and carpet areas mapped and verified' },
  { key: 'gate_pricing_ready', label: 'Pricing Book Published', desc: 'Commercial price book active with floor-rise and premium location charges' },
  { key: 'gate_lead_form_ready', label: 'Lead Capture Form Active', desc: 'Public lead intake pipeline and webhook routing validated' },
];

interface ProjectLaunch {
  id: string;
  name: string;
  project_id: string;
  status: string;
  target_launch_date?: string;
  gate_project_configured: boolean;
  gate_inventory_ready: boolean;
  gate_pricing_ready: boolean;
  gate_lead_form_ready: boolean;
  all_gates_passed?: boolean;
}

export default function MarketingLaunchesPage() {
  const [launches, setLaunches] = useState<ProjectLaunch[]>([]);
  const [loading, setLoading] = useState(true);

  const loadLaunches = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/launches`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setLaunches(data.items || data || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLaunches();
  }, []);

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <PageHeader
          title="PROJECT LAUNCH COMMAND CENTER"
          description="Institutional launch readiness checklist. Enforces deterministic multi-gate verification before commercial project launch."
          breadcrumbs={[
            { label: 'Marketing', href: '/dashboard/marketing' },
            { label: 'Project Launches' },
          ]}
          actions={
            <Button
              variant="secondary"
              size="sm"
              onClick={loadLaunches}
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />}
            >
              Refresh
            </Button>
          }
        />

        {/* Human Governance Guard Banner */}
        <div className="p-4 rounded-2xl bg-[#FFFBEB] border border-[#FDE68A] flex items-start gap-3.5">
          <div className="p-2 rounded-xl bg-[#FEF3C7] border border-[#FDE68A] text-[#B45309] shrink-0 mt-0.5">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-xs font-bold font-mono uppercase text-[#92400E]">
              AI Safety Invariant: Human Approval Gate Enforced
            </h3>
            <p className="text-xs text-[#78350F] mt-0.5 font-sans leading-relaxed">
              AI agents may assist in compiling marketing collateral, generating ad copy, and validating pricing schedules — but cannot independently trigger a public project launch. Every launch requires verified broker approval.
            </p>
          </div>
        </div>

        {/* Launch Readiness Gate Requirements Grid */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Rocket className="w-4 h-4 text-[#D97706]" />
              <CardTitle className="text-sm">Mandatory Readiness Gates</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {LAUNCH_GATES.map((gate, i) => (
                <div
                  key={gate.key}
                  className="p-3.5 rounded-xl bg-white border border-[#D4D0C8] flex items-start gap-3"
                >
                  <span className="w-6 h-6 rounded-full bg-[#FAF7F2] border border-[#D4D0C8] text-xs font-mono font-bold flex items-center justify-center text-[#1A1A1A] shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-xs font-bold text-[#1A1A1A] font-mono">{gate.label}</p>
                    <p className="text-[11px] text-[#6B6B6B] font-sans mt-0.5 leading-relaxed">
                      {gate.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Active Project Launches */}
        <div className="space-y-3">
          {loading ? (
            Array.from({ length: 2 }).map((_, i) => (
              <div
                key={i}
                className="h-24 bg-white border border-[#D4D0C8] rounded-2xl p-4 flex items-center justify-between animate-pulse"
              >
                <div className="space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
                <Skeleton className="h-6 w-20 rounded-full" />
              </div>
            ))
          ) : launches.length > 0 ? (
            launches.map((launch) => (
              <div
                key={launch.id}
                className="p-5 rounded-2xl bg-white border border-[#D4D0C8] hover:border-[#1A1A1A] transition-all shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start sm:items-center gap-3.5 min-w-0">
                  <div className="p-2.5 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] text-[#1A1A1A] shrink-0">
                    <Rocket className="w-5 h-5 text-[#D97706]" />
                  </div>
                  <div className="min-w-0">
                    <span className="font-mono text-sm font-bold text-[#1A1A1A]">
                      {launch.name}
                    </span>
                    <div className="flex items-center gap-2 text-xs text-[#6B6B6B] mt-1 font-sans">
                      <span>Project: {launch.project_id}</span>
                      {launch.target_launch_date && (
                        <>
                          <span>•</span>
                          <span>Target Date: {new Date(launch.target_launch_date).toLocaleDateString()}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
                  <StatusBadge status={launch.status} />
                </div>
              </div>
            ))
          ) : (
            <EmptyState
              icon={Rocket}
              title="No project launches scheduled"
              description="Project launches coordinate multi-tower developments with synchronized inventory availability, verified pricing, and multi-channel marketing campaigns."
              primaryAction={{
                label: 'View Inventory Supply',
                onClick: () => {
                  window.location.href = '/dashboard/inventory';
                },
                icon: Rocket,
              }}
            />
          )}
        </div>
      </main>
    </div>
  );
}
