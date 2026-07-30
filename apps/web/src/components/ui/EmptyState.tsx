'use client';

import React, { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  primaryAction?: {
    label: string;
    onClick: () => void;
    icon?: LucideIcon;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  children?: ReactNode;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  children,
}: EmptyStateProps) {
  return (
    <div className="p-8 sm:p-12 text-center rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs my-4 max-w-md mx-auto">
      <div className="w-12 h-12 rounded-2xl bg-[#E8F5A8] border border-[#D4D0C8] flex items-center justify-center mx-auto mb-4 text-[#1A1A1A] shadow-xs">
        <Icon className="w-6 h-6" />
      </div>

      <h3 className="text-base font-bold text-[#1A1A1A] font-mono mb-1.5">{title}</h3>
      <p className="text-xs text-[#6B6B6B] leading-relaxed mb-6 font-sans">{description}</p>

      {children}

      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        {primaryAction && (
          <button
            onClick={primaryAction.onClick}
            className="w-full sm:w-auto btn-lime flex items-center justify-center gap-1.5 py-2 px-4 text-xs"
          >
            {primaryAction.icon && <primaryAction.icon className="w-3.5 h-3.5" />}
            <span>{primaryAction.label}</span>
          </button>
        )}

        {secondaryAction && (
          <button
            onClick={secondaryAction.onClick}
            className="w-full sm:w-auto btn-outline py-2 px-4 text-xs"
          >
            {secondaryAction.label}
          </button>
        )}
      </div>
    </div>
  );
}
