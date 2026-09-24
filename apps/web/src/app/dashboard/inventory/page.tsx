'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2, Layers, Plus, RefreshCw, X, Shield, Lock, CheckCircle2,
  AlertCircle, ArrowRight, DollarSign, Clock, FileText, ChevronRight,
  Search, Filter, MapPin, Tag, Check, ArrowUpRight, BarChart3,
  SlidersHorizontal, Home, Key, UserCheck, Eye, Sparkles
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  available: { bg: 'bg-emerald-50 dark:bg-emerald-950/40', text: 'text-emerald-700 dark:text-emerald-300', border: 'border-emerald-200 dark:border-emerald-800' },
  reserved: { bg: 'bg-amber-50 dark:bg-amber-950/40', text: 'text-amber-700 dark:text-amber-300', border: 'border-amber-200 dark:border-amber-800' },
  under_offer: { bg: 'bg-sky-50 dark:bg-sky-950/40', text: 'text-sky-700 dark:text-sky-300', border: 'border-sky-200 dark:border-sky-800' },
  booked: { bg: 'bg-blue-50 dark:bg-blue-950/40', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-200 dark:border-blue-800' },
  sold: { bg: 'bg-purple-50 dark:bg-purple-950/40', text: 'text-purple-700 dark:text-purple-300', border: 'border-purple-200 dark:border-purple-800' },
  blocked: { bg: 'bg-rose-50 dark:bg-rose-950/40', text: 'text-rose-700 dark:text-rose-300', border: 'border-rose-200 dark:border-rose-800' },
  returned: { bg: 'bg-zinc-100 dark:bg-zinc-800', text: 'text-zinc-700 dark:text-zinc-300', border: 'border-zinc-300 dark:border-zinc-700' },
};

function formatCurrency(amount?: number | null, currency: string = 'INR'): string {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  if (amount >= 10000000) {
    return `${currency} ${(amount / 10000000).toFixed(2)} Cr`;
  }
  if (amount >= 100000) {
    return `${currency} ${(amount / 100000).toFixed(2)} L`;
  }
  return `${currency} ${Number(amount).toLocaleString('en-IN')}`;
}

export default function SupplyInventoryPage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');
  const [units, setUnits] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [bhkFilter, setBhkFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Unit 360 Drawer
  const [activeUnitId, setActiveUnitId] = useState<string | null>(null);
  const [activeUnit, setActiveUnit] = useState<any>(null);
  const [isLoadingUnit, setIsLoadingUnit] = useState(false);
  const [transitionStatus, setTransitionStatus] = useState<string>('reserved');
  const [transitionReason, setTransitionReason] = useState<string>('');
  const [transitionDealId, setTransitionDealId] = useState<string>('');
  const [transitionSuccess, setTransitionSuccess] = useState<string | null>(null);
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Modals
  const [isCreateProjectOpen, setIsCreateProjectOpen] = useState(false);
  const [isAddUnitOpen, setIsAddUnitOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Project Form
  const [projectForm, setProjectForm] = useState({
    project_name: '',
    project_type: 'residential',
    city: 'Mumbai',
    locality: 'Worli',
    rera_number: '',
    description: 'Ultra-luxury high-rise residences with panoramic sea views.',
    total_units: 120,
    price_min: 25000000,
    price_max: 85000000,
  });

  // Unit Form
  const [unitForm, setUnitForm] = useState({
    unit_number: 'A-1204',
    unit_type: '3 BHK',
    floor_number: 12,
    facing: 'Sea Facing',
    carpet_area: 1450,
    bedrooms: 3,
    bathrooms: 3,
    base_price: 32000000,
    total_price: 34500000,
  });

  const loadDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [dashRes, projRes] = await Promise.all([
        api.inventoryOS.getDashboard().catch(() => null),
        api.inventoryOS.listProjects({ limit: 50 }).catch(() => ({ items: [] }))
      ]);
      setDashboard(dashRes);
      const projs = projRes?.items || [];
      setProjects(projs);

      // Load units
      if (projs.length > 0) {
        const targetProjId = selectedProjectId === 'all' ? projs[0].id : selectedProjectId;
        const unitsRes = await api.inventoryOS.listUnits(targetProjId, { limit: 100 }).catch(() => ({ items: [] }));
        setUnits(unitsRes?.items || []);
      } else {
        setUnits([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load supply inventory data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, [selectedProjectId]);

  const openUnit360 = async (unitId: string) => {
    setActiveUnitId(unitId);
    setIsLoadingUnit(true);
    setTransitionSuccess(null);
    setTransitionError(null);
    try {
      const res = await api.inventoryOS.getUnit(unitId);
      setActiveUnit(res);
      setTransitionStatus(res.inventory_status === 'available' ? 'reserved' : 'available');
    } catch (err: any) {
      setTransitionError(err?.message || 'Failed to load unit details');
    } finally {
      setIsLoadingUnit(false);
    }
  };

  const handleTransitionStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeUnitId) return;
    setIsTransitioning(true);
    setTransitionError(null);
    setTransitionSuccess(null);
    try {
      const payload: any = {
        to_status: transitionStatus,
        reason: transitionReason || `Manual transition to ${transitionStatus}`,
      };
      if (transitionDealId.trim()) {
        payload.deal_id = transitionDealId.trim();
      }
      await api.inventoryOS.transitionUnitStatus(activeUnitId, payload);
      setTransitionSuccess(`Unit status successfully updated to ${transitionStatus.toUpperCase()}`);
      // Refresh unit details & grid
      const updated = await api.inventoryOS.getUnit(activeUnitId);
      setActiveUnit(updated);
      loadDashboardData();
    } catch (err: any) {
      setTransitionError(err?.message || 'Failed to transition unit status');
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectForm.project_name.trim()) {
      setFormError('Project name is required');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.inventoryOS.createProject({
        project_name: projectForm.project_name.trim(),
        project_type: projectForm.project_type,
        city: projectForm.city.trim(),
        locality: projectForm.locality.trim(),
        rera_number: projectForm.rera_number.trim() || undefined,
        description: projectForm.description,
        total_units: Number(projectForm.total_units),
        price_min: Number(projectForm.price_min),
        price_max: Number(projectForm.price_max),
      });
      setIsCreateProjectOpen(false);
      loadDashboardData();
    } catch (err: any) {
      setFormError(err?.message || 'Failed to register project');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddUnit = async (e: React.FormEvent) => {
    e.preventDefault();
    const projId = selectedProjectId !== 'all' ? selectedProjectId : (projects[0]?.id || '');
    if (!projId) {
      setFormError('Please select or register a project first');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      await api.inventoryOS.createUnit(projId, {
        unit_number: unitForm.unit_number.trim(),
        unit_type: unitForm.unit_type,
        floor_number: Number(unitForm.floor_number),
        facing: unitForm.facing,
        carpet_area: Number(unitForm.carpet_area),
        bedrooms: Number(unitForm.bedrooms),
        bathrooms: Number(unitForm.bathrooms),
        base_price: Number(unitForm.base_price),
        total_price: Number(unitForm.total_price),
      });
      setIsAddUnitOpen(false);
      loadDashboardData();
    } catch (err: any) {
      setFormError(err?.message || 'Failed to add unit to project');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filter units
  const filteredUnits = units.filter(u => {
    if (statusFilter !== 'all' && u.inventory_status !== statusFilter) return false;
    if (bhkFilter !== 'all' && !u.unit_type?.toLowerCase().includes(bhkFilter.toLowerCase())) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const codeMatch = u.unit_code?.toLowerCase().includes(q);
      const numMatch = u.unit_number?.toLowerCase().includes(q);
      const typeMatch = u.unit_type?.toLowerCase().includes(q);
      if (!codeMatch && !numMatch && !typeMatch) return false;
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] flex flex-col pt-16">
      <DashboardNav />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-zinc-200 dark:border-zinc-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 flex items-center gap-1">
                <Shield className="w-3 h-3" /> Supply OS Institutional Record
              </span>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">Deterministic State Machine</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
              Real Estate Supply & Inventory Command Center
            </h1>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
              Authoritative developers, multi-tower projects, floor plans, live unit reservations, and pricing books.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => loadDashboardData()}
              className="p-2 rounded-lg border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 text-zinc-600 dark:text-zinc-300 transition-colors"
              title="Refresh Data"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => setIsAddUnitOpen(true)}
              className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800/80 text-sm font-medium text-zinc-900 dark:text-zinc-100 flex items-center gap-2 shadow-sm transition-all"
            >
              <Plus className="w-4 h-4" /> Add Unit
            </button>
            <button
              onClick={() => setIsCreateProjectOpen(true)}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium flex items-center gap-2 shadow-sm transition-all"
            >
              <Building2 className="w-4 h-4" /> Register Project
            </button>
          </div>
        </div>

        {/* Global Supply KPIs */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 my-6">
          <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/60 shadow-xs">
            <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Total Projects</div>
            <div className="text-2xl font-bold mt-1 text-zinc-900 dark:text-zinc-50">
              {dashboard?.total_projects ?? projects.length}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">Active developments</div>
          </div>

          <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/60 shadow-xs">
            <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Total Units</div>
            <div className="text-2xl font-bold mt-1 text-zinc-900 dark:text-zinc-50">
              {dashboard?.total_units ?? units.length}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">Tracked inventory</div>
          </div>

          <div className="p-4 rounded-xl border border-emerald-200/60 dark:border-emerald-800/40 bg-emerald-50/40 dark:bg-emerald-950/20 shadow-xs">
            <div className="text-xs font-medium text-emerald-800 dark:text-emerald-300 uppercase tracking-wider">Available</div>
            <div className="text-2xl font-bold mt-1 text-emerald-700 dark:text-emerald-400">
              {dashboard?.available_units ?? units.filter(u => u.inventory_status === 'available').length}
            </div>
            <div className="text-xs text-emerald-600/80 dark:text-emerald-400/60 mt-0.5">Live bookable</div>
          </div>

          <div className="p-4 rounded-xl border border-amber-200/60 dark:border-amber-800/40 bg-amber-50/40 dark:bg-amber-950/20 shadow-xs">
            <div className="text-xs font-medium text-amber-800 dark:text-amber-300 uppercase tracking-wider">Reserved</div>
            <div className="text-2xl font-bold mt-1 text-amber-700 dark:text-amber-400">
              {dashboard?.reserved_units ?? units.filter(u => u.inventory_status === 'reserved').length}
            </div>
            <div className="text-xs text-amber-600/80 dark:text-amber-400/60 mt-0.5">Active hold locks</div>
          </div>

          <div className="p-4 rounded-xl border border-purple-200/60 dark:border-purple-800/40 bg-purple-50/40 dark:bg-purple-950/20 shadow-xs">
            <div className="text-xs font-medium text-purple-800 dark:text-purple-300 uppercase tracking-wider">Sold / Booked</div>
            <div className="text-2xl font-bold mt-1 text-purple-700 dark:text-purple-400">
              {(dashboard?.sold_units ?? 0) + (dashboard?.booked_units ?? 0)}
            </div>
            <div className="text-xs text-purple-600/80 dark:text-purple-400/60 mt-0.5">Committed revenue</div>
          </div>

          <div className="p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800/80 bg-white dark:bg-zinc-900/60 shadow-xs">
            <div className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">Inventory Value</div>
            <div className="text-xl font-bold mt-1 text-zinc-900 dark:text-zinc-50 truncate">
              {formatCurrency(dashboard?.total_inventory_value)}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">Gross book value</div>
          </div>
        </div>

        {/* Filter & Selector Ribbon */}
        <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/80 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            {/* Project Select */}
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-zinc-500" />
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
                className="text-sm font-medium bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                {projects.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.project_name} ({p.city})
                  </option>
                ))}
                {projects.length === 0 && <option value="all">No projects created yet</option>}
              </select>
            </div>

            {/* Status Tabs */}
            <div className="flex items-center bg-zinc-100 dark:bg-zinc-800 p-1 rounded-lg text-xs font-medium">
              {['all', 'available', 'reserved', 'booked', 'sold', 'blocked'].map(st => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded-md capitalize transition-colors ${
                    statusFilter === st
                      ? 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 shadow-xs font-semibold'
                      : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

            {/* BHK Filter */}
            <select
              value={bhkFilter}
              onChange={(e) => setBhkFilter(e.target.value)}
              className="text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg px-2.5 py-1.5 focus:outline-none"
            >
              <option value="all">All BHK Types</option>
              <option value="1 BHK">1 BHK</option>
              <option value="2 BHK">2 BHK</option>
              <option value="3 BHK">3 BHK</option>
              <option value="4 BHK">4 BHK</option>
              <option value="Penthouse">Penthouse</option>
            </select>
          </div>

          {/* Search Box */}
          <div className="relative w-full md:w-64">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search unit number, code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Units Grid */}
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-800/40 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  <th className="py-3 px-4">Unit / Code</th>
                  <th className="py-3 px-4">Configuration</th>
                  <th className="py-3 px-4">Floor & View</th>
                  <th className="py-3 px-4">Carpet Area</th>
                  <th className="py-3 px-4">Pricing</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-zinc-500">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-500" />
                      Loading inventory records...
                    </td>
                  </tr>
                ) : filteredUnits.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-zinc-500">
                      <Layers className="w-8 h-8 mx-auto mb-2 text-zinc-400" />
                      No units matching the criteria. Click &quot;Add Unit&quot; or select another project.
                    </td>
                  </tr>
                ) : (
                  filteredUnits.map((u) => {
                    const stColor = STATUS_COLORS[u.inventory_status] || STATUS_COLORS.available;
                    return (
                      <tr
                        key={u.id}
                        className="hover:bg-zinc-50/60 dark:hover:bg-zinc-800/30 transition-colors group cursor-pointer"
                        onClick={() => openUnit360(u.id)}
                      >
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-1.5">
                            <Home className="w-3.5 h-3.5 text-zinc-400" />
                            {u.unit_number}
                          </div>
                          <div className="text-xs text-zinc-400 font-mono mt-0.5">{u.unit_code}</div>
                        </td>

                        <td className="py-3.5 px-4">
                          <span className="font-medium text-zinc-800 dark:text-zinc-200">{u.unit_type}</span>
                          <div className="text-xs text-zinc-500">{u.bedrooms} Bed · {u.bathrooms || 1} Bath</div>
                        </td>

                        <td className="py-3.5 px-4">
                          <div className="text-zinc-800 dark:text-zinc-200">Floor {u.floor_number ?? '—'}</div>
                          <div className="text-xs text-zinc-500">{u.facing || 'Standard View'}</div>
                        </td>

                        <td className="py-3.5 px-4 font-mono text-zinc-800 dark:text-zinc-200">
                          {u.carpet_area ? `${Number(u.carpet_area).toLocaleString()} sqft` : '—'}
                        </td>

                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-zinc-900 dark:text-zinc-100">
                            {formatCurrency(u.total_price)}
                          </div>
                          {u.base_price && (
                            <div className="text-xs text-zinc-500">
                              Base: {formatCurrency(u.base_price)}
                            </div>
                          )}
                        </td>

                        <td className="py-3.5 px-4">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize border ${stColor.bg} ${stColor.text} ${stColor.border}`}>
                            <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
                            {u.inventory_status}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => openUnit360(u.id)}
                            className="px-2.5 py-1 rounded-md text-xs font-medium border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-300 transition-colors inline-flex items-center gap-1"
                          >
                            Unit 360 <ChevronRight className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>

      {/* Unit 360 Detail Drawer */}
      {activeUnitId && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/40 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-xl bg-white dark:bg-[#121316] h-full shadow-2xl flex flex-col border-l border-zinc-200 dark:border-zinc-800 overflow-y-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between sticky top-0 bg-white/90 dark:bg-[#121316]/90 backdrop-blur-sm z-10">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                  <Home className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                    Unit {activeUnit?.unit_number || 'Details'}
                    {activeUnit?.inventory_status && (
                      <span className={`px-2 py-0.5 rounded-md text-xs font-semibold uppercase border ${STATUS_COLORS[activeUnit.inventory_status]?.bg} ${STATUS_COLORS[activeUnit.inventory_status]?.text} ${STATUS_COLORS[activeUnit.inventory_status]?.border}`}>
                        {activeUnit.inventory_status}
                      </span>
                    )}
                  </h2>
                  <p className="text-xs text-zinc-500 font-mono">{activeUnit?.unit_code || activeUnitId}</p>
                </div>
              </div>
              <button
                onClick={() => setActiveUnitId(null)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="p-6 space-y-6 flex-1">
              {isLoadingUnit ? (
                <div className="py-20 text-center text-zinc-500">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-500" />
                  Loading Unit 360 data...
                </div>
              ) : activeUnit ? (
                <>
                  {/* Property Specs Card */}
                  <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                    <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3">
                      Architectural & Space Specifications
                    </h3>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <div className="text-xs text-zinc-400">Unit Type</div>
                        <div className="font-semibold text-zinc-900 dark:text-zinc-100">{activeUnit.unit_type}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400">Floor & Facing</div>
                        <div className="font-semibold text-zinc-900 dark:text-zinc-100">Floor {activeUnit.floor_number} · {activeUnit.facing || 'East'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400">Carpet Area</div>
                        <div className="font-semibold text-zinc-900 dark:text-zinc-100">{activeUnit.carpet_area ? `${activeUnit.carpet_area} sqft` : '—'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-zinc-400">Bedrooms / Baths</div>
                        <div className="font-semibold text-zinc-900 dark:text-zinc-100">{activeUnit.bedrooms} Bed · {activeUnit.bathrooms} Bath</div>
                      </div>
                    </div>
                  </div>

                  {/* Financial Breakdown */}
                  <div className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/50">
                    <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-3">
                      Authoritative Price Sheet
                    </h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                        <span>Base Price:</span>
                        <span className="font-mono text-zinc-900 dark:text-zinc-100">{formatCurrency(activeUnit.base_price)}</span>
                      </div>
                      <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                        <span>Rate per sq.ft:</span>
                        <span className="font-mono text-zinc-900 dark:text-zinc-100">{activeUnit.price_per_sqft ? `₹ ${Number(activeUnit.price_per_sqft).toLocaleString()}/sqft` : '—'}</span>
                      </div>
                      <div className="border-t border-zinc-200 dark:border-zinc-800 pt-2 flex justify-between font-bold text-base text-zinc-900 dark:text-zinc-100">
                        <span>Total Published Price:</span>
                        <span className="font-mono text-emerald-600 dark:text-emerald-400">{formatCurrency(activeUnit.total_price)}</span>
                      </div>
                    </div>
                  </div>

                  {/* State Machine Transition Guard */}
                  <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-800/80 bg-emerald-50/30 dark:bg-emerald-950/20">
                    <div className="flex items-center gap-2 mb-2 text-emerald-800 dark:text-emerald-300 font-semibold text-sm">
                      <Shield className="w-4 h-4 text-emerald-600" />
                      Deterministic Status Transition Gate
                    </div>
                    <p className="text-xs text-zinc-600 dark:text-zinc-400 mb-4">
                      Atomic state updates write append-only audit entries and emit transactional outbox events.
                    </p>

                    {transitionSuccess && (
                      <div className="p-3 mb-3 rounded-lg bg-emerald-100/80 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 text-xs flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        {transitionSuccess}
                      </div>
                    )}

                    {transitionError && (
                      <div className="p-3 mb-3 rounded-lg bg-rose-100/80 text-rose-900 dark:bg-rose-950/60 dark:text-rose-200 text-xs flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-rose-600" />
                        {transitionError}
                      </div>
                    )}

                    <form onSubmit={handleTransitionStatus} className="space-y-3">
                      <div>
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Target Inventory Status
                        </label>
                        <select
                          value={transitionStatus}
                          onChange={(e) => setTransitionStatus(e.target.value)}
                          className="w-full text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                        >
                          <option value="available">AVAILABLE (Release to Open Market)</option>
                          <option value="reserved">RESERVED (Asset Hold Lock)</option>
                          <option value="under_offer">UNDER OFFER (Commercial Negotiation)</option>
                          <option value="booked">BOOKED (Token Confirmed)</option>
                          <option value="sold">SOLD (Title Deed Completed)</option>
                          <option value="blocked">BLOCKED (Developer Internal Hold)</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Deal Transaction ID (Optional)
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                          value={transitionDealId}
                          onChange={(e) => setTransitionDealId(e.target.value)}
                          className="w-full text-xs font-mono bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2 focus:outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                          Audit Reason / Notes
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Token payment received by broker sign-off"
                          value={transitionReason}
                          onChange={(e) => setTransitionReason(e.target.value)}
                          className="w-full text-xs bg-white dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2 focus:outline-none"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={isTransitioning}
                        className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm transition-all"
                      >
                        {isTransitioning ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Lock className="w-3.5 h-3.5" />
                        )}
                        Execute Authoritative Transition
                      </button>
                    </form>
                  </div>

                  {/* Append-Only Status Audit Trail */}
                  <div>
                    <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2">
                      Append-Only Audit History
                    </h3>
                    <div className="space-y-2">
                      {activeUnit.status_history?.length > 0 ? (
                        activeUnit.status_history.map((log: any, idx: number) => (
                          <div key={idx} className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs">
                            <div className="flex justify-between items-center mb-1">
                              <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                                {log.previous_status ? `${log.previous_status} → ` : 'Created as '}
                                <span className="text-emerald-600 dark:text-emerald-400">{log.new_status}</span>
                              </span>
                              <span className="text-[10px] text-zinc-400">{new Date(log.created_at).toLocaleString()}</span>
                            </div>
                            <div className="text-zinc-500 text-[11px]">{log.reason || 'State transition'}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-xs text-zinc-400 italic">No historical status transitions recorded.</div>
                      )}
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Register Project Modal */}
      {isCreateProjectOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-[#121316] rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-zinc-200 dark:border-zinc-800">
            <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-800">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <Building2 className="w-5 h-5 text-emerald-600" /> Register Real Estate Project
              </h2>
              <button onClick={() => setIsCreateProjectOpen(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="my-3 p-3 rounded-lg bg-rose-100 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {formError}
              </div>
            )}

            <form onSubmit={handleCreateProject} className="space-y-3.5 mt-4">
              <div>
                <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Marina Horizon Towers"
                  value={projectForm.project_name}
                  onChange={(e) => setProjectForm({ ...projectForm, project_name: e.target.value })}
                  className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">City</label>
                  <input
                    type="text"
                    required
                    value={projectForm.city}
                    onChange={(e) => setProjectForm({ ...projectForm, city: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Locality</label>
                  <input
                    type="text"
                    required
                    value={projectForm.locality}
                    onChange={(e) => setProjectForm({ ...projectForm, locality: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">RERA Number</label>
                  <input
                    type="text"
                    placeholder="e.g. P51800012345"
                    value={projectForm.rera_number}
                    onChange={(e) => setProjectForm({ ...projectForm, rera_number: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Total Units Count</label>
                  <input
                    type="number"
                    value={projectForm.total_units}
                    onChange={(e) => setProjectForm({ ...projectForm, total_units: Number(e.target.value) })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsCreateProjectOpen(false)}
                  className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Register Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Unit Modal */}
      {isAddUnitOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-[#121316] rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-zinc-200 dark:border-zinc-800">
            <div className="flex justify-between items-center pb-4 border-b border-zinc-200 dark:border-zinc-800">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <Plus className="w-5 h-5 text-emerald-600" /> Add Inventory Unit
              </h2>
              <button onClick={() => setIsAddUnitOpen(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="my-3 p-3 rounded-lg bg-rose-100 text-rose-800 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /> {formError}
              </div>
            )}

            <form onSubmit={handleAddUnit} className="space-y-3.5 mt-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Unit Number</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Tower B - 1402"
                    value={unitForm.unit_number}
                    onChange={(e) => setUnitForm({ ...unitForm, unit_number: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Unit Type / BHK</label>
                  <select
                    value={unitForm.unit_type}
                    onChange={(e) => setUnitForm({ ...unitForm, unit_type: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  >
                    <option value="1 BHK">1 BHK</option>
                    <option value="2 BHK">2 BHK</option>
                    <option value="3 BHK">3 BHK</option>
                    <option value="4 BHK">4 BHK</option>
                    <option value="Penthouse">Penthouse</option>
                    <option value="Villa">Villa</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Floor No.</label>
                  <input
                    type="number"
                    value={unitForm.floor_number}
                    onChange={(e) => setUnitForm({ ...unitForm, floor_number: Number(e.target.value) })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Carpet (sqft)</label>
                  <input
                    type="number"
                    value={unitForm.carpet_area}
                    onChange={(e) => setUnitForm({ ...unitForm, carpet_area: Number(e.target.value) })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Facing</label>
                  <input
                    type="text"
                    value={unitForm.facing}
                    onChange={(e) => setUnitForm({ ...unitForm, facing: e.target.value })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Base Price (₹)</label>
                  <input
                    type="number"
                    value={unitForm.base_price}
                    onChange={(e) => setUnitForm({ ...unitForm, base_price: Number(e.target.value) })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Total Price (₹)</label>
                  <input
                    type="number"
                    value={unitForm.total_price}
                    onChange={(e) => setUnitForm({ ...unitForm, total_price: Number(e.target.value) })}
                    className="w-full text-xs bg-zinc-50 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg p-2.5 focus:outline-none font-mono"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setIsAddUnitOpen(false)}
                  className="px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Save Unit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
