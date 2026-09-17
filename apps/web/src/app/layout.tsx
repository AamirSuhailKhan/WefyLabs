import type { Metadata } from 'next';
import { Providers } from '@/app/providers';
import { ScrollProgress } from '@/components/animations/ScrollProgress';
import './globals.css';

export const metadata: Metadata = {
  metadataBase: new URL('https://wefylabs.com'),
  title: 'WefyLabs — AI Lead Qualification for Real Estate Brokers',
  description: 'Stop wasting hours on cold real estate leads. Let WefyLabs AI qualify them in 2 minutes. Visual CRM pipeline, notes, tags & task reminders.',
  icons: {
    icon: [
      { url: '/branding/favicon/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
      { url: '/branding/favicon/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
    apple: '/branding/favicon/apple-touch-icon.png',
  },
  manifest: '/site.webmanifest',
  openGraph: {
    title: 'WefyLabs — AI Lead Qualification for Real Estate Brokers',
    description: 'Stop wasting hours on cold real estate leads. Let WefyLabs AI qualify them in 2 minutes.',
    url: 'https://wefylabs.com',
    siteName: 'WefyLabs',
    images: [
      {
        url: '/branding/wefylabs-mark.png',
        width: 800,
        height: 418,
        alt: 'WefyLabs — AI Lead Qualification for Real Estate Brokers',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'WefyLabs — AI Lead Qualification for Real Estate Brokers',
    description: 'Stop wasting hours on cold real estate leads. Let WefyLabs AI qualify them in 2 minutes.',
    images: ['/branding/wefylabs-mark.png'],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'WefyLabs',
    url: 'https://wefylabs.com',
    logo: 'https://wefylabs.com/branding/wefylabs-mark.png',
    description: 'Autonomous AI Qualification, Matching & CRM for Real Estate Brokers',
  };

  return (
    <html lang="en" data-scroll-behavior="smooth">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-screen flex flex-col bg-[#F0EDE8] text-[#1A1A1A] font-sans antialiased">
        <ScrollProgress />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
