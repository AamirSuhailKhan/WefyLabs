'use client';

import React, { useState, useEffect } from 'react';
import { 
  Calendar, Clock, MapPin, Video, User, ShieldCheck, AlertTriangle, 
  Sparkles, CheckCircle2, ChevronRight, RefreshCw, Send, FileText, ArrowRight
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { 
  LeadDetail, CalendarTimeSlot, CalendarBookingResponse, 
  MeetingPreparationBrief, MeetingNoShowPrediction, MeetingOutcome 
} from '@/types';

interface LeadSchedulingTabProps {
  lead: LeadDetail;
  onLeadUpdated: () => void;
}

export default function LeadSchedulingTab({ lead, onLeadUpdated }: LeadSchedulingTabProps) {
  const [meetingType, setMeetingType] = useState<'PROPERTY_VIEWING' | 'SITE_VISIT' | 'VIDEO_CALL' | 'CALL' | 'OFFICE_MEETING'>('PROPERTY_VIEWING');
  const [virtualProvider, setVirtualProvider] = useState<'GOOGLE_MEET' | 'MICROSOFT_TEAMS' | 'ZOOM' | 'NONE'>('GOOGLE_MEET');
  const [durationMinutes, setDurationMinutes] = useState<number>(45);
  const [locationAddress, setLocationAddress] = useState<string>(
    lead.preferred_locations && lead.preferred_locations.length > 0
      ? `${lead.preferred_locations[0]} Site Office`
      : 'WefyLabs Real Estate Hub'
  );
  const [notes, setNotes] = useState<string>('');

  const [availableSlots, setAvailableSlots] = useState<CalendarTimeSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<CalendarTimeSlot | null>(null);
  const [searchingSlots, setSearchingSlots] = useState<boolean>(false);
  const [bookingLoading, setBookingLoading] = useState<boolean>(false);

  const [activeBooking, setActiveBooking] = useState<CalendarBookingResponse | null>(null);
  const [brief, setBrief] = useState<MeetingPreparationBrief | null>(null);
  const [noShowPred, setNoShowPred] = useState<MeetingNoShowPrediction | null>(null);
  const [outcomeSuccess, setOutcomeSuccess] = useState<boolean>(false);

  // Outcome Form state
  const [outcomeCategory, setOutcomeCategory] = useState<string>('VERY_INTERESTED');
  const [interestRating, setInterestRating] = useState<number>(4);
  const [outcomeFeedback, setOutcomeFeedback] = useState<string>('');
  const [outcomeNextStep, setOutcomeNextStep] = useState<string>('');

  const handleSearchSlots = async () => {
    setSearchingSlots(true);
    setSelectedSlot(null);
    try {
      const res = await api.calendar.searchSlots({
        lead_id: lead.id,
        meeting_type: meetingType,
        duration_minutes: durationMinutes,
        search_days_ahead: 7
      });
      setAvailableSlots(res.available_slots || []);
      if (res.available_slots && res.available_slots.length > 0) {
        setSelectedSlot(res.available_slots[0]);
      }
    } catch (err) {
      console.error('Error searching available slots:', err);
    } finally {
      setSearchingSlots(false);
    }
  };

  useEffect(() => {
    handleSearchSlots();
  }, [meetingType, durationMinutes]);

  const handleBookSlot = async () => {
    if (!selectedSlot) return;
    setBookingLoading(true);
    try {
      const booking = await api.calendar.bookMeeting({
        lead_id: lead.id,
        meeting_type: meetingType,
        slot_start_utc: selectedSlot.start_utc,
        duration_minutes: durationMinutes,
        virtual_provider: meetingType === 'VIDEO_CALL' ? virtualProvider : 'NONE',
        location_address: locationAddress,
        notes: notes,
        idempotency_key: `book_${lead.id}_${Date.now()}`
      });

      setActiveBooking(booking);
      onLeadUpdated();

      // Fetch Pre-Meeting AI Brief and No-Show Prediction
      try {
        const [briefData, noShowData] = await Promise.all([
          api.calendar.getBrief(booking.id),
          api.calendar.getNoShowPrediction(booking.id)
        ]);
        setBrief(briefData);
        setNoShowPred(noShowData);
      } catch (e) {
        console.warn('Could not load immediate brief / no-show prediction:', e);
      }
    } catch (err: any) {
      alert(`Booking Failed: ${err.message || 'Slot collision detected or server error'}`);
    } finally {
      setBookingLoading(false);
    }
  };

  const handleRecordOutcome = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBooking) return;
    try {
      await api.calendar.recordOutcome(activeBooking.id, {
        outcome_category: outcomeCategory,
        buyer_interest_level: interestRating,
        detailed_feedback: outcomeFeedback,
        agreed_next_step: outcomeNextStep
      });
      setOutcomeSuccess(true);
      onLeadUpdated();
    } catch (err: any) {
      alert(`Failed to record outcome: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Active Booking Intelligence Card */}
      {activeBooking ? (
        <div className="space-y-5 animate-in fade-in duration-300">
          <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-950/40 via-slate-900 to-slate-900 border border-emerald-500/30 text-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-emerald-500/20">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <span className="font-semibold text-emerald-300">Appointment Confirmed</span>
              </div>
              <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 font-mono">
                {activeBooking.status}
              </span>
            </div>

            <div className="mt-4 space-y-2 text-sm">
              <div className="font-medium text-base text-white">{activeBooking.title}</div>
              <div className="flex items-center gap-2 text-slate-300">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span>{new Date(activeBooking.start_utc).toLocaleString()} ({activeBooking.duration_minutes} mins)</span>
              </div>
              {activeBooking.meeting_url && (
                <div className="flex items-center gap-2 text-sky-300">
                  <Video className="w-4 h-4 text-sky-400" />
                  <a href={activeBooking.meeting_url} target="_blank" rel="noreferrer" className="underline truncate hover:text-sky-200">
                    {activeBooking.meeting_url}
                  </a>
                </div>
              )}
              {activeBooking.location_address && (
                <div className="flex items-center gap-2 text-slate-400">
                  <MapPin className="w-4 h-4 text-slate-400" />
                  <span>{activeBooking.location_address}</span>
                </div>
              )}
              <div className="pt-2 border-t border-emerald-500/10 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>⚡ Synced to Google Calendar</span>
                <span>📅 Visible in Notion Calendar</span>
              </div>
            </div>
          </div>

          {/* AI Pre-Meeting Briefing Document */}
          {brief && (
            <div className="p-5 rounded-2xl bg-gradient-to-br from-indigo-950/40 via-slate-900 to-slate-900 border border-indigo-500/30 text-slate-200">
              <div className="flex items-center gap-2 pb-3 border-b border-indigo-500/20 text-indigo-300 font-semibold">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                <span>AI Pre-Meeting Agent Briefing</span>
              </div>
              <div className="mt-4 space-y-3 text-xs leading-relaxed">
                <div>
                  <span className="font-semibold text-slate-300">Buyer Summary: </span>
                  <span className="text-slate-400">{brief.buyer_summary}</span>
                </div>
                <div>
                  <span className="font-semibold text-slate-300">Budget Ceiling: </span>
                  <span className="text-emerald-400 font-mono">{brief.verified_budget}</span>
                </div>
                {brief.key_objections && brief.key_objections.length > 0 && (
                  <div>
                    <span className="font-semibold text-slate-300">Anticipated Objections:</span>
                    <ul className="mt-1 list-disc list-inside space-y-1 text-amber-300/90">
                      {brief.key_objections.map((obj, idx) => (
                        <li key={idx}>{obj}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {brief.suggested_questions && brief.suggested_questions.length > 0 && (
                  <div>
                    <span className="font-semibold text-slate-300">Suggested Qualifying Questions:</span>
                    <ul className="mt-1 list-disc list-inside space-y-1 text-slate-300">
                      {brief.suggested_questions.map((q, idx) => (
                        <li key={idx}>{q}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="pt-2 border-t border-indigo-500/10 flex items-center gap-2 text-indigo-300 font-medium">
                  <ArrowRight className="w-4 h-4 text-indigo-400" />
                  <span>Next Best Action: {brief.next_best_action}</span>
                </div>
              </div>
            </div>
          )}

          {/* AI No-Show Risk & Preventative Mitigation */}
          {noShowPred && (
            <div className={`p-4 rounded-xl border ${
              noShowPred.risk_level === 'HIGH' 
                ? 'bg-rose-950/30 border-rose-500/30 text-rose-200' 
                : noShowPred.risk_level === 'MEDIUM'
                ? 'bg-amber-950/30 border-amber-500/30 text-amber-200'
                : 'bg-emerald-950/30 border-emerald-500/30 text-emerald-200'
            }`}>
              <div className="flex items-center justify-between text-xs font-semibold">
                <div className="flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4" />
                  <span>No-Show Risk Assessment: {noShowPred.risk_level} ({(noShowPred.no_show_probability * 100).toFixed(0)}%)</span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-white/10 font-mono">
                  Confidence {(noShowPred.confidence * 100).toFixed(0)}%
                </span>
              </div>
              {noShowPred.preventative_action && (
                <div className="mt-2 text-xs text-slate-300">
                  <span className="font-semibold">Preventative Action: </span>
                  {noShowPred.preventative_action}
                </div>
              )}
            </div>
          )}

          {/* Post-Meeting Outcome Form */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 text-slate-200">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-800 text-sm font-semibold text-slate-200">
              <FileText className="w-4 h-4 text-teal-400" />
              <span>Post-Meeting Outcome & Pipeline Sync</span>
            </div>

            {outcomeSuccess ? (
              <div className="mt-4 p-3 rounded-xl bg-emerald-500/20 text-emerald-300 text-xs text-center font-medium">
                Outcome recorded successfully! Pipeline stage advanced automatically.
              </div>
            ) : (
              <form onSubmit={handleRecordOutcome} className="mt-4 space-y-4 text-xs">
                <div>
                  <label className="block text-slate-400 font-medium mb-1">Outcome Category</label>
                  <select 
                    value={outcomeCategory} 
                    onChange={(e) => setOutcomeCategory(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
                  >
                    <option value="VERY_INTERESTED">Very Interested (Advance to Negotiation)</option>
                    <option value="INTERESTED">Interested (Viewing Completed)</option>
                    <option value="NEGOTIATION">Negotiating Terms / Payment Plan</option>
                    <option value="CONVERTED">Closed / Converted</option>
                    <option value="NOT_INTERESTED">Not Interested (Move to Nurture)</option>
                    <option value="NO_SHOW">No Show (Unresponsive)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 font-medium mb-1">Buyer Interest Rating (1 to 5)</label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        type="button"
                        key={star}
                        onClick={() => setInterestRating(star)}
                        className={`flex-1 py-1.5 rounded-lg border font-semibold ${
                          interestRating >= star
                            ? 'bg-teal-500/20 border-teal-500 text-teal-300'
                            : 'bg-slate-950 border-slate-800 text-slate-500'
                        }`}
                      >
                        {star} ★
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 font-medium mb-1">Key Buyer Feedback & Discussion Points</label>
                  <textarea
                    value={outcomeFeedback}
                    onChange={(e) => setOutcomeFeedback(e.target.value)}
                    placeholder="e.g. Buyer loved the corner unit view but requested 10% milestone deferral..."
                    rows={2}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-teal-500"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold transition flex items-center justify-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Sync Outcome to CRM</span>
                </button>
              </form>
            )}
          </div>
        </div>
      ) : (
        /* Slot Finder & Booking Configuration */
        <div className="space-y-5">
          {/* Meeting Config Options */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Meeting Type</label>
              <select
                value={meetingType}
                onChange={(e) => setMeetingType(e.target.value as any)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
              >
                <option value="PROPERTY_VIEWING">Property Viewing</option>
                <option value="SITE_VISIT">Site Visit</option>
                <option value="VIDEO_CALL">Video Call</option>
                <option value="CALL">Phone Consultation</option>
                <option value="OFFICE_MEETING">Office Meeting</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Duration</label>
              <select
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-teal-500"
              >
                <option value={30}>30 Minutes</option>
                <option value={45}>45 Minutes</option>
                <option value={60}>60 Minutes</option>
              </select>
            </div>
          </div>

          {meetingType === 'VIDEO_CALL' && (
            <div>
              <label className="block text-slate-400 font-medium text-xs mb-1">Virtual Provider</label>
              <select
                value={virtualProvider}
                onChange={(e) => setVirtualProvider(e.target.value as any)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 text-xs focus:outline-none focus:border-teal-500"
              >
                <option value="GOOGLE_MEET">Google Meet</option>
                <option value="MICROSOFT_TEAMS">Microsoft Teams</option>
                <option value="ZOOM">Zoom</option>
              </select>
            </div>
          )}

          <div>
            <label className="block text-slate-400 font-medium text-xs mb-1">Location / Address</label>
            <input
              type="text"
              value={locationAddress}
              onChange={(e) => setLocationAddress(e.target.value)}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 text-xs focus:outline-none focus:border-teal-500"
            />
          </div>

          {/* Genuine Available Slots */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-teal-400" />
                Verified Available Slots
              </span>
              <button
                type="button"
                onClick={handleSearchSlots}
                disabled={searchingSlots}
                className="text-[11px] text-teal-400 hover:text-teal-300 flex items-center gap-1"
              >
                <RefreshCw className={`w-3 h-3 ${searchingSlots ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            {searchingSlots ? (
              <div className="p-6 text-center text-xs text-slate-500">
                Checking calendar availability and working hours...
              </div>
            ) : availableSlots.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-400 text-center">
                No common slots found. Adjust parameters or check agent availability rules.
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto pr-1">
                {availableSlots.map((slot, idx) => {
                  const isSelected = selectedSlot?.start_utc === slot.start_utc;
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedSlot(slot)}
                      className={`p-3 rounded-xl border text-left transition flex items-center justify-between ${
                        isSelected
                          ? 'bg-teal-500/20 border-teal-500 text-white shadow-sm'
                          : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                      }`}
                    >
                      <div className="text-xs">
                        <div className="font-semibold text-slate-200">{slot.customer_local_start}</div>
                        <div className="text-[11px] text-slate-500">Broker Time: {slot.broker_local_start}</div>
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${
                        isSelected ? 'bg-teal-500 text-white font-medium' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {isSelected ? 'Selected' : 'Available'}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="block text-slate-400 font-medium text-xs mb-1">Appointment Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Specific units to view, client preferences, or entry gate instructions..."
              rows={2}
              className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-200 text-xs focus:outline-none focus:border-teal-500 placeholder-slate-600"
            />
          </div>

          {/* Book Appointment Button with 5-Minute Hold Protection */}
          <button
            type="button"
            onClick={handleBookSlot}
            disabled={!selectedSlot || bookingLoading}
            className="w-full py-3 rounded-xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 text-white font-semibold text-xs transition shadow-lg flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {bookingLoading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Acquiring Hold & Syncing External Calendar...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Confirm & Lock Appointment (5-Min Hold)</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
