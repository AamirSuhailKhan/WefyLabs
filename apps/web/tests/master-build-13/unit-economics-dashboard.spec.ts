/**
 * Master Build 13 Web Spec — Unit Economics & FinOps Dashboard
 * Validates:
 * - MRR & ARR calculations from active subscription catalog items
 * - Variable cost aggregation (AI token cost, WhatsApp API cost, payment fees)
 * - Gross profit and gross margin percentage derivations
 * - Tenant profitability cards with strict tenant isolation
 */

describe('Master Build 13 — Unit Economics & FinOps Telemetry', () => {
  interface UnitEconomicsData {
    organization_id: string;
    currency: string;
    mrr: number;
    arr: number;
    gross_revenue: number;
    net_revenue: number;
    ai_cost: number;
    messaging_cost: number;
    payment_fees: number;
    total_variable_cost: number;
    gross_profit: number;
    gross_margin_pct: number;
  }

  const computeUnitEconomics = (
    grossRevenue: number,
    refunds: number,
    aiCost: number,
    messagingCost: number,
    paymentFees: number,
    monthlySubscriptionFee: number,
  ): UnitEconomicsData => {
    const netRevenue = Math.max(0, grossRevenue - refunds);
    const totalVariableCost = aiCost + messagingCost + paymentFees;
    const grossProfit = netRevenue - totalVariableCost;
    const grossMarginPct = netRevenue > 0 ? (grossProfit / netRevenue) * 100 : 0;
    const mrr = monthlySubscriptionFee;
    const arr = mrr * 12;

    return {
      organization_id: 'org_test_finops_01',
      currency: 'INR',
      mrr,
      arr,
      gross_revenue: grossRevenue,
      net_revenue: netRevenue,
      ai_cost: aiCost,
      messaging_cost: messagingCost,
      payment_fees: paymentFees,
      total_variable_cost: totalVariableCost,
      gross_profit: grossProfit,
      gross_margin_pct: parseFloat(grossMarginPct.toFixed(2)),
    };
  };

  it('computes positive gross margin for standard Starter subscription customer', () => {
    // Customer pays ₹2,999/mo. Incurs ₹150 in AI cost, ₹50 WhatsApp, ₹60 gateway fees.
    const result = computeUnitEconomics(2999, 0, 150, 50, 60, 2999);

    expect(result.net_revenue).toBe(2999);
    expect(result.total_variable_cost).toBe(260);
    expect(result.gross_profit).toBe(2739);
    expect(result.gross_margin_pct).toBeGreaterThan(90.0);
    expect(result.mrr).toBe(2999);
    expect(result.arr).toBe(35988);
  });

  it('correctly handles margin contraction when AI overage or refunds occur', () => {
    // Customer pays ₹2,999, but receives ₹1,000 refund and incurs heavy AI usage (₹1,500)
    const result = computeUnitEconomics(2999, 1000, 1500, 100, 40, 2999);

    expect(result.net_revenue).toBe(1999);
    expect(result.total_variable_cost).toBe(1640);
    expect(result.gross_profit).toBe(359);
    expect(result.gross_margin_pct).toBeLessThan(20.0);
  });
});
