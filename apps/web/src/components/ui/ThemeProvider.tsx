'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolvedTheme: 'light' | 'dark';
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('light');
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    try {
      const saved = localStorage.getItem('beetlelabs-theme') as Theme;
      if (saved) {
        setThemeState(saved);
      }
    } catch (e) {
      // ignore
    }
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    let resolved: 'light' | 'dark' = 'light';

    if (theme === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } else {
      resolved = theme;
    }

    setResolvedTheme(resolved);
    if (resolved === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }

    try {
      localStorage.setItem('beetlelabs-theme', theme);
    } catch (e) {
      // ignore
    }
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme: setThemeState, resolvedTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    return {
      theme: 'light' as Theme,
      setTheme: () => {},
      resolvedTheme: 'light' as 'light' | 'dark',
    };
  }
  return context;
}
