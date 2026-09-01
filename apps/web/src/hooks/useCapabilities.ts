'use client';

/**
 * useCapabilities — System Feature Flag Hook
 *
 * Fetches real-time capability flags from the backend /v1/health-diag/capabilities
 * endpoint. The backend returns boolean flags based on actual environment
 * configuration — WhatsApp is only "enabled" when real Meta credentials exist,
 * billing only when real Razorpay live keys exist, etc.
 *
 * This prevents the frontend from showing broken features to real users.
 */

import { useState, useEffect } from 'react';
import { getApiBase } from '@/lib/api-client';

export interface SystemCapabilities {
  whatsapp: { enabled: boolean; reason: string };
  billing: { enabled: boolean; mode: 'live' | 'test' | 'disabled'; reason: string };
  ai: { enabled: boolean; provider: string };
  google_oauth: { enabled: boolean };
}

const DEFAULT_CAPABILITIES: SystemCapabilities = {
  whatsapp: { enabled: false, reason: 'loading' },
  billing: { enabled: false, mode: 'disabled', reason: 'loading' },
  ai: { enabled: true, provider: 'gemini' },
  google_oauth: { enabled: false },
};

let _cachedCapabilities: SystemCapabilities | null = null;
let _fetchPromise: Promise<SystemCapabilities> | null = null;

async function fetchCapabilities(): Promise<SystemCapabilities> {
  if (_cachedCapabilities) return _cachedCapabilities;
  if (_fetchPromise) return _fetchPromise;

  _fetchPromise = (async () => {
    try {
      const base = getApiBase(); // e.g. http://localhost:8000/api/v1
      const res = await fetch(`${base}/v1/health-diag/capabilities`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      _cachedCapabilities = data as SystemCapabilities;
      return _cachedCapabilities;
    } catch {
      // If backend is unreachable, return safe defaults (everything disabled)
      return DEFAULT_CAPABILITIES;
    } finally {
      _fetchPromise = null;
    }
  })();

  return _fetchPromise;
}

export function useCapabilities(): { capabilities: SystemCapabilities; loading: boolean } {
  const [capabilities, setCapabilities] = useState<SystemCapabilities>(
    _cachedCapabilities ?? DEFAULT_CAPABILITIES
  );
  const [loading, setLoading] = useState(!_cachedCapabilities);

  useEffect(() => {
    if (_cachedCapabilities) {
      setCapabilities(_cachedCapabilities);
      setLoading(false);
      return;
    }
    fetchCapabilities().then((caps) => {
      setCapabilities(caps);
      setLoading(false);
    });
  }, []);

  return { capabilities, loading };
}

/** Invalidates the cache — call after admin changes credentials */
export function invalidateCapabilities(): void {
  _cachedCapabilities = null;
}
