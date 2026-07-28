'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, CheckCircle2, Plus, Phone } from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { mockTasks, MockTask, TaskStatus } from '@/lib/mock-data';

type TabType = 'upcoming' | 'overdue' | 'completed';

const TAG_COLORS: Record<string, string> = {
  Call:      '#0D9488',
  Viewing:   '#3B82F6',
  'Follow-up': '#F59E0B',
  WhatsApp:  '#10B981',
};

function TaskCard({ task, onToggle, index = 0 }: { task: MockTask; onToggle: (id: string) => void; index?: number }) {
  const isOverdue = task.status === 'overdue';
  const isCompleted = task.status === 'completed' || task.completed;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
      whileHover={{ y: -2 }}
      className={`bg-white border border-[#D4D0C8] rounded-xl p-5 mb-3 transition-all ${isCompleted ? 'opacity-60' : 'hover:border-[#B0ACA4]'}`}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-3">
          <motion.button
            onClick={() => onToggle(task.id)}
            whileTap={{ scale: 0.88 }}
            animate={isCompleted ? { backgroundColor: '#10B981', borderColor: '#10B981' } : { backgroundColor: 'transparent', borderColor: '#D4D0C8' }}
            className="w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-colors"
          >
            <AnimatePresence>
              {isCompleted && (
                <motion.svg
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  exit={{ pathLength: 0 }}
                  transition={{ duration: 0.2 }}
                  className="w-3.5 h-3.5"
                  viewBox="0 0 24 24"
                >
                  <motion.path d="M4 12L9 17L20 6" stroke="white" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </motion.svg>
              )}
            </AnimatePresence>
          </motion.button>
          <span
            className={`text-[14px] font-semibold leading-tight ${isCompleted ? 'line-through text-[#6B6B6B]' : 'text-[#1A1A1A]'}`}
            style={{ fontFamily: 'Inter, sans-serif' }}
          >
            {task.title}
          </span>
        </div>

        {/* Time badge */}
        <span
          className={`shrink-0 text-[11px] font-bold px-2.5 py-1 rounded-full ${
            isCompleted
              ? 'bg-[#F5F0EB] text-[#6B6B6B]'
              : isOverdue
              ? 'bg-[#FEF3C7] text-[#B45309]'
              : 'bg-[#CCFBF1] text-[#0F766E]'
          }`}
          style={{ fontFamily: 'Inter, sans-serif' }}
        >
          {isOverdue && '⚠️ '}{task.dueAt}
        </span>
      </div>

      {/* Lead info */}
      <div className="flex items-center gap-2 mb-3 pl-8">
        <span className="text-[13px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
          {task.leadName}
        </span>
        <span className="text-[#D4D0C8]">•</span>
        <a
          href={`tel:${task.leadPhone}`}
          className="flex items-center gap-1 text-[13px] text-[#0D9488] hover:text-[#0F766E] font-medium transition-colors"
          style={{ fontFamily: 'JetBrains Mono, monospace' }}
        >
          <Phone className="w-3 h-3" />
          {task.leadPhone}
        </a>
      </div>

      {/* Bottom row */}
      <div className="flex items-center justify-between pl-8">
        <span
          className="text-[11px] font-bold px-2.5 py-1 rounded-md border text-[#4A4A4A] bg-[#F5F0EB] border-[#D4D0C8]"
          style={{ fontFamily: 'Inter, sans-serif', borderLeftColor: TAG_COLORS[task.tag], borderLeftWidth: '3px' }}
        >
          {task.tag}
        </span>
        <span className="text-[12px] text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
          📍 {task.location}
        </span>
      </div>
    </motion.div>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<MockTask[]>(mockTasks);
  const [activeTab, setActiveTab] = useState<TabType>('upcoming');
  const [showNewTask, setShowNewTask] = useState(false);
  const [newTitle, setNewTitle] = useState('');

  const handleToggle = (id: string) => {
    setTasks(prev => prev.map(t =>
      t.id === id ? { ...t, completed: !t.completed, status: (!t.completed ? 'completed' : 'upcoming') as TaskStatus } : t
    ));
  };

  const tabCounts = {
    upcoming:  tasks.filter(t => t.status === 'upcoming' && !t.completed).length,
    overdue:   tasks.filter(t => t.status === 'overdue' && !t.completed).length,
    completed: tasks.filter(t => t.completed || t.status === 'completed').length,
  };

  const filtered = tasks.filter(t => {
    if (activeTab === 'completed') return t.completed || t.status === 'completed';
    if (activeTab === 'overdue')   return t.status === 'overdue' && !t.completed;
    return t.status === 'upcoming' && !t.completed;
  });

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* ── Page Header ── */}
          <div className="py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8]">
            <div>
              <h1
                className="text-[28px] font-bold text-[#1A1A1A] tracking-tight"
                style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
              >
                TASKS &amp; REMINDERS
              </h1>
              <p className="text-[14px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                Never miss a follow-up. Track calls, viewings, and deadlines.
              </p>
            </div>
            <button
              onClick={() => setShowNewTask(!showNewTask)}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D4E894] text-[#1A1A1A] rounded-lg text-[13px] font-semibold transition-all shrink-0"
            >
              <Plus className="w-4 h-4" />
              New Task
            </button>
          </div>

          {/* ── New Task input ── */}
          {showNewTask && (
            <div className="py-4 border-b border-[#D4D0C8]">
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl p-4 flex gap-3">
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newTitle.trim()) {
                      setTasks(prev => [{
                        id: `t${Date.now()}`,
                        title: newTitle.trim(),
                        leadName: 'Unassigned',
                        leadPhone: '',
                        dueAt: 'Today',
                        tag: 'Call',
                        location: 'TBD',
                        status: 'upcoming',
                        completed: false,
                      }, ...prev]);
                      setNewTitle('');
                      setShowNewTask(false);
                    }
                  }}
                  placeholder="Task title... (press Enter to add)"
                  autoFocus
                  className="flex-1 bg-white border border-[#D4D0C8] rounded-lg px-4 py-2.5 text-[14px] text-[#1A1A1A] placeholder:text-[#A0A0A0] focus:outline-none focus:border-[#1A1A1A]"
                  style={{ fontFamily: 'Inter, sans-serif' }}
                />
                <button
                  onClick={() => { setShowNewTask(false); setNewTitle(''); }}
                  className="px-4 py-2 rounded-lg border border-[#D4D0C8] text-[13px] text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* ── Tabs ── */}
          <div className="py-5 flex items-center gap-2">
            {(['upcoming', 'overdue', 'completed'] as TabType[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold capitalize transition-all ${
                  activeTab === tab
                    ? 'bg-[#1A1A1A] text-white'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#FAF7F2]'
                }`}
                style={{ fontFamily: 'Inter, sans-serif' }}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                <span
                  className={`text-[11px] font-bold px-1.5 py-0.5 rounded-full ${
                    activeTab === tab
                      ? 'bg-white/20 text-white'
                      : 'bg-[#F5F0EB] text-[#6B6B6B]'
                  }`}
                >
                  {tabCounts[tab]}
                </span>
              </button>
            ))}
          </div>

          {/* ── Task list ── */}
          <div className="pb-12">
            {filtered.length === 0 ? (
              <div className="text-center py-16">
                <CheckCircle2 className="w-10 h-10 text-[#D4D0C8] mx-auto mb-3" />
                <p className="text-[15px] font-semibold text-[#6B6B6B]" style={{ fontFamily: 'Inter, sans-serif' }}>
                  {activeTab === 'completed' ? 'No completed tasks yet.' : `No ${activeTab} tasks!`}
                </p>
                {activeTab !== 'completed' && (
                  <p className="text-[13px] text-[#A0A0A0] mt-1">You're all caught up 🎉</p>
                )}
              </div>
            ) : (
              filtered.map((task, i) => (
                <TaskCard key={task.id} task={task} onToggle={handleToggle} index={i} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
