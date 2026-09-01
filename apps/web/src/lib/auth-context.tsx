'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { Broker } from '@/types';
import { api, getToken, removeToken } from './api-client';

/**
 * Extracts and capitalizes the first name from a full name string.
 * Examples:
 * - "aamir" -> "Aamir"
 * - "Aamir Khan" -> "Aamir"
 * - "AAMIR" -> "Aamir"
 * - "aAmIr" -> "Aamir"
 * - "Rahul Sharma" -> "Rahul"
 * - "Mohammed Aamir Khan" -> "Mohammed"
 * - "John" -> "John"
 */
export function getFirstName(name?: string | null, email?: string | null): string {
  if (name && typeof name === 'string') {
    const cleaned = name.trim();
    if (cleaned.length > 0) {
      const parts = cleaned.split(/\s+/).filter(Boolean);
      if (parts.length > 0) {
        const rawFirst = parts[0];
        return rawFirst.charAt(0).toUpperCase() + rawFirst.slice(1).toLowerCase();
      }
    }
  }

  if (email && typeof email === 'string') {
    const cleanedEmail = email.trim();
    if (cleanedEmail.length > 0) {
      const handle = cleanedEmail.split('@')[0].split(/[._-]/)[0];
      if (handle) {
        return handle.charAt(0).toUpperCase() + handle.slice(1).toLowerCase();
      }
    }
  }

  return 'Broker';
}

export function getInitials(name?: string | null, email?: string | null): string {
  if (name && typeof name === 'string') {
    const cleaned = name.trim();
    if (cleaned.length > 0) {
      const parts = cleaned.split(/\s+/).filter(Boolean);
      if (parts.length >= 2) {
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      }
      if (parts.length === 1) {
        return parts[0][0].toUpperCase();
      }
    }
  }

  if (email && typeof email === 'string') {
    const cleanedEmail = email.trim();
    if (cleanedEmail.length > 0) {
      return cleanedEmail[0].toUpperCase();
    }
  }

  return 'U';
}

interface BrokerContextType {
  broker: Broker | null;
  loading: boolean;
  firstName: string;
  initials: string;
  refreshBroker: () => Promise<Broker | null>;
  updateProfile: (data: Partial<Broker>) => Promise<Broker>;
  logout: () => void;
}

const BrokerContext = createContext<BrokerContextType | undefined>(undefined);

export function BrokerProvider({ children }: { children: ReactNode }) {
  const [broker, setBroker] = useState<Broker | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchProfile = useCallback(async (): Promise<Broker | null> => {
    const token = getToken();
    if (!token) {
      setBroker(null);
      setLoading(false);
      return null;
    }

    try {
      const b = await api.getBrokerProfile();
      setBroker(b);
      return b;
    } catch (err) {
      console.warn('[BrokerProvider] Failed fetching broker profile:', err);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfile();

    const handleProfileUpdate = () => {
      fetchProfile();
    };

    window.addEventListener('beetlelabs:auth_change', handleProfileUpdate);
    window.addEventListener('storage', handleProfileUpdate);

    return () => {
      window.removeEventListener('beetlelabs:auth_change', handleProfileUpdate);
      window.removeEventListener('storage', handleProfileUpdate);
    };
  }, [fetchProfile]);

  const updateProfile = async (data: Partial<Broker>): Promise<Broker> => {
    const updated = await api.updateBrokerProfile(data);
    setBroker(updated);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('beetlelabs:auth_change'));
    }
    return updated;
  };

  const logout = () => {
    api.auth.logout();
    setBroker(null);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('beetlelabs:auth_change'));
    }
  };

  const firstName = getFirstName(broker?.name, broker?.email);
  const initials = getInitials(broker?.name, broker?.email);

  return (
    <BrokerContext.Provider
      value={{
        broker,
        loading,
        firstName,
        initials,
        refreshBroker: fetchProfile,
        updateProfile,
        logout,
      }}
    >
      {children}
    </BrokerContext.Provider>
  );
}

export function useBroker(): BrokerContextType {
  const context = useContext(BrokerContext);
  if (!context) {
    return {
      broker: null,
      loading: false,
      firstName: 'Broker',
      initials: 'U',
      refreshBroker: async () => null,
      updateProfile: async (data: Partial<Broker>) => data as Broker,
      logout: () => {},
    };
  }
  return context;
}
