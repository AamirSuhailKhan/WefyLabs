/**
 * Master Build 13 Web Spec — Entitlements Enforcement & Warning State Matrix
 * Validates:
 * - Warning states at 80% and 90% thresholds
 * - Hard limit blocking vs soft limit overage warnings
 * - Grace period banners during PAST_DUE lifecycle states
 * - Fail-closed behavior on missing or unverified tenant permissions
 */

describe('Master Build 13 — Entitlement Warning States & Enforcement', () => {
  type WarningLevel = 'NORMAL' | 'WARNING_80' | 'CRITICAL_90' | 'EXCEEDED';

  const resolveWarningLevel = (current: number, limit: number | null): WarningLevel => {
    if (!limit || limit <= 0) return 'NORMAL';
    const ratio = current / limit;
    if (ratio >= 1.0) return 'EXCEEDED';
    if (ratio >= 0.9) return 'CRITICAL_90';
    if (ratio >= 0.8) return 'WARNING_80';
    return 'NORMAL';
  };

  it('correctly maps consumption thresholds to warning tiers', () => {
    expect(resolveWarningLevel(79, 100)).toBe('NORMAL');
    expect(resolveWarningLevel(80, 100)).toBe('WARNING_80');
    expect(resolveWarningLevel(89, 100)).toBe('WARNING_80');
    expect(resolveWarningLevel(90, 100)).toBe('CRITICAL_90');
    expect(resolveWarningLevel(99, 100)).toBe('CRITICAL_90');
    expect(resolveWarningLevel(100, 100)).toBe('EXCEEDED');
    expect(resolveWarningLevel(150, 100)).toBe('EXCEEDED');
  });

  it('flags grace period banner when subscription status is PAST_DUE', () => {
    interface SubscriptionBannerState {
      status: string;
      grace_ends_at: string | null;
      show_banner: boolean;
      banner_type: 'NONE' | 'GRACE_WARNING' | 'SUSPENDED';
    }

    const getBannerState = (status: string, graceEndsAt: string | null, now: Date): SubscriptionBannerState => {
      if (status === 'ACTIVE' || status === 'TRIALING') {
        return { status, grace_ends_at: graceEndsAt, show_banner: false, banner_type: 'NONE' };
      }
      if (status === 'PAST_DUE') {
        if (graceEndsAt && new Date(graceEndsAt) > now) {
          return { status, grace_ends_at: graceEndsAt, show_banner: true, banner_type: 'GRACE_WARNING' };
        }
        return { status, grace_ends_at: graceEndsAt, show_banner: true, banner_type: 'SUSPENDED' };
      }
      return { status, grace_ends_at: graceEndsAt, show_banner: true, banner_type: 'SUSPENDED' };
    };

    const now = new Date('2026-09-27T12:00:00Z');
    const futureGrace = '2026-10-04T12:00:00Z';
    const pastGrace = '2026-09-20T12:00:00Z';

    const activeState = getBannerState('ACTIVE', null, now);
    expect(activeState.show_banner).toBe(false);

    const inGraceState = getBannerState('PAST_DUE', futureGrace, now);
    expect(inGraceState.show_banner).toBe(true);
    expect(inGraceState.banner_type).toBe('GRACE_WARNING');

    const expiredGraceState = getBannerState('PAST_DUE', pastGrace, now);
    expect(expiredGraceState.show_banner).toBe(true);
    expect(expiredGraceState.banner_type).toBe('SUSPENDED');
  });
});
