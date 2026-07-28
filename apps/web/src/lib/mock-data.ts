// Shared mock data used by Dashboard, Leads, Pipeline, and Tasks pages

export type ScoreType = 'hot' | 'warm' | 'cold' | 'spam' | 'pending';
export type StageType = 'New' | 'Contacted' | 'Viewing Scheduled' | 'Negotiating' | 'Closed Won' | 'Closed Lost';
export type TaskStatus = 'upcoming' | 'overdue' | 'completed';

export interface MockLead {
  id: string;
  name: string;
  phone: string;
  score: ScoreType;
  budget: string;
  budget_min: number;
  budget_max: number;
  location: string;
  stage: StageType;
  source: string;
  lastActivity: string;
  tags: string[];
  reminder: string | null;
}

export interface MockTask {
  id: string;
  title: string;
  leadName: string;
  leadPhone: string;
  dueAt: string;
  tag: 'Call' | 'Viewing' | 'Follow-up' | 'WhatsApp';
  location: string;
  status: TaskStatus;
  completed: boolean;
}

export const mockLeads: MockLead[] = [
  {
    id: '1',
    name: 'Rajesh Kumar',
    phone: '+91 98765 43210',
    score: 'hot',
    budget: '₹40L-50L',
    budget_min: 4000000,
    budget_max: 5000000,
    location: 'Koramangala, HSR Layout',
    stage: 'Contacted',
    source: 'Facebook Ads',
    lastActivity: '2 hours ago',
    tags: ['Urgent', 'Loan Pending'],
    reminder: 'Call Rajesh at 11 AM with south-facing 2BHK options',
  },
  {
    id: '2',
    name: 'Priya Ananth',
    phone: '+91 87654 32109',
    score: 'warm',
    budget: '₹75L-90L',
    budget_min: 7500000,
    budget_max: 9000000,
    location: 'Indiranagar, Whitefield',
    stage: 'Viewing Scheduled',
    source: '99acres',
    lastActivity: '5 hours ago',
    tags: ['NRI Client'],
    reminder: null,
  },
  {
    id: '3',
    name: 'Amitabh Verma',
    phone: '+91 76543 21098',
    score: 'cold',
    budget: '₹20L-25L',
    budget_min: 2000000,
    budget_max: 2500000,
    location: 'Electronic City',
    stage: 'New',
    source: 'Google Ads',
    lastActivity: '1 day ago',
    tags: ['Budget Buyer'],
    reminder: null,
  },
  {
    id: '4',
    name: 'Rahul Sharma',
    phone: '+91 65432 10987',
    score: 'warm',
    budget: '₹55L-65L',
    budget_min: 5500000,
    budget_max: 6500000,
    location: 'JP Nagar, Banashankari',
    stage: 'New',
    source: 'Magicbricks',
    lastActivity: '3 hours ago',
    tags: ['Site Visit Pending'],
    reminder: 'Schedule site visit for Rahul Sharma',
  },
  {
    id: '5',
    name: 'Sunita Mehta',
    phone: '+91 54321 09876',
    score: 'hot',
    budget: '₹1.2Cr-1.5Cr',
    budget_min: 12000000,
    budget_max: 15000000,
    location: 'Bandra West, Juhu',
    stage: 'Negotiating',
    source: 'WhatsApp',
    lastActivity: '30 min ago',
    tags: ['Loan: ✅', 'Ready to Buy'],
    reminder: null,
  },
  {
    id: '6',
    name: 'Arjun Nair',
    phone: '+91 43210 98765',
    score: 'cold',
    budget: '₹30L-35L',
    budget_min: 3000000,
    budget_max: 3500000,
    location: 'Sarjapur Road',
    stage: 'Closed Lost',
    source: 'Facebook Ads',
    lastActivity: '3 days ago',
    tags: ['Low Budget'],
    reminder: null,
  },
  {
    id: '7',
    name: 'Kavya Reddy',
    phone: '+91 32109 87654',
    score: 'hot',
    budget: '₹85L-1Cr',
    budget_min: 8500000,
    budget_max: 10000000,
    location: 'Jubilee Hills, Banjara Hills',
    stage: 'Closed Won',
    source: '99acres',
    lastActivity: '5 days ago',
    tags: ['Loan: ✅', 'Deal Closed'],
    reminder: null,
  },
  {
    id: '8',
    name: 'Mohammed Arif',
    phone: '+91 21098 76543',
    score: 'warm',
    budget: '₹45L-55L',
    budget_min: 4500000,
    budget_max: 5500000,
    location: 'Marathahalli, Whitefield',
    stage: 'Contacted',
    source: 'Google Ads',
    lastActivity: '4 hours ago',
    tags: ['Investment Buyer'],
    reminder: 'Follow up with Arif on loan pre-approval',
  },
];

export const mockTasks: MockTask[] = [
  {
    id: 't1',
    title: 'Call Rajesh at 11 AM with south-facing 2BHK options',
    leadName: 'Rajesh Kumar',
    leadPhone: '+91 98765 43210',
    dueAt: 'Today, 11:00 AM',
    tag: 'Call',
    location: 'Koramangala',
    status: 'upcoming',
    completed: false,
  },
  {
    id: 't2',
    title: 'Follow up with Priya on loan pre-approval status',
    leadName: 'Priya Ananth',
    leadPhone: '+91 87654 32109',
    dueAt: 'Tomorrow, 2:00 PM',
    tag: 'Follow-up',
    location: 'Whitefield',
    status: 'upcoming',
    completed: false,
  },
  {
    id: 't3',
    title: 'Send Amitabh property photos via WhatsApp',
    leadName: 'Amitabh Verma',
    leadPhone: '+91 76543 21098',
    dueAt: 'Yesterday',
    tag: 'WhatsApp',
    location: 'Electronic City',
    status: 'completed',
    completed: true,
  },
  {
    id: 't4',
    title: 'Schedule site visit for Rahul Sharma — JP Nagar',
    leadName: 'Rahul Sharma',
    leadPhone: '+91 65432 10987',
    dueAt: 'Overdue · 1 day',
    tag: 'Viewing',
    location: 'JP Nagar',
    status: 'overdue',
    completed: false,
  },
  {
    id: 't5',
    title: 'Negotiate final price with Sunita Mehta',
    leadName: 'Sunita Mehta',
    leadPhone: '+91 54321 09876',
    dueAt: 'Today, 4:00 PM',
    tag: 'Call',
    location: 'Bandra West',
    status: 'upcoming',
    completed: false,
  },
  {
    id: 't6',
    title: 'Send Mohammed Arif the floor plan documents',
    leadName: 'Mohammed Arif',
    leadPhone: '+91 21098 76543',
    dueAt: 'Overdue · 2 days',
    tag: 'Follow-up',
    location: 'Marathahalli',
    status: 'overdue',
    completed: false,
  },
];
