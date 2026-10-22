'use client';

import { useState } from 'react';
import { PageContainer } from '@/components/ui/PageContainer';
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
    <PageContainer>
      <RevenueAutopilotView
        onOpenLead={handleOpenDrawer}
        onOpenProperty={(propId) => window.open(`/dashboard/properties?id=${propId}`, '_blank')}
      />

      <LeadDrawer
        leadId={selectedLeadId}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onLeadUpdated={() => {}}
      />
    </PageContainer>
  );
}
