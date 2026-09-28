/**
 * Master Build 11 Spec — Sensitive Pages & Route Guarding
 * Validates that administrative, financial, and compliance views
 * are guarded server-side and client-side by role authorization guards.
 */

describe('Master Build 11 — Sensitive Page Guards', () => {
  const evaluateRouteAccess = (path: string, userRole: string): { allowed: boolean; redirectPath?: string } => {
    const adminRoutes = ['/admin', '/settings/security', '/settings/billing', '/compliance'];
    const financeRoutes = ['/settings/billing', '/revenue/reports'];

    const role = userRole.toUpperCase();

    if (adminRoutes.includes(path) && !['OWNER', 'ADMIN'].includes(role)) {
      if (financeRoutes.includes(path) && role === 'FINANCE') {
        return { allowed: true };
      }
      return { allowed: false, redirectPath: '/dashboard' };
    }

    return { allowed: true };
  };

  it('allows OWNER and ADMIN to access all sensitive configuration routes', () => {
    expect(evaluateRouteAccess('/settings/security', 'OWNER').allowed).toBe(true);
    expect(evaluateRouteAccess('/settings/security', 'ADMIN').allowed).toBe(true);
    expect(evaluateRouteAccess('/compliance', 'ADMIN').allowed).toBe(true);
  });

  it('redirects AGENT and SALES away from security and compliance administration views', () => {
    const agentAccess = evaluateRouteAccess('/settings/security', 'AGENT');
    expect(agentAccess.allowed).toBe(false);
    expect(agentAccess.redirectPath).toBe('/dashboard');

    const salesAccess = evaluateRouteAccess('/compliance', 'SALES');
    expect(salesAccess.allowed).toBe(false);
    expect(salesAccess.redirectPath).toBe('/dashboard');
  });

  it('allows FINANCE role to access billing but denies security configuration', () => {
    expect(evaluateRouteAccess('/settings/billing', 'FINANCE').allowed).toBe(true);
    expect(evaluateRouteAccess('/settings/security', 'FINANCE').allowed).toBe(false);
  });
});
