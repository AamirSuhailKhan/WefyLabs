'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  badge,
  breadcrumbs,
  actions,
  className = '',
}: PageHeaderProps) {
  return (
    <div className={`pb-6 border-b border-[#D4D0C8] mb-6 ${className}`}>
      {/* Optional Breadcrumbs */}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumbs" className="flex items-center gap-1.5 text-xs text-[#6B6B6B] mb-2 font-mono">
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={idx}>
              {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-[#A8A29E] shrink-0" />}
              {crumb.href ? (
                <Link
                  href={crumb.href}
                  className="hover:text-[#1A1A1A] transition-colors underline-offset-2 hover:underline"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="text-[#1A1A1A] font-semibold">{crumb.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}

      {/* Main Header Content */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1
              className="text-2xl sm:text-3xl font-bold text-[#1A1A1A] tracking-tight"
              style={{ fontFamily: 'JetBrains Mono, Geist Mono, monospace' }}
            >
              {title}
            </h1>
            {badge && <div className="shrink-0">{badge}</div>}
          </div>
          {description && (
            <p className="text-xs sm:text-sm text-[#6B6B6B] mt-1 font-sans max-w-3xl leading-relaxed">
              {description}
            </p>
          )}
        </div>

        {/* Action Buttons */}
        {actions && (
          <div className="flex items-center gap-2 flex-wrap shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
