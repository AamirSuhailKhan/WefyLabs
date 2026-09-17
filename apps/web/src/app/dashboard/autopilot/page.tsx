'use client';

import { useState } from 'react';
import DashboardNav from '@/components/shared/DashboardNav';
import RevenueAutopilotView from '@/components/dashboard/RevenueAutopilotView';
import LeadDrawer from '@/components/leads/LeadDrawer';

export default function RevenueAutopilotPage() {
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);

  const handleOpenDrawer = (leadId: string) => {
    setSelectedLeadId(leadId);
    setIsDrawerOpen(true);
  };

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />
      <div className="pt-16">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <RevenueAutopilotView
            onOpenLead={handleOpenDrawer}
            onOpenProperty={(propId) => window.open(`/dashboard/properties?id=${propId}`, '_blank')}
          />
        </div>
      </div>

      <LeadDrawer
        leadId={selectedLeadId}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onLeadUpdated={() => {}}
      />
    </div>
  );
}
