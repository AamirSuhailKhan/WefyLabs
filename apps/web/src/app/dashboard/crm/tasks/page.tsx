'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  CheckSquare, ArrowLeft, Plus, CheckCircle2, Clock, 
  AlertCircle, Trash2, Calendar
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';
import { CRMTask } from '@/types/crm';

export default function CRMTasksPage() {
  const [tasks, setTasks] = useState<CRMTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  
  // New task form state
  const [isCreating, setIsCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newPriority, setNewPriority] = useState('normal');
  const [newDueDate, setNewDueDate] = useState('');

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await api.crm.getTasks({
        status: statusFilter || undefined,
        priority: priorityFilter || undefined
      });
      setTasks(data);
    } catch (err) {
      console.error('Failed to load tasks', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [statusFilter, priorityFilter]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      await api.crm.createTask({
        title: newTitle.trim(),
        description: newDesc.trim() || undefined,
        priority: newPriority,
        due_at: newDueDate ? new Date(newDueDate).toISOString() : undefined
      });
      setNewTitle('');
      setNewDesc('');
      setNewDueDate('');
      setIsCreating(false);
      await fetchTasks();
    } catch (err) {
      console.error('Failed to create task', err);
    }
  };

  const handleToggleComplete = async (task: CRMTask) => {
    const newStatus = task.status === 'completed' ? 'pending' : 'completed';
    try {
      await api.crm.updateTask(task.id, { status: newStatus });
      await fetchTasks();
    } catch (err) {
      console.error('Failed to update task', err);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!confirm('Are you sure you want to delete this task?')) return;
    try {
      await api.crm.deleteTask(taskId);
      await fetchTasks();
    } catch (err) {
      console.error('Failed to delete task', err);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-[1200px] mx-auto px-4 sm:px-6 pt-24 pb-16">
        <div className="flex items-center gap-2 mb-4 text-xs text-[#6B7280]">
          <Link href="/dashboard/crm" className="hover:text-[#111827] flex items-center gap-1">
            <ArrowLeft className="w-3.5 h-3.5" />
            CRM Operations
          </Link>
          <span>/</span>
          <span className="text-[#111827] font-semibold">Task Manager</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-[#111827]">CRM Task Manager</h1>
            <p className="text-xs text-[#4B5563] mt-1">
              Track client follow-ups, viewing confirmations, proposal deadlines, and team actions.
            </p>
          </div>

          <button
            onClick={() => setIsCreating(!isCreating)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#0F766E] text-white text-xs font-semibold rounded-lg hover:bg-[#0D655E] transition shadow-sm"
          >
            <Plus className="w-4 h-4" />
            {isCreating ? 'Cancel' : 'New Task'}
          </button>
        </div>

        {/* Task Creation Form Drawer */}
        {isCreating && (
          <form onSubmit={handleCreateTask} className="bg-white border border-[#E5E7EB] rounded-xl p-5 mb-6 shadow-sm">
            <h2 className="text-sm font-bold text-[#111827] mb-3">Create Operational Task</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
              <div>
                <label className="text-xs font-semibold text-[#6B7280] block mb-1">Title *</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Call Rajesh regarding Downtown 2BHK viewing"
                  required
                  className="w-full p-2 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:ring-2 focus:ring-[#0F766E]"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-[#6B7280] block mb-1">Due Date</label>
                <input
                  type="datetime-local"
                  value={newDueDate}
                  onChange={(e) => setNewDueDate(e.target.value)}
                  className="w-full p-2 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:ring-2 focus:ring-[#0F766E]"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs font-semibold text-[#6B7280] block mb-1">Description</label>
                <input
                  type="text"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Additional details or notes..."
                  className="w-full p-2 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:ring-2 focus:ring-[#0F766E]"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-[#6B7280] block mb-1">Priority</label>
                <select
                  value={newPriority}
                  onChange={(e) => setNewPriority(e.target.value)}
                  className="w-full p-2 text-xs bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg focus:ring-2 focus:ring-[#0F766E]"
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
            </div>
            <button
              type="submit"
              className="px-5 py-2 bg-[#111827] text-white text-xs font-semibold rounded-lg hover:bg-[#1F2937] transition"
            >
              Save Task
            </button>
          </form>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="py-1.5 px-3 text-xs bg-white border border-[#D1D5DB] rounded-lg text-[#374151]"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="py-1.5 px-3 text-xs bg-white border border-[#D1D5DB] rounded-lg text-[#374151]"
          >
            <option value="">All Priorities</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Tasks List */}
        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm divide-y divide-[#F3F4F6]">
          {loading ? (
            <div className="text-center py-12 text-xs text-[#9CA3AF]">
              Loading tasks...
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-center py-12 text-xs text-[#6B7280]">
              No tasks found matching your filter criteria.
            </div>
          ) : (
            tasks.map((task) => (
              <div
                key={task.id}
                className="p-4 flex items-center justify-between gap-4 hover:bg-[#F9FAFB] transition text-xs"
              >
                <div className="flex items-start gap-3 flex-1">
                  <button
                    onClick={() => handleToggleComplete(task)}
                    className="mt-0.5 text-[#9CA3AF] hover:text-[#0F766E] transition"
                  >
                    <CheckCircle2
                      className={`w-4 h-4 ${
                        task.status === 'completed' ? 'text-[#059669] fill-[#D1FAE5]' : 'text-[#D1D5DB]'
                      }`}
                    />
                  </button>
                  <div>
                    <h3 className={`font-semibold text-sm ${
                      task.status === 'completed' ? 'line-through text-[#9CA3AF]' : 'text-[#111827]'
                    }`}>
                      {task.title}
                    </h3>
                    {task.description && (
                      <p className="text-[#6B7280] mt-0.5">{task.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1 text-[11px] text-[#9CA3AF]">
                      {task.due_at && (
                        <span className={`flex items-center gap-1 ${task.is_overdue ? 'text-[#DC2626] font-semibold' : ''}`}>
                          <Clock className="w-3 h-3" />
                          Due: {new Date(task.due_at).toLocaleDateString()}
                        </span>
                      )}
                      <span className={`px-1.5 py-0.2 rounded uppercase font-semibold text-[9px] ${
                        task.priority === 'urgent'
                          ? 'bg-[#FEE2E2] text-[#B91C1C]'
                          : task.priority === 'high'
                          ? 'bg-[#FEF3C7] text-[#B45309]'
                          : 'bg-[#F3F4F6] text-[#4B5563]'
                      }`}>
                        {task.priority}
                      </span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => handleDeleteTask(task.id)}
                  className="p-1.5 text-[#9CA3AF] hover:text-[#DC2626] transition"
                  title="Delete task"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
