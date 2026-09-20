'use client';

import React, { useEffect, useState } from 'react';
import { aiGetAvailableSlots, getApiBase, type AIAvailableSlot } from '@/lib/api-client';

interface AppointmentFlowProps {
  sessionId: string;
  propertyId: string;
  organizationId: string;
  leadId: string;
  onClose: () => void;
  onConfirmed: () => void;
  onRequestHuman?: () => void;
}

type FlowState = 'selecting' | 'confirming' | 'booking' | 'success' | 'error';

export function AppointmentFlow({
  sessionId,
  propertyId,
  organizationId,
  leadId,
  onClose,
  onConfirmed,
  onRequestHuman,
}: AppointmentFlowProps) {
  const [flowState, setFlowState] = useState<FlowState>('selecting');
  const [slots, setSlots] = useState<AIAvailableSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<AIAvailableSlot | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    aiGetAvailableSlots(organizationId, propertyId)
      .then(r => setSlots(r.slots))
      .catch(() => setErrorMsg('Could not load available slots'))
      .finally(() => setLoading(false));
  }, [organizationId, propertyId]);

  const handleBook = async () => {
    if (!selectedSlot) return;
    setFlowState('booking');
    try {
      const base = getApiBase();

      const resp = await fetch(`${base}/ai-agent/v1/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: leadId,
          organization_id: organizationId,
          channel: 'web',
          content: `I want to book a viewing for property ${propertyId} on ${selectedSlot.date} at ${selectedSlot.time}. ${notes ? `Notes: ${notes}` : ''}`,
          metadata: {
            intent: 'book_viewing',
            property_id: propertyId,
            preferred_date: selectedSlot.date,
            preferred_time: selectedSlot.time,
          },
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        // Check if book_viewing tool succeeded in the response
        const toolResults = data.tool_results || [];
        const bookingResult = toolResults.find(
          (t: { tool: string; success: boolean }) => t.tool === 'book_viewing'
        );
        if (bookingResult?.success) {
          setFlowState('success');
        } else {
          setFlowState('error');
          setErrorMsg('We could not submit your visit request. Please try again or ask for a human advisor.');
        }
      } else {
        setFlowState('error');
        setErrorMsg('Booking request failed. Please try again.');
      }
    } catch {
      setFlowState('error');
      setErrorMsg('Network error. Please try again.');
    }
  };

  return (
    <div
      id="appointment-flow-modal"
      className="absolute inset-0 z-50 flex items-end sm:items-center justify-center bg-black/30 backdrop-blur-sm p-0 sm:p-4"
    >
      <div className="w-full sm:max-w-md bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 flex-shrink-0">
          <div>
            <h3 className="text-base font-black text-slate-900">
              {flowState === 'success' ? 'Visit Requested! 🎉' :
               flowState === 'error' ? 'Booking Failed' :
               'Schedule a Visit'}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {flowState === 'selecting' && 'Choose a convenient time slot'}
              {flowState === 'confirming' && 'Confirm your selected slot'}
              {flowState === 'booking' && 'Processing your request…'}
              {flowState === 'success' && 'Our agent will call to confirm'}
              {flowState === 'error' && 'Something went wrong'}
            </p>
          </div>
          {flowState !== 'booking' && (
            <button
              id="appointment-close-btn"
              onClick={onClose}
              className="w-8 h-8 rounded-full hover:bg-slate-100 flex items-center justify-center transition-colors"
            >
              <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* SELECTING STATE */}
          {flowState === 'selecting' && (
            <div className="space-y-3">
              {loading && (
                <div className="flex items-center justify-center h-32">
                  <div className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                </div>
              )}
              {!loading && errorMsg && (
                <p className="text-sm text-red-500">{errorMsg}</p>
              )}
              {!loading && slots.length === 0 && !errorMsg && (
                <div className="text-center py-8 space-y-3">
                  <p className="text-sm text-slate-600">No pre-configured slots available.</p>
                  <p className="text-xs text-slate-400">Our agent will contact you to arrange a visit.</p>
                  {onRequestHuman && (
                    <button
                      id="appointment-request-human-empty-btn"
                      onClick={() => {
                        onRequestHuman();
                        onClose();
                      }}
                      className="px-4 py-2 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-xl transition"
                    >
                      👤 Connect with a Human Specialist
                    </button>
                  )}
                </div>
              )}
              {slots.map((slot, i) => (
                <button
                  key={i}
                  id={`slot-${slot.date}-${slot.time.replace(/\s/g, '-')}`}
                  onClick={() => {
                    setSelectedSlot(slot);
                    setFlowState('confirming');
                  }}
                  className={`
                    w-full flex items-center justify-between p-3 rounded-2xl border transition-all text-left
                    ${selectedSlot?.date === slot.date && selectedSlot?.time === slot.time
                      ? 'border-violet-400 bg-violet-50'
                      : 'border-slate-100 bg-white hover:border-violet-200 hover:bg-violet-50/50'
                    }
                  `}
                >
                  <div>
                    <p className="text-sm font-bold text-slate-800">
                      {new Date(slot.date).toLocaleDateString('en-IN', {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </p>
                    <p className="text-xs text-violet-600 font-semibold">{slot.time}</p>
                    {slot.note && (
                      <p className="text-[10px] text-slate-400 mt-0.5">{slot.note}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {!slot.confirmed && (
                      <span className="text-[10px] text-amber-600 font-medium bg-amber-50 px-2 py-0.5 rounded-full">
                        Pending
                      </span>
                    )}
                    <svg className="w-4 h-4 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* CONFIRMING STATE */}
          {flowState === 'confirming' && selectedSlot && (
            <div className="space-y-4">
              <div className="bg-violet-50 border border-violet-200 rounded-2xl p-4 space-y-1">
                <p className="text-sm font-black text-violet-900">
                  {new Date(selectedSlot.date).toLocaleDateString('en-IN', {
                    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
                  })}
                </p>
                <p className="text-lg font-black bg-gradient-to-r from-violet-600 to-indigo-700 bg-clip-text text-transparent">
                  {selectedSlot.time}
                </p>
                {!selectedSlot.confirmed && (
                  <p className="text-xs text-amber-600 font-medium">
                    ⚠ This slot is subject to agent confirmation — not guaranteed.
                  </p>
                )}
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600 block mb-1.5">
                  Any notes for the agent? (optional)
                </label>
                <textarea
                  id="appointment-notes"
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="e.g. I'll be bringing my spouse. Interested in 3 BHK units only."
                  rows={3}
                  className="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-violet-300 focus:bg-white resize-none transition"
                />
              </div>

              <div className="flex gap-2">
                <button
                  id="appointment-back-btn"
                  onClick={() => setFlowState('selecting')}
                  className="flex-1 py-3 text-sm font-semibold border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-2xl transition-colors"
                >
                  ← Back
                </button>
                <button
                  id="appointment-confirm-btn"
                  onClick={handleBook}
                  className="flex-1 py-3 text-sm font-bold bg-gradient-to-r from-violet-600 to-indigo-700 text-white rounded-2xl hover:shadow-lg hover:scale-[1.02] active:scale-[0.98] transition-all"
                >
                  Confirm Visit
                </button>
              </div>
            </div>
          )}

          {/* BOOKING STATE */}
          {flowState === 'booking' && (
            <div className="flex flex-col items-center justify-center h-40 space-y-3">
              <div className="w-10 h-10 border-3 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-slate-500">Booking your visit…</p>
            </div>
          )}

          {/* SUCCESS STATE */}
          {flowState === 'success' && (
            <div className="flex flex-col items-center text-center py-6 space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center">
                <svg className="w-8 h-8 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800">Visit request submitted!</p>
                <p className="text-xs text-slate-500 mt-1">
                  Our agent will call you within 24 hours to confirm the appointment.
                </p>
                {selectedSlot && (
                  <p className="text-xs font-semibold text-violet-700 mt-2">
                    Requested: {selectedSlot.date} at {selectedSlot.time}
                  </p>
                )}
              </div>
              <button
                id="appointment-done-btn"
                onClick={onConfirmed}
                className="px-6 py-2.5 text-sm font-bold bg-gradient-to-r from-violet-600 to-indigo-700 text-white rounded-2xl hover:shadow-md transition-all"
              >
                Done
              </button>
            </div>
          )}

          {/* ERROR STATE */}
          {flowState === 'error' && (
            <div className="flex flex-col items-center text-center py-6 space-y-4">
              <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center">
                <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800">Booking failed</p>
                <p className="text-xs text-slate-500 mt-1">{errorMsg}</p>
              </div>
              <div className="flex flex-col gap-2 w-full max-w-xs">
                <div className="flex gap-2">
                  <button
                    onClick={() => setFlowState('selecting')}
                    className="flex-1 px-4 py-2.5 text-sm font-semibold border border-slate-200 text-slate-600 rounded-2xl hover:bg-slate-50 transition"
                  >
                    Try again
                  </button>
                  <button
                    onClick={onClose}
                    className="flex-1 px-4 py-2.5 text-sm font-bold bg-slate-900 text-white rounded-2xl hover:bg-slate-700 transition"
                  >
                    Close
                  </button>
                </div>
                {onRequestHuman && (
                  <button
                    id="appointment-request-human-error-btn"
                    onClick={() => {
                      onRequestHuman();
                      onClose();
                    }}
                    className="w-full py-2.5 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-2xl transition"
                  >
                    👤 Connect with a Human Specialist
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
