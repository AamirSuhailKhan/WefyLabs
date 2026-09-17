import React from 'react';
import Link from 'next/link';
import { WefyLabsIcon } from './WefyLabsIcon';

export interface WefyLabsLogoProps {
  variant?: 'full' | 'mark' | 'compact';
  size?: 'sm' | 'md' | 'lg' | 'xl' | number;
  theme?: 'light' | 'dark' | 'monochrome-light' | 'monochrome-dark' | 'auto';
  showWordmark?: boolean;
  href?: string | null;
  className?: string;
  ariaLabel?: string;
  // Backward-compatible props
  iconSize?: number;
  textSize?: string;
  dark?: boolean;
  showIcon?: boolean;
}

export function WefyLabsLogo({
  variant = 'full',
  size = 'md',
  theme = 'auto',
  showWordmark = true,
  href = '/',
  className = '',
  ariaLabel = 'WefyLabs',
  // Backward-compatible props
  iconSize,
  textSize,
  dark,
  showIcon = true,
}: WefyLabsLogoProps) {
  // Resolve theme
  const resolvedDark = dark ?? (theme === 'dark');
  const resolvedTheme = resolvedDark ? 'dark' : theme;

  // Resolve numeric mark size
  let markHeight = 24;
  let wordmarkClass = 'text-lg';

  if (iconSize) {
    markHeight = iconSize;
    if (textSize) wordmarkClass = textSize;
  } else if (typeof size === 'number') {
    markHeight = size;
  } else {
    switch (size) {
      case 'sm':
        markHeight = 18;
        wordmarkClass = 'text-sm';
        break;
      case 'md':
        markHeight = 24;
        wordmarkClass = 'text-lg';
        break;
      case 'lg':
        markHeight = 32;
        wordmarkClass = 'text-2xl';
        break;
      case 'xl':
        markHeight = 40;
        wordmarkClass = 'text-3xl';
        break;
    }
  }

  if (textSize) {
    wordmarkClass = textSize;
  }

  // Determine if wordmark should render
  const shouldRenderWordmark = variant !== 'mark' && showWordmark;

  // Text color determination
  const primaryTextColor = resolvedDark ? 'text-white' : 'text-[#1A1A1A]';
  const labsTextColor = resolvedDark ? 'text-[#93C5FD]' : 'text-[#2C4BFB]';

  const content = (
    <div
      className={`inline-flex items-center gap-2.5 font-sans select-none ${className}`}
      aria-label={ariaLabel}
    >
      {showIcon && (
        <WefyLabsIcon
          size={markHeight}
          theme={resolvedTheme}
          ariaLabel={`${ariaLabel} Mark`}
        />
      )}
      {shouldRenderWordmark && (
        <span
          className={`${wordmarkClass} tracking-tight font-sans leading-none flex items-center`}
          style={{ letterSpacing: '-0.025em' }}
        >
          <span className={`font-extrabold ${primaryTextColor}`}>Wefy</span>
          <span className={`font-medium ml-0.5 ${labsTextColor}`}>Labs</span>
        </span>
      )}
    </div>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="inline-flex items-center hover:opacity-90 active:scale-[0.98] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2C4BFB] rounded-lg"
        aria-label={ariaLabel}
      >
        {content}
      </Link>
    );
  }

  return content;
}

// Backward-compatible alias
export const BeetleLabsLogo = WefyLabsLogo;
export type BeetleLabsLogoProps = WefyLabsLogoProps;
