'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Users, Search, ArrowLeft, ArrowUpRight, Phone, Mail, MapPin } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { LeadCRMListItem } from '@/types/crm';

export default function CRMCustomersPage() {
  const [customers, setCustomers] = useState<LeadCRMListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const loadCustomers = async (searchQuery?: string) => {
    setLoading(true);
    try {
      const data = await api.crm.getCustomers({ search: searchQuery, limit: 100 });
      setCustomers(data);
    } catch (err) {
      console.error('Failed to load customers', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadCustomers(search);
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        <div className="flex items-center gap-2 mb-4 text-xs text-[#6B7280]">
          <Link href="/dashboard/crm" className="hover:text-[#111827] flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            CRM Operations
          </Link>
          <span>/</span>
          <span className="text-[#111827] font-semibold">Customer Directory</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">Customer 360 Directory</h1>
            <p className="text-xs text-[#4B5563] mt-1">
              Authoritative view of all verified customer identities, preferences, and journey states.
            </p>
          </div>

          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-[#9CA3AF]" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name, phone, email..."
                className="pl-9 pr-4 py-2 text-xs bg-white border border-[#D1D5DB] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0F766E] w-64"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-[#111827] text-white text-xs font-semibold rounded-lg hover:bg-[#1F2937] transition"
            >
              Filter
            </button>
          </form>
        </div>

        {/* Customer Table */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#4B5563]">
              <thead className="bg-[#F9FAFB] border-b border-[#E5E7EB] text-[#6B7280] font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Customer Name</th>
                  <th className="py-3 px-4">Contact Information</th>
                  <th className="py-3 px-4">Stage</th>
                  <th className="py-3 px-4">Temperature</th>
                  <th className="py-3 px-4">Budget & Interest</th>
                  <th className="py-3 px-4">Owner</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F3F4F6]">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-[#9CA3AF]">
                      Loading customer records...
                    </td>
                  </tr>
                ) : customers.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-[#6B7280]">
                      No customers found matching your criteria.
                    </td>
                  </tr>
                ) : (
                  customers.map((c) => (
                    <tr key={c.id} className="hover:bg-[#F9FAFB] transition">
                      <td className="py-3.5 px-4 font-bold text-[#111827]">
                        <Link
                          href={`/dashboard/crm/customers/${c.id}`}
                          className="hover:text-[#0F766E] flex items-center gap-1.5"
                        >
                          {c.name || 'Unnamed Client'}
                          <ArrowUpRight className="w-3.5 h-3.5 text-[#9CA3AF]" />
                        </Link>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col gap-0.5">
                          <span className="flex items-center gap-1 text-[#111827]">
                            <Phone className="w-3 h-3 text-[#9CA3AF]" />
                            {c.phone}
                          </span>
                          {c.email && (
                            <span className="flex items-center gap-1 text-[#6B7280] text-[11px]">
                              <Mail className="w-3 h-3 text-[#9CA3AF]" />
                              {c.email}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#E0F2FE] text-[#0369A1] uppercase">
                          {c.pipeline_stage}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          c.score === 'hot'
                            ? 'bg-[#FEE2E2] text-[#B91C1C]'
                            : c.score === 'warm'
                            ? 'bg-[#FEF3C7] text-[#B45309]'
                            : 'bg-[#F3F4F6] text-[#4B5563]'
                        }`}>
                          {c.score}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col">
                          <span className="font-semibold text-[#111827]">
                            {c.budget_max
                              ? `${c.budget_currency} ${c.budget_max.toLocaleString()}`
                              : 'Budget not set'}
                          </span>
                          <span className="text-[11px] text-[#6B7280]">
                            {c.property_type || 'Any Property'}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-[#374151]">
                        {c.owner_name || 'Agent'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          href={`/dashboard/crm/customers/${c.id}`}
                          className="px-3 py-1 bg-white border border-[#D1D5DB] rounded text-xs font-semibold text-[#111827] hover:bg-[#F3F4F6] transition"
                        >
                          View 360
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
