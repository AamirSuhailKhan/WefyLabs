'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, AlertCircle, HelpCircle, X } from 'lucide-react';
import { Button } from './Button';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'primary' | 'danger' | 'lime';
  iconVariant?: 'warning' | 'danger' | 'info';
  requireReason?: boolean;
  reasonPlaceholder?: string;
  isLoading?: boolean;
  onConfirm: (reason?: string) => void | Promise<void>;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'primary',
  iconVariant = 'warning',
  requireReason = false,
  reasonPlaceholder = 'Please enter reason...',
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setReason('');
      setError(null);
    }
  }, [isOpen]);

  // Handle ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoading) {
        onCancel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isLoading, onCancel]);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    if (requireReason && !reason.trim()) {
      setError('A valid reason is required to proceed.');
      return;
    }
    setError(null);
    await onConfirm(reason.trim());
  };

  const IconComponent =
    iconVariant === 'danger'
      ? AlertCircle
      : iconVariant === 'warning'
      ? AlertTriangle
      : HelpCircle;

  const iconBg =
    iconVariant === 'danger'
      ? 'bg-red-50 text-red-600 border-red-200'
      : iconVariant === 'warning'
      ? 'bg-amber-50 text-amber-600 border-amber-200'
      : 'bg-blue-50 text-blue-600 border-blue-200';

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => !isLoading && onCancel()}
          className="fixed inset-0 bg-[#1A1A1A]/40 backdrop-blur-xs"
        />

        {/* Dialog Content */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 8 }}
          transition={{ duration: 0.15 }}
          className="relative w-full max-w-md bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 shadow-xl z-10"
        >
          <div className="flex items-start gap-3.5 mb-4">
            <div className={`p-2.5 rounded-xl border shrink-0 ${iconBg}`}>
              <IconComponent className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0 pr-6">
              <h3
                className="text-base font-bold text-[#1A1A1A] leading-snug tracking-tight"
                style={{ fontFamily: 'JetBrains Mono, monospace' }}
              >
                {title}
              </h3>
              <p className="text-xs text-[#6B6B6B] mt-1 font-sans leading-relaxed">
                {description}
              </p>
            </div>
            <button
              onClick={onCancel}
              disabled={isLoading}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#EBE6E0] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {requireReason && (
            <div className="mb-4">
              <label className="block text-[11px] font-mono font-bold uppercase text-[#6B6B6B] mb-1.5">
                Reason / Justification <span className="text-red-500">*</span>
              </label>
              <textarea
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  if (error) setError(null);
                }}
                disabled={isLoading}
                placeholder={reasonPlaceholder}
                rows={2}
                className="w-full text-xs font-sans p-2.5 rounded-xl bg-white border border-[#D4D0C8] text-[#1A1A1A] placeholder-[#9CA3AF] focus:ring-2 focus:ring-[#1A1A1A] focus:outline-none transition-all resize-none"
              />
              {error && <p className="text-[11px] text-red-600 font-sans mt-1">{error}</p>}
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[#E5E1DA]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={isLoading}
              onClick={onCancel}
            >
              {cancelLabel}
            </Button>
            <Button
              type="button"
              variant={variant}
              size="sm"
              isLoading={isLoading}
              onClick={handleConfirm}
            >
              {confirmLabel}
            </Button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
