'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, Phone, MessageSquare, Calendar, Tag as TagIcon, StickyNote, 
  CheckCircle2, Clock, Plus, Trash2, ShieldCheck, Sparkles 
} from 'lucide-react';
import { api } from '@/lib/api-client';
import { LeadDetail, LeadNote, LeadTag, Task, Conversation } from '@/types';
import ScoreBadge from '@/components/shared/ScoreBadge';

interface LeadDrawerProps {
  leadId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onLeadUpdated: () => void;
}

export default function LeadDrawer({ leadId, isOpen, onClose, onLeadUpdated }: LeadDrawerProps) {
  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [notes, setNotes] = useState<LeadNote[]>([]);
  const [allTags, setAllTags] = useState<LeadTag[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'notes' | 'tasks' | 'chat'>('overview');

  // Form states
  const [newNote, setNewNote] = useState('');
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskDate, setNewTaskDate] = useState('');
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState('#0D9488');
  const [showAddTag, setShowAddTag] = useState(false);

  const STAGES = [
    { name: 'New', color: 'bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]' },
    { name: 'Contacted', color: 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]' },
    { name: 'Viewing Scheduled', color: 'bg-[#FEF3C7] text-[#B45309] border-[#FDE68A]' },
    { name: 'Negotiating', color: 'bg-[#FFEDD5] text-[#C2410C] border-[#FED7AA]' },
    { name: 'Closed Won', color: 'bg-[#DCFCE7] text-[#15803D] border-[#BBF7D0]' },
    { name: 'Closed Lost', color: 'bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA]' },
  ];

  const fetchDetails = async () => {
    if (!leadId) return;
    setLoading(true);
    try {
      const fullDetail = await api.getLeadById(leadId);
      setLead(fullDetail);
      setConversations(fullDetail.conversations || []);
      setNotes(fullDetail.notes || []);
      setTasks(fullDetail.tasks || []);

      const tagsList = await api.getTags();
      setAllTags(tagsList);
    } catch (e) {
      console.error('Error fetching lead details in drawer:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && leadId) {
      fetchDetails();
    }
  }, [leadId, isOpen]);

  if (!isOpen || !leadId) return null;

  const handleStageChange = async (newStageName: string) => {
    if (!lead) return;
    try {
      await api.updateLeadStage(lead.id, newStageName);
      setLead({ ...lead, stage_name: newStageName });
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to update stage:', e);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNote.trim() || !lead) return;
    try {
      const created = await api.createLeadNote(lead.id, newNote);
      setNotes([created, ...notes]);
      setNewNote('');
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to create note:', e);
    }
  };

  const handleDeleteNote = async (noteId: string) => {
    try {
      await api.deleteLeadNote(noteId);
      setNotes(notes.filter(n => n.id !== noteId));
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to delete note:', e);
    }
  };

  const handleAddTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || !lead) return;
    try {
      const dueIso = newTaskDate ? new Date(newTaskDate).toISOString() : new Date(Date.now() + 86400000).toISOString();
      const created = await api.createTask({
        lead_id: lead.id,
        title: newTaskTitle,
        due_at: dueIso
      });
      setTasks([...tasks, created]);
      setNewTaskTitle('');
      setNewTaskDate('');
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to create task:', e);
    }
  };

  const handleToggleTaskStatus = async (task: Task) => {
    const nextStatus = task.status === 'completed' ? 'pending' : 'completed';
    try {
      const updated = await api.updateTaskStatus(task.id, nextStatus);
      setTasks(tasks.map(t => t.id === task.id ? updated : t));
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to update task status:', e);
    }
  };

  const handleAssignTag = async (tagId: string) => {
    if (!lead) return;
    try {
      await api.assignTagToLead(lead.id, tagId);
      const tagObj = allTags.find(t => t.id === tagId);
      if (tagObj && !lead.tags?.some(t => t.id === tagId)) {
        setLead({ ...lead, tags: [...(lead.tags || []), tagObj] });
      }
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to assign tag:', e);
    }
  };

  const handleRemoveTag = async (tagId: string) => {
    if (!lead) return;
    try {
      await api.removeTagFromLead(lead.id, tagId);
      setLead({ ...lead, tags: lead.tags?.filter(t => t.id !== tagId) });
      onLeadUpdated();
    } catch (e) {
      console.error('Failed to remove tag:', e);
    }
  };

  const handleCreateNewTag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTagName.trim()) return;
    try {
      const created = await api.createTag(newTagName, newTagColor);
      setAllTags([...allTags, created]);
      if (lead) {
        await handleAssignTag(created.id);
      }
      setNewTagName('');
      setShowAddTag(false);
    } catch (e) {
      console.error('Failed to create new tag:', e);
    }
  };

  const formatCurrency = (amount?: number) => {
    if (!amount) return 'N/A';
    if (amount >= 10000000) return `₹${(amount / 10000000).toFixed(2)} Cr`;
    if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)} Lakhs`;
    return `₹${amount.toLocaleString('en-IN')}`;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-[#0F172A]/40 backdrop-blur-sm transition-opacity animate-in fade-in duration-200">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-2xl bg-white border-l border-[#E2E8F0] shadow-2xl flex flex-col">
          
          {/* Drawer Header */}
          <div className="p-6 border-b border-[#E2E8F0] bg-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-[#CCFBF1] border border-[#99F6E4] flex items-center justify-center text-[#0D9488] font-extrabold text-lg">
                {(lead?.name || 'L')[0].toUpperCase()}
              </div>
              <div>
                <h2 className="text-xl font-bold text-[#0F172A] flex items-center gap-2">
                  {lead?.name || 'Unnamed Lead'}
                  {lead && <ScoreBadge score={lead.score} confidence={lead.score_confidence} />}
                </h2>
                <p className="text-xs text-[#64748B] font-mono mt-0.5">{lead?.phone}</p>
              </div>
            </div>

            <button
              onClick={onClose}
              className="p-2 text-[#94A3B8] hover:text-[#0F172A] rounded-lg hover:bg-[#F1F5F9] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Action Buttons */}
          <div className="px-6 py-3.5 bg-[#FAFAF9] border-b border-[#E2E8F0] flex items-center gap-3">
            <a
              href={`tel:${lead?.phone}`}
              className="flex-1 py-2.5 px-4 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-sm"
            >
              <Phone className="w-4 h-4 fill-white" />
              <span>Call Now</span>
            </a>
            <a
              href={`https://wa.me/${lead?.phone?.replace(/\+/g, '')}`}
              target="_blank"
              rel="noreferrer"
              className="flex-1 py-2.5 px-4 bg-white hover:bg-[#F8FAFC] text-[#0D9488] border border-[#0D9488] rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-all"
            >
              <MessageSquare className="w-4 h-4" />
              <span>WhatsApp Chat</span>
            </a>
          </div>

          {/* Pipeline Stage Switcher Bar */}
          <div className="p-4 bg-[#F5F5F4] border-b border-[#E2E8F0] space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-[#64748B]">
              <span>Pipeline Stage:</span>
              <span className="text-[#0F172A] font-bold">{lead?.stage_name || 'New'}</span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
              {STAGES.map((stg) => {
                const isActive = lead?.stage_name === stg.name;
                return (
                  <button
                    key={stg.name}
                    onClick={() => handleStageChange(stg.name)}
                    className={`px-2 py-1.5 rounded-lg text-[11px] font-bold border transition-all truncate text-center ${
                      isActive ? 'bg-[#0D9488] text-white border-[#0D9488] shadow-sm' : stg.color
                    }`}
                  >
                    {stg.name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Drawer Navigation Tabs */}
          <div className="flex border-b border-[#E2E8F0] px-6 bg-white">
            <button
              onClick={() => setActiveTab('overview')}
              className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'overview' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Overview & AI</span>
            </button>

            <button
              onClick={() => setActiveTab('notes')}
              className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'notes' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <StickyNote className="w-3.5 h-3.5" />
              <span>Notes ({notes.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('tasks')}
              className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'tasks' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span>Tasks ({tasks.filter(t => t.status === 'pending').length})</span>
            </button>

            <button
              onClick={() => setActiveTab('chat')}
              className={`py-3 px-4 text-xs font-bold border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === 'chat' ? 'border-[#0D9488] text-[#0D9488]' : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Chat Log ({conversations.length})</span>
            </button>
          </div>

          {/* Drawer Body Scroll Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#FAFAF9]">

            {/* TAB 1: OVERVIEW & AI */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                
                {/* Tags Section */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-extrabold uppercase tracking-wider text-[#64748B] flex items-center gap-1.5">
                      <TagIcon className="w-3.5 h-3.5 text-[#0D9488]" />
                      Lead Tags
                    </span>
                    <button
                      onClick={() => setShowAddTag(!showAddTag)}
                      className="text-xs text-[#0D9488] font-bold hover:underline flex items-center gap-1"
                    >
                      <Plus className="w-3 h-3" /> Manage Tags
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {lead?.tags && lead.tags.length > 0 ? (
                      lead.tags.map((t) => (
                        <span
                          key={t.id}
                          style={{ backgroundColor: `${t.color}15`, borderColor: `${t.color}30`, color: t.color }}
                          className="px-2.5 py-1 rounded-lg text-xs font-bold border flex items-center gap-1.5 shadow-sm"
                        >
                          {t.name}
                          <button onClick={() => handleRemoveTag(t.id)} className="hover:opacity-75">
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))
                    ) : (
                      <p className="text-xs text-[#94A3B8] italic">No tags attached.</p>
                    )}
                  </div>

                  {/* Add Tag Sub-Panel */}
                  {showAddTag && (
                    <div className="mt-3 p-3 bg-white border border-[#E2E8F0] rounded-xl space-y-3 shadow-sm">
                      <p className="text-xs font-bold text-[#0F172A]">Attach Existing Tag:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {allTags.map((t) => (
                          <button
                            key={t.id}
                            onClick={() => handleAssignTag(t.id)}
                            style={{ backgroundColor: `${t.color}15`, color: t.color }}
                            className="px-2 py-1 rounded text-xs font-bold hover:brightness-110 transition-all border border-[#E2E8F0]"
                          >
                            + {t.name}
                          </button>
                        ))}
                      </div>

                      <form onSubmit={handleCreateNewTag} className="pt-2 border-t border-[#E2E8F0] flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="New tag name..."
                          value={newTagName}
                          onChange={(e) => setNewTagName(e.target.value)}
                          className="flex-1 bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-1.5 rounded-lg text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488]"
                        />
                        <input
                          type="color"
                          value={newTagColor}
                          onChange={(e) => setNewTagColor(e.target.value)}
                          className="w-8 h-8 rounded bg-transparent cursor-pointer"
                        />
                        <button
                          type="submit"
                          className="px-3 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] text-white rounded-lg text-xs font-bold"
                        >
                          Add
                        </button>
                      </form>
                    </div>
                  )}
                </div>

                {/* AI Extracted Attributes Grid */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Budget Range</span>
                    <p className="text-sm font-extrabold text-[#0D9488]">
                      {formatCurrency(lead?.budget_min)} - {formatCurrency(lead?.budget_max)}
                    </p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Property Type</span>
                    <p className="text-sm font-bold text-[#0F172A] capitalize">{lead?.property_type || 'Unspecified'}</p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Preferred Area</span>
                    <p className="text-sm font-bold text-[#0F172A] truncate">
                      {(lead?.preferred_locations || []).join(', ') || 'Bengaluru'}
                    </p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Timeline</span>
                    <p className="text-sm font-bold text-[#0F172A] capitalize">{lead?.timeline?.replace('_', ' ') || 'Immediate'}</p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Loan Status</span>
                    <p className="text-sm font-bold text-[#D97706] capitalize">{lead?.loan_status?.replace('_', ' ') || 'Not Started'}</p>
                  </div>

                  <div className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1 shadow-sm">
                    <span className="text-[11px] font-bold text-[#64748B] uppercase tracking-wider">Lead Source</span>
                    <p className="text-sm font-bold text-[#0369A1] uppercase tracking-wider">{lead?.source?.replace('_', ' ') || 'WhatsApp'}</p>
                  </div>
                </div>

                {/* AI Reasoning Box */}
                {lead?.latest_score && (
                  <div className="p-4 bg-[#CCFBF1]/40 border border-[#99F6E4] rounded-xl space-y-2 shadow-sm">
                    <h4 className="text-xs font-extrabold text-[#0F766E] flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4" />
                      AI Scoring Insights ({Math.round((lead.score_confidence || 0) * 100)}% Confidence)
                    </h4>
                    <p className="text-xs text-[#0F172A] leading-relaxed font-sans">
                      {lead.latest_score.reasoning}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: NOTES */}
            {activeTab === 'notes' && (
              <div className="space-y-4">
                <form onSubmit={handleAddNote} className="space-y-2">
                  <textarea
                    rows={3}
                    placeholder="Write a note (e.g. Needs south-facing 2BHK, flexible budget)..."
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    className="w-full bg-white border border-[#E2E8F0] rounded-xl p-3 text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488]"
                  />
                  <button
                    type="submit"
                    disabled={!newNote.trim()}
                    className="w-full py-2.5 bg-[#0D9488] hover:bg-[#0F766E] disabled:opacity-50 text-white rounded-xl font-bold text-xs transition-all shadow-sm"
                  >
                    + Save Free-text Note
                  </button>
                </form>

                <div className="space-y-3 pt-2">
                  {notes.length > 0 ? (
                    notes.map((note) => (
                      <div key={note.id} className="p-3.5 bg-white border border-[#E2E8F0] rounded-xl space-y-1.5 relative group shadow-sm">
                        <div className="flex items-center justify-between text-[11px] text-[#64748B]">
                          <span className="font-semibold text-[#0D9488]">Broker Note</span>
                          <span>{new Date(note.created_at).toLocaleString()}</span>
                        </div>
                        <p className="text-xs text-[#0F172A] whitespace-pre-wrap">{note.content}</p>
                        <button
                          onClick={() => handleDeleteNote(note.id)}
                          className="absolute bottom-2.5 right-2.5 opacity-0 group-hover:opacity-100 p-1 text-[#94A3B8] hover:text-[#DC2626] transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-[#94A3B8] text-xs">
                      No notes written yet. Add notes above to remember lead details.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: TASKS & REMINDERS */}
            {activeTab === 'tasks' && (
              <div className="space-y-4">
                <form onSubmit={handleAddTask} className="p-4 bg-white border border-[#E2E8F0] rounded-xl space-y-3 shadow-sm">
                  <span className="text-xs font-bold text-[#0F172A]">Set Task Reminder</span>
                  <input
                    type="text"
                    placeholder="e.g. Call Rajesh tomorrow 11 AM about Koramangala site visit"
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    className="w-full bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-2 rounded-lg text-xs text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#0D9488]"
                  />
                  <div className="flex items-center gap-2">
                    <input
                      type="datetime-local"
                      value={newTaskDate}
                      onChange={(e) => setNewTaskDate(e.target.value)}
                      className="flex-1 bg-[#FAFAF9] border border-[#E2E8F0] px-3 py-1.5 rounded-lg text-xs text-[#0F172A] focus:outline-none focus:border-[#0D9488]"
                    />
                    <button
                      type="submit"
                      disabled={!newTaskTitle.trim()}
                      className="px-4 py-1.5 bg-[#0D9488] hover:bg-[#0F766E] disabled:opacity-50 text-white font-bold text-xs rounded-lg transition-all"
                    >
                      Set Reminder
                    </button>
                  </div>
                </form>

                <div className="space-y-2 pt-2">
                  {tasks.length > 0 ? (
                    tasks.map((task) => (
                      <div
                        key={task.id}
                        className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 transition-all ${
                          task.status === 'completed' 
                            ? 'bg-[#F8FAFC] border-[#E2E8F0] text-[#94A3B8] line-through' 
                            : 'bg-white border-[#E2E8F0] text-[#0F172A] shadow-sm'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleToggleTaskStatus(task)}
                            className={`w-5 h-5 rounded-full border flex items-center justify-center transition-colors ${
                              task.status === 'completed'
                                ? 'bg-[#0D9488] border-[#0D9488] text-white'
                                : 'border-[#CBD5E1] hover:border-[#0D9488]'
                            }`}
                          >
                            {task.status === 'completed' && <CheckCircle2 className="w-3.5 h-3.5" />}
                          </button>
                          <div>
                            <p className="text-xs font-semibold">{task.title}</p>
                            <p className="text-[10px] text-[#64748B] flex items-center gap-1 mt-0.5">
                              <Clock className="w-3 h-3 text-[#D97706]" />
                              <span>Due: {new Date(task.due_at).toLocaleString()}</span>
                            </p>
                          </div>
                        </div>

                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[#CCFBF1] text-[#0F766E] border border-[#99F6E4]">
                          WhatsApp Active
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-[#94A3B8] text-xs">
                      No task reminders set for this lead.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 4: CHAT LOG */}
            {activeTab === 'chat' && (
              <div className="space-y-3">
                {conversations.length > 0 ? (
                  conversations.map((msg) => (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${msg.sender_type === 'lead' ? 'items-start' : 'items-end'}`}
                    >
                      <div
                        className={`max-w-[80%] p-3 rounded-2xl text-xs space-y-1 shadow-sm ${
                          msg.sender_type === 'lead'
                            ? 'bg-white text-[#0F172A] rounded-tl-none border border-[#E2E8F0]'
                            : 'bg-[#DCF8C6] text-[#0F172A] border border-[#BBF7D0] rounded-tr-none'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-4 text-[10px] opacity-75">
                          <span className="font-bold capitalize">{msg.sender_type}</span>
                          <span suppressHydrationWarning>{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <p className="whitespace-pre-wrap">{msg.message}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-[#94A3B8] text-xs">
                    No conversation logs recorded yet.
                  </div>
                )}
              </div>
            )}

          </div>

        </div>
      </div>
    </div>
  );
}
