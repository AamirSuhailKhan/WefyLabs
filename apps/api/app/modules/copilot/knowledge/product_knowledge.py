"""
Volume 2 PART 25 — Canonical Product Knowledge Layer
=====================================================
Structured, authoritatively controlled documentation layer for the CRM Copilot.
Prevents hallucination by grounding all product capability, workflow, configuration,
and billing answers in verified application knowledge with provenance citations.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Optional


PRODUCT_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "id": "overview",
        "category": "Architecture & Overview",
        "title": "CRM Platform Overview",
        "citation": "Product Documentation → Platform Overview",
        "keywords": ["what is this", "crm", "features", "overview", "wefylabs", "beetlelabs", "capabilities", "what can you do"],
        "summary": "Enterprise multi-tenant real estate CRM platform with AI lead scoring, pipeline management, calendar scheduling, and team collaboration.",
        "content": (
            "WefyLabs Real Estate CRM is an enterprise-grade customer relationship management system "
            "designed specifically for real estate brokers, agencies, and sales teams. "
            "Core capabilities include:\n"
            "- Multi-channel Lead Ingestion (WhatsApp forward capture, Facebook/Google ads, CSV import, manual entry)\n"
            "- AI Lead Scoring (HOT, WARM, COLD classification with conversion confidence)\n"
            "- Visual Kanban Pipeline Management (drag-and-drop stages from New to Closed Won)\n"
            "- Smart CRM Tasks & Automated Follow-Up Reminders\n"
            "- Google Calendar Integration for client site visits and appointments\n"
            "- Role-Based Team Management (Owner, Admin, Manager, Agent)\n"
            "- Transactional Email via Brevo SMTP\n"
            "- Revenue Forecasting and Pipeline Health Analytics\n"
            "- Secure Multi-Tenant Architecture with strict data isolation."
        )
    },
    {
        "id": "lead_management",
        "category": "Leads",
        "title": "Lead Management & AI Scoring",
        "citation": "Product Documentation → Lead Management",
        "keywords": ["lead", "leads", "import leads", "add lead", "scoring", "hot", "warm", "cold", "qualification"],
        "summary": "How leads are created, qualified, scored, and managed across their lifecycle.",
        "content": (
            "Leads can be added manually via the Leads page (/dashboard/leads) or ingested automatically. "
            "Each lead contains contact details (name, phone, email), budget range (min/max), property type preferences, "
            "preferred locations, and current pipeline stage.\n\n"
            "AI Qualification & Scoring:\n"
            "- HOT: High intent, pre-approved budget, ready to transact within 30 days.\n"
            "- WARM: Clear interest and budget, evaluating properties, 1-3 month timeline.\n"
            "- COLD: Early research, unverified budget, or indefinite timeline (>3 months).\n\n"
            "To view or filter leads, navigate to /dashboard/leads. You can search by client name, phone, "
            "filter by score (HOT/WARM/COLD), filter by pipeline stage, and add internal notes."
        )
    },
    {
        "id": "pipeline_deals",
        "category": "Pipeline & Deals",
        "title": "Pipeline Stages & Deal Tracking",
        "citation": "Product Documentation → Pipeline & Deals",
        "keywords": ["pipeline", "stages", "deals", "kanban", "negotiating", "closed won", "closed lost", "funnel"],
        "summary": "Default Kanban pipeline stages, stage progression, and revenue tracking.",
        "content": (
            "The CRM features a 6-stage default sales pipeline accessible at /dashboard/pipeline:\n"
            "1. New: Fresh uncontacted inquiries.\n"
            "2. Contacted: Initial outreach made by broker or automated assistant.\n"
            "3. Viewing Scheduled: Property tour or site visit arranged on calendar.\n"
            "4. Negotiating: Pricing, unit selection, payment milestones under discussion.\n"
            "5. Closed Won: Deal signed, booking token deposited, transaction completed.\n"
            "6. Closed Lost: Client chose competitor, postponed indefinitely, or dropped out.\n\n"
            "Moving leads between stages updates stage velocity metrics and recalculates weighted pipeline revenue."
        )
    },
    {
        "id": "tasks_followups",
        "category": "Tasks & Activities",
        "title": "CRM Tasks & Automated Follow-Ups",
        "citation": "Product Documentation → Tasks & Follow-Ups",
        "keywords": ["task", "tasks", "follow-up", "reminder", "overdue", "todo", "schedule task"],
        "summary": "Creating tasks, setting due dates and priorities, and tracking completion.",
        "content": (
            "Tasks help brokers track required client outreach, documentation requests, and site inspections. "
            "Manage tasks at /dashboard/tasks.\n"
            "- Priority Levels: Urgent (same-day action required), High, Normal, Low.\n"
            "- Statuses: Pending, In Progress, Completed, Cancelled.\n"
            "- Lead Association: Tasks can be linked directly to a specific Lead for continuous activity timeline tracking.\n"
            "- Reminders: The system triggers proactive notifications for overdue and upcoming tasks."
        )
    },
    {
        "id": "google_calendar",
        "category": "Calendar & Scheduling",
        "title": "Google Calendar Integration & Meeting Scheduling",
        "citation": "Product Documentation → Calendar Integration",
        "keywords": ["calendar", "google calendar", "meeting", "schedule", "viewing", "appointment", "availability", "slot"],
        "summary": "Connecting Google Calendar, checking availability slots, and booking client viewings.",
        "content": (
            "Brokers can connect their Google Calendar account securely via OAuth from /dashboard/settings. "
            "Once connected:\n"
            "- Meeting & Viewing Scheduling: Book client property tours directly with automated conflict checking.\n"
            "- Slot Availability: Checks broker's live busy/free slots before creating new bookings.\n"
            "- Sync: Meetings created in the CRM sync to Google Calendar, and updates reflect in the CRM timeline.\n"
            "- Revocation: Disconnecting or deleting your CRM account automatically revokes Google OAuth tokens."
        )
    },
    {
        "id": "team_rbac",
        "category": "Team & Access Control",
        "title": "Team Member Invitations & RBAC Roles",
        "citation": "Product Documentation → Team & RBAC",
        "keywords": ["team", "invite", "add member", "roles", "admin", "owner", "manager", "agent", "permissions"],
        "summary": "Team member roles, permission boundaries, and email invitation workflows.",
        "content": (
            "The platform enforces multi-role Role-Based Access Control (RBAC) scoped to your Organization:\n"
            "- Owner: Complete control over organization, billing, subscriptions, team members, and deletion.\n"
            "- Admin: Can invite team members, assign leads, view all workspace pipelines, and configure settings.\n"
            "- Manager: Can manage team pipelines, review performance, assign leads, and monitor tasks.\n"
            "- Agent: Can view and manage assigned leads, personal tasks, and personal calendar appointments.\n\n"
            "Inviting Members: Admins and Owners can invite colleagues at /dashboard/settings using their email. "
            "Invitations generate a secure, single-use token sent via email valid for 7 days."
        )
    },
    {
        "id": "billing_pricing",
        "category": "Billing & Subscriptions",
        "title": "Subscription Plans, Pricing & Billing",
        "citation": "Product Documentation → Billing & Plans",
        "keywords": ["billing", "pricing", "plan", "cost", "subscription", "upgrade", "trial", "starter", "pro", "razorpay"],
        "summary": "Official subscription plans, pricing tiers in INR, 7-day free trial, and payment security.",
        "content": (
            "Official Subscription Plans:\n"
            "- Starter Plan: ₹2,999 / month (indicative — not yet finalized, subject to change; Includes up to 500 Leads, Standard Pipeline, Basic AI Qualifying, Email support).\n"
            "- Pro / Enterprise Plan: ₹4,999 / month (indicative — not yet finalized, subject to change; Includes Unlimited Leads, Full AI Copilot OS, Google Calendar sync, Multi-Broker Team management, Advanced Analytics).\n\n"
            "Trial Policy:\n"
            "- Every new organization receives an active 7-day full-feature trial upon registration.\n\n"
            "Payment Processing:\n"
            "- Payments are processed securely via Razorpay in TEST MODE during current pre-production.\n"
            "- To view invoices or upgrade your plan, visit /dashboard/settings."
        )
    },
    {
        "id": "email_communication",
        "category": "Communication",
        "title": "Transactional Email Integration",
        "citation": "Product Documentation → Email Communication",
        "keywords": ["email", "brevo", "smtp", "send email", "draft email", "client email"],
        "summary": "Outbound email delivery via Brevo SMTP and follow-up email drafts.",
        "content": (
            "The platform integrates with Brevo SMTP for authenticated outbound communications:\n"
            "- Password reset verification links\n"
            "- Organization team member email invitations\n"
            "- Client follow-up emails and viewing confirmations\n\n"
            "Safety Policy: When asking the AI Copilot to send an email to a client, the Copilot creates "
            "a preview draft and requires your explicit confirmation before dispatching."
        )
    },
    {
        "id": "security_privacy",
        "category": "Security & Data Privacy",
        "title": "Tenant Isolation & Security Safeguards",
        "citation": "Product Documentation → Security & Privacy",
        "keywords": ["security", "privacy", "tenant", "password reset", "account deletion", "isolation", "safe"],
        "summary": "Multi-tenant data isolation, self-service password reset, and account deletion.",
        "content": (
            "Security guarantees:\n"
            "- Strict Tenant Isolation: Every query and tool execution is enforced by server-side organization_id and broker_id. No broker can ever access or modify another organization's data.\n"
            "- Self-Service Password Reset: Forgot password flow at /login sends a 1-hour cryptographic single-use token via Brevo email.\n"
            "- Google OAuth Token Revocation: Deleting your account permanently deletes all CRM data and automatically revokes Google OAuth refresh tokens at oauth2.googleapis.com/revoke.\n"
            "- Credentials Protection: AES-128-CBC + HMAC-SHA256 authenticated symmetric token encryption for stored third-party credentials."
        )
    },
    {
        "id": "limitations_roadmap",
        "category": "System Limitations",
        "title": "System Status, Limitations & Roadmap",
        "citation": "Product Documentation → System Limitations",
        "keywords": ["whatsapp", "limitations", "unsupported", "roadmap", "can you send whatsapp"],
        "summary": "Explicit product boundaries and currently disabled features.",
        "content": (
            "Current Product Status & Known Limitations:\n"
            "- WhatsApp Messaging: WhatsApp integration is currently DISABLED. The Copilot cannot send WhatsApp messages, execute WhatsApp tools, or simulate WhatsApp delivery. It will clearly state this limitation if requested.\n"
            "- Payment Gateway: Razorpay operates in TEST MODE; live customer credit card charging is not activated.\n"
            "- Arbitrary Code: The AI Copilot cannot execute arbitrary SQL or Python code. It operates exclusively through controlled, authorized backend tools."
        )
    }
]


def search_product_knowledge(query: str, category: Optional[str] = None, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves grounded product knowledge articles matching the user's query keywords.
    Guarantees deterministic, factual grounding for CRM features, billing, workflows, and settings.
    """
    if not query:
        return PRODUCT_KNOWLEDGE_BASE[:limit]

    terms = set(re.findall(r"\w+", query.lower()))
    scored_articles = []

    for article in PRODUCT_KNOWLEDGE_BASE:
        if category and article["category"].lower() != category.lower():
            continue

        score = 0
        keywords = [k.lower() for k in article.get("keywords", [])]
        title_words = set(re.findall(r"\w+", article["title"].lower()))
        content_lower = article["content"].lower()

        for term in terms:
            if term in keywords:
                score += 5
            for kw in keywords:
                if term in kw:
                    score += 2
            if term in title_words:
                score += 4
            if term in content_lower:
                score += 1

        if score > 0:
            scored_articles.append((score, article))

    scored_articles.sort(key=lambda x: x[0], reverse=True)
    results = [art for _, art in scored_articles[:limit]]

    # If no specific matches found, return platform overview and limitations
    if not results:
        results = [PRODUCT_KNOWLEDGE_BASE[0]]

    return results
