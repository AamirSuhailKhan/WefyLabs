'use client';

import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className = '', ...props }: CardProps) {
  return (
    <div
      className={`bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-5 sm:p-6 shadow-xs ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '', ...props }: CardProps) {
  return (
    <div className={`pb-4 border-b border-[#E5E1DA] mb-4 flex items-center justify-between ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '', ...props }: CardProps) {
  return (
    <h3
      className={`text-base font-bold text-[#1A1A1A] tracking-tight ${className}`}
      style={{ fontFamily: 'JetBrains Mono, monospace' }}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardDescription({ children, className = '', ...props }: CardProps) {
  return (
    <p className={`text-xs text-[#6B6B6B] mt-0.5 font-sans leading-relaxed ${className}`} {...props}>
      {children}
    </p>
  );
}

export function CardContent({ children, className = '', ...props }: CardProps) {
  return (
    <div className={`space-y-4 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className = '', ...props }: CardProps) {
  return (
    <div className={`pt-4 border-t border-[#E5E1DA] mt-4 flex items-center justify-between ${className}`} {...props}>
      {children}
    </div>
  );
}
