'use client';

/**
 * WefyLabs Centralized Entitlement & Subscription Utility
 * Part 21 Unified Product Experience OS
 */

export type SubscriptionStatus = 'active' | 'trial' | 'expired' | 'suspended';

export interface EntitlementState {
  status: SubscriptionStatus;
  plan: 'free' | 'starter' | 'pro' | 'enterprise';
  trialDaysRemaining: number | null;
  trialEndsAt?: string | null;
}

export const DEFAULT_ENTITLEMENT_STATE: EntitlementState = {
  status: 'trial',
  plan: 'starter',
  trialDaysRemaining: 7,
  trialEndsAt: null,
};

/**
 * Features that remain accessible in read-only mode even after trial expires.
 * Allows brokers to review existing records without data loss.
 */
const READ_ONLY_PERMITTED_FEATURES = [
  'leads.view',
  'pipeline.view',
  'deals.view',
  'inventory.view',
  'marketing.view',
  'partners.view',
  'intelligence.view',
  'tasks.view',
  'settings.view',
];

/**
 * Mutation features that are strictly blocked when a trial is expired.
 */
const MUTATION_FEATURES = [
  'leads.create',
  'leads.import',
  'deals.create',
  'deals.advance_stage',
  'inventory.reserve',
  'inventory.book',
  'marketing.create_campaign',
  'marketing.publish_listing',
  'marketing.launch_project',
  'partners.register_lead',
  'ai.generate_copy',
  'ai.auto_pilot',
];

/**
 * Check if the current user can access a given feature.
 */
export function canAccess(feature: string, state: EntitlementState): boolean {
  if (state.status === 'suspended') return false;
  if (state.status === 'active') return true;
  if (state.status === 'trial') return true;

  // If trial is expired, check if it's permitted read-only feature
  if (state.status === 'expired') {
    return READ_ONLY_PERMITTED_FEATURES.includes(feature) || !MUTATION_FEATURES.includes(feature);
  }

  return true;
}

/**
 * Check if a feature is in read-only mode for the current user.
 */
export function isReadOnly(feature: string, state: EntitlementState): boolean {
  if (state.status === 'expired') return true;
  return false;
}

/**
 * Check if performing an action requires upgrading the plan.
 */
export function requiresUpgrade(feature: string, state: EntitlementState): boolean {
  if (state.status === 'expired' && MUTATION_FEATURES.includes(feature)) {
    return true;
  }
  return false;
}

/**
 * Helper to get clean human-readable badge text and styling.
 */
export function getEntitlementBadge(state: EntitlementState): {
  label: string;
  variant: 'success' | 'warning' | 'danger' | 'info';
  isExpired: boolean;
} {
  if (state.status === 'active') {
    return { label: 'Pro Active', variant: 'success', isExpired: false };
  }
  if (state.status === 'expired' || (state.trialDaysRemaining !== null && state.trialDaysRemaining <= 0)) {
    return { label: 'Trial Expired', variant: 'danger', isExpired: true };
  }
  if (state.trialDaysRemaining !== null && state.trialDaysRemaining <= 3) {
    return { label: `${state.trialDaysRemaining}d Trial Left`, variant: 'warning', isExpired: false };
  }
  const days = state.trialDaysRemaining ?? 7;
  return { label: `${days}d Trial Left`, variant: 'info', isExpired: false };
}
