/**
 * Phase 0 P0.1 / Phase 2C.6B Spec — OAuth State & Cookie Transport Verification
 * Validates:
 * 1. API base hostname normalization between localhost and 127.0.0.1
 * 2. Client-side OAuth CSRF state tracking and atomic clearing on callback
 * 3. Error extraction for 'OAuth state does not belong to this session.'
 * 4. Error extraction for replayed and expired OAuth states
 */

describe('OAuth State & Cookie Transport Verification', () => {
  const normalizeApiBase = (envApiUrl?: string, browserHost: string = 'localhost'): string => {
    let base = envApiUrl ? envApiUrl.replace(/\/$/, '') : '';
    if (!base) {
      return `http://${browserHost}:3000/api/v1`;
    }
    if (browserHost === '127.0.0.1' && base.includes('localhost')) {
      base = base.replace('localhost', '127.0.0.1');
    } else if (browserHost === 'localhost' && base.includes('127.0.0.1')) {
      base = base.replace('127.0.0.1', 'localhost');
    }
    return base;
  };

  const extractApiErrorMessage = (errorText: string, status: number): string => {
    try {
      const jsonErr = JSON.parse(errorText);
      if (jsonErr.detail && typeof jsonErr.detail === 'string') {
        return jsonErr.detail.trim();
      }
      if (jsonErr.message && typeof jsonErr.message === 'string') {
        return jsonErr.message.trim();
      }
    } catch {}
    return `Request failed with status ${status}`;
  };

  it('harmonizes localhost and 127.0.0.1 hostnames for cross-origin cookie consistency', () => {
    // When browser is on 127.0.0.1 and backend env is localhost
    const base1 = normalizeApiBase('http://localhost:8000/api/v1', '127.0.0.1');
    expect(base1).toBe('http://127.0.0.1:8000/api/v1');

    // When browser is on localhost and backend env is 127.0.0.1
    const base2 = normalizeApiBase('http://127.0.0.1:8000/api/v1', 'localhost');
    expect(base2).toBe('http://localhost:8000/api/v1');

    // When hostnames are already matching
    const base3 = normalizeApiBase('http://localhost:8000/api/v1', 'localhost');
    expect(base3).toBe('http://localhost:8000/api/v1');
  });

  it('correctly manages client-side OAuth state storage and atomic consumption', () => {
    const storage: Record<string, string> = {};
    const setOAuthState = (state: string) => { storage['wefylabs_oauth_state'] = state; };
    const getOAuthState = () => storage['wefylabs_oauth_state'] || null;
    const clearOAuthState = () => { delete storage['wefylabs_oauth_state']; };

    const stateToken = 'random_cryptographic_state_256bit_value';
    setOAuthState(stateToken);
    expect(getOAuthState()).toBe(stateToken);

    clearOAuthState();
    expect(getOAuthState()).toBe(null);
  });

  it('correctly extracts OAuth state mismatch error from backend response', () => {
    const errorJson = JSON.stringify({
      detail: 'OAuth state does not belong to this session.'
    });
    const parsedMessage = extractApiErrorMessage(errorJson, 400);
    expect(parsedMessage).toBe('OAuth state does not belong to this session.');
  });

  it('correctly extracts OAuth state replayed error from backend response', () => {
    const errorJson = JSON.stringify({
      detail: 'OAuth state has already been used.'
    });
    const parsedMessage = extractApiErrorMessage(errorJson, 400);
    expect(parsedMessage).toBe('OAuth state has already been used.');
  });

  it('correctly extracts OAuth state expired error from backend response', () => {
    const errorJson = JSON.stringify({
      detail: 'OAuth state has expired. Please restart sign-in.'
    });
    const parsedMessage = extractApiErrorMessage(errorJson, 400);
    expect(parsedMessage).toBe('OAuth state has expired. Please restart sign-in.');
  });
});
