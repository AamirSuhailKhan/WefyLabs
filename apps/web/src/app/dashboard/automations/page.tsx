'use client';

import React, { useState } from 'react';
import { VisualWorkflowCanvas } from '@/components/automation/VisualWorkflowCanvas';
import { Zap, Sparkles, Plus, Play, CheckCircle2, RefreshCw, Layers } from 'lucide-react';

export default function AutomationsPage() {
  const [aiPrompt, setAiPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const workflows = [
    {
      id: '1',
      name: 'High Budget Lead Auto-Assignment & Brochure Dispatch',
      description: 'Triggers when a new lead arrives on WhatsApp with budget > $1M.',
      is_active: true,
      trigger_type: 'whatsapp_received',
      nodes_count: 4,
      last_executed_at: '2 min ago'
    },
    {
      id: '2',
      name: 'Stalled Deal Escalate to Manager',
      description: "Triggers when a deal remains in 'Booking' stage for over 5 days.",
      is_active: true,
      trigger_type: 'deal_moved',
      nodes_count: 3,
      last_executed_at: '1 hour ago'
    }
  ];

  const handleGenerateAI = () => {
    if (!aiPrompt.trim()) return;
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      setAiPrompt('');
    }, 800);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#1A1A1A]">No-Code Visual Workflow Builder</h1>
          <p className="text-xs text-[#6B6B6B] font-sans">
            Zapier & HubSpot grade workflow engine. Automate triggers, conditions, WhatsApp bots, and manager escalations.
          </p>
        </div>

        <button className="btn-lime px-4 py-2 text-xs flex items-center gap-1.5 self-start sm:self-auto">
          <Plus className="w-4 h-4" />
          <span>Create Blank Workflow</span>
        </button>
      </div>

      {/* AI Prompt Generator Toolbar */}
      <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-2xl space-y-2 shadow-xs">
        <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#1A1A1A]">
          <Sparkles className="w-4 h-4 text-amber-500 fill-amber-300" />
          <span>AI Natural Language Workflow Generator</span>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="text"
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGenerateAI()}
            placeholder="e.g., When a high budget UAE lead arrives on WhatsApp, assign to senior agent and send brochure..."
            className="flex-1 px-3.5 py-2.5 bg-white border border-[#D4D0C8] rounded-xl text-xs text-[#1A1A1A] placeholder-gray-400 focus:outline-none"
          />
          <button
            onClick={handleGenerateAI}
            disabled={isGenerating}
            className="btn-lime px-4 py-2.5 text-xs flex items-center gap-1.5"
          >
            {isGenerating ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
            <span>Generate Workflow</span>
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Active Workflows List */}
        <div className="lg:col-span-5 space-y-4">
          <h3 className="text-xs font-mono font-bold uppercase text-gray-500">Active Workflows ({workflows.length})</h3>

          <div className="space-y-3">
            {workflows.map((wf) => (
              <div key={wf.id} className="bg-white border border-[#D4D0C8] p-4 rounded-2xl shadow-xs space-y-2 cursor-pointer hover:border-[#1A1A1A] transition-colors">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                    Active • {wf.nodes_count} Nodes
                  </span>
                  <span className="text-[10px] font-mono text-gray-400">Ran {wf.last_executed_at}</span>
                </div>

                <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">{wf.name}</h4>
                <p className="text-xs text-gray-600 font-sans">{wf.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Visual Workflow Canvas */}
        <div className="lg:col-span-7">
          <VisualWorkflowCanvas />
        </div>
      </div>
    </div>
  );
}
