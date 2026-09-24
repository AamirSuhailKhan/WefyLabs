'use client';

import React from 'react';
import { AlertCircle, RefreshCw, Lock, ShieldAlert, WifiOff } from 'lucide-react';
import { Button } from './Button';

interface ErrorStateProps {
  title?: string;
  description?: string;
  statusCode?: number | string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title,
  description,
  statusCode,
  onRetry,
  className = '',
}: ErrorStateProps) {
  let displayTitle = title;
  let displayDesc = description;
  let Icon = AlertCircle;
  let iconBg = 'bg-[#FEF2F2] text-[#991B1B] border-[#FECACA]';

  const code = Number(statusCode);

  if (code === 401 || code === 403) {
    displayTitle = displayTitle || 'Access Restricted';
    displayDesc = displayDesc || 'You do not have permission to view or modify this record. Please contact your workspace administrator.';
    Icon = Lock;
    iconBg = 'bg-[#FFFBEB] text-[#B45309] border-[#FDE68A]';
  } else if (code === 404) {
    displayTitle = displayTitle || 'Record Not Found';
    displayDesc = displayDesc || 'The requested resource does not exist or may have been archived.';
    Icon = ShieldAlert;
  } else if (code === 429) {
    displayTitle = displayTitle || 'Rate Limit Exceeded';
    displayDesc = displayDesc || 'Too many requests were submitted in a short time. Please wait a moment before trying again.';
    Icon = AlertCircle;
  } else if (code >= 500) {
    displayTitle = displayTitle || 'Service Temporarily Unavailable';
    displayDesc = displayDesc || 'Our API servers encountered an unexpected error. Please retry in a few seconds.';
    Icon = WifiOff;
  } else {
    displayTitle = displayTitle || 'Failed to Load Data';
    displayDesc = displayDesc || 'An error occurred while fetching information from the server.';
  }

  return (
    <div
      className={`p-8 sm:p-12 text-center rounded-2xl bg-[#FAF7F2] border border-[#D4D0C8] shadow-xs my-6 max-w-lg mx-auto ${className}`}
    >
      <div className={`w-12 h-12 rounded-2xl border flex items-center justify-center mx-auto mb-4 shadow-xs ${iconBg}`}>
        <Icon className="w-6 h-6" />
      </div>

      <h3
        className="text-base font-bold text-[#1A1A1A] mb-1.5"
        style={{ fontFamily: 'JetBrains Mono, monospace' }}
      >
        {displayTitle}
      </h3>
      <p className="text-xs text-[#6B6B6B] leading-relaxed mb-6 font-sans">
        {displayDesc}
      </p>

      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
        >
          Try Again
        </Button>
      )}
    </div>
  );
}
