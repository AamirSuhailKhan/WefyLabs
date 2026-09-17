'use client';

import React, { useState, useEffect } from 'react';
import { Play, Pause, Square, Sparkles, Clock, Check, X, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api-client';

interface LeadAutomationPanelProps {
  leadId: string;
  leadName?: string;
  initialStatus?: string;
}

export function LeadAutomationPanel({ leadId, leadName = 'Lead', initialStatus }: LeadAutomationPanelProps) {
  const [status, setStatus] = useState<string>(initialStatus || 'ACTIVE');
  const [loading, setLoading] = useState(false);
  const [leadStatusData, setLeadStatusData] = useState<any>(null);
  const [reengageDraft, setReengageDraft] = useState<any>(null);
  const [isReengaging, setIsReengaging] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await api.followups.getLeadStatus(leadId);
      setLeadStatusData(res);
      if (res?.is_suppressed) {
        setStatus('STOPPED');
      } else if (res?.lifecycle_state === 'HUMAN_HANDOFF') {
        setStatus('PAUSED');
      } else {
        setStatus('ACTIVE');
      }
    } catch {
      // Fallback
    }
  };

  useEffect(() => {
    if (leadId) {
      fetchStatus();
    }
  }, [leadId]);

  const handlePause = async () => {
    setLoading(true);
    try {
      await api.followups.pauseLead(leadId, 'Agent requested pause via automation panel');
      setStatus('PAUSED');
    } catch (e: any) {
      alert(e.message || 'Failed to pause automation');
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    setLoading(true);
    try {
      await api.followups.resumeLead(leadId);
      setStatus('ACTIVE');
    } catch (e: any) {
      alert(e.message || 'Failed to resume automation');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    if (!confirm('Permanently stop all automation and record client opt-out for this lead?')) return;
    setLoading(true);
    try {
      await api.followups.stopLead(leadId);
      setStatus('STOPPED');
    } catch (e: any) {
      alert(e.message || 'Failed to stop automation');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReengagement = async () => {
    setIsReengaging(true);
    try {
      const res = await api.followups.reengageLead(leadId);
      setReengageDraft(res);
    } catch (e: any) {
      alert(e.message || 'Failed to generate re-engagement draft');
    } finally {
      setIsReengaging(false);
    }
  };

  return (
    <div className="bg-white border border-[#E8E4DC] rounded-2xl p-5 shadow-xs space-y-4 font-mono text-xs text-[#1A1A1A]">
      <div className="flex items-center justify-between border-b border-[#E8E4DC] pb-3">
        <div>
          <span className="text-[10px] text-gray-500 uppercase">Follow-Up Automation</span>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={`w-2 h-2 rounded-full ${
              status === 'ACTIVE' ? 'bg-emerald-500 animate-pulse' : (status === 'PAUSED' ? 'bg-amber-500' : 'bg-rose-500')
            }`} />
            <h4 className="font-bold">{status}</h4>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {status === 'ACTIVE' ? (
            <button
              onClick={handlePause}
              disabled={loading}
              className="px-2.5 py-1 rounded-lg border border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 flex items-center gap-1 text-[11px]"
            >
              <Pause className="w-3 h-3" />
              <span>Pause</span>
            </button>
          ) : status === 'PAUSED' ? (
            <button
              onClick={handleResume}
              disabled={loading}
              className="px-2.5 py-1 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 flex items-center gap-1 text-[11px]"
            >
              <Play className="w-3 h-3" />
              <span>Resume</span>
            </button>
          ) : null}

          {status !== 'STOPPED' && (
            <button
              onClick={handleStop}
              disabled={loading}
              className="px-2.5 py-1 rounded-lg border border-rose-300 bg-rose-50 text-rose-800 hover:bg-rose-100 flex items-center gap-1 text-[11px]"
            >
              <Square className="w-3 h-3" />
              <span>Stop</span>
            </button>
          )}
        </div>
      </div>

      {leadStatusData?.next_best_action && (
        <div className="bg-[#FAF7F2] p-3 rounded-xl space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-gray-400 uppercase">Recommended Next Action</span>
            <span className="text-[10px] text-amber-700 font-bold">Confidence {Math.round((leadStatusData.next_best_action.confidence || 1) * 100)}%</span>
          </div>
          <p className="font-bold text-[#1A1A1A]">{leadStatusData.next_best_action.recommended_action}</p>
          <p className="text-[11px] text-gray-600">{leadStatusData.next_best_action.action_reason}</p>
        </div>
      )}

      <div className="pt-1 flex items-center justify-between">
        <button
          onClick={handleGenerateReengagement}
          disabled={isReengaging}
          className="btn-lime px-3 py-1.5 rounded-lg flex items-center gap-1.5 text-[11px] font-bold"
        >
          {isReengaging ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
          <span>Generate AI Re-engagement</span>
        </button>
      </div>

      {reengageDraft && (
        <div className="bg-emerald-50/60 border border-emerald-200 p-3.5 rounded-xl space-y-2 mt-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-emerald-800 uppercase">Grounded Message Draft</span>
            <button onClick={() => setReengageDraft(null)} className="text-gray-400 hover:text-gray-600">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <p className="text-xs text-[#2B2B2B] bg-white p-2.5 rounded-lg border border-emerald-100">
            {reengageDraft.message_body}
          </p>
          <span className="text-[10px] text-gray-500">
            Draft generated from real CRM facts. Copy to send via WhatsApp or Email.
          </span>
        </div>
      )}
    </div>
  );
}
