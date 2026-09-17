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
    <div className="flex items-center gap-1 border-b border-[#E5E7EB] dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur-md px-6 py-2.5 overflow-x-auto">
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
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all whitespace-nowrap ${
              isActive
                ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900 shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800/60'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </div>
  );
}

export default LeadCaptureNav;

