'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, UserPlus, Phone, User, FileText } from 'lucide-react';
import { api } from '@/lib/api-client';

interface NewLeadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function NewLeadModal({ isOpen, onClose, onSuccess }: NewLeadModalProps) {
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone) {
      setError('Please enter a valid phone number');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api.createLead({
        phone,
        name: name || undefined,
        source: 'manual',
        notes: notes || undefined,
      });
      onSuccess();
      onClose();
      setPhone('');
      setName('');
      setNotes('');
    } catch (err: any) {
      setError(err.message || 'Failed to create lead');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            className="fixed inset-0 flex items-center justify-center p-4 z-50 pointer-events-none"
          >
            <div className="bg-[#FAF7F2] border border-[#D4D0C8] w-full max-w-md rounded-2xl shadow-2xl p-6 relative pointer-events-auto">
              <button
                onClick={onClose}
                className="absolute top-4 right-4 p-2 text-[#6B6B6B] hover:text-[#1A1A1A] rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-lg bg-[#CCFBF1] text-[#0D9488] flex items-center justify-center border border-[#99F6E4]">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-extrabold text-[#0F172A]">Add New Lead</h3>
                  <p className="text-xs text-[#64748B]">Trigger AI Qualification via WhatsApp</p>
                </div>
              </div>

              {error && (
                <div className="mb-4 p-3 rounded-lg bg-[#FEE2E2] border border-[#FECACA] text-[#B91C1C] text-xs font-semibold">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-[#64748B] uppercase mb-1.5">
                    Phone Number (WhatsApp) *
                  </label>
                  <div className="relative">
                    <Phone className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
                    <input
                      type="text"
                      placeholder="+91 98765 43210"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      required
                      className="w-full bg-[#FAFAF9] border border-[#E2E8F0] rounded-lg pl-10 pr-4 py-2.5 text-sm text-[#0F172A] focus:outline-none focus:border-[#0D9488] transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#64748B] uppercase mb-1.5">
                    Lead Full Name
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
                    <input
                      type="text"
                      placeholder="e.g. Rajesh Kumar"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full bg-[#FAFAF9] border border-[#E2E8F0] rounded-lg pl-10 pr-4 py-2.5 text-sm text-[#0F172A] focus:outline-none focus:border-[#0D9488] transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-[#64748B] uppercase mb-1.5">
                    Broker Initial Notes
                  </label>
                  <div className="relative">
                    <FileText className="w-4 h-4 absolute left-3.5 top-3 text-[#94A3B8]" />
                    <textarea
                      placeholder="Met at property expo, interested in 2BHK..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                      className="w-full bg-[#FAFAF9] border border-[#E2E8F0] rounded-lg pl-10 pr-4 py-2 text-sm text-[#0F172A] focus:outline-none focus:border-[#0D9488] transition-colors"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="px-4 py-2 rounded-lg text-xs font-semibold text-[#64748B] hover:text-[#0F172A] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-[#0D9488] hover:bg-[#0F766E] text-white px-5 py-2.5 rounded-lg text-xs font-bold transition-all shadow-sm disabled:opacity-50"
                  >
                    {loading ? 'Creating...' : 'Create & Qualify Lead'}
                  </button>
                </div>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
