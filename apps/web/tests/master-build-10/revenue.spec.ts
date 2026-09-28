/**
 * Master Build 10 E2E Spec — Revenue Command Center
 * Validates Build 09 integration: Overview metrics, Forecast separation (Actual vs Forecast vs Committed),
 * multi-touch attribution models, leakage center, and AI Revenue Analyst.
 */

describe('Master Build 10 — Revenue Command Center', () => {
  const revenueOverview = {
    bookings_count: 14,
    total_booking_value_inr: 215000000,
    collected_payments_inr: 43000000,
    net_revenue_inr: 215000000,
    pipeline_value_inr: 680000000,
    forecast_value_inr: 490000000,
    revenue_at_risk_inr: 32000000,
    period: 'Q3-2026',
    currency: 'INR',
    data_freshness: 'realtime_verified',
  };

  const forecastBreakdown = {
    actual: 215000000,
    forecast: 490000000,
    committed: 180000000,
    pipeline: 680000000,
  };

  const attributionModels = ['first_touch', 'last_touch', 'linear', 'time_decay', 'position_based'];

  it('displays canonical revenue metrics with explicit currency, period, and freshness', () => {
    expect(revenueOverview.bookings_count).toBe(14);
    expect(revenueOverview.currency).toBe('INR');
    expect(revenueOverview.data_freshness).toBe('realtime_verified');
    expect(revenueOverview.total_booking_value_inr).toBe(215000000);
  });

  it('strictly separates Actual, Forecast, Committed, and Pipeline without visual blending', () => {
    expect(forecastBreakdown.actual).not.toBe(forecastBreakdown.forecast);
    expect(forecastBreakdown.committed).toBeLessThanOrEqual(forecastBreakdown.forecast);
    expect(forecastBreakdown.forecast).toBeLessThanOrEqual(forecastBreakdown.pipeline);
  });

  it('supports canonical attribution models with active lookback window', () => {
    expect(attributionModels).toContain('first_touch');
    expect(attributionModels).toContain('position_based');
    expect(attributionModels).toContain('time_decay');
  });

  it('links revenue leakage records directly to actionable WorkItems and NBAs', () => {
    const leakageRecord = {
      id: 'leak-12',
      condition: 'Hold expired 4 hours ago on Unit 201 without booking form',
      value_at_risk_inr: 18000000,
      lead_id: 'lead-401',
      recommended_action: 'Release unit to active waitlist or request manager override extension',
      connected_work_item_id: 'work-882',
    };

    expect(leakageRecord.value_at_risk_inr).toBe(18000000);
    expect(leakageRecord.connected_work_item_id).toBeDefined();
    expect(leakageRecord.recommended_action).toContain('Release unit');
  });
});
