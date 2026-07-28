import type { Metadata } from 'next';
import { Providers } from '@/app/providers';
import { ScrollProgress } from '@/components/animations/ScrollProgress';
import './globals.css';

export const metadata: Metadata = {
  title: 'BeetleLabs — AI Lead Qualification for Real Estate Brokers',
  description: 'Stop wasting hours on cold real estate leads. Let BeetleLabs AI qualify them on WhatsApp in 2 minutes. Visual CRM-Lite pipeline, notes, tags & task reminders.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen flex flex-col bg-[#F0EDE8] text-[#1A1A1A] font-sans antialiased">
        <ScrollProgress />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
