'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Activity, ArrowLeft, RefreshCw, Phone, Mail, Calendar, CheckSquare, MessageSquare } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { CRMActivity } from '@/types/crm';

export default function CRMActivitiesPage() {
  const [activities, setActivities] = useState<CRMActivity[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchActivities = async () => {
    setLoading(true);
    try {
      const data = await api.crm.getActivities(undefined, 100);
      setActivities(data);
    } catch (err) {
      console.error('Failed to load activities', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();
  }, []);

  const getActivityIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'call':
      case 'call_made':
        return <Phone className="w-4 h-4 text-[#2563EB]" />;
      case 'email':
        return <Mail className="w-4 h-4 text-[#7C3AED]" />;
      case 'meeting':
      case 'site_visit':
      case 'meeting_booked':
        return <Calendar className="w-4 h-4 text-[#D97706]" />;
      case 'task_completed':
        return <CheckSquare className="w-4 h-4 text-[#059669]" />;
      default:
        return <Activity className="w-4 h-4 text-[#0F766E]" />;
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1200px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        <div className="flex items-center gap-2 mb-4 text-xs text-[#6B7280]">
          <Link href="/dashboard/crm" className="hover:text-[#111827] flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            CRM Operations
          </Link>
          <span>/</span>
          <span className="text-[#111827] font-semibold">Activity Audit Feed</span>
        </div>

        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">Activity Audit Feed</h1>
            <p className="text-xs text-[#4B5563] mt-1">
              Immutable timeline of all customer interactions, broker actions, and system events.
            </p>
          </div>

          <button
            onClick={() => fetchActivities()}
            className="p-2 border border-[#E5E7EB] bg-white rounded-lg hover:bg-[#F3F4F6] text-[#374151] transition"
            title="Refresh activities"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Feed List */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6">
          {loading ? (
            <div className="text-center py-12 text-xs text-[#9CA3AF]">
              Loading activity records...
            </div>
          ) : activities.length === 0 ? (
            <div className="text-center py-12 text-xs text-[#6B7280]">
              No activities logged yet.
            </div>
          ) : (
            <div className="relative border-l-2 border-[#E5E7EB] ml-3 pl-6 space-y-6">
              {activities.map((act) => (
                <div key={act.id} className="relative">
                  <div className="absolute -left-[31px] top-1 w-3.5 h-3.5 rounded-full bg-white border-2 border-[#0F766E] flex items-center justify-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E]" />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getActivityIcon(act.activity_type)}
                      <span className="text-xs font-bold text-[#111827]">{act.title}</span>
                    </div>
                    <span className="text-[11px] text-[#9CA3AF]">
                      {new Date(act.created_at).toLocaleString()}
                    </span>
                  </div>

                  {act.description && (
                    <p className="text-xs text-[#4B5563] mt-1">{act.description}</p>
                  )}

                  <div className="flex items-center gap-2 mt-2 text-[10px] text-[#6B7280]">
                    <span className="px-1.5 py-0.5 bg-[#F3F4F6] rounded uppercase font-semibold">
                      Type: {act.activity_type}
                    </span>
                    <span className="px-1.5 py-0.5 bg-[#EFF6FF] text-[#2563EB] rounded uppercase font-semibold">
                      Actor: {act.actor_type}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
