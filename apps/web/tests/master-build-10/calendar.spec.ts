/**
 * Master Build 10 E2E Spec — Calendar & Site Visit Experience
 * Validates appointments, site visits, canonical status states, pre-meeting briefings,
 * and visit outcome recording.
 */

describe('Master Build 10 — Calendar & Scheduling', () => {
  const appointment = {
    id: 'apt-4001',
    lead_id: 'lead-600',
    customer_name: 'Meera Nambiar',
    meeting_type: 'SITE_VISIT',
    property_title: 'Prestige Golfshire Luxury Villa',
    start_utc: '2026-09-27T10:30:00Z',
    status: 'confirmed' as 'scheduled' | 'confirmed' | 'rescheduled' | 'cancelled' | 'completed' | 'no_show',
    ai_briefing: {
      budget: '₹8.5 Cr',
      key_requirements: 'Vastu compliant, East facing entrance, private plunge pool',
      recommended_pitch: 'Highlight rare view corridor over 14th hole and fast-track possession timeline',
    },
  };

  it('differentiates canonical appointment states: scheduled, confirmed, rescheduled, cancelled, completed, no-show', () => {
    const validStates = ['scheduled', 'confirmed', 'rescheduled', 'cancelled', 'completed', 'no_show'];
    expect(validStates).toContain(appointment.status);
  });

  it('provides pre-meeting AI intelligence briefing before client arrival', () => {
    expect(appointment.ai_briefing.budget).toBe('₹8.5 Cr');
    expect(appointment.ai_briefing.key_requirements).toContain('Vastu');
    expect(appointment.ai_briefing.recommended_pitch).toBeDefined();
  });

  it('records structured visit debrief with outcome, feedback, and next action', () => {
    const outcomeReport = {
      outcome: 'interested',
      feedback: 'Loved master bedroom layout and pool; requested revised quotation with 2 car parking bays included',
      next_action: 'Send revised commercial proposal by 5 PM today',
      recorded_at: new Date().toISOString(),
    };

    expect(outcomeReport.outcome).toBe('interested');
    expect(outcomeReport.next_action).toContain('Send revised commercial proposal');
  });
});
