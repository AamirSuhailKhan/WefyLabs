'use client';

import Link from 'next/link';
import { ShieldAlert } from 'lucide-react';

/**
 * The former page displayed invented platform revenue and customer records.
 * Keep the route honest until the authenticated, audited operations API is
 * implemented; presenting plausible figures is worse than no control center.
 */
export default function AdminPage() {
  return (
    <main className="max-w-2xl mx-auto px-4 py-16 text-center">
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-8">
        <ShieldAlert className="w-10 h-10 mx-auto mb-4 text-amber-400" aria-hidden="true" />
        <h1 className="text-xl font-bold text-white">Admin control center unavailable</h1>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          Platform metrics and customer administration are not shown here until they are backed by
          audited data and a complete operator authorization model.
        </p>
        <Link
          href="/dashboard"
          className="inline-flex mt-6 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-slate-200"
        >
          Return to dashboard
        </Link>
      </div>
    </main>
  );
}
