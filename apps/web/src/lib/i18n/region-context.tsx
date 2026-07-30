'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { RegionCode, RegionConfig, REGIONS } from './regions';

interface RegionContextType {
  regionCode: RegionCode;
  region: RegionConfig;
  setRegion: (code: RegionCode) => void;
  isModalOpen: boolean;
  setIsModalOpen: (open: boolean) => void;
  openModal: () => void;
  closeModal: () => void;
}

const RegionContext = createContext<RegionContextType | undefined>(undefined);

const STORAGE_KEY = 'leadscore-region';
const SELECTED_KEY = 'leadscore-region-selected';

function detectDefaultRegion(): { code: RegionCode; hasSelected: boolean } {
  if (typeof window === 'undefined') return { code: 'IN', hasSelected: false };

  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    const hasSelected = localStorage.getItem(SELECTED_KEY) === 'true';

    if (saved && saved in REGIONS) {
      return { code: saved as RegionCode, hasSelected };
    }

    const navLang = navigator.language || '';
    if (navLang.includes('-AE')) return { code: 'AE', hasSelected: false };
    if (navLang.includes('-SG')) return { code: 'SG', hasSelected: false };
    if (navLang.includes('-GB')) return { code: 'GB', hasSelected: false };
    if (navLang.includes('-US')) return { code: 'US', hasSelected: false };
    if (navLang.includes('-AU')) return { code: 'AU', hasSelected: false };
    if (navLang.includes('-CA')) return { code: 'CA', hasSelected: false };
    if (navLang.includes('-IN')) return { code: 'IN', hasSelected: false };
  } catch (e) {
    // fallback
  }

  return { code: 'IN', hasSelected: false };
}

export function RegionProvider({ children }: { children: ReactNode }) {
  const [regionCode, setRegionCode] = useState<RegionCode>('IN');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const { code } = detectDefaultRegion();
    setRegionCode(code);
    setMounted(true);

    // Auto-open country selector modal when website opens so user can choose their market
    const hasSeenThisSession = typeof window !== 'undefined' && sessionStorage.getItem('leadscore-modal-dismissed') === 'true';
    if (!hasSeenThisSession) {
      const timer = setTimeout(() => {
        setIsModalOpen(true);
      }, 350);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleSetRegion = (code: RegionCode) => {
    setRegionCode(code);
    try {
      localStorage.setItem(STORAGE_KEY, code);
      localStorage.setItem(SELECTED_KEY, 'true');
      sessionStorage.setItem('leadscore-modal-dismissed', 'true');
    } catch (e) {
      // ignore
    }
  };

  const region = REGIONS[regionCode] || REGIONS.IN;

  return (
    <RegionContext.Provider
      value={{
        regionCode,
        region,
        setRegion: handleSetRegion,
        isModalOpen,
        setIsModalOpen,
        openModal: () => setIsModalOpen(true),
        closeModal: () => {
          try {
            sessionStorage.setItem('leadscore-modal-dismissed', 'true');
          } catch (e) {}
          setIsModalOpen(false);
        }
      }}
    >
      {children}
    </RegionContext.Provider>
  );
}

export function useRegion() {
  const context = useContext(RegionContext);
  if (!context) {
    // Fallback if rendered outside provider
    return {
      regionCode: 'IN' as RegionCode,
      region: REGIONS.IN,
      setRegion: () => {},
      isModalOpen: false,
      setIsModalOpen: () => {},
      openModal: () => {},
      closeModal: () => {}
    };
  }
  return context;
}
