'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'lime' | 'secondary' | 'outline' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  isLoading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      loadingText,
      leftIcon,
      rightIcon,
      disabled,
      className = '',
      onClick,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-sans font-semibold transition-all duration-150 select-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#1A1A1A] focus:ring-offset-1 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none';

    const variants: Record<string, string> = {
      primary:
        'bg-[#1A1A1A] text-white hover:bg-black border border-transparent shadow-xs',
      lime:
        'bg-[#E8F5A8] text-[#1A1A1A] hover:bg-[#D4E894] border border-[#D4D0C8] shadow-xs',
      secondary:
        'bg-[#FAF7F2] text-[#1A1A1A] hover:bg-[#F0EDE8] border border-[#D4D0C8] shadow-xs',
      outline:
        'bg-transparent text-[#1A1A1A] hover:bg-[#1A1A1A] hover:text-white border border-[#1A1A1A]',
      danger:
        'bg-[#FEF2F2] text-[#991B1B] hover:bg-[#FEE2E2] border border-[#FECACA]',
      ghost:
        'bg-transparent text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#EBE6E0] border border-transparent',
    };

    const sizes: Record<string, string> = {
      sm: 'text-xs px-3 py-1.5 rounded-lg gap-1.5 h-8',
      md: 'text-xs sm:text-sm px-4 py-2 rounded-xl gap-2 h-10',
      lg: 'text-sm sm:text-base px-6 py-2.5 rounded-xl gap-2.5 h-12',
      icon: 'p-2 rounded-xl h-10 w-10',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        onClick={(e) => {
          if (isLoading || disabled) {
            e.preventDefault();
            return;
          }
          onClick?.(e);
        }}
        className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin text-current shrink-0" />
            {loadingText && <span>{loadingText}</span>}
          </>
        ) : (
          <>
            {leftIcon && <span className="shrink-0">{leftIcon}</span>}
            {children}
            {rightIcon && <span className="shrink-0">{rightIcon}</span>}
          </>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
