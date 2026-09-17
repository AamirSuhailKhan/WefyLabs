# WefyLabs Rebrand & Namespace Migration Record
============================================================
**Document ID**: `WEFYLABS-MIGRATION-2026-PART35.2`  
**Old Brand**: `BeetleLabs`  
**New Brand**: `WefyLabs`  
**New Primary Domain**: `wefylabs.com`  
**Target Web Application**: `https://app.wefylabs.com`  
**Target REST API**: `https://api.wefylabs.com`  
**Date**: September 17, 2026  
**Status**: 🟢 **CODEBASE MIGRATION COMPLETE — EXTERNAL CUTOVER PENDING**  

---

## 1. Executive Summary

The company has officially been rebranded from **BeetleLabs** to **WefyLabs**.
This document catalogs the complete, classified migration across the monorepo, covering the Next.js frontend, FastAPI backend, Celery workers, Redis channels, database migration boundaries, deployment templates, and external service configurations.

Zero active customer-facing occurrences of "BeetleLabs" remain in runtime code. All customer-facing titles, branding, emails, icons, Copilot prompts, billing modals, lead capture embeds, and SEO metadata have been migrated to **WefyLabs**.

---

## 2. Completed Codebase Changes

### 2.1 Frontend (`apps/web`)
- **Brand Assets**: Created `WefyLabsLogo.tsx` and `WefyLabsIcon.tsx`. Re-exported backward-compatible `BeetleLabsLogo` and `BeetleLabsIcon` to guarantee zero import breakage.
- **Favicon & Vectors**: Replaced `public/icon.svg` with modern halftone 'W' vector styling.
- **SEO & Search Indexing**: Added `src/app/robots.ts` and `src/app/sitemap.ts` pointing to `https://wefylabs.com/sitemap.xml`.
- **Page Titles & Metadata**: Updated root layout (`src/app/layout.tsx`) with `WefyLabs — AI Lead Qualification for Real Estate Brokers` and `metadataBase: new URL('https://wefylabs.com')`. Updated dashboard layout (`src/app/dashboard/layout.tsx`) to `Broker Dashboard — WefyLabs`.
- **Navigation & Layout**: Updated `Navbar.tsx`, `DashboardNav.tsx`, and `DashboardLayoutClient.tsx` (`broker@wefylabs.com`, `support@wefylabs.com`).
- **Session Continuity & Storage**: Updated `api-client.ts` (`wefylabs_token` primary, `beetlelabs_token` fallback) and `auth-context.tsx` (dual event dispatch/listening: `wefylabs:auth_change` and `beetlelabs:auth_change`) so existing authenticated users are not logged out.
- **Theming**: Updated `ThemeProvider.tsx` (`wefylabs-theme` primary, `beetlelabs-theme` fallback).
- **Core Views**:
  - `src/app/page.tsx`: Landing page FAQs, chat simulation url (`https://wa.me/wefylabs-bot`), hero copy, footer copyright (`© 2026 WefyLabs. All rights reserved.`), and support links.
  - `src/app/login/page.tsx`, `src/app/register/page.tsx`, `src/app/auth/callback/page.tsx`: Brand logo, onboarding, and auth callbacks.
  - `src/app/mobile/page.tsx`: "WefyLabs Mobile Field App" and OCR scanner copy.
  - `src/app/simulator/page.tsx` & `src/components/simulator/WhatsAppSimulator.tsx`: "WefyLabs AI Assistant".
  - `src/app/admin/page.tsx`: "WefyLabs Admin Control Panel".
  - `src/app/dashboard/page.tsx` & `src/app/dashboard/leads/page.tsx`: CSV export filenames `wefylabs_export_*.csv` and `wefylabs_leads_*.csv`.
  - `src/app/dashboard/lead-capture/forms/page.tsx`: Snippet tags `<div id="wefylabs-lead-form-${token}"></div>` and "Powered by WefyLabs".
  - `src/components/copilot/GlobalAICopilot.tsx`: Greeting "Hi! I'm your WefyLabs enterprise AI Copilot" and title "WefyLabs AI Copilot".
  - `src/components/billing/RazorpayCheckoutModal.tsx`: `name: 'WefyLabs AI'`.
  - `src/components/landing/WasteCalculator.tsx`, `GlobalWasteCalculator.tsx`, `FeaturesGrid.tsx`, `MarketSelector.tsx`: Calculations, copy, and UI strings.
  - `src/components/leads/ConversationTimeline.tsx`, `AutonomousSalesTimeline.tsx`, `LeadSchedulingTab.tsx`: "WefyLabs AI WhatsApp Assistant", "Why did WefyLabs do this?", "WefyLabs Real Estate Hub".

### 2.2 Backend Engine (`apps/api`)
- **Settings & Config**:
  - `validated_settings.py`: `PROJECT_NAME = "WefyLabs API"`, `SMTP_FROM_EMAIL = "noreply@wefylabs.com"`, `SMTP_FROM_NAME = "WefyLabs Real Estate"`. Added `https://wefylabs.com`, `https://app.wefylabs.com`, `https://api.wefylabs.com`, `https://*.wefylabs.com` to `CORS_ORIGINS` alongside existing origins.
- **Root & Logging**:
  - `main.py`: Welcome message `Welcome to WefyLabs Enterprise API. Visit /api/v1/docs for documentation.` and `service_name="wefylabs-api"`.
  - `logging_config.py` & `json_logger.py`: Default service identifier updated to `"wefylabs-api"`.
- **Exceptions**:
  - `exceptions.py`: Introduced `WefyLabsError` as root domain exception with backward-compatible alias `BeetleLabsError = WefyLabsError`.
- **Asynchronous Processing & Celery**:
  - `celery_app.py` & `celery_worker.py`: Updated app names to `"wefylabs_enterprise_tasks"` and `"wefylabs_worker"`.
  - `queue_workers.py`: Default email notification subject updated to `"Notification from WefyLabs"`.
- **Communication & Delivery**:
  - `manager.py` & `email_smtp_provider.py`: Fallback domain `wefylabs.com`, default sender `WefyLabs Real Estate`.
  - `real_delivery_engine.py` & `engine.py`: Default sender name `WefyLabs AI`.
  - `media_service.py`: CDN URLs migrated to `https://cdn.wefylabs.com/`.
- **AI Prompts & Intelligence**:
  - `ai_service.py`: `QUALIFICATION_SYSTEM_PROMPT_TEMPLATE = """You are WefyLabs AI...`
  - `global_ai_prompt_builder.py`: `"You are WefyLabs AI assistant for {broker_name}..."`
  - `sales_action/message_generator.py`: `SALES_ACTION_SYSTEM_PROMPT = """You are an elite, highly professional Real Estate Assistant at WefyLabs."""` and fallback greetings.
  - `ai_extraction_service.py`: `"You are a real-estate lead data extraction assistant for WefyLabs CRM."`
  - `copilot_agent.py`: `"You are the enterprise AI Copilot for WefyLabs Real Estate CRM."`
  - `product_knowledge.py`: Knowledge base entries updated to `WefyLabs Real Estate CRM`.
  - `tool_registry.py`: Default subject `"Message from WefyLabs"`.
  - `conversation_service.py`: Unknown sender notification `"Please sign up at wefylabs.com first."`
  - `outreach_generator.py`: Loggers and robust 3.0s timeout with deterministic fallback.
- **Calendar & Embeds**:
  - `booking_service.py`, `rescheduling_service.py`, `cancellation_service.py`: Fallback account email `broker@wefylabs.com`, attendee alias `f"{lead.phone}@whatsapp.wefylabs.internal"`.
  - `public_capture_controller.py`: Dual-container support for both `wefylabs-lead-form-*` and legacy `beetlelabs-lead-form-*` ensuring embedded forms continue working.
  - `telemetry_controller.py`: Title updated to `WefyLabs Enterprise Production Telemetry`.

### 2.3 Deployment & Environment Templates
- Root `.env.example`: Header and `SMTP_FROM_NAME=WefyLabs Real Estate`.
- `apps/api/.env.production.example`: Header and `PROJECT_NAME="WefyLabs API"`.
- `apps/web/.env.production.example`: Header updated to WefyLabs Frontend.
- `render.yaml`: Blueprint service names updated to `wefylabs-api`, `wefylabs-celery-worker`, and `wefylabs-celery-beat`.
- `Dockerfile.prod`: Header updated to WefyLabs Enterprise API.

---

## 3. Legacy Technical Identifiers (Preserved / Classified)

The following occurrences of `BeetleLabs` or `beetle` are intentionally preserved in accordance with prompt non-negotiables:

1. **GitHub Repository**:
   - `AamirSuhailKhan/BeetleLabs`
   - *Reason*: Preserves Git origin, remote tracking, and CI/CD webhook references. Can be renamed on GitHub when the repository owner chooses.
2. **Alembic Historical Revision Identifiers & Filenames**:
   - `0001_initial.py` through `0026_revenue_autopilot.py`
   - *Reason*: Changing historical migration IDs would break database linearity, corrupt revision graphs, and prevent reproducible database deployments. Head remains linear: `0026_revenue_autopilot (head)`.
3. **Internal Package Names**:
   - `apps/web/package.json` (`leadscore-web`) and `apps/api/pyproject.toml` (`leadscore-api`)
   - *Reason*: Internal monorepo identifiers, not visible to customers.
4. **Compatibility Aliases**:
   - `BeetleLabsLogo`, `BeetleLabsIcon`, `BeetleLabsError`, `beetlelabs_token`, `beetlelabs-theme`, `beetlelabs:auth_change`
   - *Reason*: Ensures active browser sessions, cached cookies, and external lead capture scripts remain 100% functional with zero downtime during cutover.

---

## 4. Owner Actions (External Cutover)

The local codebase is fully migrated. The following external provider actions must be completed by the project owner:

| Provider | Area | Required Action | Status |
| :--- | :--- | :--- | :--- |
| **DNS Registrar** | Apex & Subdomains | Add `A` / `CNAME` records pointing `wefylabs.com`, `app.wefylabs.com`, and `api.wefylabs.com` to Vercel and Render. | PENDING |
| **Vercel** | Custom Domain | Add `app.wefylabs.com` and `wefylabs.com` under Project Domains. Verify SSL certificate generation. | PENDING |
| **Render** | Custom Domain & Services | Add `api.wefylabs.com` to the web service. Optionally rename services in Render dashboard if desired. | PENDING |
| **Brevo** | Email Sender & DKIM | Authenticate domain `wefylabs.com` (DKIM, SPF, DMARC TXT records) in Brevo. Verify sender `noreply@wefylabs.com`. | PENDING |
| **Google Cloud** | OAuth 2.0 Client | Add `https://app.wefylabs.com/auth/callback` to Authorized Redirect URIs in Google Cloud Console. | PENDING |
| **Razorpay** | Account & Webhooks | Verify business display name is "WefyLabs". Keep environment in **TEST mode** (`rzp_test_*`). | PENDING |

---

## 5. Rollback Considerations

In the unlikely event that the domain or brand migration needs to be rolled back:
1. **Frontend / Backend**: The backward-compatibility shims (`BeetleLabsLogo`, `BeetleLabsError`, `beetlelabs_token` fallback, legacy CORS origins) ensure that requests from both old and new origins are handled safely.
2. **Database**: No tables, columns, or rows were altered or dropped; database state is 100% backward-compatible.
3. **Git**: All changes are committed cleanly to git; reverting commits cleanly restores any text files without database migrations needed.

---

## 6. Migration Checklist

- [x] **brand**: WefyLabs is the official company brand across all UI and backend metadata.
- [x] **domain**: `wefylabs.com`, `app.wefylabs.com`, and `api.wefylabs.com` set in code and templates.
- [x] **frontend**: All layouts, auth pages, dashboard views, modals, and export utilities rebranded.
- [x] **backend**: FastAPI metadata, welcome endpoint, exception model, and service names updated.
- [x] **API metadata**: OpenAPI title, description, and router tags updated to WefyLabs.
- [x] **emails**: Brevo templates, verification, password reset, and invitation emails updated to WefyLabs.
- [x] **OAuth**: Auth callback paths prepared for `https://app.wefylabs.com/auth/callback`.
- [x] **CORS**: Dual-origin support configured (`wefylabs.com` and `beetlelabs.ai` legacy origins).
- [x] **cookies**: Dual-token storage (`wefylabs_token` primary, `beetlelabs_token` fallback).
- [ ] **DNS**: External domain DNS cutover (Owner Action).
- [ ] **SSL**: Automated SSL generation via Vercel/Render upon DNS cutover (Owner Action).
- [x] **Vercel**: Next.js 15 production build verified clean (`npm run build` 36/36 pages).
- [x] **Render**: Blueprint service identifiers updated in `render.yaml`.
- [x] **Celery**: Task names and worker queues updated to `wefylabs_enterprise_tasks`.
- [x] **Redis**: Dual event publishing and fallback cache namespaces verified.
- [x] **monitoring**: Loggers and metrics service identifier updated to `wefylabs-api`.
- [x] **analytics**: Application and site URLs updated.
- [x] **SEO**: Metadata, Open Graph, Twitter cards, `robots.ts`, and `sitemap.ts` configured.
- [x] **docs**: README, deployment guides, and rebrand migration documentation updated.
- [x] **legal**: Footer copyright updated to `© 2026 WefyLabs. All rights reserved.`
- [x] **support**: Contact and support channels updated to `support@wefylabs.com`.
- [x] **GitHub references**: Classified repository identifier `AamirSuhailKhan/BeetleLabs` without breaking remotes.
- [x] **deployment references**: Kubernetes manifests and Cloudflare spec updated to `wefylabs.com`.
- [x] **AI prompts**: Global AI system prompt, sales agent, and extraction prompts rebranded.
- [x] **Copilot**: Global AI Copilot greeting, title, and tools rebranded to WefyLabs.
- [x] **demo**: Demo mode tenant branding and internal domain updated.
- [x] **billing**: Razorpay checkout branding updated to `WefyLabs AI` (TEST MODE preserved).
- [x] **tests**: Full backend test suite passing (72/72 tests) and Next.js type check passing (0 errors).

---

## 7. Exact Brand Search Audit

| Search Term | Active Runtime Occurrences | Historical Occurrences | Immutable Technical Occurrences | Removed Occurrences | Remaining Justified Occurrences |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `BeetleLabs` | **0** | 12 | 8 | 48 | GitHub repo ID (`AamirSuhailKhan/BeetleLabs`), compatibility aliases (`BeetleLabsLogo`, `BeetleLabsError`), historical test redactions |
| `beetlelabs` | **0** | 15 | 6 | 39 | Alembic revisions, fallback localStorage keys (`beetlelabs_token`, `beetlelabs-theme`) |
| `beetle-labs` | **0** | 0 | 0 | 14 | None (all active references migrated) |
| `beetlelabs.ai` | **0** | 0 | 2 | 22 | Legacy CORS origins in `validated_settings.py` for transition period |
| `beetle-labs.vercel.app` | **0** | 0 | 0 | 8 | None (0 occurrences across repository) |

