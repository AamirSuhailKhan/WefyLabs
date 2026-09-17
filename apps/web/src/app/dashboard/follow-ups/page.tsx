'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Clock, Calendar, AlertTriangle, CheckCircle2, ShieldAlert, Sparkles,
  Plus, Play, Pause, Square, RefreshCw, Filter, ArrowRight, User, Phone,
  Check, SlidersHorizontal, MessageSquare, AlertCircle, ChevronRight, X
} from 'lucide-react';
import DashboardNav from '@/components/shared/DashboardNav';
import { api } from '@/lib/api-client';

export type FollowUpTab = 'today' | 'upcoming' | 'rules' | 'analytics';

export default function FollowUpsPage() {
  const [activeTab, setActiveTab] = useState<FollowUpTab>('today');
  const [summary, setSummary] = useState<any>(null);
  const [briefing, setBriefing] = useState<any>(null);
  const [rules, setRules] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Snooze Modal State
  const [snoozeTaskId, setSnoozeTaskId] = useState<string | null>(null);
  const [snoozeTime, setSnoozeTime] = useState<string>('tomorrow');
  const [isSnoozing, setIsSnoozing] = useState(false);

  // Rule Creation Modal
  const [isCreateRuleOpen, setIsCreateRuleOpen] = useState(false);
  const [newRule, setNewRule] = useState({
    name: '',
    trigger: 'lead_no_response',
    action: 'create_task',
    delay_minutes: 1440,
    priority: 'normal',
    task_title: 'Follow up with {{lead_name}}'
  });

  const fetchData = async () => {
    try {
      setRefreshing(true);
      const [sumRes, briefRes, rulesRes, perfRes] = await Promise.all([
        api.followups.getDashboardSummary().catch(() => null),
        api.followups.getDailyBriefing().catch(() => null),
        api.followups.getRules().catch(() => []),
        api.followups.getPerformance().catch(() => null),
      ]);
      setSummary(sumRes);
      setBriefing(briefRes);
      setRules(rulesRes || []);
      setAnalytics(perfRes);
    } catch (e) {
      console.warn('Failed to load follow-up dashboard data', e);
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCompleteTask = async (taskId: string) => {
    try {
      await api.updateTask(taskId, { status: 'completed' });
      fetchData();
    } catch (err: any) {
      alert(err.message || 'Failed to complete task');
    }
  };

  const handleSnoozeConfirm = async () => {
    if (!snoozeTaskId) return;
    setIsSnoozing(true);
    try {
      const now = new Date();
      let targetDate = new Date();
      if (snoozeTime === 'later_today') {
        targetDate = new Date(now.getTime() + 3 * 3600 * 1000);
      } else if (snoozeTime === 'tomorrow') {
        targetDate = new Date(now.getTime() + 24 * 3600 * 1000);
        targetDate.setHours(9, 30, 0, 0);
      } else if (snoozeTime === 'next_week') {
        targetDate = new Date(now.getTime() + 7 * 24 * 3600 * 1000);
        targetDate.setHours(9, 30, 0, 0);
      }
      await api.followups.snoozeTask(snoozeTaskId, targetDate.toISOString());
      setSnoozeTaskId(null);
      fetchData();
    } catch (err: any) {
      alert(err.message || 'Failed to snooze task');
    } finally {
      setIsSnoozing(false);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.followups.createRule({
        name: newRule.name,
        trigger: newRule.trigger,
        action: newRule.action,
        delay_minutes: Number(newRule.delay_minutes),
        priority: newRule.priority,
        action_config: { task_title: newRule.task_title }
      });
      setIsCreateRuleOpen(false);
      setNewRule({
        name: '',
        trigger: 'lead_no_response',
        action: 'create_task',
        delay_minutes: 1440,
        priority: 'normal',
        task_title: 'Follow up with {{lead_name}}'
      });
      fetchData();
    } catch (err: any) {
      alert(err.message || 'Failed to create rule');
    }
  };

  const handleToggleRule = async (rule: any) => {
    try {
      await api.followups.updateRule(rule.id, { enabled: !rule.enabled });
      fetchData();
    } catch (err: any) {
      alert(err.message || 'Failed to update rule');
    }
  };

  const counts = summary?.counts || {
    due_today: 0,
    overdue: 0,
    upcoming: 0,
    sla_breaches: 0,
    awaiting_first_contact: 0
  };

  return (
    <div className="min-h-screen bg-[#FDFBF7] text-[#1A1A1A]">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header Title & Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E8E4DC] pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-amber-100 text-amber-900 uppercase">
                Autonomous CRM Engine
              </span>
              <span className="text-xs text-gray-500 font-mono">15m SLA • Timezone Aware</span>
            </div>
            <h1 className="text-2xl font-bold font-mono tracking-tight text-[#1A1A1A]">
              Follow-Up & SLA Automation Hub
            </h1>
            <p className="text-xs text-[#6B6B6B]">
              Continuous lifecycle lead monitoring, deterministic response SLAs, and intelligent re-engagement.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              disabled={refreshing}
              className="px-3.5 py-2 rounded-xl border border-[#D4D0C8] bg-white text-xs font-mono font-bold hover:bg-gray-50 transition-colors flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              <span>Sync Status</span>
            </button>
            <button
              onClick={() => setIsCreateRuleOpen(true)}
              className="btn-lime px-4 py-2 text-xs font-mono font-bold flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>New Follow-Up Rule</span>
            </button>
          </div>
        </div>

        {/* AI Daily Briefing Banner */}
        {briefing && (
          <div className="bg-white border border-[#E8E4DC] rounded-2xl p-5 shadow-xs relative overflow-hidden">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-mono font-bold text-emerald-800">
                  <Sparkles className="w-4 h-4 text-emerald-600 fill-emerald-200" />
                  <span>Verified Daily Briefing</span>
                </div>
                <p className="text-xs font-mono text-[#2B2B2B] whitespace-pre-line leading-relaxed">
                  {briefing.summary_text}
                </p>
              </div>

              {briefing.top_priority_lead && (
                <div className="hidden md:block bg-amber-50 border border-amber-200 p-3.5 rounded-xl text-right max-w-xs">
                  <span className="text-[10px] font-mono font-bold uppercase text-amber-800">Next Best Action</span>
                  <p className="text-xs font-bold text-[#1A1A1A] mt-0.5 truncate">{briefing.top_priority_lead.name}</p>
                  <p className="text-[11px] text-gray-600 truncate">{briefing.top_priority_lead.reason}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Metric Cards Row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white border border-[#E8E4DC] rounded-xl p-4">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="text-[11px] font-mono font-bold uppercase">Due Today</span>
              <Clock className="w-4 h-4 text-amber-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-[#1A1A1A]">{counts.due_today}</div>
            <span className="text-[10px] text-gray-500">Scheduled for today</span>
          </div>

          <div className="bg-white border border-[#E8E4DC] rounded-xl p-4">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="text-[11px] font-mono font-bold uppercase">Overdue</span>
              <AlertCircle className="w-4 h-4 text-rose-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-rose-600">{counts.overdue}</div>
            <span className="text-[10px] text-rose-500">Requires agent action</span>
          </div>

          <div className="bg-white border border-[#E8E4DC] rounded-xl p-4">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="text-[11px] font-mono font-bold uppercase">SLA Breaches</span>
              <ShieldAlert className="w-4 h-4 text-purple-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-purple-700">{counts.sla_breaches}</div>
            <span className="text-[10px] text-purple-600">First-contact breaches</span>
          </div>

          <div className="bg-white border border-[#E8E4DC] rounded-xl p-4">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="text-[11px] font-mono font-bold uppercase">Upcoming (7D)</span>
              <Calendar className="w-4 h-4 text-blue-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-[#1A1A1A]">{counts.upcoming}</div>
            <span className="text-[10px] text-gray-500">Next 7 days</span>
          </div>

          <div className="bg-white border border-[#E8E4DC] rounded-xl p-4">
            <div className="flex items-center justify-between text-gray-500 mb-1">
              <span className="text-[11px] font-mono font-bold uppercase">Awaiting Contact</span>
              <User className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-2xl font-bold font-mono text-emerald-700">{counts.awaiting_first_contact}</div>
            <span className="text-[10px] text-emerald-600">Fresh incoming leads</span>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#E8E4DC] gap-6">
          <button
            onClick={() => setActiveTab('today')}
            className={`pb-3 text-xs font-mono font-bold uppercase transition-colors relative ${
              activeTab === 'today' ? 'text-[#1A1A1A]' : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            Today & Urgent ({counts.due_today + counts.overdue})
            {activeTab === 'today' && (
              <motion.div layoutId="fu-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#1A1A1A]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('upcoming')}
            className={`pb-3 text-xs font-mono font-bold uppercase transition-colors relative ${
              activeTab === 'upcoming' ? 'text-[#1A1A1A]' : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            Upcoming Horizon ({counts.upcoming})
            {activeTab === 'upcoming' && (
              <motion.div layoutId="fu-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#1A1A1A]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('rules')}
            className={`pb-3 text-xs font-mono font-bold uppercase transition-colors relative ${
              activeTab === 'rules' ? 'text-[#1A1A1A]' : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            Automation Rules ({rules.length})
            {activeTab === 'rules' && (
              <motion.div layoutId="fu-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#1A1A1A]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('analytics')}
            className={`pb-3 text-xs font-mono font-bold uppercase transition-colors relative ${
              activeTab === 'analytics' ? 'text-[#1A1A1A]' : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            SLA & Efficiency Metrics
            {activeTab === 'analytics' && (
              <motion.div layoutId="fu-tab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#1A1A1A]" />
            )}
          </button>
        </div>

        {/* Tab Content: TODAY */}
        {activeTab === 'today' && (
          <div className="space-y-6">
            {/* Overdue Section */}
            {summary?.tasks_overdue?.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                  <h3 className="text-xs font-mono font-bold uppercase text-rose-700">
                    Overdue Actions ({summary.tasks_overdue.length})
                  </h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {summary.tasks_overdue.map((t: any) => (
                    <div key={t.id} className="bg-rose-50/50 border border-rose-200 rounded-xl p-4 flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-rose-200 text-rose-900">
                            {t.priority}
                          </span>
                          <span className="text-[11px] font-mono text-rose-700">
                            Due: {t.due_at ? new Date(t.due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'ASAP'}
                          </span>
                        </div>
                        <h4 className="text-xs font-bold text-[#1A1A1A]">{t.title}</h4>
                        <p className="text-[11px] text-gray-600 line-clamp-2">{t.description}</p>
                      </div>

                      <div className="flex items-center gap-1.5 self-start">
                        <button
                          onClick={() => setSnoozeTaskId(t.id)}
                          className="px-2.5 py-1 text-[11px] font-mono bg-white border border-[#D4D0C8] rounded-lg hover:bg-gray-50"
                        >
                          Snooze
                        </button>
                        <button
                          onClick={() => handleCompleteTask(t.id)}
                          className="px-2.5 py-1 text-[11px] font-mono btn-lime rounded-lg flex items-center gap-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Done</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Due Today Section */}
            <div className="space-y-3">
              <h3 className="text-xs font-mono font-bold uppercase text-gray-600">
                Tasks Due Today ({summary?.tasks_due_today?.length || 0})
              </h3>
              {summary?.tasks_due_today?.length === 0 ? (
                <div className="bg-white border border-[#E8E4DC] rounded-xl p-8 text-center text-gray-400 font-mono text-xs">
                  No tasks due today. You are fully caught up!
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {summary?.tasks_due_today?.map((t: any) => (
                    <div key={t.id} className="bg-white border border-[#E8E4DC] rounded-xl p-4 flex items-start justify-between gap-3 shadow-2xs">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-amber-100 text-amber-900">
                            {t.priority}
                          </span>
                          <span className="text-[11px] font-mono text-gray-500">
                            Due: {t.due_at ? new Date(t.due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Today'}
                          </span>
                        </div>
                        <h4 className="text-xs font-bold text-[#1A1A1A]">{t.title}</h4>
                        <p className="text-[11px] text-gray-600 line-clamp-2">{t.description}</p>
                      </div>

                      <div className="flex items-center gap-1.5 self-start">
                        <button
                          onClick={() => setSnoozeTaskId(t.id)}
                          className="px-2.5 py-1 text-[11px] font-mono bg-white border border-[#D4D0C8] rounded-lg hover:bg-gray-50"
                        >
                          Snooze
                        </button>
                        <button
                          onClick={() => handleCompleteTask(t.id)}
                          className="px-2.5 py-1 text-[11px] font-mono btn-lime rounded-lg flex items-center gap-1"
                        >
                          <Check className="w-3.5 h-3.5" />
                          <span>Done</span>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Active SLA Breaches Table */}
            {summary?.sla_breaches?.length > 0 && (
              <div className="space-y-3 pt-4 border-t border-[#E8E4DC]">
                <h3 className="text-xs font-mono font-bold uppercase text-purple-800">
                  Recent Response SLA Breaches ({summary.sla_breaches.length})
                </h3>
                <div className="bg-white border border-[#E8E4DC] rounded-xl overflow-hidden shadow-2xs">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[#FAF7F2] border-b border-[#E8E4DC] text-gray-500">
                      <tr>
                        <th className="p-3">SLA Type</th>
                        <th className="p-3">Lead Identifier</th>
                        <th className="p-3">Overdue Time</th>
                        <th className="p-3">Breached At</th>
                        <th className="p-3 text-right">Escalation Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E8E4DC]">
                      {summary.sla_breaches.map((b: any) => (
                        <tr key={b.id} className="hover:bg-gray-50/50">
                          <td className="p-3 font-bold text-purple-900">{b.sla_type}</td>
                          <td className="p-3 text-gray-600 font-mono">{b.lead_id.slice(0, 8)}...</td>
                          <td className="p-3 text-rose-600 font-bold">+{b.overdue_minutes} mins</td>
                          <td className="p-3 text-gray-500">{b.breached_at ? new Date(b.breached_at).toLocaleTimeString() : 'N/A'}</td>
                          <td className="p-3 text-right">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 uppercase">
                              Escalated
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab Content: UPCOMING */}
        {activeTab === 'upcoming' && (
          <div className="space-y-3">
            <h3 className="text-xs font-mono font-bold uppercase text-gray-600">
              Upcoming Scheduled Follow-Ups ({summary?.tasks_upcoming?.length || 0})
            </h3>
            {summary?.tasks_upcoming?.length === 0 ? (
              <div className="bg-white border border-[#E8E4DC] rounded-xl p-8 text-center text-gray-400 font-mono text-xs">
                No upcoming follow-ups scheduled for the next 7 days.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {summary.tasks_upcoming.map((t: any) => (
                  <div key={t.id} className="bg-white border border-[#E8E4DC] rounded-xl p-4 flex items-start justify-between gap-3 shadow-2xs">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-blue-100 text-blue-800">
                          {new Date(t.due_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                        </span>
                        <span className="text-[11px] font-mono text-gray-500">
                          {new Date(t.due_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-[#1A1A1A]">{t.title}</h4>
                      <p className="text-[11px] text-gray-600 line-clamp-2">{t.description}</p>
                    </div>

                    <button
                      onClick={() => setSnoozeTaskId(t.id)}
                      className="px-2.5 py-1 text-[11px] font-mono bg-white border border-[#D4D0C8] rounded-lg hover:bg-gray-50"
                    >
                      Reschedule
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab Content: RULES */}
        {activeTab === 'rules' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-mono font-bold uppercase text-gray-600">
                  Active Follow-Up Automation Rules ({rules.length})
                </h3>
                <p className="text-[11px] text-gray-500">
                  Deterministic conditions triggered on lead events with working-hours alignment.
                </p>
              </div>

              <button
                onClick={() => setIsCreateRuleOpen(true)}
                className="btn-lime px-3 py-1.5 text-xs font-mono font-bold flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Rule</span>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {rules.map((rule) => (
                <div key={rule.id} className="bg-white border border-[#E8E4DC] rounded-xl p-5 shadow-2xs space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">{rule.name}</h4>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                          rule.enabled ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {rule.enabled ? 'Active' : 'Paused'}
                        </span>
                      </div>
                      <span className="text-[11px] text-gray-500 font-mono">Trigger: {rule.trigger}</span>
                    </div>

                    <button
                      onClick={() => handleToggleRule(rule)}
                      className={`px-3 py-1 rounded-lg text-xs font-mono font-bold border transition-colors ${
                        rule.enabled
                          ? 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100'
                          : 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                      }`}
                    >
                      {rule.enabled ? 'Pause' : 'Activate'}
                    </button>
                  </div>

                  <div className="bg-[#FAF7F2] p-3 rounded-lg text-[11px] font-mono text-gray-600 space-y-1">
                    <div><span className="text-gray-400">Action:</span> {rule.action}</div>
                    <div><span className="text-gray-400">Delay:</span> {rule.delay_minutes} minutes ({Math.round(rule.delay_minutes / 60)}h)</div>
                    <div><span className="text-gray-400">Priority:</span> {rule.priority}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab Content: ANALYTICS */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-white border border-[#E8E4DC] p-5 rounded-xl text-center">
                <span className="text-xs font-mono text-gray-500 uppercase">SLA Compliance Rate</span>
                <div className="text-3xl font-bold font-mono text-emerald-600 mt-2">
                  {analytics?.sla_compliance_rate_pct ?? 100}%
                </div>
                <span className="text-[10px] text-gray-400">Met vs Total Response Timers</span>
              </div>

              <div className="bg-white border border-[#E8E4DC] p-5 rounded-xl text-center">
                <span className="text-xs font-mono text-gray-500 uppercase">Task Completion Rate</span>
                <div className="text-3xl font-bold font-mono text-blue-600 mt-2">
                  {analytics?.completion_rate_pct ?? 0}%
                </div>
                <span className="text-[10px] text-gray-400">Completed vs Assigned Tasks</span>
              </div>

              <div className="bg-white border border-[#E8E4DC] p-5 rounded-xl text-center">
                <span className="text-xs font-mono text-gray-500 uppercase">Automated Actions Executed</span>
                <div className="text-3xl font-bold font-mono text-purple-600 mt-2">
                  {analytics?.automated_actions_executed ?? 0}
                </div>
                <span className="text-[10px] text-gray-400">Deduplicated engine events</span>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Snooze Modal */}
      <AnimatePresence>
        {snoozeTaskId && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white border border-[#D4D0C8] rounded-2xl max-w-sm w-full p-6 space-y-4 shadow-xl"
            >
              <div className="flex items-center justify-between border-b border-[#E8E4DC] pb-3">
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Snooze Follow-Up Task</h3>
                <button onClick={() => setSnoozeTaskId(null)} className="text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <p className="text-xs text-gray-600">
                Reschedule this task without triggering automated reset conflicts:
              </p>

              <div className="space-y-2">
                {[
                  { id: 'later_today', label: 'Later Today (+3 Hours)' },
                  { id: 'tomorrow', label: 'Tomorrow Morning (09:30 AM)' },
                  { id: 'next_week', label: 'Next Week (Monday 09:30 AM)' }
                ].map((opt) => (
                  <label
                    key={opt.id}
                    className={`flex items-center justify-between p-3 rounded-xl border text-xs font-mono cursor-pointer transition-colors ${
                      snoozeTime === opt.id ? 'border-[#1A1A1A] bg-gray-50 font-bold' : 'border-[#E8E4DC] hover:border-gray-300'
                    }`}
                  >
                    <span>{opt.label}</span>
                    <input
                      type="radio"
                      name="snooze_opt"
                      value={opt.id}
                      checked={snoozeTime === opt.id}
                      onChange={() => setSnoozeTime(opt.id)}
                      className="accent-[#1A1A1A]"
                    />
                  </label>
                ))}
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setSnoozeTaskId(null)}
                  className="px-3.5 py-2 rounded-xl text-xs font-mono text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSnoozeConfirm}
                  disabled={isSnoozing}
                  className="btn-lime px-4 py-2 text-xs font-mono font-bold"
                >
                  {isSnoozing ? 'Snoozing...' : 'Confirm Snooze'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Create Rule Modal */}
      <AnimatePresence>
        {isCreateRuleOpen && (
          <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white border border-[#D4D0C8] rounded-2xl max-w-md w-full p-6 space-y-4 shadow-xl"
            >
              <div className="flex items-center justify-between border-b border-[#E8E4DC] pb-3">
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Create Follow-Up Rule</h3>
                <button onClick={() => setIsCreateRuleOpen(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateRule} className="space-y-3 text-xs font-mono">
                <div>
                  <label className="block text-gray-500 mb-1">Rule Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 24h No Response Follow-Up"
                    value={newRule.name}
                    onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                    className="w-full px-3 py-2 border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-gray-500 mb-1">Trigger Event</label>
                    <select
                      value={newRule.trigger}
                      onChange={(e) => setNewRule({ ...newRule, trigger: e.target.value })}
                      className="w-full px-3 py-2 border border-[#D4D0C8] rounded-xl text-xs focus:outline-none bg-white"
                    >
                      <option value="lead_created">Lead Created</option>
                      <option value="lead_no_response">No Customer Response</option>
                      <option value="first_contact_sla_breach">SLA Breached</option>
                      <option value="lead_stale">Lead Inactivity Stale</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-gray-500 mb-1">Action</label>
                    <select
                      value={newRule.action}
                      onChange={(e) => setNewRule({ ...newRule, action: e.target.value })}
                      className="w-full px-3 py-2 border border-[#D4D0C8] rounded-xl text-xs focus:outline-none bg-white"
                    >
                      <option value="create_task">Create Task</option>
                      <option value="send_notification">Send In-App Alert</option>
                      <option value="escalate">Manager Escalation</option>
                      <option value="create_reengagement_task">AI Re-engagement Task</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-gray-500 mb-1">Delay (Minutes)</label>
                    <input
                      type="number"
                      value={newRule.delay_minutes}
                      onChange={(e) => setNewRule({ ...newRule, delay_minutes: Number(e.target.value) })}
                      className="w-full px-3 py-2 border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-gray-500 mb-1">Priority</label>
                    <select
                      value={newRule.priority}
                      onChange={(e) => setNewRule({ ...newRule, priority: e.target.value })}
                      className="w-full px-3 py-2 border border-[#D4D0C8] rounded-xl text-xs focus:outline-none bg-white"
                    >
                      <option value="low">Low</option>
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                      <option value="urgent">Urgent</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-gray-500 mb-1">Task Title Template</label>
                  <input
                    type="text"
                    value={newRule.task_title}
                    onChange={(e) => setNewRule({ ...newRule, task_title: e.target.value })}
                    className="w-full px-3 py-2 border border-[#D4D0C8] rounded-xl text-xs focus:outline-none"
                  />
                  <span className="text-[10px] text-gray-400">Supports variables: &#123;&#123;lead_name&#125;&#125;, &#123;&#123;phone&#125;&#125;</span>
                </div>

                <div className="flex items-center justify-end gap-2 pt-3">
                  <button
                    type="button"
                    onClick={() => setIsCreateRuleOpen(false)}
                    className="px-3.5 py-2 rounded-xl text-xs font-mono text-gray-600 hover:bg-gray-100"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-lime px-4 py-2 text-xs font-mono font-bold"
                  >
                    Save Rule
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
