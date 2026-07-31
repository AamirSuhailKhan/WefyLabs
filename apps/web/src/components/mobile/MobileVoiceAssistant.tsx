'use client';

import React, { useState } from 'react';
import { Mic, MicOff, Sparkles, CheckCircle2, RefreshCw, Volume2 } from 'lucide-react';

interface Props {
  onTranscriptComplete?: (transcript: string, summary: string, tasks: string[]) => void;
}

export function MobileVoiceAssistant({ onTranscriptComplete }: Props) {
  const [isRecording, setIsRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<{ transcript: string; summary: string; tasks: string[] } | null>(null);

  const toggleRecording = () => {
    if (!isRecording) {
      setIsRecording(true);
      setResult(null);
    } else {
      setIsRecording(false);
      setProcessing(true);
      setTimeout(() => {
        const res = {
          transcript: "Met buyer Rahul Sharma at DLF Phase 5 site. High interest in 3BHK ready penthouse. Budget is 2.5 Cr cash. Needs floor plan on WhatsApp by tomorrow 10 AM.",
          summary: "Site visit completed with Rahul Sharma for DLF Phase 5 3BHK. High intent cash buyer.",
          tasks: [
            "Send floor plan PDF to Rahul Sharma via WhatsApp by tomorrow 10 AM",
            "Schedule follow-up call for Aug 1, 2026"
          ]
        };
        setResult(res);
        setProcessing(false);
        onTranscriptComplete?.(res.transcript, res.summary, res.tasks);
      }, 700);
    }
  };

  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-5 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-2">
        <div className="flex items-center gap-1.5 text-xs font-mono font-bold text-[#1A1A1A]">
          <Mic className="w-4 h-4 text-rose-600" />
          <span>1-Tap Voice Dictation & AI Transcription</span>
        </div>
        <span className="bg-[#E8F5A8] text-[#1A1A1A] text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border border-[#D4D0C8]">
          Hands-Free Field Mode
        </span>
      </div>

      {/* Voice Dictation Button */}
      <div className="flex flex-col items-center justify-center py-4 space-y-2">
        <button
          onClick={toggleRecording}
          className={`w-16 h-16 rounded-full flex items-center justify-center transition-all ${
            isRecording
              ? 'bg-rose-600 text-white animate-pulse scale-110 shadow-lg'
              : 'bg-[#1A1A1A] text-white hover:scale-105'
          }`}
        >
          {isRecording ? <MicOff className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
        </button>

        <span className="text-xs font-mono font-bold text-gray-700">
          {isRecording ? 'Listening... Tap to stop' : 'Tap mic to dictate site visit voice note'}
        </span>
      </div>

      {processing && (
        <div className="flex items-center justify-center gap-2 text-xs text-gray-500 font-mono py-2">
          <RefreshCw className="w-4 h-4 animate-spin text-amber-500" />
          <span>Transcribing audio & extracting CRM tasks...</span>
        </div>
      )}

      {result && (
        <div className="bg-white border border-[#D4D0C8] rounded-2xl p-4 space-y-3 shadow-xs">
          <div>
            <span className="text-[10px] font-mono uppercase text-gray-400 font-bold block">AI Speech-to-Text Transcript</span>
            <p className="text-xs text-[#1A1A1A] font-sans italic mt-0.5">"{result.transcript}"</p>
          </div>

          <div className="bg-emerald-50 border border-emerald-200 p-2.5 rounded-xl space-y-1">
            <div className="flex items-center gap-1 text-xs font-mono font-bold text-emerald-950">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Extracted CRM Action Items ({result.tasks.length})</span>
            </div>
            <ul className="text-xs text-emerald-900 font-sans list-disc list-inside space-y-0.5">
              {result.tasks.map((task, i) => (
                <li key={i}>{task}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
