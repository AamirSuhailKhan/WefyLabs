import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: { '2xl': '1280px' },
    },
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono', 'JetBrains Mono', 'Courier New', 'monospace'],
      },
      colors: {
        beige: {
          DEFAULT: '#F0EDE8',
          card: '#FAF7F2',
          alt: '#F5F0EB',
        },
        ink: {
          DEFAULT: '#1A1A1A',
          secondary: '#4A4A4A',
          muted: '#6B6B6B',
        },
        lime: {
          DEFAULT: '#E8F5A8',
          hover: '#D4E894',
        },
        warm: {
          border: '#D4D0C8',
          divider: '#D4D0C8',
        },
        accent: {
          DEFAULT: '#0D9488',
          hover: '#0F766E',
        },
        brand: {
          DEFAULT: 'var(--brand-primary)',
          primary: 'var(--brand-primary)',
          'primary-hover': 'var(--brand-primary-hover)',
          'primary-light': 'var(--brand-primary-light)',
          secondary: 'var(--brand-secondary)',
          silver: 'var(--brand-silver)',
          'silver-light': 'var(--brand-silver-light)',
        },
      },
      borderRadius: {
        '4xl': '32px',
        '3xl': '24px',
        '2xl': '16px',
      },
      boxShadow: {
        card: 'none',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        marquee: {
          '0%': { transform: 'translateX(0%)' },
          '100%': { transform: 'translateX(-50%)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.6s ease-out forwards',
        'fade-in': 'fade-in 0.4s ease-out forwards',
        marquee: 'marquee 35s linear infinite',
      },
    },
  },
  plugins: [],
}

export default config
