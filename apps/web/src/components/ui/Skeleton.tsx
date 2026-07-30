'use client';

import React from 'react';

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-[#EAE7E1] dark:bg-gray-800 rounded-lg ${className}`}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-white border border-[#D4D0C8] rounded-xl p-4 space-y-3 shadow-xs">
      <div className="flex justify-between items-center">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-12 rounded-full" />
      </div>
      <Skeleton className="h-5 w-24" />
      <Skeleton className="h-3 w-40" />
      <div className="pt-2 border-t border-[#F0EDE8] flex justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16" />
      </div>
    </div>
  );
}

export function SkeletonTableRow() {
  return (
    <div className="flex items-center justify-between p-3.5 border-b border-[#EAE7E1] animate-pulse">
      <div className="flex items-center gap-3">
        <Skeleton className="w-8 h-8 rounded-full" />
        <div className="space-y-1.5">
          <Skeleton className="h-3.5 w-28" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <Skeleton className="h-4 w-16 rounded-full" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-4 w-20" />
    </div>
  );
}
