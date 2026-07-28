# LeadScore — Project Rules & Architectural Guidelines

This document serves as the single source of truth for engineering conventions, tech stack choices, API standards, and system architecture for **LeadScore** — the AI-powered lead qualification platform for Indian real estate brokers.

---

## 1. Tech Stack & Version Specifications

| Component | Technology | Version / Spec |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI | 0.115+ |
| **Language** | Python | 3.11+ / 3.14 |
| **Database** | PostgreSQL | 16 (Async SQLAlchemy 2.0+) |
| **Migrations** | Alembic | 1.13+ |
| **Validation** | Pydantic | 2.9+ (v2 Mode) |
| **Async Cache / Queue** | Redis | 7 |
| **Task Queue** | Celery | 5.4+ |
| **AI LLM Engine** | OpenAI API | GPT-4o with GPT-4o-mini fallback |
| **WhatsApp Integration**| 360dialog WABA API | `/v1/messages` endpoint |
| **Payments** | Razorpay Python SDK | Subscriptions API |
| **Frontend Framework** | Next.js | 14+ (App Router, TypeScript) |
| **Styling** | Tailwind CSS / Vanilla CSS | Modern dark mode, glassmorphism |
| **Monorepo Manager** | Turbo / pnpm | Workspace layout |

---

## 2. Monolith Architecture & Project Structure

- **No Microservices. No Kubernetes.** The entire backend is built as a single modular monolith inside `apps/api`.
- Directory structure:
  ```plain
  apps/api/
  ├── app/
  │   ├── main.py              # FastAPI entry point with lifespan
  │   ├── config.py            # Settings with env vars
  │   ├── database.py          # Async SQLAlchemy engine + session
  │   ├── dependencies.py      # Auth & DB session dependencies
  │   ├── models/              # SQLAlchemy 2.0 Models
  │   ├── schemas/             # Pydantic v2 Schemas
  │   ├── services/            # Core Business Services (AI, WhatsApp, Scorer, FollowUp, Razorpay)
  │   ├── tasks/               # Celery async tasks & Beat schedules
  │   ├── modules/             # Auth & Lead Domain Modules
  │   └── routers/             # API Endpoint Routers
  ```

---

## 3. Core Database & Model Guidelines

- **Async Everywhere**: All DB operations must use `AsyncSession` and `await db.execute(select(...))`.
- **Soft Deletes**: `Lead` records use a `deleted_at` TIMESTAMPTZ column. All default queries MUST include `Lead.deleted_at.is_(None)`.
- **Multi-Tenant Isolation**: Every lead operation must strictly enforce `Lead.broker_id == current_broker.id`.
- **Cross-Database Compatibility**:
  - PostgreSQL native `ARRAY(String)` and `JSONB` columns must use `.with_variant(JSON(), "sqlite")` so SQLite in-memory pytest fixtures run seamlessly.
- **Relationship Loading**: Use `selectinload(...)` on AsyncSession queries to prevent `greenlet_spawn` lazy loading runtime errors.

---

## 4. Auth, Rate Limiting & Trial Enforcement

- **Phone Format**: Indian phone numbers must be formatted and normalized to `+91XXXXXXXXXX` (10 digits starting with 6, 7, 8, or 9).
- **Rate Limiting**: Auth endpoints (`/register`, `/login`) are rate-limited to 5 requests/minute per IP/email.
- **Trial Policy**: New brokers receive a 7-day trial starting from registration. When trial expires without an active paid subscription, protected operations (e.g. creating leads) return HTTP 403 `TRIAL_EXPIRED`.

---

## 5. WhatsApp & AI Qualification Engine

- **360dialog Webhook (`POST /api/v1/whatsapp/webhook`)**:
  - Always returns HTTP 200 OK to prevent infinite 360dialog webhook retries.
  - Automatically identifies sender: registered Broker vs existing Lead vs Unknown.
  - Broker forwarding: Forwarding a 10-digit lead number creates a `whatsapp_forward` lead, notifies the broker, and initiates AI qualification with the lead.
- **AI Conversation Flow**:
  - OpenAI GPT-4o asks max 5 qualifying questions (budget, locality, property type, transaction type, timeline, loan status).
  - Keeps messages concise (under 160 characters when possible).
  - Uses structured JSON mode output. Max 8 bot messages per lead.
- **PRD Section 8 Lead Scoring**:
  - Evaluates ExtractedData against deterministic point rules:
    - **HOT** (`hot_points >= 3`): Confidence `70% - 95%`.
    - **WARM** (`hot_points >= 1` or `warm_points >= 2`): Confidence `50% - 75%`.
    - **COLD**: Confidence `10% - 30%`.
  - Audits every qualification run in `scores` table with JSONB `extracted_data`.

---

## 6. Automated Follow-Ups & Billing

- **Follow-Up Automation**:
  - Schedules 3 follow-ups at T+24h, T+48h, and T+72h upon qualification.
  - Automatically cancels pending follow-ups when lead replies via WhatsApp or when lead stage/status moves to `closed_won`, `closed_lost`, `converted`, or `lost`.
  - Hourly Celery Beat task (`check_and_schedule_followups`) dispatches due follow-ups.
- **Razorpay Subscription Billing**:
  - Hardcoded paise plans (`starter_monthly` ₹2,999, `starter_annual` ₹29,999, `pro_monthly` ₹4,999, `pro_annual` ₹49,999).
  - Verifies HMAC SHA256 webhook signatures (`X-Razorpay-Signature`).
  - Processes `subscription.activated`, `charged`, `cancelled`, and `expired` events idempotently.

---

## 7. Testing & Quality Requirements

- **100% Passing Test Requirement**: Never declare a feature or fix complete without running:
  ```bash
  python -m pytest -v
  ```
