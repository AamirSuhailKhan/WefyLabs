import type { Metadata } from 'next';
import DashboardLayoutClient from '@/components/dashboard/DashboardLayoutClient';

export const metadata: Metadata = {
  title: 'Broker Dashboard — WefyLabs',
  description: 'Visual pipeline stages, task reminders, AI lead scoring and CRM for real estate brokers.',
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardLayoutClient>{children}</DashboardLayoutClient>
    </div>
  );
}
