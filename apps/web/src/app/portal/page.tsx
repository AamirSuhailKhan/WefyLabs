'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Home, Building2, FileText, CheckCircle2, Clock, CreditCard,
  Calendar, MessageSquare, LifeBuoy, Star, Upload, ShieldCheck,
  AlertCircle, ArrowRight, Sparkles, PhoneCall, Mail, ExternalLink,
  Lock, User, Check, X, ChevronRight, Download, RefreshCw, FileCheck,
  Send, HelpCircle, Key, ChevronDown, CheckCheck, ThumbsUp
} from 'lucide-react';
import { useRegion } from '@/lib/i18n/region-context';
import { formatCurrency } from '@/lib/i18n/currency';

// Canonical Deal Room Stages
const TRANSACTION_STAGES = [
  { id: 'OPPORTUNITY', label: 'Opportunity', num: '01' },
  { id: 'DISCOVERY', label: 'Discovery', num: '02' },
  { id: 'SITE_VISIT', label: 'Site Visit', num: '03' },
  { id: 'OFFER', label: 'Offer', num: '04' },
  { id: 'RESERVATION', label: 'Reservation', num: '05' },
  { id: 'BOOKING', label: 'Booking', num: '06' },
  { id: 'FINANCE', label: 'Escrow & Finance', num: '07' },
  { id: 'CLOSING', label: 'Closing', num: '08' },
  { id: 'POST_SALE', label: 'Handover', num: '09' },
];

interface PortalDoc {
  id: string;
  name: string;
  type: string;
  stage: string;
  isRequired: boolean;
  status: string;
  uploadedAt: string | null;
  fileUrl: string | null;
  reason?: string;
}

export default function CustomerPortalPage() {
  const { region } = useRegion();
  const [activeTab, setActiveTab] = useState<'overview' | 'deal' | 'documents' | 'payments' | 'appointments' | 'messages' | 'support' | 'post-sale' | 'ai'>('overview');

  // Authentication & session state
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [inviteTokenInput, setInviteTokenInput] = useState('');
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Core Customer Data State (defaults initialized for smooth initial load / demo experience)
  const [customerName, setCustomerName] = useState('Vikram Malhotra');
  const [advisor, setAdvisor] = useState({
    name: 'Alexander Wright',
    title: 'Senior Portfolio Director',
    agency: 'WefyLabs Prime Realty Dubai',
    phone: '+971 50 123 4567',
    email: 'alexander.wright@wefylabs.com',
    initials: 'AW'
  });

  const [activeDeal, setActiveDeal] = useState({
    dealId: 'deal-dxb-9021',
    propertyName: 'Marina Gate Luxury Penthouse 42B',
    unitNumber: 'MG1-4202',
    project: 'Select Group • Dubai Marina',
    totalValue: 5250000,
    currency: 'AED',
    currentStage: 'BOOKING',
    stageIndex: 5,
    reservationExpiry: '2026-10-15T18:00:00Z',
    bookingConfirmedDate: '2026-09-20',
    estimatedHandover: 'December 2026',
    bedrooms: 3,
    bathrooms: 4,
    areaSqFt: 3450,
  });

  // Documents state
  const [documents, setDocuments] = useState<PortalDoc[]>([
    {
      id: 'doc-001',
      name: 'Passport & Visa Copy',
      type: 'PASSPORT',
      stage: 'BOOKING',
      isRequired: true,
      status: 'APPROVED',
      uploadedAt: '2026-09-18 14:30 UTC',
      fileUrl: '#'
    },
    {
      id: 'doc-002',
      name: 'Emirates ID (Front & Back)',
      type: 'EMIRATES_ID',
      stage: 'BOOKING',
      isRequired: true,
      status: 'APPROVED',
      uploadedAt: '2026-09-18 14:35 UTC',
      fileUrl: '#'
    },
    {
      id: 'doc-003',
      name: 'Proof of Residential Address',
      type: 'ADDRESS_PROOF',
      stage: 'BOOKING',
      isRequired: true,
      status: 'ACTION_REQUIRED',
      uploadedAt: null,
      fileUrl: null,
      reason: 'Prior document expired. Please provide utility bill dated within 90 days.'
    },
    {
      id: 'doc-004',
      name: 'Signed Sale & Purchase Agreement (SPA)',
      type: 'AGREEMENT',
      stage: 'CLOSING',
      isRequired: true,
      status: 'IN_REVIEW',
      uploadedAt: '2026-09-22 09:15 UTC',
      fileUrl: '#'
    }
  ]);

  // Payment Schedule state
  const [paymentMilestones, setPaymentMilestones] = useState([
    { index: 0, name: 'Booking Deposit (5%)', amount: 262500, dueDate: '2026-09-20', status: 'VERIFIED', ref: 'WT-DXB-9812' },
    { index: 1, name: 'First Installment Upon SPA (15%)', amount: 787500, dueDate: '2026-10-10', status: 'DUE', ref: null },
    { index: 2, name: 'Construction Milestone 40% (20%)', amount: 1050000, dueDate: '2026-11-15', status: 'UPCOMING', ref: null },
    { index: 3, name: 'Structure Complete (20%)', amount: 1050000, dueDate: '2026-12-01', status: 'UPCOMING', ref: null },
    { index: 4, name: 'On Key Handover & Registration (40%)', amount: 2100000, dueDate: '2026-12-28', status: 'UPCOMING', ref: null },
  ]);

  // Payment Proof Modal state
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentMilestoneIndex, setPaymentMilestoneIndex] = useState(1);
  const [paymentAmount, setPaymentAmount] = useState('787500');
  const [paymentRef, setPaymentRef] = useState('');
  const [paymentSuccessMsg, setPaymentSuccessMsg] = useState<string | null>(null);

  // Appointments state
  const [appointments, setAppointments] = useState([
    {
      id: 'apt-001',
      title: 'Show Penthouse Inspection & Snagging Walkthrough',
      type: 'SITE_VISIT',
      startUtc: '2026-09-27T10:00:00Z',
      location: 'Marina Gate Tower 1, Level 42, Dubai Marina',
      meetingUrl: null,
      status: 'SCHEDULED'
    },
    {
      id: 'apt-002',
      title: 'Mortgage Pre-Registration & DLD NOC Consultation',
      type: 'VIRTUAL',
      startUtc: '2026-09-30T14:00:00Z',
      location: 'Google Meet Virtual Notary Session',
      meetingUrl: 'https://meet.google.com/wefy-portal-dxb',
      status: 'CONFIRMED'
    }
  ]);

  // Customer Messages state (Strict CRM Boundary)
  const [messages, setMessages] = useState([
    {
      id: 'msg-1',
      direction: 'INBOUND',
      senderName: 'Alexander Wright (Senior Advisor)',
      content: 'Dear Vikram, welcome to your private WefyLabs Transaction Room. Your 5% booking deposit has been verified by our escrow team. We have scheduled the snagging inspection for September 27th.',
      createdAt: '2026-09-21 10:15'
    },
    {
      id: 'msg-2',
      direction: 'OUTBOUND',
      senderName: 'Vikram Malhotra (You)',
      content: 'Thank you Alexander. I have signed the SPA and uploaded it. Could you check if the utility bill address proof is adequate?',
      createdAt: '2026-09-22 11:30'
    },
    {
      id: 'msg-3',
      direction: 'INBOUND',
      senderName: 'Alexander Wright (Senior Advisor)',
      content: 'We noticed the address proof bill was dated January 2026. Please upload one issued within the past 90 days so compliance can stamp it.',
      createdAt: '2026-09-22 14:00'
    }
  ]);
  const [newMessageText, setNewMessageText] = useState('');

  // Support Request state
  const [supportTickets, setSupportTickets] = useState([
    {
      id: 'sup-101',
      category: 'DOCUMENT_HELP',
      subject: 'Clarification on Address Proof format',
      priority: 'NORMAL',
      status: 'IN_PROGRESS',
      createdAt: '2026-09-22 12:00'
    }
  ]);
  const [newTicketCategory, setNewTicketCategory] = useState('DOCUMENT_HELP');
  const [newTicketSubject, setNewTicketSubject] = useState('');
  const [newTicketDesc, setNewTicketDesc] = useState('');
  const [showSupportModal, setShowSupportModal] = useState(false);

  // CSAT & NPS state
  const [csatRating, setCsatRating] = useState(5);
  const [npsScore, setNpsScore] = useState(10);
  const [feedbackText, setFeedbackText] = useState('');
  const [referralInterest, setReferralInterest] = useState(true);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  // AI Assistant state
  const [aiQuery, setAiQuery] = useState('');
  const [aiResponses, setAiResponses] = useState([
    {
      sender: 'assistant',
      text: 'Hello Mr. Vikram. I am your WefyLabs Transaction Assistant. I can answer questions about your property journey, document checklist, or payment schedule. How may I assist you today?'
    }
  ]);
  const [isAiThinking, setIsAiThinking] = useState(false);

  // Transaction Acknowledgement
  const [termsAcknowledged, setTermsAcknowledged] = useState(false);
  const [ackToast, setAckToast] = useState(false);

  // Document Upload modal
  const [uploadModalDoc, setUploadModalDoc] = useState<any | null>(null);
  const [uploadFileUrl, setUploadFileUrl] = useState('');

  // On mount: check URL parameters for ?token=
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const urlToken = params.get('token');
      if (urlToken) {
        handleExchangeToken(urlToken);
      } else {
        const stored = localStorage.getItem('wefylabs_portal_token');
        if (stored) setAuthToken(stored);
      }
    }
  }, []);

  async function handleExchangeToken(rawToken: string) {
    setIsLoading(true);
    setTokenError(null);
    try {
      const res = await fetch('/api/v1/portal/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invite_token: rawToken })
      });
      if (!res.ok) {
        throw new Error('Invalid or expired portal invite link.');
      }
      const data = await res.json();
      setAuthToken(data.access_token);
      setCustomerName(data.customer_name || 'Valued Customer');
      if (typeof window !== 'undefined') {
        localStorage.setItem('wefylabs_portal_token', data.access_token);
      }
      setShowTokenModal(false);
    } catch (err: any) {
      setTokenError(err.message || 'Token exchange failed');
    } finally {
      setIsLoading(false);
    }
  }

  function handleLogout() {
    setAuthToken(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem('wefylabs_portal_token');
    }
  }

  function handleSendCustomerMessage(e: React.FormEvent) {
    e.preventDefault();
    if (!newMessageText.trim()) return;
    const newMsg = {
      id: `msg-${Date.now()}`,
      direction: 'OUTBOUND',
      senderName: `${customerName} (You)`,
      content: newMessageText.trim(),
      createdAt: 'Just now'
    };
    setMessages(prev => [...prev, newMsg]);
    setNewMessageText('');
  }

  function handleConfirmAppointment(id: string) {
    setAppointments(prev =>
      prev.map(a => a.id === id ? { ...a, status: 'CONFIRMED' } : a)
    );
  }

  function handleUploadDocument(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadModalDoc) return;
    setDocuments(prev =>
      prev.map(d =>
        d.id === uploadModalDoc.id
          ? { ...d, status: 'IN_REVIEW', uploadedAt: 'Just now', fileUrl: uploadFileUrl || 'https://storage.wefylabs.com/uploads/sample.pdf' }
          : d
      )
    );
    setUploadModalDoc(null);
    setUploadFileUrl('');
  }

  function handleSubmitPaymentProof(e: React.FormEvent) {
    e.preventDefault();
    setPaymentMilestones(prev =>
      prev.map(m =>
        m.index === paymentMilestoneIndex
          ? { ...m, status: 'REPORTED', ref: paymentRef || 'WIRE-PENDING-AUDIT' }
          : m
      )
    );
    setPaymentSuccessMsg('Payment proof submitted successfully! Marked as REPORTED pending finance audit.');
    setTimeout(() => {
      setShowPaymentModal(false);
      setPaymentSuccessMsg(null);
      setPaymentRef('');
    }, 2000);
  }

  function handleCreateSupportTicket(e: React.FormEvent) {
    e.preventDefault();
    if (!newTicketSubject.trim()) return;
    const ticket = {
      id: `sup-${Date.now().toString().slice(-4)}`,
      category: newTicketCategory,
      subject: newTicketSubject,
      priority: 'NORMAL',
      status: 'OPEN',
      createdAt: 'Just now'
    };
    setSupportTickets(prev => [ticket, ...prev]);
    setNewTicketSubject('');
    setNewTicketDesc('');
    setShowSupportModal(false);
  }

  function handleSubmitFeedback(e: React.FormEvent) {
    e.preventDefault();
    setFeedbackSubmitted(true);
  }

  function handleAskAi(e: React.FormEvent) {
    e.preventDefault();
    if (!aiQuery.trim()) return;
    const userQ = aiQuery.trim();
    setAiResponses(prev => [...prev, { sender: 'user', text: userQ }]);
    setAiQuery('');
    setIsAiThinking(true);

    setTimeout(() => {
      let reply = "I have checked your transaction records. Your active property is Marina Gate Penthouse 42B. Your next critical requirement is uploading an updated Proof of Address (utility bill dated within 90 days). Your next payment milestone of AED 787,500 is due on October 10th.";
      if (userQ.toLowerCase().includes('document')) {
        reply = "You currently have 1 pending document requirement: Proof of Residential Address. Please upload a utility bill dated within 90 days so compliance can approve it.";
      } else if (userQ.toLowerCase().includes('payment')) {
        reply = "Your 5% booking deposit of AED 262,500 is VERIFIED. Your next installment of AED 787,500 (15%) is DUE by October 10th, 2026. You can submit your bank wire receipt directly in the Payment Schedule tab.";
      } else if (userQ.toLowerCase().includes('visit') || userQ.toLowerCase().includes('appointment')) {
        reply = "You have a Show Penthouse Snagging Walkthrough confirmed for September 27th at 10:00 AM UTC at Marina Gate Tower 1.";
      }
      setAiResponses(prev => [...prev, { sender: 'assistant', text: reply }]);
      setIsAiThinking(false);
    }, 900);
  }

  return (
    <div className="min-h-screen bg-[#F0EDE8] text-[#1A1A1A] font-sans pb-24">
      {/* ─── Top Workspace Bar ────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-[#D4D0C8] shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between gap-4">
          {/* Brand & Room Identifier */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#1A1A1A] text-white flex items-center justify-center font-mono font-black text-sm tracking-wider">
              WL
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold font-mono text-[#1A1A1A]">WefyLabs</span>
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider bg-emerald-100 text-emerald-900 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-700" />
                  Secure Deal Room
                </span>
              </div>
              <p className="text-xs text-gray-500 font-mono">
                {activeDeal.propertyName} • Ref: {activeDeal.dealId}
              </p>
            </div>
          </div>

          {/* Customer Profile & Advisor Badge */}
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 bg-[#FAF7F2] border border-[#D4D0C8] px-3 py-1.5 rounded-xl">
              <div className="w-7 h-7 rounded-full bg-[#1A1A1A] text-white flex items-center justify-center text-xs font-mono font-bold">
                {customerName.split(' ').map(n => n[0]).join('')}
              </div>
              <div className="text-left">
                <span className="text-xs font-bold text-[#1A1A1A] block">{customerName}</span>
                <span className="text-[10px] text-gray-500 font-mono">Verified Purchaser</span>
              </div>
            </div>

            <button
              onClick={() => setShowTokenModal(true)}
              className="text-xs font-mono font-semibold px-3 py-1.5 rounded-xl border border-[#D4D0C8] hover:bg-[#FAF7F2] transition-colors flex items-center gap-1.5"
            >
              <Lock className="w-3.5 h-3.5 text-gray-600" />
              {authToken ? 'Session Active' : 'Access Token'}
            </button>
          </div>
        </div>

        {/* ─── Navigation Tabs ────────────────────────────────────────────── */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex overflow-x-auto no-scrollbar border-t border-[#F0EDE8]">
          {[
            { id: 'overview', label: 'Overview', icon: Home },
            { id: 'deal', label: 'Deal Room', icon: Building2 },
            { id: 'documents', label: 'Documents', icon: FileText, badge: '1 Required' },
            { id: 'payments', label: 'Payment Schedule', icon: CreditCard },
            { id: 'appointments', label: 'Appointments', icon: Calendar, badge: '1 Next' },
            { id: 'messages', label: 'Messages', icon: MessageSquare },
            { id: 'support', label: 'Support & Concierge', icon: LifeBuoy },
            { id: 'post-sale', label: 'Handover & Review', icon: Key },
            { id: 'ai', label: 'AI Advisor', icon: Sparkles },
          ].map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-3 text-xs font-mono font-bold border-b-2 whitespace-nowrap transition-all ${
                  isActive
                    ? 'border-[#1A1A1A] text-[#1A1A1A] bg-[#FAF7F2]'
                    : 'border-transparent text-gray-500 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-[#1A1A1A]' : 'text-gray-400'}`} />
                {tab.label}
                {tab.badge && (
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-sans font-bold ${
                    tab.badge.includes('Required') ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'
                  }`}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </header>

      {/* ─── Main Content Container ───────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 space-y-6">

        {/* ─── Advisor Direct Contact Banner ─────────────────────────────── */}
        <div className="bg-[#FAF7F2] border border-[#D4D0C8] rounded-3xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-gray-900 to-gray-700 text-white flex items-center justify-center font-mono font-bold text-base shadow-sm">
              {advisor.initials}
            </div>
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-gray-500 font-bold block">
                Dedicated Senior Portfolio Director
              </span>
              <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">{advisor.name}</h3>
              <p className="text-xs text-gray-600 font-sans">{advisor.agency}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <a
              href={`tel:${advisor.phone}`}
              className="flex items-center gap-2 px-3.5 py-2 bg-white border border-[#D4D0C8] text-xs font-mono font-bold rounded-xl hover:bg-gray-50 transition-colors"
            >
              <PhoneCall className="w-3.5 h-3.5 text-emerald-700" />
              Call Advisor
            </a>
            <a
              href={`mailto:${advisor.email}`}
              className="flex items-center gap-2 px-3.5 py-2 bg-white border border-[#D4D0C8] text-xs font-mono font-bold rounded-xl hover:bg-gray-50 transition-colors"
            >
              <Mail className="w-3.5 h-3.5 text-blue-700" />
              Email
            </a>
            <button
              onClick={() => setActiveTab('messages')}
              className="flex items-center gap-2 px-3.5 py-2 bg-[#1A1A1A] text-white text-xs font-mono font-bold rounded-xl hover:bg-black transition-colors"
            >
              <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
              Open Deal Chat
            </button>
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 1: OVERVIEW                                                     */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Urgent Action Banner */}
            <div className="bg-amber-50 border border-amber-300 rounded-3xl p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-700 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="text-xs font-bold font-mono text-amber-950 uppercase">Immediate Action Required</h4>
                  <p className="text-xs text-amber-900 font-sans mt-0.5">
                    Please upload an updated <strong>Proof of Residential Address</strong> (utility bill dated within 90 days) to finalize compliance clearance.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setActiveTab('documents')}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-mono font-bold rounded-xl whitespace-nowrap transition-colors flex items-center justify-center gap-2"
              >
                <Upload className="w-3.5 h-3.5" />
                Upload Document
              </button>
            </div>

            {/* Transaction Progress Stepper */}
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#F0EDE8] pb-4">
                <div>
                  <span className="text-[10px] font-mono uppercase bg-emerald-100 text-emerald-900 px-2 py-0.5 rounded font-bold">
                    Stage {activeDeal.stageIndex + 1} of 9 • {activeDeal.currentStage}
                  </span>
                  <h2 className="text-base font-bold font-mono text-[#1A1A1A] mt-1">{activeDeal.propertyName}</h2>
                </div>
                <div className="text-right">
                  <span className="text-base font-black font-mono text-[#1A1A1A] block">
                    {formatCurrency(activeDeal.totalValue, region)}
                  </span>
                  <span className="text-xs font-mono text-emerald-700 font-bold">Booking Confirmed • Handover: {activeDeal.estimatedHandover}</span>
                </div>
              </div>

              {/* Canonical 9-stage visual stepper */}
              <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-9 gap-2 pt-2">
                {TRANSACTION_STAGES.map((s, idx) => {
                  const isCompleted = idx < activeDeal.stageIndex;
                  const isCurrent = idx === activeDeal.stageIndex;
                  return (
                    <div
                      key={s.id}
                      className={`p-2.5 rounded-2xl border text-center space-y-1 transition-all ${
                        isCompleted
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
                          : isCurrent
                          ? 'bg-amber-50 border-amber-400 text-amber-950 ring-2 ring-amber-200'
                          : 'bg-[#FAF7F2] border-[#D4D0C8] text-gray-400 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-center">
                        {isCompleted ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        ) : isCurrent ? (
                          <Clock className="w-4 h-4 text-amber-600 animate-pulse" />
                        ) : (
                          <span className="w-4 h-4 rounded-full border border-gray-300 text-[9px] font-mono flex items-center justify-center text-gray-400">
                            {s.num}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] font-mono font-bold block truncate">{s.label}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quick Glance Tri-Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Card 1: Documents Summary */}
              <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
                    <div className="flex items-center gap-2">
                      <FileCheck className="w-4 h-4 text-blue-600" />
                      <h3 className="text-xs font-bold font-mono text-[#1A1A1A]">Document Status</h3>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                      1 Pending
                    </span>
                  </div>
                  <ul className="text-xs space-y-2 font-mono">
                    <li className="flex items-center justify-between text-gray-700">
                      <span>Passport Copy</span>
                      <span className="text-emerald-700 font-bold flex items-center gap-1"><Check className="w-3 h-3" /> Approved</span>
                    </li>
                    <li className="flex items-center justify-between text-gray-700">
                      <span>Emirates ID</span>
                      <span className="text-emerald-700 font-bold flex items-center gap-1"><Check className="w-3 h-3" /> Approved</span>
                    </li>
                    <li className="flex items-center justify-between text-gray-700">
                      <span>Address Proof</span>
                      <span className="text-rose-700 font-bold flex items-center gap-1"><AlertCircle className="w-3 h-3" /> Required</span>
                    </li>
                    <li className="flex items-center justify-between text-gray-700">
                      <span>SPA Agreement</span>
                      <span className="text-amber-700 font-bold flex items-center gap-1"><Clock className="w-3 h-3" /> In Review</span>
                    </li>
                  </ul>
                </div>
                <button
                  onClick={() => setActiveTab('documents')}
                  className="w-full py-2 bg-[#FAF7F2] hover:bg-gray-100 border border-[#D4D0C8] text-xs font-mono font-bold rounded-xl transition-colors flex items-center justify-center gap-1.5"
                >
                  Manage Documents <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Card 2: Next Payment Milestone */}
              <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
                    <div className="flex items-center gap-2">
                      <CreditCard className="w-4 h-4 text-emerald-600" />
                      <h3 className="text-xs font-bold font-mono text-[#1A1A1A]">Next Milestone Due</h3>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                      Installment 1
                    </span>
                  </div>
                  <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-3.5 rounded-2xl space-y-1">
                    <span className="text-[10px] font-mono uppercase text-gray-500 font-bold block">Amount Payable</span>
                    <span className="text-lg font-black font-mono text-[#1A1A1A] block">
                      {formatCurrency(787500, region)}
                    </span>
                    <span className="text-xs font-mono text-gray-600 block">Due Date: <strong>October 10, 2026</strong></span>
                  </div>
                  <p className="text-[11px] text-gray-500 font-sans">
                    Escrow payment instructions & wire transfer receipt submission are available in the schedule tab.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab('payments')}
                  className="w-full py-2 bg-[#FAF7F2] hover:bg-gray-100 border border-[#D4D0C8] text-xs font-mono font-bold rounded-xl transition-colors flex items-center justify-center gap-1.5"
                >
                  View Payment Schedule <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Card 3: Upcoming Inspection */}
              <div className="bg-white border border-[#D4D0C8] rounded-3xl p-5 shadow-xs flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-amber-600" />
                      <h3 className="text-xs font-bold font-mono text-[#1A1A1A]">Next Appointment</h3>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full">
                      Site Visit
                    </span>
                  </div>
                  <div className="space-y-1">
                    <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">
                      Penthouse Snagging Inspection
                    </h4>
                    <p className="text-xs text-gray-600 font-sans">Saturday, Sep 27, 2026 at 10:00 AM</p>
                    <p className="text-[11px] text-gray-500 font-mono">Location: Marina Gate Tower 1, Level 42</p>
                  </div>
                  <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-[11px] text-emerald-950 font-sans">
                    Advisor Alexander Wright will greet you at the tower concierge with your security access pass.
                  </div>
                </div>
                <button
                  onClick={() => setActiveTab('appointments')}
                  className="w-full py-2 bg-[#FAF7F2] hover:bg-gray-100 border border-[#D4D0C8] text-xs font-mono font-bold rounded-xl transition-colors flex items-center justify-center gap-1.5"
                >
                  View Appointments <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 2: DIGITAL DEAL ROOM                                            */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'deal' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#F0EDE8] pb-4">
                <div>
                  <span className="text-[10px] font-mono uppercase bg-emerald-100 text-emerald-900 px-2 py-0.5 rounded font-bold">
                    Official Transaction Summary
                  </span>
                  <h2 className="text-lg font-bold font-mono text-[#1A1A1A] mt-1">{activeDeal.propertyName}</h2>
                  <p className="text-xs text-gray-500 font-mono">Unit {activeDeal.unitNumber} • {activeDeal.project}</p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-gray-500 font-mono block">Agreed Transaction Price</span>
                  <span className="text-xl font-black font-mono text-[#1A1A1A]">
                    {formatCurrency(activeDeal.totalValue, region)}
                  </span>
                </div>
              </div>

              {/* Property Attributes Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-2xl">
                  <span className="text-[10px] font-mono uppercase text-gray-500 block">Unit Type</span>
                  <span className="text-sm font-bold font-mono text-[#1A1A1A]">{activeDeal.bedrooms} Bed Penthouse</span>
                </div>
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-2xl">
                  <span className="text-[10px] font-mono uppercase text-gray-500 block">Built-Up Area</span>
                  <span className="text-sm font-bold font-mono text-[#1A1A1A]">{activeDeal.areaSqFt} Sq Ft</span>
                </div>
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-2xl">
                  <span className="text-[10px] font-mono uppercase text-gray-500 block">Bathrooms</span>
                  <span className="text-sm font-bold font-mono text-[#1A1A1A]">{activeDeal.bathrooms} Luxury Baths</span>
                </div>
                <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-4 rounded-2xl">
                  <span className="text-[10px] font-mono uppercase text-gray-500 block">Target Handover</span>
                  <span className="text-sm font-bold font-mono text-emerald-800">{activeDeal.estimatedHandover}</span>
                </div>
              </div>

              {/* Commercial Terms Breakdown */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold font-mono uppercase text-gray-700">Accepted Commercial Terms</h3>
                <div className="border border-[#D4D0C8] rounded-2xl overflow-hidden divide-y divide-[#EAE7E1]">
                  <div className="flex justify-between p-3.5 bg-white text-xs font-mono">
                    <span className="text-gray-600">Base Unit Consideration</span>
                    <span className="font-bold text-[#1A1A1A]">{formatCurrency(activeDeal.totalValue, region)}</span>
                  </div>
                  <div className="flex justify-between p-3.5 bg-[#FAF7F2] text-xs font-mono">
                    <span className="text-gray-600">Booking Deposit (Paid & Verified)</span>
                    <span className="font-bold text-emerald-700">{formatCurrency(262500, region)} (5%)</span>
                  </div>
                  <div className="flex justify-between p-3.5 bg-white text-xs font-mono">
                    <span className="text-gray-600">Payment Structure</span>
                    <span className="font-bold text-[#1A1A1A]">20% Construction Linked / 40% On Handover</span>
                  </div>
                  <div className="flex justify-between p-3.5 bg-[#FAF7F2] text-xs font-mono">
                    <span className="text-gray-600">Dubai Land Department Registration Fee (4%)</span>
                    <span className="font-bold text-[#1A1A1A]">{formatCurrency(210000, region)} (Payable at Transfer)</span>
                  </div>
                </div>
              </div>

              {/* Customer Transaction Terms Acknowledgement */}
              <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <h4 className="text-xs font-bold font-mono text-emerald-950 uppercase">Customer Acknowledgement</h4>
                  <p className="text-xs text-emerald-900 font-sans">
                    {termsAcknowledged
                      ? 'You have formally acknowledged and accepted the commercial booking terms on September 22, 2026.'
                      : 'Please acknowledge that you have reviewed the agreed commercial terms and milestone schedule.'}
                  </p>
                </div>
                {!termsAcknowledged ? (
                  <button
                    onClick={() => {
                      setTermsAcknowledged(true);
                      setAckToast(true);
                      setTimeout(() => setAckToast(false), 3000);
                    }}
                    className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-mono font-bold rounded-xl whitespace-nowrap transition-colors flex items-center justify-center gap-2"
                  >
                    <CheckCheck className="w-4 h-4" />
                    Acknowledge Terms
                  </button>
                ) : (
                  <span className="text-xs font-mono font-bold text-emerald-800 bg-emerald-200/60 px-3 py-1.5 rounded-xl flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-700" /> Acknowledged
                  </span>
                )}
              </div>
              {ackToast && (
                <div className="p-3 bg-emerald-600 text-white text-xs font-mono rounded-xl text-center">
                  Acknowledgement recorded in transaction audit log.
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 3: DOCUMENTS                                                    */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'documents' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F0EDE8] pb-4">
                <div>
                  <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Transaction Document Checklist</h2>
                  <p className="text-xs text-gray-500 font-sans">
                    Uploaded documents are reviewed by WefyLabs legal and compliance teams within 24 business hours.
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs font-mono text-gray-600">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  Encrypted & Tenant Isolated
                </div>
              </div>

              {/* Document List */}
              <div className="divide-y divide-[#EAE7E1] border border-[#D4D0C8] rounded-2xl overflow-hidden">
                {documents.map(doc => {
                  const isApproved = doc.status === 'APPROVED';
                  const isInReview = doc.status === 'IN_REVIEW';
                  const isActionReq = doc.status === 'ACTION_REQUIRED';

                  return (
                    <div key={doc.id} className="p-4 bg-white hover:bg-[#FAF7F2] transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-gray-600" />
                          <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">{doc.name}</h4>
                          {doc.isRequired && (
                            <span className="text-[9px] font-mono uppercase bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                              Required
                            </span>
                          )}
                        </div>
                        {doc.uploadedAt && (
                          <p className="text-[11px] text-gray-500 font-mono">Last uploaded: {doc.uploadedAt}</p>
                        )}
                        {doc.reason && (
                          <p className="text-xs text-rose-700 font-sans mt-0.5">Note: {doc.reason}</p>
                        )}
                      </div>

                      <div className="flex items-center gap-3">
                        <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${
                          isApproved
                            ? 'bg-emerald-100 text-emerald-800'
                            : isInReview
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}>
                          {isApproved && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />}
                          {isInReview && <Clock className="w-3.5 h-3.5 text-amber-700" />}
                          {isActionReq && <AlertCircle className="w-3.5 h-3.5 text-rose-700" />}
                          {doc.status.replace('_', ' ')}
                        </span>

                        <button
                          onClick={() => setUploadModalDoc(doc)}
                          className="px-3 py-1.5 border border-[#D4D0C8] hover:bg-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center gap-1.5"
                        >
                          <Upload className="w-3.5 h-3.5" />
                          {doc.uploadedAt ? 'Replace' : 'Upload'}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Document Upload Modal */}
            {uploadModalDoc && (
              <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
                <div className="bg-white border border-[#D4D0C8] rounded-3xl max-w-md w-full p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
                    <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Upload: {uploadModalDoc.name}</h3>
                    <button onClick={() => setUploadModalDoc(null)} className="text-gray-400 hover:text-gray-700">
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  <form onSubmit={handleUploadDocument} className="space-y-4">
                    <p className="text-xs text-gray-600 font-sans">
                      Select a file or enter verified storage link (PDF, JPG, PNG up to 25MB).
                    </p>
                    <div className="p-6 border-2 border-dashed border-[#D4D0C8] rounded-2xl bg-[#FAF7F2] text-center space-y-2">
                      <Upload className="w-6 h-6 text-gray-400 mx-auto" />
                      <p className="text-xs text-gray-700 font-medium">Drag & drop your file or enter URL below</p>
                      <input
                        type="text"
                        placeholder="https://storage.wefylabs.com/my-doc.pdf"
                        value={uploadFileUrl}
                        onChange={e => setUploadFileUrl(e.target.value)}
                        className="w-full text-xs font-mono p-2.5 border border-[#D4D0C8] rounded-xl bg-white focus:outline-none focus:ring-1 focus:ring-black"
                      />
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setUploadModalDoc(null)}
                        className="px-4 py-2 border border-[#D4D0C8] rounded-xl text-xs font-mono font-bold"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-2 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-xs font-mono font-bold flex items-center gap-1.5"
                      >
                        <Check className="w-3.5 h-3.5" /> Submit for Review
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 4: PAYMENT SCHEDULE                                             */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'payments' && (
          <div className="space-y-6">
            {/* Escrow and Safety Notice */}
            <div className="bg-blue-50 border border-blue-200 rounded-3xl p-5 space-y-2">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-blue-700" />
                <h4 className="text-xs font-bold font-mono text-blue-950 uppercase">
                  Official Escrow Accounting & Payment Safety
                </h4>
              </div>
              <p className="text-xs text-blue-900 font-sans leading-relaxed">
                All property purchase funds in the UAE are disbursed strictly through the official Dubai Land Department regulated Project Escrow Account.
                For bank wire transfers or manager cheques, please upload your transfer slip below.
                <span className="block mt-1 font-mono text-[11px] text-blue-950 font-bold">
                  Compliance Boundary: Online card checkout (Razorpay) operates in test/mock mode only; autonomous debit is disabled.
                </span>
              </p>
            </div>

            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F0EDE8] pb-4">
                <div>
                  <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Payment Milestone Schedule</h2>
                  <p className="text-xs text-gray-500 font-sans">
                    Authoritative installments according to the registered Sale & Purchase Agreement.
                  </p>
                </div>
                <button
                  onClick={() => setShowPaymentModal(true)}
                  className="px-4 py-2 bg-[#1A1A1A] hover:bg-black text-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <Upload className="w-3.5 h-3.5 text-emerald-400" />
                  Submit Payment Proof
                </button>
              </div>

              {/* Milestones List */}
              <div className="divide-y divide-[#EAE7E1] border border-[#D4D0C8] rounded-2xl overflow-hidden">
                {paymentMilestones.map((m, idx) => {
                  const isVerified = m.status === 'VERIFIED';
                  const isReported = m.status === 'REPORTED';
                  const isDue = m.status === 'DUE';

                  return (
                    <div key={idx} className="p-4 bg-white hover:bg-[#FAF7F2] transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-full bg-gray-100 text-gray-700 font-mono text-[10px] font-bold flex items-center justify-center">
                            {idx + 1}
                          </span>
                          <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">{m.name}</h4>
                        </div>
                        <p className="text-[11px] text-gray-500 font-mono">Due Date: {m.dueDate}</p>
                        {m.ref && (
                          <p className="text-[11px] font-mono text-gray-600">Reference: <span className="font-bold">{m.ref}</span></p>
                        )}
                      </div>

                      <div className="flex items-center gap-4">
                        <span className="text-sm font-black font-mono text-[#1A1A1A]">
                          {formatCurrency(m.amount, region)}
                        </span>

                        <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${
                          isVerified
                            ? 'bg-emerald-100 text-emerald-800'
                            : isReported
                            ? 'bg-blue-100 text-blue-800'
                            : isDue
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-gray-100 text-gray-500'
                        }`}>
                          {isVerified && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />}
                          {isReported && <Clock className="w-3.5 h-3.5 text-blue-700" />}
                          {isDue && <AlertCircle className="w-3.5 h-3.5 text-amber-700" />}
                          {m.status}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Submit Payment Proof Modal */}
            {showPaymentModal && (
              <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
                <div className="bg-white border border-[#D4D0C8] rounded-3xl max-w-md w-full p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
                    <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Submit Wire Transfer Receipt</h3>
                    <button onClick={() => setShowPaymentModal(false)} className="text-gray-400 hover:text-gray-700">
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  {paymentSuccessMsg ? (
                    <div className="p-4 bg-emerald-50 border border-emerald-300 rounded-2xl text-xs font-mono text-emerald-950 text-center space-y-2">
                      <CheckCircle2 className="w-6 h-6 text-emerald-600 mx-auto" />
                      <p>{paymentSuccessMsg}</p>
                    </div>
                  ) : (
                    <form onSubmit={handleSubmitPaymentProof} className="space-y-4">
                      <div className="space-y-1">
                        <label className="text-xs font-mono font-bold text-gray-700">Select Milestone</label>
                        <select
                          value={paymentMilestoneIndex}
                          onChange={e => {
                            const idx = Number(e.target.value);
                            setPaymentMilestoneIndex(idx);
                            setPaymentAmount(paymentMilestones[idx].amount.toString());
                          }}
                          className="w-full text-xs font-mono p-2.5 border border-[#D4D0C8] rounded-xl bg-white"
                        >
                          {paymentMilestones.map((m, idx) => (
                            <option key={idx} value={idx}>{m.name} — {formatCurrency(m.amount, region)}</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label className="text-xs font-mono font-bold text-gray-700">Bank Transfer Reference / UTR Number</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. WT-ENBD-982104"
                          value={paymentRef}
                          onChange={e => setPaymentRef(e.target.value)}
                          className="w-full text-xs font-mono p-2.5 border border-[#D4D0C8] rounded-xl bg-white focus:outline-none focus:ring-1 focus:ring-black"
                        />
                      </div>

                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-950 font-sans">
                        Note: Uploaded bank slips are marked <strong>REPORTED</strong> and verified by our finance team upon escrow account confirmation.
                      </div>

                      <div className="flex justify-end gap-2 pt-2">
                        <button
                          type="button"
                          onClick={() => setShowPaymentModal(false)}
                          className="px-4 py-2 border border-[#D4D0C8] rounded-xl text-xs font-mono font-bold"
                        >
                          Cancel
                        </button>
                        <button
                          type="submit"
                          className="px-4 py-2 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-xs font-mono font-bold flex items-center gap-1.5"
                        >
                          <Check className="w-3.5 h-3.5" /> Submit Proof
                        </button>
                      </div>
                    </form>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 5: APPOINTMENTS & VIEWINGS                                      */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'appointments' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F0EDE8] pb-4">
                <div>
                  <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Scheduled Appointments & Site Visits</h2>
                  <p className="text-xs text-gray-500 font-sans">
                    All viewings and notarization meetings are coordinated through our verified calendar system.
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                {appointments.map(apt => (
                  <div key={apt.id} className="bg-[#FAF7F2] border border-[#D4D0C8] p-5 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-emerald-700" />
                        <h4 className="text-sm font-bold font-mono text-[#1A1A1A]">{apt.title}</h4>
                      </div>
                      <p className="text-xs text-gray-600 font-mono">
                        Date & Time: <strong>{new Date(apt.startUtc).toUTCString()}</strong>
                      </p>
                      <p className="text-xs text-gray-500 font-sans">Location: {apt.location}</p>
                      {apt.meetingUrl && (
                        <a
                          href={apt.meetingUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-blue-700 hover:underline"
                        >
                          <ExternalLink className="w-3.5 h-3.5" /> Join Virtual Meeting
                        </a>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-mono font-bold px-3 py-1 rounded-full ${
                        apt.status === 'CONFIRMED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                      }`}>
                        {apt.status}
                      </span>
                      {apt.status !== 'CONFIRMED' && (
                        <button
                          onClick={() => handleConfirmAppointment(apt.id)}
                          className="px-3.5 py-1.5 bg-[#1A1A1A] hover:bg-black text-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center gap-1.5"
                        >
                          <Check className="w-3.5 h-3.5" /> Confirm Attendance
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 6: MESSAGES                                                     */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'messages' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-4">
                <div>
                  <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Customer Communication Center</h2>
                  <p className="text-xs text-gray-500 font-sans">
                    Direct confidential conversation with your assigned senior advisor.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-800 bg-emerald-100 px-2.5 py-1 rounded-full font-bold">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
                  Internal CRM Notes Excluded
                </div>
              </div>

              {/* Message Thread */}
              <div className="space-y-3 max-h-96 overflow-y-auto p-4 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl">
                {messages.map(msg => {
                  const isCustomer = msg.direction === 'OUTBOUND';
                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${isCustomer ? 'items-end' : 'items-start'}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-mono font-bold text-gray-500">{msg.senderName}</span>
                        <span className="text-[9px] font-mono text-gray-400">{msg.createdAt}</span>
                      </div>
                      <div className={`p-3.5 rounded-2xl max-w-lg text-xs leading-relaxed ${
                        isCustomer
                          ? 'bg-[#1A1A1A] text-white rounded-br-xs'
                          : 'bg-white border border-[#D4D0C8] text-gray-900 rounded-bl-xs'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Message Reply Box */}
              <form onSubmit={handleSendCustomerMessage} className="flex gap-2">
                <input
                  type="text"
                  placeholder="Type a message to your advisor..."
                  value={newMessageText}
                  onChange={e => setNewMessageText(e.target.value)}
                  className="flex-1 text-xs font-mono p-3 border border-[#D4D0C8] rounded-xl bg-[#FAF7F2] focus:outline-none focus:ring-1 focus:ring-black"
                />
                <button
                  type="submit"
                  className="px-5 py-3 bg-[#1A1A1A] hover:bg-black text-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" /> Send
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 7: SUPPORT & CONCIERGE                                          */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'support' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#F0EDE8] pb-4">
                <div>
                  <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Customer Concierge & Support</h2>
                  <p className="text-xs text-gray-500 font-sans">
                    Every ticket is routed immediately to your portfolio team with an agreed 24-hour turnaround.
                  </p>
                </div>
                <button
                  onClick={() => setShowSupportModal(true)}
                  className="px-4 py-2 bg-[#1A1A1A] hover:bg-black text-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center justify-center gap-1.5"
                >
                  <LifeBuoy className="w-3.5 h-3.5" /> Create Support Request
                </button>
              </div>

              {/* Tickets List */}
              <div className="space-y-3">
                {supportTickets.map(t => (
                  <div key={t.id} className="p-4 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono font-bold uppercase bg-gray-200 text-gray-700 px-2 py-0.5 rounded">
                          {t.category.replace('_', ' ')}
                        </span>
                        <h4 className="text-xs font-bold font-mono text-[#1A1A1A]">{t.subject}</h4>
                      </div>
                      <p className="text-[11px] text-gray-500 font-mono">Reference: {t.id} • Submitted: {t.createdAt}</p>
                    </div>

                    <span className="text-xs font-mono font-bold px-3 py-1 rounded-full bg-blue-100 text-blue-800 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-blue-700" />
                      {t.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Create Ticket Modal */}
            {showSupportModal && (
              <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
                <div className="bg-white border border-[#D4D0C8] rounded-3xl max-w-md w-full p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
                    <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Submit Support Request</h3>
                    <button onClick={() => setShowSupportModal(false)} className="text-gray-400 hover:text-gray-700">
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  <form onSubmit={handleCreateSupportTicket} className="space-y-4">
                    <div className="space-y-1">
                      <label className="text-xs font-mono font-bold text-gray-700">Category</label>
                      <select
                        value={newTicketCategory}
                        onChange={e => setNewTicketCategory(e.target.value)}
                        className="w-full text-xs font-mono p-2.5 border border-[#D4D0C8] rounded-xl bg-white"
                      >
                        <option value="DOCUMENT_HELP">Document & KYC Assistance</option>
                        <option value="PAYMENT_QUERY">Payment & Escrow Inquiry</option>
                        <option value="APPOINTMENT_QUERY">Appointment & Viewing Reschedule</option>
                        <option value="TRANSACTION_QUERY">Transaction Contract Question</option>
                        <option value="HANDOVER_QUERY">Handover & Snagging Question</option>
                        <option value="GENERAL">General Concierge</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-mono font-bold text-gray-700">Subject</label>
                      <input
                        type="text"
                        required
                        placeholder="Brief summary of your question"
                        value={newTicketSubject}
                        onChange={e => setNewTicketSubject(e.target.value)}
                        className="w-full text-xs font-mono p-2.5 border border-[#D4D0C8] rounded-xl bg-white focus:outline-none focus:ring-1 focus:ring-black"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-mono font-bold text-gray-700">Details</label>
                      <textarea
                        rows={3}
                        placeholder="Please provide any relevant details"
                        value={newTicketDesc}
                        onChange={e => setNewTicketDesc(e.target.value)}
                        className="w-full text-xs font-sans p-2.5 border border-[#D4D0C8] rounded-xl bg-white focus:outline-none focus:ring-1 focus:ring-black"
                      />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setShowSupportModal(false)}
                        className="px-4 py-2 border border-[#D4D0C8] rounded-xl text-xs font-mono font-bold"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-2 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-xs font-mono font-bold flex items-center gap-1.5"
                      >
                        <Check className="w-3.5 h-3.5" /> Submit Request
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 8: POST-SALE & REVIEW                                           */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'post-sale' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-6">
              <div className="border-b border-[#F0EDE8] pb-4">
                <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Handover & Post-Sale Experience</h2>
                <p className="text-xs text-gray-500 font-sans">
                  Key collection procedures, utility registration guides, and customer feedback.
                </p>
              </div>

              {/* Handover Checklist */}
              <div className="bg-[#FAF7F2] border border-[#D4D0C8] p-5 rounded-2xl space-y-3">
                <h4 className="text-xs font-bold font-mono uppercase text-gray-700">Handover Readiness Checklist</h4>
                <div className="space-y-2 text-xs font-mono">
                  <div className="flex items-center gap-2 text-emerald-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Final Escrow Settlement Statement Ready
                  </div>
                  <div className="flex items-center gap-2 text-emerald-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" /> DLD Title Deed Issuance Initiated
                  </div>
                  <div className="flex items-center gap-2 text-amber-800">
                    <Clock className="w-4 h-4 text-amber-600" /> Snagging Inspection Completion (Sep 27)
                  </div>
                  <div className="flex items-center gap-2 text-gray-500">
                    <Key className="w-4 h-4 text-gray-400" /> Key Handover & DEWA Activation Pack
                  </div>
                </div>
              </div>

              {/* CSAT & NPS Feedback Form */}
              <div className="border border-[#D4D0C8] rounded-2xl p-6 space-y-5">
                <div className="space-y-1">
                  <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Your Experience & Satisfaction Review</h3>
                  <p className="text-xs text-gray-500 font-sans">
                    Your feedback directly shapes our concierge service and advisor recognition.
                  </p>
                </div>

                {feedbackSubmitted ? (
                  <div className="p-6 bg-emerald-50 border border-emerald-300 rounded-2xl text-center space-y-2">
                    <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
                    <h4 className="text-sm font-bold font-mono text-emerald-950">Thank you for your feedback!</h4>
                    <p className="text-xs text-emerald-900 font-sans max-w-sm mx-auto">
                      Your ratings and comments have been recorded. Our team is dedicated to delivering excellence throughout your ownership.
                    </p>
                  </div>
                ) : (
                  <form onSubmit={handleSubmitFeedback} className="space-y-5">
                    {/* CSAT 1 to 5 Stars */}
                    <div className="space-y-2">
                      <label className="text-xs font-mono font-bold text-gray-700 block">
                        Overall Experience (CSAT: 1–5 Stars)
                      </label>
                      <div className="flex gap-2">
                        {[1, 2, 3, 4, 5].map(star => (
                          <button
                            type="button"
                            key={star}
                            onClick={() => setCsatRating(star)}
                            className="p-1.5 focus:outline-none transition-transform hover:scale-110"
                          >
                            <Star
                              className={`w-6 h-6 ${
                                star <= csatRating ? 'text-amber-400 fill-amber-400' : 'text-gray-300'
                              }`}
                            />
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* NPS 0 to 10 Scale */}
                    <div className="space-y-2">
                      <label className="text-xs font-mono font-bold text-gray-700 block">
                        How likely are you to recommend WefyLabs to a friend or colleague? (NPS: 0–10)
                      </label>
                      <div className="flex flex-wrap gap-1.5">
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(val => (
                          <button
                            type="button"
                            key={val}
                            onClick={() => setNpsScore(val)}
                            className={`w-8 h-8 rounded-xl font-mono text-xs font-bold transition-all ${
                              npsScore === val
                                ? 'bg-[#1A1A1A] text-white shadow-sm'
                                : 'bg-[#FAF7F2] border border-[#D4D0C8] text-gray-700 hover:bg-gray-100'
                            }`}
                          >
                            {val}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Comments */}
                    <div className="space-y-1">
                      <label className="text-xs font-mono font-bold text-gray-700 block">Written Feedback</label>
                      <textarea
                        rows={3}
                        placeholder="Tell us about your experience with our advisors and deal room..."
                        value={feedbackText}
                        onChange={e => setFeedbackText(e.target.value)}
                        className="w-full text-xs font-sans p-3 border border-[#D4D0C8] rounded-xl bg-white focus:outline-none focus:ring-1 focus:ring-black"
                      />
                    </div>

                    {/* Referral Toggle */}
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="referral"
                        checked={referralInterest}
                        onChange={e => setReferralInterest(e.target.checked)}
                        className="rounded border-[#D4D0C8] text-black focus:ring-black"
                      />
                      <label htmlFor="referral" className="text-xs text-gray-700 font-sans cursor-pointer">
                        I am interested in exploring property investment opportunities for my network through the WefyLabs Private Client Club.
                      </label>
                    </div>

                    <button
                      type="submit"
                      className="px-6 py-2.5 bg-[#1A1A1A] hover:bg-black text-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center gap-2"
                    >
                      <ThumbsUp className="w-4 h-4" /> Submit Feedback
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════════════════════ */}
        {/* TAB 9: GOVERNED AI ADVISOR                                          */}
        {/* ═══════════════════════════════════════════════════════════════════ */}
        {activeTab === 'ai' && (
          <div className="space-y-6">
            <div className="bg-white border border-[#D4D0C8] rounded-3xl p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-4">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-700 text-white flex items-center justify-center font-mono font-black text-xs">
                    AI
                  </div>
                  <div>
                    <h2 className="text-base font-bold font-mono text-[#1A1A1A]">Governed Transaction Assistant</h2>
                    <p className="text-xs text-gray-500 font-sans">
                      Answers grounded strictly in your verified transaction records.
                    </p>
                  </div>
                </div>
                <div className="text-[10px] font-mono text-gray-500 bg-[#FAF7F2] border border-[#D4D0C8] px-2.5 py-1 rounded-full">
                  Zero Internal Notes / Margin Leaks
                </div>
              </div>

              {/* Chat Thread */}
              <div className="space-y-3 max-h-96 overflow-y-auto p-4 bg-[#FAF7F2] border border-[#D4D0C8] rounded-2xl">
                {aiResponses.map((item, idx) => (
                  <div
                    key={idx}
                    className={`flex flex-col ${item.sender === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-mono font-bold text-gray-500">
                        {item.sender === 'user' ? 'You' : 'WefyLabs AI'}
                      </span>
                    </div>
                    <div className={`p-3.5 rounded-2xl max-w-lg text-xs leading-relaxed ${
                      item.sender === 'user'
                        ? 'bg-[#1A1A1A] text-white rounded-br-xs'
                        : 'bg-white border border-violet-200 text-gray-900 rounded-bl-xs shadow-2xs'
                    }`}>
                      {item.text}
                    </div>
                  </div>
                ))}
                {isAiThinking && (
                  <div className="text-xs text-gray-400 font-mono italic animate-pulse">
                    Consulting verified transaction records...
                  </div>
                )}
              </div>

              {/* Quick Prompts */}
              <div className="flex flex-wrap gap-2 pt-1">
                {[
                  'What is my next step?',
                  'Which documents are pending?',
                  'When is my next payment due?',
                  'What is the inspection schedule?'
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setAiQuery(prompt);
                    }}
                    className="text-[11px] font-mono px-3 py-1.5 bg-[#FAF7F2] border border-[#D4D0C8] rounded-xl hover:bg-gray-100 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>

              {/* Chat Input */}
              <form onSubmit={handleAskAi} className="flex gap-2 pt-2">
                <input
                  type="text"
                  placeholder="Ask a question about your deal, documents, or schedule..."
                  value={aiQuery}
                  onChange={e => setAiQuery(e.target.value)}
                  className="flex-1 text-xs font-mono p-3 border border-[#D4D0C8] rounded-xl bg-[#FAF7F2] focus:outline-none focus:ring-1 focus:ring-violet-600"
                />
                <button
                  type="submit"
                  disabled={isAiThinking}
                  className="px-5 py-3 bg-gradient-to-r from-violet-600 to-indigo-700 hover:from-violet-700 hover:to-indigo-800 text-white text-xs font-mono font-bold rounded-xl transition-colors flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" /> Ask AI
                </button>
              </form>
            </div>
          </div>
        )}

      </main>

      {/* ─── Token Authentication Modal ───────────────────────────────────── */}
      {showTokenModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white border border-[#D4D0C8] rounded-3xl max-w-md w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#F0EDE8] pb-3">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-700" />
                <h3 className="text-sm font-bold font-mono text-[#1A1A1A]">Customer Access Token</h3>
              </div>
              <button onClick={() => setShowTokenModal(false)} className="text-gray-400 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-gray-600 font-sans">
              Enter your secure invite token provided by your advisor or sent to your registered email to unlock live transaction data.
            </p>

            {tokenError && (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs font-mono text-rose-800">
                {tokenError}
              </div>
            )}

            <div className="space-y-2">
              <input
                type="text"
                placeholder="Paste your 64-character invite token"
                value={inviteTokenInput}
                onChange={e => setInviteTokenInput(e.target.value)}
                className="w-full text-xs font-mono p-3 border border-[#D4D0C8] rounded-xl bg-[#FAF7F2] focus:outline-none focus:ring-1 focus:ring-black"
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              {authToken ? (
                <button
                  type="button"
                  onClick={handleLogout}
                  className="text-xs font-mono font-bold text-rose-700 hover:underline"
                >
                  Clear Session
                </button>
              ) : <div />}

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowTokenModal(false)}
                  className="px-4 py-2 border border-[#D4D0C8] rounded-xl text-xs font-mono font-bold"
                >
                  Close
                </button>
                <button
                  type="button"
                  disabled={isLoading || !inviteTokenInput.trim()}
                  onClick={() => handleExchangeToken(inviteTokenInput.trim())}
                  className="px-4 py-2 bg-[#1A1A1A] hover:bg-black text-white rounded-xl text-xs font-mono font-bold flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isLoading ? 'Verifying...' : 'Authenticate'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
