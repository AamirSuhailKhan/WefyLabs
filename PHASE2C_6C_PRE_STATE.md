# Phase 2C.6C System Freeze & Pre-State Baseline

## 1. Executive Freeze Summary
This report captures the frozen system baseline for WefyLabs at the commencement of **Phase 2C.6C: Production Product Truth & End-to-End Revenue Loop Certification**.

In accordance with Phase 0 freeze directives, all system configurations, git states, dependencies, database entities, and governance flags have been recorded directly from production runtime instances before any domain verification begins.

---

## 2. Infrastructure & Environment Freeze State

| Parameter | Authoritative Value | Source / Verification Method |
| :--- | :--- | :--- |
| **Git Commit** | `9bc40ca9ccf853c1ee02be54f63c33564a7d8410` | `git log -1` (Complete Level 3 code) |
| **Git Branch** | `level-3` | `git branch --show-current` |
| **Frontend Framework** | Next.js 15.5.24 / React 19.0.0 | `apps/web/package.json` |
| **Frontend Version** | `leadscore-web@0.1.0` | `apps/web/package.json` |
| **Backend Framework** | FastAPI 0.115.0 / Python 3.14.6 | `apps/api/pyproject.toml` |
| **Backend Version** | `leadscore-api@0.1.0` | `apps/api/pyproject.toml` |
| **Database Engine** | PostgreSQL 17.6 on x86_64-pc-linux-gnu | Supabase AWS ap-south-1 direct connection |
| **Database Migration** | `0042_phase2c_pilot_tables` | `alembic_version` table in public schema |
| **Redis Cache & Broker**| Upstash Redis 8.4.0 (Serverless) | Direct `redis.ping()` pong confirmed |
| **Celery Worker Engine**| Celery 5.4.0 (51 task queues, JSON serializer) | `app.celery_app.celery_app.conf` |
| **API Base URL** | `http://localhost:8000/api/v1` | `apps/web/.env.local` / `apps/api/.env` |
| **Frontend Origin** | `http://localhost:3000` | `apps/web/.env.local` |
| **OAuth Configuration**| Google OAuth Client ID `416262084725-...` | `apps/api/.env` (Redirect: `http://localhost:3000/auth/callback`) |

---

## 3. Governance & Autonomy Freeze State

```
RUNTIME:                         STAGE_1_SHADOW
AUTONOMY:                        0
EFFECTIVE AUTONOMY:              0
STAGE-2 ELIGIBILITY:             NOT_ELIGIBLE
GENUINE STAGE-1 DAYS:            4 / 14 (Enrolled: 2026-10-02)
VERIFIED HUMAN DECISIONS:        1 / 50 (Lead: Rajesh Kumar)
SECURITY P0 STATUS:              CLOSED
SECURITY P0.1 STATUS:            CLOSED
PROVIDER SIDE EFFECTS:           0
SYNTHETIC COMMERCIAL EVIDENCE:   0
AUTONOMOUS REVENUE ATTRIBUTION:  ₹0
```

---

## 4. Authoritative Production Pilot Tenant

The active production pilot tenant is registered in PostgreSQL table `pilot_tenants`:
- **Pilot ID**: `d153ea17-b2d3-40ab-b258-75951ef7de28`
- **Organization ID**: `a0317351-e076-493e-8b84-182f8c43666e`
- **Organization Name**: `Aamir Suhail's Agency`
- **Organization Slug**: `org-9d0620`
- **Authenticated Broker / Owner**: `c193be18-4a6a-4030-9089-f94c42119189`
- **Broker Name**: `Aamir Suhail` (`aamir.fresh@bmu.edu.in`)
- **Role**: `owner` (confirmed in `organization_members`)
- **Onboarding Status**: `ONBOARDED`
- **Subscription Status**: `trial`

---

## 5. Authoritative Domain Record Counts

### Pilot Tenant Entities (`a0317351-e076-493e-8b84-182f8c43666e`):
1. **Real Leads**: **3**
   - Amit Sharma (`2434cac9-3b94-49fb-a377-789f4ad785f6`)
   - Vikram Malhotra (`47d1dc97-2458-4dec-980f-a0d3afa24601`)
   - Rajesh Kumar (`1d3d636e-1460-4507-bc3c-2ac0f19f7250`)
2. **Real Property Listings**: **3**
   - Luxury 3BHK Penthouse in Marina Gate (`28060f30-aa07-479c-b97f-3a3d7a6f17bc`, ₹28,500,000)
   - Modern 2BHK Apartment in Downtown Heights (`056d7f57-fc63-4100-b8f7-1e34b683b515`, ₹12,500,000)
   - Sunny 2BHK Palm Grove Indiranagar (`93a0d570-c0c4-4583-b16d-ed19d25bbd25`, ₹5,200,000)
3. **Real Site Visits**: **1**
   - `1232912f-4db5-4f20-a3f8-c33454ed6b48` (Vikram Malhotra, Luxury 3BHK Penthouse, `ATTENDED`)
4. **Real Deals**: **1**
   - `9de15f6a-f7b6-4632-947f-44346260d3f2` (`DEAL-2026-001`, Vikram Malhotra, Agreed: ₹22,000,000)
5. **Real Deal Bookings**: **1**
   - `40c6ad98-06af-4d0a-9a38-8b6bc96a48ac` (`BKG-2026-001`, Booked: ₹22,000,000, Token: ₹1,100,000, Confirmed)
6. **Real Deal Commissions**: **1**
   - `a447aef4-7f97-435f-b531-90ce61b3b20a` (`INV-COM-2026-001`, Gross: ₹440,000, Net: ₹396,000, Approved)
7. **Pilot Observations**: **1**
   - `6fb1586d-54c1-49e6-afa2-f33c4c305b00` (Lead: Rajesh Kumar, Mode: `SHADOW`)
8. **Verified Human Decisions**: **1**
   - `c7c8c0cb-5db3-4056-92d9-2e402de1c73d` (Actor: Aamir Suhail, `SUMMARIZE_LEAD`)

### Global Database Counts (All 11 Organizations):
- `organizations`: 11
- `users`: 11
- `brokers`: 11
- `organization_members`: 11
- `leads`: 7
- `property_listings`: 9
- `revenue_opportunities`: 3
- `deals`: 1
- `deal_bookings`: 1
- `deal_commissions`: 1
- `deal_transactions`: 2
- `site_visits`: 1
- `tasks`: 10
- `meetings`: 1
- `pilot_tenants`: 1
- `pilot_observations`: 1
- `pilot_human_decisions`: 1
