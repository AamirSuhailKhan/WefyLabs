'use client';

import { motion, AnimatePresence } from 'framer-motion';

export function Toast({
  message,
  isVisible,
  onClose,
}: {
  message: string;
  isVisible: boolean;
  onClose?: () => void;
}) {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          className="fixed top-20 right-6 bg-[#1A1A1A] text-white px-5 py-3 rounded-xl shadow-lg z-50 flex items-center gap-3 text-sm font-medium border border-white/10"
        >
          <span>{message}</span>
          {onClose && (
            <button onClick={onClose} className="text-white/60 hover:text-white text-xs">
              ✕
            </button>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
