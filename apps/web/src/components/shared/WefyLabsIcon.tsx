import React from 'react';
import Image from 'next/image';

export interface WefyLabsIconProps {
  className?: string;
  size?: number | string;
  theme?: 'light' | 'dark' | 'monochrome-light' | 'monochrome-dark' | 'auto';
  fill?: string;
  ariaLabel?: string;
}

export function WefyLabsIcon({
  className = '',
  size = 28,
  theme = 'auto',
  fill,
  ariaLabel = 'WefyLabs Mark',
}: WefyLabsIconProps) {
  const numericSize = typeof size === 'number' ? size : parseInt(size as string, 10) || 28;
  // Aspect ratio is 220 : 115 (approx 1.91 : 1)
  const width = Math.round(numericSize * 1.91);
  const height = numericSize;

  // Monochrome filter classes if requested
  let filterClass = '';
  if (theme === 'monochrome-dark') {
    filterClass = 'brightness-0 invert opacity-95';
  } else if (theme === 'monochrome-light') {
    filterClass = 'brightness-0 opacity-90';
  }

  return (
    <span
      className={`inline-flex items-center justify-center select-none shrink-0 relative ${className}`}
      style={{ width: `${width}px`, height: `${height}px` }}
      role="img"
      aria-label={ariaLabel}
    >
      <Image
        src="/branding/wefylabs-mark.png"
        alt={ariaLabel}
        width={width}
        height={height}
        priority
        className={`object-contain transition-opacity duration-200 ${filterClass}`}
        style={{ width: '100%', height: '100%' }}
      />
    </span>
  );
}

// Backward-compatible alias
export const BeetleLabsIcon = WefyLabsIcon;
