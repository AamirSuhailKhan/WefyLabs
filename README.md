# 🏠 WefyLabs — AI-Powered Lead Qualification Platform for Real Estate Brokers

**WefyLabs** (formerly BeetleLabs) is an enterprise-grade AI lead qualification and revenue autopilot platform built specifically for real estate brokers and sales teams. Operating on `wefylabs.com`, it integrates AI lead scoring, instant multi-channel qualification, visual Kanban pipelines, automated CRM workflows, calendar site-visit scheduling, and proactive revenue opportunities.

---

## 🛠 Tech Stack

- **Backend**: FastAPI 0.115+, Python 3.11+, Async SQLAlchemy 2.0+, Alembic 1.13+, Pydantic 2.9+, Uvicorn 0.30+
- **Database & Cache**: PostgreSQL 16, Redis 7
- **Task Queue**: Celery 5.4+ with Celery Beat
- **AI & Integrations**: OpenAI GPT-4o, 360dialog WhatsApp Business API, Razorpay Subscriptions SDK
- **Frontend**: Next.js 14+ (App Router, TypeScript, Tailwind CSS, Framer Motion)
- **Monorepo & CI/CD**: TurboRepo, pnpm, Docker, GitHub Actions, Railway, Vercel

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- [Docker & Docker Compose](https://docs.docker.com/get-docker/)
- [Node.js 18+ & pnpm](https://pnpm.io/)
- [Python 3.11+](https://www.python.org/)

### 2. One-Command Boot

1. **Clone the repository and set up environment variables**:
   ```bash
   git clone https://github.com/leadscore/leadscore-crm.git
   cd leadscore-crm
   cp .env.example .env
   ```

2. **Install Node.js dependencies**:
   ```bash
   pnpm install
   ```

3. **Start all backend services (PostgreSQL, Redis, FastAPI, Celery Worker, Celery Beat)**:
   ```bash
   docker-compose up --build -d
   ```

4. **Run Database Migrations**:
   ```bash
   cd apps/api
   poetry run alembic upgrade head
   ```

5. **Start Frontend & Local Servers**:
   ```bash
   pnpm dev
   ```

---

## 🌐 Endpoints & Interactive Docs

Once running, access the services locally:

- **Web Dashboard**: `http://localhost:3000`
- **FastAPI OpenAPI Swagger Documentation**: `http://localhost:8000/docs`
- **Health Check Endpoint**: `http://localhost:8000/health`

---

## 🧪 Running the Test Suite

LeadScore comes with a 100% passing automated test suite covering authentication, broker profiles, lead CRUD, 360dialog WhatsApp webhooks, AI qualification scoring, Celery follow-ups, and Razorpay billing:

```bash
cd apps/api
poetry run pytest -v
```

---

## 🚀 Production Deployment

### 1. Deploy API (Railway)
Make sure Railway CLI is installed (`npm i -g @railway/cli`) and run:
```bash
./scripts/deploy-api.sh
```

### 2. Deploy Web Dashboard (Vercel)
Make sure Vercel CLI is installed (`npm i -g vercel`) and run:
```bash
./scripts/deploy-web.sh
```

---

## 📄 License
Commercial / Proprietary — LeadScore Inc. All rights reserved.
