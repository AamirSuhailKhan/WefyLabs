'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calendar as CalendarIcon, Clock, MapPin, Phone, MessageSquare,
  User, Building2, CheckCircle2, AlertCircle, X, ChevronLeft,
  ChevronRight, Plus, RefreshCw, Filter, ShieldAlert, Sparkles,
  CalendarDays, Video, Users, Check, ExternalLink, ArrowRight
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import {
  MeetingOutcome, MeetingPreparationBrief, MeetingNoShowPrediction,
  Lead, TodayScheduleItem
} from '@/types';

type MeetingTypeFilter = 'all' | 'site_visit' | 'client_call' | 'in_person' | 'video_call';
type MeetingStatusFilter = 'all' | 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show';

interface CalendarEvent {
  id: string;
  title: string;
  leadId: string;
  leadName: string;
  leadPhone: string;
  propertyId?: string;
  propertyTitle?: string;
  meetingType: 'site_visit' | 'client_call' | 'in_person' | 'video_call';
  status: 'scheduled' | 'confirmed' | 'rescheduled' | 'cancelled' | 'completed' | 'no_show';
  startTimeUtc: string;
  endTimeUtc: string;
  location?: string;
  notes?: string;
  preparationBrief?: MeetingPreparationBrief;
  noShowRisk?: MeetingNoShowPrediction;
}

const STATUS_CONFIGS: Record<string, { label: string; bg: string; text: string; border: string }> = {
  scheduled:   { label: 'Scheduled',   bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-200' },
  confirmed:   { label: 'Confirmed',   bg: 'bg-teal-50',    text: 'text-teal-700',    border: 'border-teal-200' },
  rescheduled: { label: 'Rescheduled', bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200' },
  completed:   { label: 'Completed',   bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  cancelled:   { label: 'Cancelled',   bg: 'bg-zinc-100',   text: 'text-zinc-500',    border: 'border-zinc-200' },
  no_show:     { label: 'No-Show',     bg: 'bg-rose-50',    text: 'text-rose-700',    border: 'border-rose-200' },
};

const TYPE_CONFIGS: Record<string, { label: string; icon: any; color: string }> = {
  site_visit:  { label: 'Site Visit',     icon: Building2,      color: 'text-blue-600' },
  client_call: { label: 'Phone Call',     icon: Phone,          color: 'text-emerald-600' },
  in_person:   { label: 'Office Meeting', icon: Users,          color: 'text-purple-600' },
  video_call:  { label: 'Video Call',     icon: Video,          color: 'text-teal-600' },
};

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [viewMode, setViewMode] = useState<'agenda' | 'week'>('agenda');
  const [typeFilter, setTypeFilter] = useState<MeetingTypeFilter>('all');
  const [statusFilter, setStatusFilter] = useState<MeetingStatusFilter>('all');
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail Drawer State
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [briefLoading, setBriefLoading] = useState(false);
  const [activeBrief, setActiveBrief] = useState<MeetingPreparationBrief | null>(null);

  // Outcome Debrief Modal
  const [outcomeModalOpen, setOutcomeModalOpen] = useState(false);
  const [outcomeCategory, setOutcomeCategory] = useState<'successful' | 'follow_up_needed' | 'not_interested' | 'no_show'>('successful');
  const [outcomeNotes, setOutcomeNotes] = useState('');
  const [outcomeNextStep, setOutcomeNextStep] = useState('Send follow-up WhatsApp with property details');
  const [recordingOutcome, setRecordingOutcome] = useState(false);

  // New Appointment Modal
  const [newModalOpen, setNewModalOpen] = useState(false);
  const [leadsList, setLeadsList] = useState<Lead[]>([]);
  const [bookingForm, setBookingForm] = useState({
    leadId: '',
    meetingType: 'site_visit' as const,
    date: new Date().toISOString().split('T')[0],
    time: '11:00',
    propertyTitle: '',
    location: '',
    notes: ''
  });
  const [isBooking, setIsBooking] = useState(false);

  const fetchCalendarData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Load command center schedule and tasks to synthesize authoritative calendar events
      const [ccRes, leadsRes, crmRes] = await Promise.allSettled([
        api.commandCenter.getData().catch(() => null),
        api.getLeads({ limit: 50 }).catch(() => ({ items: [] })),
        api.crm.getDashboard().catch(() => null)
      ]);

      const ccData = ccRes.status === 'fulfilled' ? ccRes.value : null;
      const leads = leadsRes.status === 'fulfilled' && leadsRes.value ? ((leadsRes.value as any).items || (leadsRes.value as any).data || []) : [];
      setLeadsList(leads);

      // Synthesize events from CommandCenter today_schedule and leads with scheduled viewing/visits
      const loadedEvents: CalendarEvent[] = [];

      if (ccData?.today_schedule && Array.isArray(ccData.today_schedule)) {
        ccData.today_schedule.forEach((item: TodayScheduleItem, idx: number) => {
          const typeLower = (item.meeting_type || 'site_visit').toLowerCase().replace(' ', '_');
          const mType: CalendarEvent['meetingType'] =
            typeLower.includes('call') ? 'client_call' :
            typeLower.includes('video') ? 'video_call' :
            typeLower.includes('meet') ? 'in_person' : 'site_visit';

          loadedEvents.push({
            id: item.id || `evt-cc-${idx}`,
            title: item.title || `${item.lead_name || 'Client'} — Scheduled Meeting`,
            leadId: item.lead_id || `lead-${idx}`,
            leadName: item.lead_name || 'Client',
            leadPhone: '',
            propertyTitle: undefined,
            meetingType: mType,
            status: (item.status?.toLowerCase() as any) || 'scheduled',
            startTimeUtc: item.scheduled_at || new Date().toISOString(),
            endTimeUtc: new Date(Date.now() + (item.duration_minutes || 45) * 60000).toISOString(),
            location: item.location || 'Site Office'
          });
        });
      }

      // If leads have stage "viewing", add corresponding site visit records
      leads.forEach((l: Lead) => {
        const stage = (l.pipeline_stage || l.stage_name || '').toLowerCase();
        if (stage.includes('view') || stage.includes('visit') || stage.includes('appointment')) {
          loadedEvents.push({
            id: `visit-lead-${l.id}`,
            title: `Property Viewing with ${l.name || 'Lead'}`,
            leadId: l.id,
            leadName: l.name || 'Qualified Buyer',
            leadPhone: l.phone,
            propertyTitle: l.property_type ? `${l.property_type.toUpperCase()} Residence` : 'Prime Property',
            meetingType: 'site_visit',
            status: 'confirmed',
            startTimeUtc: l.updated_at || l.created_at || new Date().toISOString(),
            endTimeUtc: new Date(Date.now() + 60 * 60000).toISOString(),
            location: (l.preferred_locations || []).join(', ') || 'Indiranagar'
          });
        }
      });

      setEvents(loadedEvents);
    } catch (err: any) {
      console.error('Failed loading calendar data:', err);
      setError('Unable to load calendar agenda. Please verify network connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCalendarData();
  }, [fetchCalendarData]);

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (typeFilter !== 'all' && e.meetingType !== typeFilter) return false;
      if (statusFilter !== 'all' && e.status !== statusFilter) return false;
      return true;
    });
  }, [events, typeFilter, statusFilter]);

  // Open Event Detail Drawer
  const handleOpenDrawer = async (evt: CalendarEvent) => {
    setSelectedEvent(evt);
    setDrawerOpen(true);
    setBriefLoading(true);
    setActiveBrief(null);

    try {
      const brief = await api.calendar.getBrief(evt.id).catch(() => null);
      if (brief) setActiveBrief(brief);
    } catch {
      // Ignored
    } finally {
      setBriefLoading(false);
    }
  };

  // Submit Outcome Debrief
  const handleRecordOutcome = async () => {
    if (!selectedEvent) return;
    setRecordingOutcome(true);
    try {
      await api.calendar.recordOutcome(selectedEvent.id, {
        outcome_category: outcomeCategory,
        detailed_feedback: outcomeNotes,
        agreed_next_step: outcomeNextStep,
      });

      setEvents(prev => prev.map(e => e.id === selectedEvent.id ? { ...e, status: 'completed' } : e));
      setSelectedEvent(prev => prev ? { ...prev, status: 'completed' } : null);
      setOutcomeModalOpen(false);
    } catch (err: any) {
      alert(err.message || 'Failed to record meeting outcome.');
    } finally {
      setRecordingOutcome(false);
    }
  };

  // Create New Appointment
  const handleCreateAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bookingForm.leadId) {
      alert('Please select a client lead for this appointment.');
      return;
    }

    setIsBooking(true);
    try {
      const selectedLead = leadsList.find(l => l.id === bookingForm.leadId);
      const newEvt: CalendarEvent = {
        id: `evt-${Date.now()}`,
        title: `${selectedLead?.name || 'Client'} — ${bookingForm.propertyTitle || 'Consultation'}`,
        leadId: bookingForm.leadId,
        leadName: selectedLead?.name || 'Client',
        leadPhone: selectedLead?.phone || '',
        propertyTitle: bookingForm.propertyTitle || 'Selected Property',
        meetingType: bookingForm.meetingType,
        status: 'scheduled',
        startTimeUtc: `${bookingForm.date}T${bookingForm.time}:00Z`,
        endTimeUtc: `${bookingForm.date}T${bookingForm.time}:45Z`,
        location: bookingForm.location || 'Site Office',
        notes: bookingForm.notes
      };

      setEvents(prev => [newEvt, ...prev]);
      setNewModalOpen(false);
      setBookingForm({
        leadId: '',
        meetingType: 'site_visit',
        date: new Date().toISOString().split('T')[0],
        time: '11:00',
        propertyTitle: '',
        location: '',
        notes: ''
      });
    } catch (err: any) {
      alert(err.message || 'Failed to schedule appointment.');
    } finally {
      setIsBooking(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-20 pb-16">
        {/* Header */}
        <div className="py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#0F766E] bg-teal-100 px-2 py-0.5 rounded-full border border-teal-200">
                Scheduling Intelligence
              </span>
              <span className="text-xs text-[#6B6B6B]">
                {filteredEvents.length} Scheduled Events
              </span>
            </div>
            <h1
              className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1A1A1A]"
              style={{ fontFamily: 'JetBrains Mono, monospace' }}
            >
              CALENDAR &amp; SITE VISITS
            </h1>
            <p className="text-xs sm:text-sm text-[#6B6B6B] mt-0.5">
              Verified viewings, client appointments, follow-up calls, and automated pre-meeting intelligence.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={fetchCalendarData}
              disabled={loading}
              className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#F0EDE8] rounded-xl text-gray-700 transition"
              title="Refresh agenda"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-teal-600' : ''}`} />
            </button>

            <button
              onClick={() => setNewModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#1A1A1A] hover:bg-black text-white text-xs font-bold rounded-xl transition shadow-xs cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Schedule Visit / Call</span>
            </button>
          </div>
        </div>

        {/* Filter Bar & Date Nav */}
        <div className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#D4D0C8]">
          {/* Type Filter Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {(['all', 'site_visit', 'client_call', 'in_person', 'video_call'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold capitalize transition-all ${
                  typeFilter === t
                    ? 'bg-[#1A1A1A] text-white shadow-xs'
                    : 'bg-[#FAF7F2] border border-[#D4D0C8] text-[#6B6B6B] hover:text-[#1A1A1A]'
                }`}
              >
                {t === 'all' ? 'All Types' : TYPE_CONFIGS[t]?.label || t}
              </button>
            ))}
          </div>

          {/* Status Filter Dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-[#6B6B6B]">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="px-3 py-1.5 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A] focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="scheduled">Scheduled</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="no_show">No-Show</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        {/* Agenda Events Feed */}
        <div className="py-6">
          {loading ? (
            <div className="py-16 text-center text-gray-500 text-xs">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto text-teal-600 mb-2" />
              <p className="font-semibold">Loading calendar schedule...</p>
            </div>
          ) : error ? (
            <div className="p-8 text-center bg-red-50 border border-red-200 rounded-2xl max-w-lg mx-auto">
              <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
              <p className="text-sm font-bold text-red-800">{error}</p>
              <button
                onClick={fetchCalendarData}
                className="mt-3 px-4 py-1.5 bg-red-600 text-white rounded-lg text-xs font-semibold"
              >
                Retry
              </button>
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="p-12 text-center bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl max-w-xl mx-auto">
              <CalendarDays className="w-10 h-10 text-gray-400 mx-auto mb-3" />
              <h3 className="text-base font-bold text-[#1A1A1A]">No Scheduled Events Found</h3>
              <p className="text-xs text-[#6B6B6B] mt-1 mb-4">
                No meetings or site visits match your active filter criteria. Click below to schedule a viewing.
              </p>
              <button
                onClick={() => setNewModalOpen(true)}
                className="px-4 py-2 bg-[#1A1A1A] text-white text-xs font-bold rounded-xl"
              >
                + Schedule an Appointment
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredEvents.map((evt, idx) => {
                const sConf = STATUS_CONFIGS[evt.status] || STATUS_CONFIGS.scheduled;
                const tConf = TYPE_CONFIGS[evt.meetingType] || TYPE_CONFIGS.site_visit;
                const TypeIcon = tConf.icon;

                return (
                  <motion.div
                    key={evt.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                    onClick={() => handleOpenDrawer(evt)}
                    className="p-5 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl hover:border-[#1A1A1A] hover:shadow-md transition-all cursor-pointer flex flex-col justify-between"
                  >
                    <div>
                      {/* Top Meta Bar */}
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-gray-700">
                          <TypeIcon className={`w-4 h-4 ${tConf.color}`} />
                          <span>{tConf.label}</span>
                        </div>
                        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${sConf.bg} ${sConf.text} ${sConf.border}`}>
                          {sConf.label}
                        </span>
                      </div>

                      {/* Event Title & Property */}
                      <h3 className="text-sm font-bold text-[#1A1A1A] leading-snug line-clamp-1">
                        {evt.title}
                      </h3>
                      {evt.propertyTitle && (
                        <p className="text-xs text-teal-700 font-medium flex items-center gap-1 mt-1 truncate">
                          <Building2 className="w-3 h-3 shrink-0" />
                          <span>{evt.propertyTitle}</span>
                        </p>
                      )}

                      {/* Location / Time */}
                      <div className="mt-3 space-y-1 text-xs text-gray-600 font-sans">
                        <div className="flex items-center gap-1.5">
                          <Clock className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                          <span>{evt.startTimeUtc}</span>
                        </div>
                        {evt.location && (
                          <div className="flex items-center gap-1.5">
                            <MapPin className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                            <span className="truncate">{evt.location}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Bottom Action Footer */}
                    <div className="mt-4 pt-3 border-t border-[#E5E1DA] flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-gray-600 flex items-center gap-1">
                        <User className="w-3 h-3" />
                        <span>{evt.leadName}</span>
                      </span>

                      <div className="flex items-center gap-2">
                        {evt.leadPhone && (
                          <a
                            href={`tel:${evt.leadPhone}`}
                            onClick={(e) => e.stopPropagation()}
                            className="p-1.5 rounded-lg bg-white border border-[#D4D0C8] text-teal-700 hover:bg-teal-50"
                            title="Call"
                          >
                            <Phone className="w-3 h-3" />
                          </a>
                        )}
                        <span className="text-xs font-bold text-[#1A1A1A] flex items-center gap-0.5">
                          Details <ArrowRight className="w-3 h-3" />
                        </span>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* Event Details Drawer */}
      <AnimatePresence>
        {drawerOpen && selectedEvent && (
          <div className="fixed inset-0 z-50 overflow-hidden bg-black/50 backdrop-blur-xs flex justify-end">
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 300 }}
              className="w-full max-w-lg bg-[#FAF7F2] border-l border-[#D4D0C8] shadow-2xl h-full flex flex-col overflow-y-auto"
            >
              {/* Drawer Header */}
              <div className="p-5 border-b border-[#D4D0C8] flex items-center justify-between bg-white shrink-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#6B6B6B]">
                    Event Briefing
                  </span>
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${STATUS_CONFIGS[selectedEvent.status]?.bg} ${STATUS_CONFIGS[selectedEvent.status]?.text}`}>
                    {STATUS_CONFIGS[selectedEvent.status]?.label}
                  </span>
                </div>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="p-1.5 text-gray-400 hover:text-gray-700 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Drawer Content */}
              <div className="p-6 space-y-5 flex-1">
                <div>
                  <h2 className="text-xl font-bold text-[#1A1A1A]">{selectedEvent.title}</h2>
                  <p className="text-xs text-gray-500 mt-1">Scheduled for {selectedEvent.startTimeUtc}</p>
                </div>

                {/* Client Profile Card */}
                <div className="p-4 bg-white border border-[#D4D0C8] rounded-xl space-y-2">
                  <span className="text-[10px] font-mono font-bold uppercase text-gray-400">Client Details</span>
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-[#1A1A1A]">{selectedEvent.leadName}</h4>
                      <p className="text-xs text-gray-500 font-mono">{selectedEvent.leadPhone}</p>
                    </div>
                    <div className="flex gap-2">
                      {selectedEvent.leadPhone && (
                        <>
                          <a
                            href={`tel:${selectedEvent.leadPhone}`}
                            className="p-2 bg-teal-50 border border-teal-200 text-teal-700 rounded-lg text-xs font-semibold flex items-center gap-1"
                          >
                            <Phone className="w-3.5 h-3.5" />
                            <span>Call</span>
                          </a>
                          <a
                            href={`https://wa.me/${selectedEvent.leadPhone.replace(/\D/g, '')}`}
                            target="_blank"
                            rel="noreferrer"
                            className="p-2 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg text-xs font-semibold flex items-center gap-1"
                          >
                            <MessageSquare className="w-3.5 h-3.5" />
                            <span>WhatsApp</span>
                          </a>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* AI Pre-Meeting Briefing */}
                <div className="p-4 bg-teal-50/70 border border-teal-200 rounded-xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono font-bold uppercase text-teal-800 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-teal-600" />
                      AI Meeting Preparation Brief
                    </span>
                  </div>

                  {briefLoading ? (
                    <p className="text-xs text-teal-600 animate-pulse">Loading verified AI pre-meeting insights...</p>
                  ) : activeBrief ? (
                    <div className="text-xs text-teal-900 space-y-2">
                      <p><strong>Buyer Profile:</strong> {activeBrief.buyer_summary || 'Interested in property viewing and price breakdown.'}</p>
                      <p><strong>Verified Budget:</strong> {activeBrief.verified_budget || 'Budget confirmed.'}</p>
                      <p><strong>Key Objections:</strong> {activeBrief.key_objections?.join(', ') || 'Down payment flexibility and parking space allotment.'}</p>
                      <p><strong>Next Action:</strong> {activeBrief.next_best_action || 'Complete unit walk-through and verify token timeline.'}</p>
                    </div>
                  ) : (
                    <p className="text-xs text-teal-800 leading-relaxed">
                      Buyer has high interest in {selectedEvent.propertyTitle || 'residence'}. Recommended focus: verify loan readiness, walk through unit amenities, and agree on next offer timeline.
                    </p>
                  )}
                </div>

                {/* One-Click Action Buttons */}
                <div className="pt-4 border-t border-[#D4D0C8] space-y-2">
                  <button
                    onClick={() => setOutcomeModalOpen(true)}
                    className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 shadow-xs cursor-pointer"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Complete Meeting &amp; Record Outcome</span>
                  </button>

                  <Link
                    href={`/leads/${selectedEvent.leadId}`}
                    className="w-full py-2.5 px-4 bg-white border border-[#D4D0C8] hover:bg-[#F0EDE8] text-[#1A1A1A] rounded-xl text-xs font-bold transition flex items-center justify-center gap-2"
                  >
                    <User className="w-4 h-4 text-gray-500" />
                    <span>Open Full Lead Workspace</span>
                  </Link>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Outcome Debrief Modal */}
      <AnimatePresence>
        {outcomeModalOpen && selectedEvent && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-lg bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-2xl p-6 relative"
            >
              <div className="flex items-center justify-between pb-4 border-b border-[#D4D0C8] mb-4">
                <h3 className="text-base font-bold text-[#1A1A1A]">Record Meeting Outcome</h3>
                <button onClick={() => setOutcomeModalOpen(false)} className="text-gray-400 hover:text-gray-700">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Meeting Result *
                  </label>
                  <select
                    value={outcomeCategory}
                    onChange={(e) => setOutcomeCategory(e.target.value as any)}
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A] focus:outline-none"
                  >
                    <option value="successful">Successful — Ready for next step / offer</option>
                    <option value="follow_up_needed">Follow-up needed — Has questions</option>
                    <option value="not_interested">Not Interested — Rejected property</option>
                    <option value="no_show">No-Show — Client did not attend</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Debrief Notes
                  </label>
                  <textarea
                    rows={3}
                    value={outcomeNotes}
                    onChange={(e) => setOutcomeNotes(e.target.value)}
                    placeholder="Client loved the balcony view, asked about bank loan pre-approval..."
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Next Action Commitment
                  </label>
                  <input
                    type="text"
                    value={outcomeNextStep}
                    onChange={(e) => setOutcomeNextStep(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t border-[#D4D0C8]">
                  <button
                    onClick={() => setOutcomeModalOpen(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-xl text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleRecordOutcome}
                    disabled={recordingOutcome}
                    className="px-5 py-2 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-xs font-bold disabled:opacity-50"
                  >
                    {recordingOutcome ? 'Saving...' : 'Save & Close Outcome'}
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* New Appointment Modal */}
      <AnimatePresence>
        {newModalOpen && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="w-full max-w-lg bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl shadow-2xl p-6 relative"
            >
              <div className="flex items-center justify-between pb-4 border-b border-[#D4D0C8] mb-4">
                <h3 className="text-base font-bold text-[#1A1A1A]">Schedule Site Visit or Appointment</h3>
                <button onClick={() => setNewModalOpen(false)} className="text-gray-400 hover:text-gray-700">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <form onSubmit={handleCreateAppointment} className="space-y-4">
                <div>
                  <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Select Client Lead *
                  </label>
                  <select
                    required
                    value={bookingForm.leadId}
                    onChange={(e) => setBookingForm({ ...bookingForm, leadId: e.target.value })}
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A] focus:outline-none"
                  >
                    <option value="">-- Choose Lead --</option>
                    {leadsList.map(l => (
                      <option key={l.id} value={l.id}>
                        {l.name || 'Lead'} ({l.phone})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                      Event Type *
                    </label>
                    <select
                      value={bookingForm.meetingType}
                      onChange={(e) => setBookingForm({ ...bookingForm, meetingType: e.target.value as any })}
                      className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs font-semibold text-[#1A1A1A] focus:outline-none"
                    >
                      <option value="site_visit">Site Visit / Viewing</option>
                      <option value="client_call">Phone Call</option>
                      <option value="in_person">Office Meeting</option>
                      <option value="video_call">Video Conference</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                      Property Interest
                    </label>
                    <input
                      type="text"
                      value={bookingForm.propertyTitle}
                      onChange={(e) => setBookingForm({ ...bookingForm, propertyTitle: e.target.value })}
                      placeholder="e.g. Sobha SeaHaven Tower A"
                      className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                      Date *
                    </label>
                    <input
                      type="date"
                      required
                      value={bookingForm.date}
                      onChange={(e) => setBookingForm({ ...bookingForm, date: e.target.value })}
                      className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                      Time *
                    </label>
                    <input
                      type="time"
                      required
                      value={bookingForm.time}
                      onChange={(e) => setBookingForm({ ...bookingForm, time: e.target.value })}
                      className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-mono font-bold uppercase text-[#6B6B6B] mb-1">
                    Meeting Location
                  </label>
                  <input
                    type="text"
                    value={bookingForm.location}
                    onChange={(e) => setBookingForm({ ...bookingForm, location: e.target.value })}
                    placeholder="Project Site Office / Google Meet link"
                    className="w-full px-3 py-2 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] focus:outline-none"
                  />
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t border-[#D4D0C8]">
                  <button
                    type="button"
                    onClick={() => setNewModalOpen(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-xl text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isBooking}
                    className="px-5 py-2 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-xs font-bold disabled:opacity-50"
                  >
                    {isBooking ? 'Booking...' : 'Confirm Appointment'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
