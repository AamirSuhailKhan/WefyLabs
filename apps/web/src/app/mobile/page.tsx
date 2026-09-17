'use client';

import React, { useState } from 'react';
import { MobileVoiceAssistant } from '@/components/mobile/MobileVoiceAssistant';
import { Smartphone, WifiOff, Camera, MapPin, UserCheck, RefreshCw, CheckCircle2, QrCode, Scan } from 'lucide-react';

export default function MobileAppPage() {
  const [isOffline, setIsOffline] = useState(false);
  const [ocrResult, setOcrResult] = useState<any>(null);
  const [scanning, setScanning] = useState(false);

  const handleScanBusinessCard = () => {
    setScanning(true);
    setTimeout(() => {
      setOcrResult({
        name: 'Dr. Sameer Kapoor',
        company: 'Apex Healthcare UAE',
        phone: '+971 50 987 6543',
        email: 'dr.sameer@apexhealth.ae',
        locality: 'Palm Jumeirah',
        budget: 'AED 4,500,000'
      });
      setScanning(false);
    }, 600);
  };

  return (
    <div className="min-h-screen bg-[#FAF7F2] p-4 max-w-md mx-auto space-y-5">
      {/* Top Mobile Header */}
      <div className="flex items-center justify-between bg-[#1A1A1A] text-white p-4 rounded-3xl shadow-lg">
        <div className="flex items-center gap-2">
          <Smartphone className="w-5 h-5 text-[#E8F5A8]" />
          <div>
            <h1 className="text-sm font-bold font-mono">WefyLabs Mobile Field App</h1>
            <span className="text-[10px] text-gray-400 font-mono">iOS & Android WebView / PWA</span>
          </div>
        </div>

        <button
          onClick={() => setIsOffline(!isOffline)}
          className={`px-2.5 py-1 rounded-full text-[10px] font-mono font-bold flex items-center gap-1 transition-colors ${
            isOffline ? 'bg-amber-400 text-amber-950' : 'bg-emerald-500 text-white'
          }`}
        >
          {isOffline ? <WifiOff className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
          <span>{isOffline ? 'Offline Mode' : 'Online Sync'}</span>
        </button>
      </div>

      {/* Offline Alert Banner */}
      {isOffline && (
        <div className="bg-amber-50 border border-amber-300 p-3 rounded-2xl text-xs text-amber-950 font-sans flex items-center justify-between">
          <span>⚠️ Offline Mode Active (3 local edits queued for background sync)</span>
          <span className="text-[10px] font-mono underline font-bold">LWW Sync</span>
        </div>
      )}

      {/* 1-Tap Voice Assistant Dictation Widget */}
      <MobileVoiceAssistant />

      {/* Business Card OCR Scanner Widget */}
      <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-2">
          <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#1A1A1A]">
            <Camera className="w-4 h-4 text-indigo-600" />
            <span>Business Card AI OCR Scanner</span>
          </div>
          <Scan className="w-4 h-4 text-gray-400" />
        </div>

        <p className="text-xs text-gray-600 font-sans">
          Snap or upload a photo of a prospect's business card to instantly parse contact profile into WefyLabs.
        </p>

        <button
          onClick={handleScanBusinessCard}
          disabled={scanning}
          className="btn-lime w-full py-2.5 text-xs flex items-center justify-center gap-2"
        >
          {scanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
          <span>Scan Business Card Photo</span>
        </button>

        {ocrResult && (
          <div className="p-3 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl text-xs space-y-1 font-mono">
            <span className="text-[10px] text-emerald-800 font-bold uppercase block">AI OCR Extracted Lead Profile</span>
            <div className="font-bold text-[#1A1A1A]">{ocrResult.name}</div>
            <div className="text-gray-600">{ocrResult.company} • {ocrResult.locality}</div>
            <div className="text-gray-600">{ocrResult.phone} | {ocrResult.email}</div>
            <div className="text-emerald-700 font-bold mt-1">Est. Budget: {ocrResult.budget}</div>
          </div>
        )}
      </div>
    </div>
  );
}
