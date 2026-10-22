'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Radio, FormInput, FileSpreadsheet, Activity } from 'lucide-react';

const TABS = [
  { label: 'Overview', href: '/dashboard/lead-capture', icon: LayoutDashboard },
  { label: 'Sources', href: '/dashboard/lead-capture/sources', icon: Radio },
  { label: 'Form Builder', href: '/dashboard/lead-capture/forms', icon: FormInput },
  { label: 'Import Wizard', href: '/dashboard/lead-capture/import', icon: FileSpreadsheet },
  { label: 'Ingestion Feed', href: '/dashboard/lead-capture/events', icon: Activity },
];

interface LeadCaptureNavProps {
  activeTab?: string;
}

export function LeadCaptureNav({ activeTab }: LeadCaptureNavProps = {}) {
  const pathname = usePathname();

  return (
    <div className="w-full flex items-center gap-1 p-1 rounded-xl bg-[#FAF7F2] border border-[#D4D0C8] mb-6 overflow-x-auto shadow-2xs">
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive =
          activeTab
            ? tab.href.endsWith(`/${activeTab}`) || (activeTab === 'overview' && tab.href === '/dashboard/lead-capture')
            : tab.href === '/dashboard/lead-capture'
            ? pathname === '/dashboard/lead-capture'
            : pathname.startsWith(tab.href);

        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap cursor-pointer ${
              isActive
                ? 'bg-[#1A1A1A] text-white shadow-xs'
                : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8]'
            }`}
          >
            <Icon className="w-3.5 h-3.5 shrink-0" />
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

export default LeadCaptureNav;
