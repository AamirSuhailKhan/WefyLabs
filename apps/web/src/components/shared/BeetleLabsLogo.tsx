import React from 'react';
import Link from 'next/link';
import { BeetleLabsIcon } from './BeetleLabsIcon';

interface BeetleLabsLogoProps {
  href?: string;
  iconSize?: number;
  textSize?: string;
  className?: string;
  dark?: boolean;
  showIcon?: boolean;
}

export function BeetleLabsLogo({
  href = '/',
  iconSize = 24,
  textSize = 'text-xl',
  className = '',
  dark = false,
  showIcon = true,
}: BeetleLabsLogoProps) {
  const textColor = dark ? 'text-white' : 'text-[#1A1A1A]';
  const iconColor = dark ? '#FFFFFF' : '#1A1A1A';

  const content = (
    <div className={`inline-flex items-center gap-2.5 font-sans ${className}`}>
      {showIcon && (
        <div className={`flex items-center justify-center p-1 rounded-md ${dark ? 'bg-black' : 'bg-transparent'}`}>
          <BeetleLabsIcon size={iconSize} fill={iconColor} />
        </div>
      )}
      <span className={`${textSize} tracking-tight ${textColor} select-none`}>
        <span className="font-extrabold">Beetle</span>
        <span className="font-light">Labs</span>
      </span>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="inline-block hover:opacity-90 transition-opacity">
        {content}
      </Link>
    );
  }

  return content;
}
