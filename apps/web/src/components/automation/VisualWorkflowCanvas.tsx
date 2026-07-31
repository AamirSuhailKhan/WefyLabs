'use client';

import React from 'react';
import { Zap, GitBranch, Play, CheckCircle2, Plus, Sparkles, ArrowDown } from 'lucide-react';

interface NodeData {
  id: string;
  type: 'trigger' | 'condition' | 'action';
  title: string;
  subtitle: string;
  badge: string;
}

interface Props {
  nodes?: NodeData[];
  onAddNode?: () => void;
}

export function VisualWorkflowCanvas({
  nodes = [
    {
      id: '1',
      type: 'trigger',
      title: 'Trigger: Inbound WhatsApp Lead',
      subtitle: 'Triggers when a new lead sends a message on WhatsApp',
      badge: 'WhatsApp API'
    },
    {
      id: '2',
      type: 'condition',
      title: 'Condition: Budget > $1,000,000 & Country = UAE',
      subtitle: 'Branch if lead intent score is Hot (>80)',
      badge: 'Logic Filter'
    },
    {
      id: '3',
      type: 'action',
      title: 'Action: Assign Lead to Senior Broker (Dubai Team)',
      subtitle: 'Round-robin assignment based on agent capacity',
      badge: 'CRM Action'
    },
    {
      id: '4',
      type: 'action',
      title: 'Action: Send Automated PDF Brochure & Video Walkthrough',
      subtitle: 'Dispatches custom WhatsApp template with PDF media attachment',
      badge: 'WhatsApp Bot'
    }
  ],
  onAddNode
}: Props) {
  return (
    <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl p-6 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-[#EAE7E1] pb-3">
        <div className="flex items-center gap-2 font-mono font-bold text-[#1A1A1A]">
          <Zap className="w-4 h-4 text-[#1A1A1A]" />
          <span>Visual Workflow DAG Node Graph Canvas</span>
        </div>

        <button onClick={onAddNode} className="btn-lime text-xs px-3 py-1.5 flex items-center gap-1">
          <Plus className="w-3.5 h-3.5" />
          <span>Add Node</span>
        </button>
      </div>

      {/* Visual Nodes Sequence */}
      <div className="flex flex-col items-center space-y-3 py-2">
        {nodes.map((node, index) => (
          <React.Fragment key={node.id}>
            {/* Node Card */}
            <div
              className={`w-full max-w-lg p-4 rounded-2xl border transition-all shadow-xs ${
                node.type === 'trigger'
                  ? 'bg-[#1A1A1A] text-white border-black'
                  : node.type === 'condition'
                  ? 'bg-amber-50 text-amber-950 border-amber-200'
                  : 'bg-white text-[#1A1A1A] border-[#D4D0C8]'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span
                  className={`text-[9px] font-mono font-bold uppercase px-2 py-0.5 rounded ${
                    node.type === 'trigger'
                      ? 'bg-[#E8F5A8] text-[#1A1A1A]'
                      : node.type === 'condition'
                      ? 'bg-amber-200 text-amber-900'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {node.badge}
                </span>
                <span className="text-[10px] font-mono opacity-60">Step {index + 1}</span>
              </div>
              <h4 className="text-xs font-bold font-mono">{node.title}</h4>
              <p className="text-[11px] font-sans opacity-80 mt-0.5">{node.subtitle}</p>
            </div>

            {/* Connection Arrow */}
            {index < nodes.length - 1 && (
              <div className="flex flex-col items-center text-gray-400">
                <ArrowDown className="w-4 h-4 text-[#1A1A1A]" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
