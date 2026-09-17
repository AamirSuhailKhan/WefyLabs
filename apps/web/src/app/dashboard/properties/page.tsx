'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { PropertyValuationCard } from '@/components/properties/PropertyValuationCard';
import {
  Building2, Search, Filter, Plus, Home, MapPin, Eye, Tag, Sparkles,
  Trash2, X, Check, RefreshCw, Share2, Calendar, Users, Bookmark,
  Layers, ArrowUpDown, UploadCloud, Copy, CheckCircle2, AlertCircle,
  Clock, ArrowRight
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { formatCurrencyINR } from '@/lib/utils';
import { api } from '@/lib/api-client';

function PropertiesContent() {
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [properties, setProperties] = useState<any[]>([]);
  const [kpiData, setKpiData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [isVisitModalOpen, setIsVisitModalOpen] = useState(false);
  const [isLeadsModalOpen, setIsLeadsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Selected property for modal context
  const [activeProperty, setActiveProperty] = useState<any>(null);
  const [propertyLeads, setPropertyLeads] = useState<any[]>([]);
  const [matchedBuyerLeads, setMatchedBuyerLeads] = useState<any[]>([]);
  const [leadsModalTab, setLeadsModalTab] = useState<'ai_matched' | 'linked'>('ai_matched');
  const [isLoadingMatchedLeads, setIsLoadingMatchedLeads] = useState<boolean>(false);
  const [copiedLink, setCopiedLink] = useState(false);

  // P1 Property Deep-link State
  const searchParams = useSearchParams();
  const deepLinkId = searchParams.get('id') || searchParams.get('property_id');
  const [highlightedId, setHighlightedId] = useState<string | null>(null);

  // P2 Price Update Workflow State
  const [isPriceModalOpen, setIsPriceModalOpen] = useState(false);
  const [priceModalProperty, setPriceModalProperty] = useState<any>(null);
  const [newPrice, setNewPrice] = useState<number>(0);
  const [priceReason, setPriceReason] = useState<string>('Market Correction');
  const [priceUpdateSuccess, setPriceUpdateSuccess] = useState<string | null>(null);

  // P2 Site Visit Completion Workflow State
  const [scheduledVisits, setScheduledVisits] = useState<any[]>([]);
  const [isLoadingVisits, setIsLoadingVisits] = useState(false);
  const [isDebriefModalOpen, setIsDebriefModalOpen] = useState(false);
  const [debriefVisit, setDebriefVisit] = useState<any>(null);
  const [debriefInterest, setDebriefInterest] = useState<'High' | 'Medium' | 'Low' | 'Not interested'>('High');
  const [debriefObjection, setDebriefObjection] = useState<string>('');
  const [debriefNotes, setDebriefNotes] = useState<string>('');
  const [debriefNextStep, setDebriefNextStep] = useState<string>('Send offer sheet / arrange second viewing');
  const [visitOutcomeSuccess, setVisitOutcomeSuccess] = useState<string | null>(null);

  // Create Property Form
  const [formData, setFormData] = useState({
    title: '',
    property_type: 'apartment',
    property_category: 'residential',
    transaction_category: 'resale',
    listing_type: 'exclusive',
    status: 'available',
    price: 12000000,
    built_up_area_sqft: 1400,
    bedrooms: 2,
    bathrooms: 2,
    balconies: 1,
    furnishing: 'semi_furnished',
    construction_status: 'ready_to_move',
    locality: 'Indiranagar',
    city: 'Bengaluru',
    project_name: '',
    unit_number: '',
    address: '',
    description: '',
    owner_name: '',
    owner_phone: '',
    amenities: 'Gym, Swimming Pool, 24/7 Security, Clubhouse'
  });

  // Site Visit Form
  const [visitLeadId, setVisitLeadId] = useState('');
  const [visitDate, setVisitDate] = useState('');
  const [visitNotes, setVisitNotes] = useState('');

  const fetchProperties = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [listData, dashData] = await Promise.all([
        api.properties.list({
          property_type: selectedType !== 'all' ? selectedType : undefined,
          status: selectedStatus !== 'all' ? selectedStatus : undefined,
          search: searchQuery ? searchQuery : undefined
        }),
        api.properties.getDashboard().catch(() => null)
      ]);
      setProperties((listData as any)?.items || (listData as any)?.data || (Array.isArray(listData) ? listData : []));
      if (dashData) setKpiData(dashData);
    } catch (err: any) {
      setError(err?.message || 'Failed to load properties');
      setProperties([]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchVisits = async () => {
    setIsLoadingVisits(true);
    try {
      const visits = await api.properties.listVisits();
      setScheduledVisits(visits || []);
    } catch {
      setScheduledVisits([]);
    } finally {
      setIsLoadingVisits(false);
    }
  };

  useEffect(() => {
    fetchProperties();
    fetchVisits();
  }, [selectedType, selectedStatus, searchQuery]);

  // Deep-link effect: select and scroll to property
  useEffect(() => {
    if (deepLinkId) {
      setHighlightedId(deepLinkId);
    }
  }, [deepLinkId]);

  useEffect(() => {
    if (highlightedId && properties.length > 0) {
      const el = document.getElementById(`property-${highlightedId}`);
      if (el) {
        setTimeout(() => {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 150);
      }
    }
  }, [highlightedId, properties]);

  // Price Update Handlers
  const openPriceModal = (prop: any) => {
    setPriceModalProperty(prop);
    setNewPrice(prop.price);
    setPriceReason('Market Correction');
    setIsPriceModalOpen(true);
  };

  const handleUpdatePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!priceModalProperty || newPrice <= 0) return;
    setIsSubmitting(true);
    try {
      await api.properties.updatePrice(priceModalProperty.id, {
        new_price: Number(newPrice),
        reason: priceReason,
      });
      setPriceUpdateSuccess(`Price updated to ${formatCurrencyINR(newPrice)}! Price history logged and revenue engine re-evaluated.`);
      setTimeout(() => setPriceUpdateSuccess(null), 6000);
      setIsPriceModalOpen(false);
      fetchProperties();
    } catch (err: any) {
      alert(`Failed to update price: ${err?.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Site Visit Debrief Handlers
  const openDebriefModal = (visit: any) => {
    setDebriefVisit(visit);
    setDebriefInterest('High');
    setDebriefObjection('');
    setDebriefNotes('');
    setDebriefNextStep('Send offer sheet / arrange second viewing');
    setIsDebriefModalOpen(true);
  };

  const handleCompleteVisit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!debriefVisit) return;
    setIsSubmitting(true);
    try {
      const outcomeVal = debriefInterest === 'High' ? 'interested' : debriefInterest === 'Not interested' ? 'rejected' : 'attended';
      const feedbackText = [
        `Client Interest: ${debriefInterest}`,
        debriefObjection ? `Objection: ${debriefObjection}` : null,
        debriefNotes ? `Notes: ${debriefNotes}` : null,
      ].filter(Boolean).join('\n');

      await api.properties.recordVisitOutcome(debriefVisit.meeting_id, {
        outcome: outcomeVal,
        feedback: feedbackText,
        next_action: debriefNextStep,
      });

      setVisitOutcomeSuccess(`Site visit for ${debriefVisit.property_title || 'property'} marked completed! Revenue Autopilot generated a POST_SITE_VISIT_FOLLOW_UP opportunity.`);
      setTimeout(() => setVisitOutcomeSuccess(null), 6000);
      setIsDebriefModalOpen(false);
      fetchVisits();
    } catch (err: any) {
      alert(`Failed to complete site visit: ${err?.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateProperty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      setFormError('Property title is required');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      const amenitiesList = formData.amenities
        ? formData.amenities.split(',').map(s => s.trim()).filter(Boolean)
        : [];

      await api.properties.create({
        title: formData.title.trim(),
        property_type: formData.property_type,
        property_category: formData.property_category,
        transaction_category: formData.transaction_category,
        listing_type: formData.listing_type,
        status: formData.status,
        price: Number(formData.price),
        currency_code: 'INR',
        built_up_area_sqft: Number(formData.built_up_area_sqft),
        bedrooms: Number(formData.bedrooms),
        bathrooms: Number(formData.bathrooms),
        balconies: Number(formData.balconies),
        furnishing: formData.furnishing,
        construction_status: formData.construction_status,
        locality: formData.locality.trim(),
        city: formData.city.trim(),
        project_name: formData.project_name.trim() || undefined,
        unit_number: formData.unit_number.trim() || undefined,
        address: formData.address.trim() || undefined,
        description: formData.description.trim() || undefined,
        owner_name: formData.owner_name.trim() || undefined,
        owner_phone: formData.owner_phone.trim() || undefined,
        amenities: amenitiesList
      });

      setIsCreateModalOpen(false);
      fetchProperties();
    } catch (err: any) {
      setFormError(err?.message || 'Failed to create property listing');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReserveProperty = async (prop: any) => {
    if (!confirm(`Reserve property "${prop.title}" (${prop.property_code})?`)) return;
    try {
      await api.properties.reserve(prop.id);
      alert('Property marked as RESERVED successfully.');
      fetchProperties();
    } catch (err: any) {
      alert(err?.message || 'Failed to reserve property');
    }
  };

  const handleDeleteProperty = async (id: string, title: string) => {
    if (!confirm(`Are you sure you want to archive property "${title}"?`)) return;
    try {
      await api.properties.delete(id);
      setProperties(prev => prev.filter(p => p.id !== id));
    } catch (err: any) {
      alert(err?.message || 'Failed to delete property');
    }
  };

  const openShareModal = (prop: any) => {
    setActiveProperty(prop);
    setCopiedLink(false);
    setIsShareModalOpen(true);
  };

  const openLeadsModal = async (prop: any) => {
    setActiveProperty(prop);
    setIsLeadsModalOpen(true);
    setLeadsModalTab('ai_matched');
    setIsLoadingMatchedLeads(true);
    try {
      const [leads, matchesRes] = await Promise.all([
        api.properties.getLeads(prop.id).catch(() => []),
        api.matching.getPropertyLeadMatches(prop.id, { limit: 10 }).catch(() => ({ matches: [] }))
      ]);
      setPropertyLeads(leads || []);
      setMatchedBuyerLeads(Array.isArray(matchesRes) ? matchesRes : (matchesRes?.matches || []));
    } catch {
      setPropertyLeads([]);
      setMatchedBuyerLeads([]);
    } finally {
      setIsLoadingMatchedLeads(false);
    }
  };

  const handleShortlistLeadForProp = async (leadId: string) => {
    if (!activeProperty) return;
    try {
      await api.matching.shortlist({
        lead_id: leadId,
        property_id: activeProperty.id,
        notes: `Shortlisted for property ${activeProperty.property_code}`
      });
      alert('Lead shortlisted for this property!');
    } catch (err: any) {
      alert(err?.message || 'Failed to shortlist');
    }
  };

  const handleRecommendPropToLead = async (leadId: string) => {
    if (!activeProperty) return;
    try {
      await api.matching.recommend({
        lead_id: leadId,
        property_id: activeProperty.id,
        notes: `Recommended property ${activeProperty.property_code} to lead`
      });
      alert('Property recommended to lead! Task created.');
    } catch (err: any) {
      alert(err?.message || 'Failed to recommend');
    }
  };

  const openVisitModal = (prop: any) => {
    setActiveProperty(prop);
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(11, 0, 0, 0);
    setVisitDate(tomorrow.toISOString().slice(0, 16));
    setIsVisitModalOpen(true);
  };

  const handleScheduleVisit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!visitLeadId) {
      alert('Please enter a Lead UUID to book visit');
      return;
    }
    setIsSubmitting(true);
    try {
      await api.properties.scheduleVisit(activeProperty.id, {
        lead_id: visitLeadId.trim(),
        scheduled_at: new Date(visitDate).toISOString(),
        duration_minutes: 60,
        notes: visitNotes.trim()
      });
      alert('Site visit scheduled successfully! Task and meeting created.');
      setIsVisitModalOpen(false);
      setVisitLeadId('');
      setVisitNotes('');
      fetchVisits();
    } catch (err: any) {
      alert(err?.message || 'Failed to schedule visit');
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyShareLink = () => {
    if (!activeProperty?.share_token) return;
    const url = `${typeof window !== 'undefined' ? window.location.origin : ''}/api/v1/properties/public/${activeProperty.share_token}`;
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8] pb-6">
          <div>
            <div className="flex items-center gap-2">
              <h1
                className="text-[26px] sm:text-[28px] font-bold text-[#1A1A1A] tracking-tight leading-tight"
                style={{ fontFamily: 'JetBrains Mono, monospace' }}
              >
                PROPERTY INVENTORY &amp; CRM
              </h1>
              <span className="bg-[#1A1A1A] text-[#E8F5A8] text-[10px] font-mono px-2 py-0.5 rounded font-bold">
                PART 28
              </span>
            </div>
            <p className="text-[13px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
              Manage active listings, track live availability, lead interest, site visits &amp; public customer sharing.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={fetchProperties}
              disabled={isLoading}
              title="Refresh inventory"
              className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#4A4A4A] rounded-lg transition-all"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[#0D9488]' : ''}`} />
            </button>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[11px] font-bold transition-all shadow-xs"
            >
              <Plus className="w-4 h-4" />
              <span>+ Add New Property</span>
            </button>
          </div>
        </div>

        {/* Inventory KPI Summary Bar */}
        {kpiData && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="bg-white border border-[#D4D0C8] p-3.5 rounded-xl shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Total Units</span>
              <div className="text-xl font-bold font-mono text-[#1A1A1A] mt-0.5">{kpiData.total_properties}</div>
            </div>
            <div className="bg-white border border-[#D4D0C8] p-3.5 rounded-xl shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-emerald-600 font-bold">Available</span>
              <div className="text-xl font-bold font-mono text-emerald-700 mt-0.5">{kpiData.available}</div>
            </div>
            <div className="bg-white border border-[#D4D0C8] p-3.5 rounded-xl shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-amber-600 font-bold">Reserved</span>
              <div className="text-xl font-bold font-mono text-amber-700 mt-0.5">{kpiData.reserved}</div>
            </div>
            <div className="bg-white border border-[#D4D0C8] p-3.5 rounded-xl shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-blue-600 font-bold">Sold / Rented</span>
              <div className="text-xl font-bold font-mono text-blue-700 mt-0.5">{kpiData.sold + kpiData.rented}</div>
            </div>
            <div className="bg-white border border-[#D4D0C8] p-3.5 rounded-xl shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Avg Price</span>
              <div className="text-sm font-bold font-mono text-[#1A1A1A] mt-1.5">{formatCurrencyINR(kpiData.average_price)}</div>
            </div>
            <div className="bg-white border border-[#D4D0C8] p-3.5 rounded-xl shadow-2xs">
              <span className="text-[10px] font-mono uppercase text-gray-500 font-bold">Avg Price/SqFt</span>
              <div className="text-sm font-bold font-mono text-[#1A1A1A] mt-1.5">₹{kpiData.average_price_per_sqft}/sqft</div>
            </div>
          </div>
        )}

        {/* Filter & Search Toolbar */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-3 bg-[#FAF7F2] border border-[#D4D0C8] p-3.5 rounded-2xl shadow-xs">
          <div className="relative w-full md:w-80">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by code, title, project, locality..."
              className="w-full pl-9 pr-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs focus:outline-none focus:border-[#1A1A1A]"
              style={{ fontFamily: 'Inter, sans-serif' }}
            />
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
            {/* Status Tabs */}
            <div className="flex items-center bg-white border border-[#D4D0C8] rounded-lg p-0.5">
              {['all', 'available', 'reserved', 'sold'].map((st) => (
                <button
                  key={st}
                  onClick={() => setSelectedStatus(st)}
                  className={`px-2.5 py-1 text-[11px] font-mono font-bold rounded-md uppercase transition-all ${
                    selectedStatus === st ? 'bg-[#1A1A1A] text-white' : 'text-gray-600 hover:text-black'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>

            {/* Type Tabs */}
            <div className="flex items-center bg-white border border-[#D4D0C8] rounded-lg p-0.5">
              {['all', 'apartment', 'villa', 'penthouse', 'commercial'].map((t) => (
                <button
                  key={t}
                  onClick={() => setSelectedType(t)}
                  className={`px-2.5 py-1 text-[11px] font-mono font-bold rounded-md uppercase transition-all ${
                    selectedType === t ? 'bg-[#1A1A1A] text-white' : 'text-gray-600 hover:text-black'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Deep-link notification & Success banners */}
        {deepLinkId && !isLoading && !properties.some(p => p.id === deepLinkId) && (
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between text-xs text-amber-800 shadow-xs">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>
                Property ID <strong className="font-mono">{deepLinkId}</strong> was not found in current inventory or you lack authorization.
              </span>
            </div>
            <button onClick={() => setHighlightedId(null)} className="text-amber-700 hover:text-black">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {priceUpdateSuccess && (
          <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between text-xs text-emerald-800 shadow-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{priceUpdateSuccess}</span>
            </div>
            <Link href="/dashboard/autopilot" className="font-bold underline text-emerald-900 ml-2 shrink-0">
              View in Autopilot →
            </Link>
          </div>
        )}

        {visitOutcomeSuccess && (
          <div className="p-3.5 bg-teal-50 border border-teal-200 rounded-xl flex items-center justify-between text-xs text-teal-800 shadow-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-teal-600 shrink-0" />
              <span>{visitOutcomeSuccess}</span>
            </div>
            <Link href="/dashboard/autopilot" className="font-bold underline text-teal-900 ml-2 shrink-0">
              View Follow-up in Autopilot →
            </Link>
          </div>
        )}

        {/* ─── P2 Upcoming & Scheduled Site Visits Section ─── */}
        {scheduledVisits.filter(v => v.status !== 'completed' && v.status !== 'cancelled').length > 0 && (
          <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 sm:p-5 shadow-xs space-y-3">
            <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-teal-600" />
                <h2 className="text-sm font-bold font-mono text-[#1A1A1A] uppercase tracking-wide">
                  Upcoming Site Visits ({scheduledVisits.filter(v => v.status !== 'completed' && v.status !== 'cancelled').length})
                </h2>
              </div>
              <span className="text-[11px] text-[#6B6B6B] font-mono">
                Active Client Viewings
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {scheduledVisits
                .filter(v => v.status !== 'completed' && v.status !== 'cancelled')
                .map((visit) => (
                  <div
                    key={visit.meeting_id}
                    className="p-3.5 rounded-xl border border-[#E5E0D8] bg-[#FAF7F2] flex flex-col justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#1A1A1A] font-sans">
                          {visit.lead_name || 'Client Lead'}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-100 text-amber-800 border border-amber-200">
                          {visit.status?.toUpperCase() || 'SCHEDULED'}
                        </span>
                      </div>
                      {visit.lead_phone && (
                        <div className="text-[11px] text-gray-500 font-mono">
                          {visit.lead_phone}
                        </div>
                      )}
                      <div className="text-gray-700 font-medium">
                        {visit.property_title} {visit.property_code ? `(${visit.property_code})` : ''}
                      </div>
                      <div className="text-[11px] text-gray-500 flex items-center gap-1 font-mono">
                        <Clock className="w-3 h-3 text-gray-400" />
                        <span>
                          {visit.scheduled_at ? new Date(visit.scheduled_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Scheduled'}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => openDebriefModal(visit)}
                      className="w-full py-1.5 px-3 bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" />
                      <span>Mark Completed</span>
                    </button>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Property Cards Grid */}
        {isLoading ? (
          <div className="text-center py-20 text-sm text-[#6B6B6B] font-mono">Loading inventory...</div>
        ) : error ? (
          <div className="text-center py-20 text-sm text-red-500">{error}</div>
        ) : properties.length === 0 ? (
          <div className="text-center py-20 bg-white border border-[#D4D0C8] rounded-2xl p-8">
            <Building2 className="w-12 h-12 text-[#9CA3AF] mx-auto mb-3" />
            <h3 className="text-sm font-bold text-[#1A1A1A] mb-1 font-mono">No properties found</h3>
            <p className="text-xs text-[#6B6B6B] max-w-sm mx-auto mb-4 font-sans">
              No active listings match your current filters. Add new inventory to track lead interest and visits.
            </p>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-4 py-2 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-xs font-bold"
            >
              + Add Property
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {properties.map((prop) => (
              <div
                key={prop.id}
                id={`property-${prop.id}`}
                className={`bg-white border rounded-2xl overflow-hidden shadow-xs hover:border-[#B0ACA4] transition-all flex flex-col justify-between ${
                  highlightedId === prop.id
                    ? 'ring-2 ring-teal-600 border-teal-600 shadow-xl'
                    : 'border-[#D4D0C8]'
                }`}
              >
                <div>
                  {/* P1 Autopilot Direct Target Banner */}
                  {highlightedId === prop.id && (
                    <div className="bg-teal-600 text-white px-3 py-1.5 text-[11px] font-mono font-bold flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" />
                        AUTOPILOT TARGET LISTING
                      </span>
                      <button
                        onClick={() => setHighlightedId(null)}
                        className="text-teal-200 hover:text-white"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {/* Top Bar / Badges */}
                  <div className="p-3.5 bg-[#FAF7F2] border-b border-[#F0EDE8] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="bg-[#1A1A1A] text-white text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase">
                        {prop.property_code || 'PROP'}
                      </span>
                      <span className="bg-gray-100 text-gray-800 text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase">
                        {prop.property_type || 'apartment'}
                      </span>
                      <span
                        className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded uppercase ${
                          prop.status === 'available'
                            ? 'bg-emerald-100 text-emerald-800'
                            : prop.status === 'reserved'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {prop.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openShareModal(prop)}
                        title="Share Sanitized Link"
                        className="p-1.5 text-gray-500 hover:text-black rounded hover:bg-gray-200 transition-colors"
                      >
                        <Share2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteProperty(prop.id, prop.title)}
                        title="Archive Property"
                        className="p-1.5 text-gray-400 hover:text-red-600 rounded hover:bg-red-50 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Content */}
                  <div className="p-5 space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="text-base font-bold text-[#1A1A1A] leading-tight font-sans">
                          {prop.title}
                        </h3>
                        <div className="flex items-center gap-1 text-xs text-gray-500 font-sans mt-1">
                          <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                          <span>
                            {prop.project_name ? `${prop.project_name}, ` : ''}
                            {prop.locality}, {prop.city}
                          </span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-lg font-bold font-mono text-[#1A1A1A]">
                          {formatCurrencyINR(prop.price)}
                        </div>
                        <div className="text-[10px] font-mono text-gray-500">
                          ₹{prop.price_per_sqft || Math.round(prop.price / (prop.built_up_area_sqft || 1000))}/sqft
                        </div>
                      </div>
                    </div>

                    {/* Specs Row */}
                    <div className="grid grid-cols-4 gap-2 bg-[#F8F7F4] border border-[#ECE8E1] p-2.5 rounded-xl text-center">
                      <div>
                        <span className="text-[10px] font-mono text-gray-500 uppercase block">Bedrooms</span>
                        <span className="text-xs font-bold font-mono text-[#1A1A1A]">{prop.bedrooms} BHK</span>
                      </div>
                      <div>
                        <span className="text-[10px] font-mono text-gray-500 uppercase block">Baths</span>
                        <span className="text-xs font-bold font-mono text-[#1A1A1A]">{prop.bathrooms}</span>
                      </div>
                      <div>
                        <span className="text-[10px] font-mono text-gray-500 uppercase block">Area</span>
                        <span className="text-xs font-bold font-mono text-[#1A1A1A]">{prop.built_up_area_sqft} sqft</span>
                      </div>
                      <div>
                        <span className="text-[10px] font-mono text-gray-500 uppercase block">Furnishing</span>
                        <span className="text-xs font-bold font-mono text-[#1A1A1A] capitalize">{prop.furnishing || 'Unfurnished'}</span>
                      </div>
                    </div>

                    {/* Amenities pills */}
                    {prop.amenities && prop.amenities.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {prop.amenities.slice(0, 4).map((a: string, i: number) => (
                          <span key={i} className="text-[10px] font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                            {a}
                          </span>
                        ))}
                        {prop.amenities.length > 4 && (
                          <span className="text-[10px] font-mono text-gray-400">+{prop.amenities.length - 4} more</span>
                        )}
                      </div>
                    )}

                    {/* AVM Valuation Card */}
                    {prop.valuation && (
                      <PropertyValuationCard
                        price={prop.price}
                        areaSqft={prop.built_up_area_sqft || prop.area_value || 1000}
                        valuation={prop.valuation}
                      />
                    )}
                  </div>
                </div>

                {/* Bottom Action Footer */}
                <div className="p-3.5 bg-[#FAF7F2] border-t border-[#F0EDE8] flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => openLeadsModal(prop)}
                      className="px-2.5 py-1.5 bg-white border border-[#D4D0C8] hover:bg-gray-50 text-gray-800 rounded-lg text-xs font-bold flex items-center gap-1 transition-all"
                    >
                      <Users className="w-3.5 h-3.5 text-blue-600" />
                      <span>Interested Leads</span>
                    </button>
                    <button
                      onClick={() => openVisitModal(prop)}
                      className="px-2.5 py-1.5 bg-white border border-[#D4D0C8] hover:bg-gray-50 text-gray-800 rounded-lg text-xs font-bold flex items-center gap-1 transition-all"
                    >
                      <Calendar className="w-3.5 h-3.5 text-teal-600" />
                      <span>Book Visit</span>
                    </button>
                    {/* P2 Price Update Action Button */}
                    <button
                      onClick={() => openPriceModal(prop)}
                      className="px-2.5 py-1.5 bg-white border border-[#D4D0C8] hover:bg-gray-50 text-gray-800 rounded-lg text-xs font-bold flex items-center gap-1 transition-all"
                      title="Update price & trigger match evaluation"
                    >
                      <Tag className="w-3.5 h-3.5 text-amber-600" />
                      <span>Update Price</span>
                    </button>
                  </div>

                  {prop.status === 'available' ? (
                    <button
                      onClick={() => handleReserveProperty(prop)}
                      className="px-3 py-1.5 bg-[#1A1A1A] hover:bg-black text-white rounded-lg text-xs font-bold font-mono transition-all"
                    >
                      Reserve Unit
                    </button>
                  ) : (
                    <span className="text-xs font-mono text-gray-500 font-bold capitalize">
                      Status: {prop.status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Share Modal ─── */}
      {isShareModalOpen && activeProperty && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold font-mono text-[#1A1A1A] text-base">Public Property Share Link</h3>
              <button onClick={() => setIsShareModalOpen(false)} className="text-gray-400 hover:text-black">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-gray-600">
              This link is sanitized for external sharing with clients. Internal notes, owner phone/email, and commission data are strictly omitted.
            </p>
            <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-3 rounded-xl flex items-center justify-between gap-2">
              <span className="text-xs font-mono truncate text-gray-700">
                {`/api/v1/properties/public/${activeProperty.share_token}`}
              </span>
              <button
                onClick={copyShareLink}
                className="px-3 py-1.5 bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold rounded-lg shrink-0 flex items-center gap-1"
              >
                {copiedLink ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedLink ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── Site Visit Modal ─── */}
      {isVisitModalOpen && activeProperty && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="font-bold font-mono text-[#1A1A1A] text-base">Schedule Site Visit</h3>
              <button onClick={() => setIsVisitModalOpen(false)} className="text-gray-400 hover:text-black">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleScheduleVisit} className="space-y-3">
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">Lead ID / Client UUID</label>
                <input
                  type="text"
                  required
                  value={visitLeadId}
                  onChange={(e) => setVisitLeadId(e.target.value)}
                  placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">Date &amp; Time</label>
                <input
                  type="datetime-local"
                  required
                  value={visitDate}
                  onChange={(e) => setVisitDate(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                />
              </div>
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">Viewing Notes</label>
                <textarea
                  rows={2}
                  value={visitNotes}
                  onChange={(e) => setVisitNotes(e.target.value)}
                  placeholder="Key at security desk, client arriving with architect..."
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                />
              </div>
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] font-bold text-xs rounded-xl transition-all"
              >
                {isSubmitting ? 'Booking Visit...' : 'Confirm Site Visit & Create Task'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ─── Interested & Matched Leads Modal ─── */}
      {isLeadsModalOpen && activeProperty && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-xl max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#ECE8E1] pb-3">
              <div>
                <h3 className="font-bold font-mono text-[#1A1A1A] text-base">
                  Lead Intelligence: {activeProperty.property_code}
                </h3>
                <p className="text-xs text-gray-500 font-mono">
                  {activeProperty.title} • {formatCurrencyINR(activeProperty.price)}
                </p>
              </div>
              <button onClick={() => setIsLeadsModalOpen(false)} className="text-gray-400 hover:text-black">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Tab navigation */}
            <div className="flex items-center gap-2 border-b border-[#ECE8E1] pb-2">
              <button
                onClick={() => setLeadsModalTab('ai_matched')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                  leadsModalTab === 'ai_matched'
                    ? 'bg-[#1A1A1A] text-white'
                    : 'bg-[#FAF7F2] text-gray-600 hover:text-black'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-[#E8F5A8]" />
                <span>AI Matched Buyer Leads ({matchedBuyerLeads.length})</span>
              </button>
              <button
                onClick={() => setLeadsModalTab('linked')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  leadsModalTab === 'linked'
                    ? 'bg-[#1A1A1A] text-white'
                    : 'bg-[#FAF7F2] text-gray-600 hover:text-black'
                }`}
              >
                Linked CRM Leads ({propertyLeads.length})
              </button>
            </div>

            {/* AI Matched Buyer Leads Tab */}
            {leadsModalTab === 'ai_matched' && (
              <div className="space-y-3">
                {isLoadingMatchedLeads ? (
                  <div className="text-center py-8 text-xs text-gray-500 font-mono space-y-2">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto text-black" />
                    <p>Evaluating buyer requirements against this property...</p>
                  </div>
                ) : matchedBuyerLeads.length === 0 ? (
                  <div className="text-center py-8 text-xs text-gray-500 font-mono">
                    No buyer leads currently match this property's budget, BHK, and location.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {matchedBuyerLeads.map((item: any) => {
                      const score = Math.round(item.final_score ?? item.score ?? 0);
                      return (
                        <div
                          key={item.lead_id}
                          className="p-3.5 bg-[#FAF7F2] border border-[#ECE8E1] rounded-xl space-y-2 hover:border-[#D4D0C8] transition-all"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-black">{item.lead_name || 'Buyer Lead'}</span>
                                {item.lead_score && (
                                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold">
                                    Score {item.lead_score}
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] font-mono text-gray-500 mt-0.5">
                                {item.lead_phone} • Status: <span className="capitalize">{item.lead_status}</span>
                              </div>
                            </div>

                            <div className="text-right shrink-0">
                              <span className="text-xs font-mono font-extrabold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full border border-emerald-200">
                                {score}% MATCH
                              </span>
                            </div>
                          </div>

                          {/* Reasons & Match Factors */}
                          {item.reasons && item.reasons.length > 0 && (
                            <div className="text-[11px] text-gray-600 space-y-0.5 pt-1 border-t border-[#ECE8E1]">
                              {item.reasons.slice(0, 2).map((r: string, idx: number) => (
                                <div key={idx} className="flex items-center gap-1.5 text-emerald-700">
                                  <CheckCircle2 className="w-3 h-3 shrink-0" />
                                  <span className="truncate">{r}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Actions */}
                          <div className="flex items-center justify-end gap-2 pt-1 border-t border-[#ECE8E1]">
                            <button
                              onClick={() => handleShortlistLeadForProp(item.lead_id)}
                              className="px-2.5 py-1 bg-white border border-[#D4D0C8] hover:bg-gray-50 text-gray-800 text-[11px] font-bold rounded-lg transition-all flex items-center gap-1"
                            >
                              <Bookmark className="w-3 h-3" />
                              <span>Shortlist</span>
                            </button>
                            <button
                              onClick={() => handleRecommendPropToLead(item.lead_id)}
                              className="px-3 py-1 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] text-[11px] font-bold rounded-lg transition-all flex items-center gap-1"
                            >
                              <Sparkles className="w-3 h-3" />
                              <span>Recommend</span>
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Previously Linked Leads Tab */}
            {leadsModalTab === 'linked' && (
              <div className="space-y-2">
                {propertyLeads.length === 0 ? (
                  <div className="text-center py-8 text-xs text-gray-500 font-mono">
                    No leads currently linked to this property.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {propertyLeads.map((item, idx) => (
                      <div key={idx} className="p-3 bg-[#FAF7F2] border border-[#ECE8E1] rounded-xl flex items-center justify-between">
                        <div>
                          <div className="text-xs font-bold text-black">{item.lead_name}</div>
                          <div className="text-[11px] font-mono text-gray-500">{item.lead_phone}</div>
                        </div>
                        <div className="text-right">
                          <span className="text-[10px] font-mono font-bold px-2 py-0.5 bg-blue-100 text-blue-800 rounded uppercase">
                            {item.status}
                          </span>
                          <div className="text-[10px] text-gray-400 mt-1 font-mono">Visits: {item.visit_count}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Create Property Modal ─── */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#D4D0C8] pb-3">
              <h3 className="font-bold font-mono text-[#1A1A1A] text-base">Add New Property Listing</h3>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-gray-400 hover:text-black">
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateProperty} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="sm:col-span-2">
                  <label className="text-xs font-bold text-gray-700 block mb-1">Listing Headline *</label>
                  <input
                    type="text"
                    required
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="e.g. Luxury 3BHK Penthouse in Indiranagar"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">Property Type</label>
                  <select
                    value={formData.property_type}
                    onChange={(e) => setFormData({ ...formData, property_type: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black bg-white"
                  >
                    <option value="apartment">Apartment</option>
                    <option value="villa">Villa</option>
                    <option value="penthouse">Penthouse</option>
                    <option value="independent_house">Independent House</option>
                    <option value="plot">Plot / Land</option>
                    <option value="commercial">Commercial Office</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">Price (INR) *</label>
                  <input
                    type="number"
                    required
                    value={formData.price}
                    onChange={(e) => setFormData({ ...formData, price: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">Built-Up Area (SqFt) *</label>
                  <input
                    type="number"
                    required
                    value={formData.built_up_area_sqft}
                    onChange={(e) => setFormData({ ...formData, built_up_area_sqft: Number(e.target.value) })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-bold text-gray-700 block mb-1">Bedrooms</label>
                    <input
                      type="number"
                      value={formData.bedrooms}
                      onChange={(e) => setFormData({ ...formData, bedrooms: Number(e.target.value) })}
                      className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-gray-700 block mb-1">Bathrooms</label>
                    <input
                      type="number"
                      value={formData.bathrooms}
                      onChange={(e) => setFormData({ ...formData, bathrooms: Number(e.target.value) })}
                      className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">Locality</label>
                  <input
                    type="text"
                    value={formData.locality}
                    onChange={(e) => setFormData({ ...formData, locality: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">City</label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">Project Name</label>
                  <input
                    type="text"
                    value={formData.project_name}
                    onChange={(e) => setFormData({ ...formData, project_name: e.target.value })}
                    placeholder="e.g. Prestige Green Heights"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold text-gray-700 block mb-1">Unit Number</label>
                  <input
                    type="text"
                    value={formData.unit_number}
                    onChange={(e) => setFormData({ ...formData, unit_number: e.target.value })}
                    placeholder="e.g. Tower A - 402"
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="text-xs font-bold text-gray-700 block mb-1">Amenities (comma-separated)</label>
                  <input
                    type="text"
                    value={formData.amenities}
                    onChange={(e) => setFormData({ ...formData, amenities: e.target.value })}
                    className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="text-xs font-bold text-gray-700 block mb-1">Owner Contact (Internal Only)</label>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      placeholder="Owner Name"
                      value={formData.owner_name}
                      onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })}
                      className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                    />
                    <input
                      type="text"
                      placeholder="Owner Phone"
                      value={formData.owner_phone}
                      onChange={(e) => setFormData({ ...formData, owner_phone: e.target.value })}
                      className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                    />
                  </div>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-[#D4D0C8]">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-gray-600 hover:text-black"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] font-bold text-xs rounded-xl transition-all shadow-xs"
                >
                  {isSubmitting ? 'Creating...' : 'Create Listing & Calculate AVM'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── P2 Price Update Modal ─── */}
      {isPriceModalOpen && priceModalProperty && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#ECE8E1] pb-3">
              <div>
                <h3 className="font-bold font-mono text-[#1A1A1A] text-base flex items-center gap-2">
                  <Tag className="w-4 h-4 text-amber-600" />
                  Update Property Price
                </h3>
                <p className="text-xs text-gray-500 truncate max-w-[320px]">
                  {priceModalProperty.title}
                </p>
              </div>
              <button onClick={() => setIsPriceModalOpen(false)} className="text-gray-400 hover:text-black">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUpdatePrice} className="space-y-4">
              <div className="p-3 bg-[#FAF7F2] border border-[#E5E0D8] rounded-xl flex items-center justify-between">
                <span className="text-xs font-mono text-gray-500 font-bold uppercase">Current Price:</span>
                <span className="text-sm font-bold font-mono text-[#1A1A1A]">
                  {formatCurrencyINR(priceModalProperty.price)}
                </span>
              </div>

              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">
                  New Price (INR)
                </label>
                <input
                  type="number"
                  required
                  min={1}
                  step={10000}
                  value={newPrice || ''}
                  onChange={(e) => setNewPrice(Number(e.target.value))}
                  placeholder="e.g. 13800000"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-mono"
                />
                {newPrice > 0 && (
                  <p className="text-[11px] font-mono text-teal-700 mt-1">
                    Preview: {formatCurrencyINR(newPrice)}
                  </p>
                )}
              </div>

              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">
                  Price Change Reason
                </label>
                <select
                  value={priceReason}
                  onChange={(e) => setPriceReason(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black"
                >
                  <option value="Market Correction">Market Correction</option>
                  <option value="Motivated Seller">Motivated Seller / Distress Sale</option>
                  <option value="Price Drop Promotion">Price Drop Promotion</option>
                  <option value="Seller Requested Increase">Seller Requested Increase</option>
                  <option value="Periodic Repricing">Periodic Repricing</option>
                </select>
              </div>

              <p className="text-[11px] text-gray-500 leading-relaxed">
                Saving will append a record to <strong>PropertyPriceHistory</strong>, log an audit event, and trigger the Revenue Autopilot to scan for buyer budget matches.
              </p>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-[#D4D0C8]">
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => setIsPriceModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-gray-600 hover:text-black"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || newPrice <= 0 || newPrice === priceModalProperty.price}
                  className="px-5 py-2.5 bg-[#1A1A1A] hover:bg-black text-white font-bold text-xs rounded-xl transition-all shadow-xs flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving Price...</span>
                    </>
                  ) : (
                    <span>Save &amp; Re-evaluate</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── P2 Site Visit Debrief & Completion Modal ─── */}
      {isDebriefModalOpen && debriefVisit && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#ECE8E1] pb-3">
              <div>
                <h3 className="font-bold font-mono text-[#1A1A1A] text-base flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-teal-600" />
                  Complete Site Visit
                </h3>
                <p className="text-xs text-gray-500">
                  {debriefVisit.lead_name} • {debriefVisit.property_title}
                </p>
              </div>
              <button onClick={() => setIsDebriefModalOpen(false)} className="text-gray-400 hover:text-black">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCompleteVisit} className="space-y-3">
              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">
                  Buyer Interest Level
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {(['High', 'Medium', 'Low', 'Not interested'] as const).map((lvl) => (
                    <button
                      type="button"
                      key={lvl}
                      onClick={() => setDebriefInterest(lvl)}
                      className={`py-2 px-1 text-center rounded-xl text-xs font-bold transition-all border ${
                        debriefInterest === lvl
                          ? 'bg-[#1A1A1A] text-white border-black'
                          : 'bg-[#FAF7F2] text-gray-700 border-[#E5E0D8] hover:bg-gray-100'
                      }`}
                    >
                      {lvl}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">
                  Client Objection (Optional)
                </label>
                <input
                  type="text"
                  value={debriefObjection}
                  onChange={(e) => setDebriefObjection(e.target.value)}
                  placeholder="e.g. Floor too low, kitchen smaller than expected"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-sans"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">
                  Debrief Notes (Optional)
                </label>
                <textarea
                  rows={3}
                  value={debriefNotes}
                  onChange={(e) => setDebriefNotes(e.target.value)}
                  placeholder="Client visited with spouse, requested payment plan details..."
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-sans"
                />
              </div>

              <div>
                <label className="text-xs font-bold text-gray-700 block mb-1">
                  Recommended Next Step
                </label>
                <input
                  type="text"
                  value={debriefNextStep}
                  onChange={(e) => setDebriefNextStep(e.target.value)}
                  placeholder="e.g. Send offer sheet, schedule second viewing"
                  className="w-full px-3 py-2 text-xs border border-[#D4D0C8] rounded-xl focus:outline-none focus:border-black font-sans"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-[#D4D0C8]">
                <button
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => setIsDebriefModalOpen(false)}
                  className="px-4 py-2 text-xs font-bold text-gray-600 hover:text-black"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] font-bold text-xs rounded-xl transition-all shadow-xs flex items-center gap-1.5"
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Completing...</span>
                    </>
                  ) : (
                    <span>Complete Visit</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PropertiesPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F0EDE8] flex items-center justify-center font-mono text-sm text-gray-500">Loading Properties CRM...</div>}>
      <PropertiesContent />
    </Suspense>
  );
}
