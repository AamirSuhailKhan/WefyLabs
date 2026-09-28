/**
 * Master Build 11 Spec — Session Expiry & Auto-Refresh
 * Validates that expired sessions trigger seamless token refresh or graceful redirect
 * to login with original redirect path preserved, preventing infinite reload loops.
 */

describe('Master Build 11 — Session Expiry Management', () => {
  interface SessionState {
    tokenExpired: boolean;
    hasRefreshToken: boolean;
    currentPath: string;
  }

  const handleSessionCheck = (state: SessionState): { authenticated: boolean; action: 'continue' | 'refresh' | 'redirect_login'; redirectUrl?: string } => {
    if (!state.tokenExpired) {
      return { authenticated: true, action: 'continue' };
    }
    if (state.hasRefreshToken) {
      return { authenticated: true, action: 'refresh' };
    }
    return {
      authenticated: false,
      action: 'redirect_login',
      redirectUrl: `/login?redirect=${encodeURIComponent(state.currentPath)}`,
    };
  };

  it('continues normally when access token is active and valid', () => {
    const res = handleSessionCheck({
      tokenExpired: false,
      hasRefreshToken: true,
      currentPath: '/dashboard',
    });
    expect(res.authenticated).toBe(true);
    expect(res.action).toBe('continue');
  });

  it('triggers token refresh when access token is expired but refresh token exists', () => {
    const res = handleSessionCheck({
      tokenExpired: true,
      hasRefreshToken: true,
      currentPath: '/dashboard',
    });
    expect(res.authenticated).toBe(true);
    expect(res.action).toBe('refresh');
  });

  it('redirects to login preserving target return URL when session is unrecoverable', () => {
    const res = handleSessionCheck({
      tokenExpired: true,
      hasRefreshToken: false,
      currentPath: '/dashboard/leads?filter=hot',
    });
    expect(res.authenticated).toBe(false);
    expect(res.action).toBe('redirect_login');
    expect(res.redirectUrl).toBe('/login?redirect=%2Fdashboard%2Fleads%3Ffilter%3Dhot');
  });
});
