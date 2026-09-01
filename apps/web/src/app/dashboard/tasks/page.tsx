'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2,
  Plus,
  Phone,
  Calendar,
  Clock,
  MapPin,
  Pencil,
  Trash2,
  AlertCircle,
  X,
  User,
  Flag,
  Tag as TagIcon,
  RefreshCw
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { Lead } from '@/types';

export type TabType = 'upcoming' | 'overdue' | 'completed';
export type TaskTag = 'Call' | 'Viewing' | 'Follow-up' | 'WhatsApp' | 'Meeting' | 'Deadline';
export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent';

export interface TaskItem {
  id: string;
  title: string;
  description?: string;
  leadId?: string;
  leadName?: string;
  leadPhone?: string;
  dueAt?: string;
  dueDate?: string;
  dueTime?: string;
  priority: TaskPriority;
  tag: TaskTag;
  location?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  completed: boolean;
  completedAt?: string;
  createdAt: string;
}

const TAG_COLORS: Record<TaskTag, { bg: string; text: string; border: string; bar: string }> = {
  Call:        { bg: '#CCFBF1', text: '#0F766E', border: '#99F6E4', bar: '#0D9488' },
  Viewing:     { bg: '#DBEAFE', text: '#1E40AF', border: '#BFDBFE', bar: '#3B82F6' },
  'Follow-up': { bg: '#FEF3C7', text: '#92400E', border: '#FDE68A', bar: '#F59E0B' },
  WhatsApp:    { bg: '#D1FAE5', text: '#065F46', border: '#A7F3D0', bar: '#10B981' },
  Meeting:     { bg: '#EDE9FE', text: '#5B21B6', border: '#DDD6FE', bar: '#8B5CF6' },
  Deadline:    { bg: '#FEE2E2', text: '#991B1B', border: '#FECACA', bar: '#EF4444' },
};

const PRIORITY_BADGES: Record<TaskPriority, { label: string; bg: string; text: string }> = {
  low:    { label: 'Low',    bg: '#F3F4F6', text: '#4B5563' },
  normal: { label: 'Normal', bg: '#E0F2FE', text: '#0369A1' },
  high:   { label: 'High',   bg: '#FEF3C7', text: '#B45309' },
  urgent: { label: 'Urgent', bg: '#FEE2E2', text: '#B91C1C' },
};

function inferTag(title: string, priority: string): TaskTag {
  const lower = title.toLowerCase();
  if (lower.includes('view') || lower.includes('site visit')) return 'Viewing';
  if (lower.includes('call') || lower.includes('phone')) return 'Call';
  if (lower.includes('whatsapp') || lower.includes('message') || lower.includes('chat')) return 'WhatsApp';
  if (lower.includes('meet') || lower.includes('appointment')) return 'Meeting';
  if (lower.includes('deadline') || priority === 'urgent') return 'Deadline';
  return 'Follow-up';
}

function parseDueDate(iso?: string) {
  if (!iso) return { formattedTime: 'No time set', isOverdue: false, dateStr: '', timeStr: '' };
  const d = new Date(iso);
  if (isNaN(d.getTime())) return { formattedTime: 'No time set', isOverdue: false, dateStr: '', timeStr: '' };

  const isOverdue = d < new Date();
  const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  const dateInput = d.toISOString().split('T')[0];
  const timeInput = d.toTimeString().slice(0, 5);

  return {
    formattedTime: `${dateStr} · ${timeStr}`,
    isOverdue,
    dateStr: dateInput,
    timeStr: timeInput,
  };
}

function TaskCard({
  task,
  onToggle,
  onEdit,
  onDelete,
  index = 0,
}: {
  task: TaskItem;
  onToggle: (id: string, e: React.MouseEvent) => void;
  onEdit: (task: TaskItem) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  index?: number;
}) {
  const isCompleted = task.completed || task.status === 'completed';
  const dueInfo = parseDueDate(task.dueAt);
  const isOverdue = !isCompleted && dueInfo.isOverdue;
  const tagStyle = TAG_COLORS[task.tag] || TAG_COLORS['Follow-up'];
  const priorityStyle = PRIORITY_BADGES[task.priority] || PRIORITY_BADGES.normal;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.25, delay: Math.min(index * 0.03, 0.3) }}
      className={`bg-white border rounded-2xl p-5 mb-3.5 transition-all shadow-sm ${
        isCompleted
          ? 'opacity-65 border-[#E5E0D8] bg-[#FAF8F5]'
          : isOverdue
          ? 'border-[#FCD34D] hover:border-[#F59E0B]'
          : 'border-[#D4D0C8] hover:border-[#A8A29E]'
      }`}
    >
      {/* Top Row: Checkbox, Title, Badges */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3.5 flex-1 min-w-0">
          {/* Complete Checkbox */}
          <button
            type="button"
            aria-label={`Mark task "${task.title}" as ${isCompleted ? 'incomplete' : 'completed'}`}
            onClick={(e) => onToggle(task.id, e)}
            className={`w-6 h-6 rounded-lg border-2 shrink-0 mt-0.5 flex items-center justify-center transition-all cursor-pointer ${
              isCompleted
                ? 'bg-[#10B981] border-[#10B981] text-white shadow-sm'
                : 'border-[#A8A29E] bg-white hover:border-[#1A1A1A] hover:bg-[#F5F0EB]'
            }`}
          >
            {isCompleted && (
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>

          {/* Title & Description */}
          <div className="flex-1 min-w-0">
            <h3
              className={`text-[15px] font-bold leading-snug tracking-tight truncate ${
                isCompleted ? 'line-through text-[#8A8A8A]' : 'text-[#1A1A1A]'
              }`}
              style={{ fontFamily: 'Inter, sans-serif' }}
              title={task.title}
            >
              {task.title}
            </h3>

            {task.description && (
              <p className="text-[13px] text-[#6B6B6B] mt-1 line-clamp-2 leading-relaxed" style={{ fontFamily: 'Inter, sans-serif' }}>
                {task.description}
              </p>
            )}
          </div>
        </div>

        {/* Due Time Badge */}
        {task.dueAt && (
          <span
            className={`shrink-0 text-[11px] font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${
              isCompleted
                ? 'bg-[#F0EDE8] text-[#8A8A8A]'
                : isOverdue
                ? 'bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]'
                : 'bg-[#E0F2FE] text-[#0369A1] border border-[#BAE6FD]'
            }`}
            style={{ fontFamily: 'JetBrains Mono, monospace' }}
          >
            {isOverdue && '⚠️ '}{dueInfo.formattedTime}
          </span>
        )}
      </div>

      {/* Middle Row: Contact / Lead & Location Info */}
      {(task.leadName || task.location) && (
        <div className="flex flex-wrap items-center gap-y-1.5 gap-x-4 mt-3 pl-9.5 text-[13px] text-[#6B6B6B]">
          {task.leadName && (
            <div className="flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-[#8A8A8A]" />
              <span className="font-semibold text-[#374151]">{task.leadName}</span>
              {task.leadPhone && (
                <>
                  <span className="text-[#D4D0C8]">•</span>
                  <a
                    href={`tel:${task.leadPhone}`}
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 text-[#0D9488] hover:text-[#0F766E] font-medium hover:underline transition-colors"
                    style={{ fontFamily: 'JetBrains Mono, monospace' }}
                    title={`Call ${task.leadPhone}`}
                  >
                    <Phone className="w-3 h-3" />
                    {task.leadPhone}
                  </a>
                </>
              )}
            </div>
          )}

          {task.location && (
            <div className="flex items-center gap-1 text-[#6B6B6B]">
              <MapPin className="w-3.5 h-3.5 text-[#8A8A8A]" />
              <span>{task.location}</span>
            </div>
          )}
        </div>
      )}

      {/* Bottom Row: Tag Badge, Priority, and Action Buttons */}
      <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-[#F0EDE8] pl-9.5">
        <div className="flex items-center gap-2">
          {/* Tag / Category Badge */}
          <span
            className="text-[11px] font-bold px-2.5 py-0.5 rounded-md border"
            style={{
              fontFamily: 'Inter, sans-serif',
              backgroundColor: tagStyle.bg,
              color: tagStyle.text,
              borderColor: tagStyle.border,
            }}
          >
            {task.tag}
          </span>

          {/* Priority Badge */}
          {task.priority !== 'normal' && (
            <span
              className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider"
              style={{
                backgroundColor: priorityStyle.bg,
                color: priorityStyle.text,
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              {priorityStyle.label}
            </span>
          )}
        </div>

        {/* Action buttons (Edit & Delete) */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onEdit(task)}
            className="p-1.5 text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#F0EDE8] rounded-lg transition-colors"
            title="Edit task"
            aria-label={`Edit task "${task.title}"`}
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={(e) => onDelete(task.id, e)}
            className="p-1.5 text-[#9CA3AF] hover:text-[#DC2626] hover:bg-red-50 rounded-lg transition-colors"
            title="Delete task"
            aria-label={`Delete task "${task.title}"`}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [activeTab, setActiveTab] = useState<TabType>('upcoming');

  // Modal State for New / Edit Task
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskItem | null>(null);
  const [modalTitle, setModalTitle] = useState('');
  const [modalDescription, setModalDescription] = useState('');
  const [modalTag, setModalTag] = useState<TaskTag>('Follow-up');
  const [modalPriority, setModalPriority] = useState<TaskPriority>('normal');
  const [modalLeadId, setModalLeadId] = useState<string>('');
  const [modalDate, setModalDate] = useState<string>('');
  const [modalTime, setModalTime] = useState<string>('11:00');
  const [modalLocation, setModalLocation] = useState<string>('');
  const [modalSubmitting, setModalSubmitting] = useState(false);
  const [modalError, setModalError] = useState('');

  // Delete Confirmation State
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const fetchTasksAndLeads = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [serverTasks, serverLeads] = await Promise.all([
        api.getTasks(),
        api.getLeads().catch(() => ({ items: [] }))
      ]);

      if (serverLeads && serverLeads.items) {
        setLeads(serverLeads.items);
      }

      if (Array.isArray(serverTasks)) {
        const formatted: TaskItem[] = serverTasks.map((st: any) => {
          const isDone = st.status === 'completed' || !!st.completed_at;
          const tag = inferTag(st.title || '', st.priority || 'normal');
          return {
            id: String(st.id),
            title: st.title || 'Untitled Task',
            description: st.description || '',
            leadId: st.lead_id || (st.lead ? st.lead.id : undefined),
            leadName: st.lead?.name || undefined,
            leadPhone: st.lead?.phone || undefined,
            dueAt: st.due_at || undefined,
            priority: (st.priority || 'normal') as TaskPriority,
            tag,
            location: st.location || undefined,
            status: isDone ? 'completed' : 'pending',
            completed: isDone,
            completedAt: st.completed_at || undefined,
            createdAt: st.created_at || new Date().toISOString(),
          };
        });
        setTasks(formatted);
      }
    } catch (err: any) {
      console.warn('[Tasks] Error fetching tasks from server:', err);
      setError(err.message || 'Could not load tasks from server.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasksAndLeads();
  }, [fetchTasksAndLeads]);

  // Modal Open Handlers
  const handleOpenNewTask = () => {
    setEditingTask(null);
    setModalTitle('');
    setModalDescription('');
    setModalTag('Follow-up');
    setModalPriority('normal');
    setModalLeadId('');
    // Default tomorrow at 11:00 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setModalDate(tomorrow.toISOString().split('T')[0]);
    setModalTime('11:00');
    setModalLocation('');
    setModalError('');
    setIsModalOpen(true);
  };

  const handleOpenEditTask = (task: TaskItem) => {
    setEditingTask(task);
    setModalTitle(task.title);
    setModalDescription(task.description || '');
    setModalTag(task.tag);
    setModalPriority(task.priority);
    setModalLeadId(task.leadId || '');
    setModalLocation(task.location || '');
    setModalError('');

    if (task.dueAt) {
      const parsed = parseDueDate(task.dueAt);
      setModalDate(parsed.dateStr);
      setModalTime(parsed.timeStr || '11:00');
    } else {
      const today = new Date().toISOString().split('T')[0];
      setModalDate(today);
      setModalTime('11:00');
    }

    setIsModalOpen(true);
  };

  // Checkbox Complete Toggle Handler
  const handleToggleTask = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const target = tasks.find(t => t.id === id);
    if (!target) return;

    const previousStatus = target.status;
    const previousCompleted = target.completed;
    const nextCompleted = !previousCompleted;
    const nextStatus = nextCompleted ? 'completed' : 'pending';

    // Optimistic Update
    setTasks(prev => prev.map(t =>
      t.id === id ? { ...t, completed: nextCompleted, status: nextStatus } : t
    ));

    try {
      if (nextCompleted) {
        await api.completeTask(id);
      } else {
        await api.updateTaskStatus(id, 'pending');
      }
    } catch (err: any) {
      console.error('[Tasks] Task completion toggle failed:', err);
      // Revert optimistic update
      setTasks(prev => prev.map(t =>
        t.id === id ? { ...t, completed: previousCompleted, status: previousStatus } : t
      ));
      setError(err.message || 'Failed to update task status on server.');
    }
  };

  // Submit Handler for Create / Edit Modal
  const handleSaveTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modalTitle.trim()) {
      setModalError('Task title is required.');
      return;
    }

    let dueAtIso: string | undefined = undefined;
    if (modalDate) {
      const combined = new Date(`${modalDate}T${modalTime || '09:00'}:00`);
      if (!isNaN(combined.getTime())) {
        dueAtIso = combined.toISOString();
      }
    }

    setModalSubmitting(true);
    setModalError('');

    try {
      if (editingTask) {
        // Update Existing Task
        const updated = await api.updateTask(editingTask.id, {
          title: modalTitle.trim(),
          description: modalDescription.trim() || undefined,
          due_at: dueAtIso,
          priority: modalPriority,
          lead_id: modalLeadId || undefined,
        });

        const selectedLead = leads.find(l => l.id === modalLeadId);
        setTasks(prev => prev.map(t => {
          if (t.id !== editingTask.id) return t;
          return {
            ...t,
            title: updated.title || modalTitle.trim(),
            description: updated.description || modalDescription.trim(),
            dueAt: updated.due_at || dueAtIso,
            priority: (updated.priority || modalPriority) as TaskPriority,
            tag: modalTag,
            leadId: modalLeadId || undefined,
            leadName: updated.lead?.name || selectedLead?.name || t.leadName,
            leadPhone: updated.lead?.phone || selectedLead?.phone || t.leadPhone,
            location: modalLocation || t.location,
          };
        }));
      } else {
        // Create New Task
        const created = await api.createTask({
          title: modalTitle.trim(),
          description: modalDescription.trim() || undefined,
          due_at: dueAtIso,
          priority: modalPriority,
          lead_id: modalLeadId || undefined,
        });

        const selectedLead = leads.find(l => l.id === modalLeadId);
        const newTask: TaskItem = {
          id: String(created.id),
          title: created.title || modalTitle.trim(),
          description: created.description || modalDescription.trim(),
          leadId: modalLeadId || undefined,
          leadName: created.lead?.name || selectedLead?.name || undefined,
          leadPhone: created.lead?.phone || selectedLead?.phone || undefined,
          dueAt: created.due_at || dueAtIso,
          priority: (created.priority || modalPriority) as TaskPriority,
          tag: modalTag,
          location: modalLocation || undefined,
          status: 'pending',
          completed: false,
          createdAt: created.created_at || new Date().toISOString(),
        };

        setTasks(prev => [newTask, ...prev]);
      }

      setIsModalOpen(false);
    } catch (err: any) {
      console.error('[Tasks] Task save failed:', err);
      setModalError(err.message || 'Failed to save task. Please try again.');
    } finally {
      setModalSubmitting(false);
    }
  };

  // Delete Handlers
  const handleOpenDeleteConfirm = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingTaskId(id);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingTaskId) return;
    const targetId = deletingTaskId;
    setDeleteConfirmOpen(false);
    setDeletingTaskId(null);

    // Optimistically remove from list
    const previous = [...tasks];
    setTasks(prev => prev.filter(t => t.id !== targetId));

    try {
      await api.deleteTask(targetId);
    } catch (err: any) {
      console.error('[Tasks] Delete task failed:', err);
      setTasks(previous);
      setError(err.message || 'Failed to delete task.');
    }
  };

  // Tab Filtering and Accurate Real Dynamic Counts
  const tabCounts = useMemo(() => {
    const now = new Date();
    let upcoming = 0;
    let overdue = 0;
    let completed = 0;

    for (const t of tasks) {
      const isDone = t.completed || t.status === 'completed';
      if (isDone) {
        completed++;
      } else if (t.dueAt && new Date(t.dueAt) < now) {
        overdue++;
      } else {
        upcoming++;
      }
    }

    return { upcoming, overdue, completed };
  }, [tasks]);

  const filteredTasks = useMemo(() => {
    const now = new Date();
    return tasks.filter(t => {
      const isDone = t.completed || t.status === 'completed';
      if (activeTab === 'completed') return isDone;
      if (activeTab === 'overdue') return !isDone && !!t.dueAt && new Date(t.dueAt) < now;
      // Default: Upcoming (not completed and either future due date or no date)
      return !isDone && (!t.dueAt || new Date(t.dueAt) >= now);
    });
  }, [tasks, activeTab]);

  return (
    <div className="min-h-screen bg-[#F0EDE8]">
      <DashboardNav />

      <div className="pt-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">

          {/* ── Page Header ── */}
          <div className="py-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D4D0C8]">
            <div>
              <h1
                className="text-[26px] sm:text-[28px] font-bold text-[#1A1A1A] tracking-tight leading-tight"
                style={{ fontFamily: 'JetBrains Mono, Geist Mono, Courier New, monospace' }}
              >
                TASKS &amp; REMINDERS
              </h1>
              <p className="text-[14px] text-[#6B6B6B] mt-0.5" style={{ fontFamily: 'Inter, sans-serif' }}>
                Never miss a follow-up. Track calls, viewings, and deadlines.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={fetchTasksAndLeads}
                disabled={loading}
                title="Refresh tasks"
                className="p-2.5 bg-[#FAF7F2] border border-[#D4D0C8] hover:bg-[#EBE7E0] text-[#4A4A4A] rounded-xl transition-all"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-[#0D9488]' : ''}`} />
              </button>

              <button
                type="button"
                onClick={handleOpenNewTask}
                className="flex items-center gap-2 px-4 py-2.5 bg-[#E8F5A8] hover:bg-[#D8EB8E] text-[#1A1A1A] rounded-xl text-[13px] font-bold transition-all shadow-sm shrink-0"
              >
                <Plus className="w-4 h-4 stroke-[2.5]" />
                New Task
              </button>
            </div>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="my-4 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <AlertCircle className="w-5 h-5 shrink-0 text-red-500" />
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={fetchTasksAndLeads}
                className="text-xs font-bold underline hover:no-underline text-red-800"
              >
                Retry
              </button>
            </div>
          )}

          {/* ── Tabs ── */}
          <div className="py-5 flex items-center gap-2">
            {(['upcoming', 'overdue', 'completed'] as TabType[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[13px] font-bold capitalize transition-all cursor-pointer ${
                  activeTab === tab
                    ? 'bg-[#1A1A1A] text-white shadow-sm'
                    : 'text-[#6B6B6B] hover:text-[#1A1A1A] hover:bg-[#FAF7F2]'
                }`}
                style={{ fontFamily: 'Inter, sans-serif' }}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                <span
                  className={`text-[11px] font-bold px-2 py-0.5 rounded-full transition-colors ${
                    activeTab === tab
                      ? 'bg-white/20 text-white'
                      : tab === 'overdue' && tabCounts.overdue > 0
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-[#E5E0D8] text-[#6B6B6B]'
                  }`}
                  style={{ fontFamily: 'JetBrains Mono, monospace' }}
                >
                  {tabCounts[tab]}
                </span>
              </button>
            ))}
          </div>

          {/* ── Task List ── */}
          <div className="pb-16">
            {loading && tasks.length === 0 ? (
              <div className="text-center py-20 bg-white/50 border border-[#D4D0C8] rounded-2xl">
                <div className="w-8 h-8 border-3 border-[#1A1A1A] border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                <p className="text-sm font-semibold text-[#6B6B6B]">Loading your tasks &amp; follow-ups...</p>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="text-center py-16 bg-white border border-[#D4D0C8] rounded-2xl shadow-sm p-8">
                <CheckCircle2 className="w-12 h-12 text-[#10B981] mx-auto mb-3" />
                <h3 className="text-[17px] font-bold text-[#1A1A1A]" style={{ fontFamily: 'Inter, sans-serif' }}>
                  {activeTab === 'completed'
                    ? 'No completed tasks yet'
                    : activeTab === 'overdue'
                    ? 'No overdue tasks!'
                    : 'No upcoming tasks!'}
                </h3>
                <p className="text-[13px] text-[#6B6B6B] mt-1 max-w-sm mx-auto" style={{ fontFamily: 'Inter, sans-serif' }}>
                  {activeTab === 'completed'
                    ? 'Tasks you complete will be archived here for your record.'
                    : activeTab === 'overdue'
                    ? 'All your follow-ups and meetings are on track. Great job!'
                    : "You're all caught up! Create a new task to track calls, viewings, or deadlines."}
                </p>
                {activeTab !== 'completed' && (
                  <button
                    type="button"
                    onClick={handleOpenNewTask}
                    className="mt-5 inline-flex items-center gap-2 px-4 py-2 bg-[#E8F5A8] hover:bg-[#D8EB8E] text-[#1A1A1A] rounded-xl text-[13px] font-bold transition-all shadow-sm"
                  >
                    <Plus className="w-4 h-4" />
                    Create Task
                  </button>
                )}
              </div>
            ) : (
              <AnimatePresence mode="popLayout">
                {filteredTasks.map((task, i) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onToggle={handleToggleTask}
                    onEdit={handleOpenEditTask}
                    onDelete={handleOpenDeleteConfirm}
                    index={i}
                  />
                ))}
              </AnimatePresence>
            )}
          </div>
        </div>
      </div>

      {/* ── New / Edit Task Modal ── */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => !modalSubmitting && setIsModalOpen(false)}
              className="absolute inset-0 bg-[#0F172A]/50 backdrop-blur-sm"
            />

            {/* Modal Dialog */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="relative w-full max-w-lg bg-white rounded-3xl p-6 sm:p-8 shadow-2xl border border-[#D4D0C8] z-10 max-h-[90vh] overflow-y-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D8]">
                <h2 className="text-xl font-bold text-[#1A1A1A] font-serif">
                  {editingTask ? 'Edit Task' : 'Create New Task'}
                </h2>
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  disabled={modalSubmitting}
                  className="p-1.5 text-[#8A8A8A] hover:text-[#1A1A1A] rounded-lg hover:bg-[#F5F0EB] transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Modal Error */}
              {modalError && (
                <div className="mt-4 p-3 rounded-xl bg-red-50 border border-red-200 text-xs font-semibold text-red-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
                  <span>{modalError}</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSaveTask} className="mt-5 space-y-4">
                {/* Title */}
                <div>
                  <label htmlFor="task-title" className="block text-xs font-bold text-[#374151] mb-1.5">
                    Task Title <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="task-title"
                    type="text"
                    required
                    value={modalTitle}
                    onChange={(e) => setModalTitle(e.target.value)}
                    placeholder="e.g. Call Rajesh Kumar — 2BHK Koramangala options"
                    className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] placeholder-[#9CA3AF] focus:outline-none transition-all"
                  />
                </div>

                {/* Tag / Type Selection */}
                <div>
                  <label className="block text-xs font-bold text-[#374151] mb-1.5">
                    Task Type
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['Call', 'Viewing', 'Follow-up', 'WhatsApp', 'Meeting', 'Deadline'] as TaskTag[]).map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => setModalTag(tag)}
                        className={`py-2 px-2.5 rounded-xl text-xs font-bold border transition-all text-center ${
                          modalTag === tag
                            ? 'border-[#1A1A1A] bg-[#1A1A1A] text-white shadow-sm'
                            : 'border-[#D4D0C8] bg-[#FAFAF9] text-[#4A4A4A] hover:bg-[#F0EDE8]'
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Lead / Contact Selector */}
                <div>
                  <label htmlFor="task-lead" className="block text-xs font-bold text-[#374151] mb-1.5">
                    Associated Contact / Lead
                  </label>
                  <select
                    id="task-lead"
                    value={modalLeadId}
                    onChange={(e) => setModalLeadId(e.target.value)}
                    className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] focus:outline-none transition-all"
                  >
                    <option value="">-- None / General Task --</option>
                    {leads.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name || 'Unnamed'} ({l.phone})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Date & Time Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="task-date" className="block text-xs font-bold text-[#374151] mb-1.5">
                      Due Date
                    </label>
                    <input
                      id="task-date"
                      type="date"
                      value={modalDate}
                      onChange={(e) => setModalDate(e.target.value)}
                      className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] focus:outline-none transition-all"
                    />
                  </div>

                  <div>
                    <label htmlFor="task-time" className="block text-xs font-bold text-[#374151] mb-1.5">
                      Due Time
                    </label>
                    <input
                      id="task-time"
                      type="time"
                      value={modalTime}
                      onChange={(e) => setModalTime(e.target.value)}
                      className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] focus:outline-none transition-all"
                    />
                  </div>
                </div>

                {/* Priority & Location Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="task-priority" className="block text-xs font-bold text-[#374151] mb-1.5">
                      Priority
                    </label>
                    <select
                      id="task-priority"
                      value={modalPriority}
                      onChange={(e) => setModalPriority(e.target.value as TaskPriority)}
                      className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] focus:outline-none transition-all capitalize"
                    >
                      <option value="low">Low Priority</option>
                      <option value="normal">Normal Priority</option>
                      <option value="high">High Priority</option>
                      <option value="urgent">Urgent Priority</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="task-location" className="block text-xs font-bold text-[#374151] mb-1.5">
                      Location (Optional)
                    </label>
                    <input
                      id="task-location"
                      type="text"
                      value={modalLocation}
                      onChange={(e) => setModalLocation(e.target.value)}
                      placeholder="e.g. Indiranagar, Bengaluru"
                      className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] placeholder-[#9CA3AF] focus:outline-none transition-all"
                    />
                  </div>
                </div>

                {/* Description / Notes */}
                <div>
                  <label htmlFor="task-desc" className="block text-xs font-bold text-[#374151] mb-1.5">
                    Notes / Description
                  </label>
                  <textarea
                    id="task-desc"
                    rows={3}
                    value={modalDescription}
                    onChange={(e) => setModalDescription(e.target.value)}
                    placeholder="Details about client requirements, property units to show, questions to ask..."
                    className="w-full bg-[#FAFAF9] border border-[#D4D0C8] focus:border-[#1A1A1A] focus:bg-white rounded-xl px-3.5 py-2.5 text-sm text-[#1A1A1A] placeholder-[#9CA3AF] focus:outline-none transition-all resize-none"
                  />
                </div>

                {/* Submit / Cancel buttons */}
                <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#E5E0D8]">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    disabled={modalSubmitting}
                    className="px-4 py-2.5 rounded-xl border border-[#D4D0C8] text-sm font-semibold text-[#4A4A4A] hover:bg-[#F5F0EB] transition-colors"
                  >
                    Cancel
                  </button>

                  <button
                    type="submit"
                    disabled={modalSubmitting}
                    className="px-5 py-2.5 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-sm font-bold shadow-sm transition-all disabled:opacity-50"
                  >
                    {modalSubmitting ? 'Saving...' : editingTask ? 'Update Task' : 'Create Task'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Delete Confirmation Dialog ── */}
      <AnimatePresence>
        {deleteConfirmOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDeleteConfirmOpen(false)}
              className="absolute inset-0 bg-[#0F172A]/50 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative w-full max-w-sm bg-white rounded-2xl p-6 shadow-2xl border border-[#D4D0C8] z-10 text-center"
            >
              <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto mb-3">
                <Trash2 className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-[#1A1A1A] mb-1">Delete Task?</h3>
              <p className="text-xs text-[#6B6B6B] mb-5">
                Are you sure you want to permanently delete this task? This action cannot be undone.
              </p>
              <div className="flex items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={() => setDeleteConfirmOpen(false)}
                  className="px-4 py-2 rounded-xl border border-[#D4D0C8] text-xs font-semibold text-[#4A4A4A] hover:bg-[#F5F0EB]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDelete}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-xl shadow-sm"
                >
                  Yes, Delete
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
