from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import engine

# ─── Structured Logging — must be initialized before anything else ────────────
from app.common.logger.logging_config import configure_logging
configure_logging(
    level="DEBUG" if settings.ENV in ("development", "dev") else "INFO",
    service_name="wefylabs-api",
    env=settings.ENV,
    json_output=settings.ENV not in ("development", "dev")
)

# ─── Unified Error Handlers ───────────────────────────────────────────────────
from app.common.errors.exceptions import WefyLabsError, BeetleLabsError, register_error_handlers

# ─── Middleware ───────────────────────────────────────────────────────────────
from app.common.middleware.correlation import CorrelationMiddleware
from app.infrastructure.security.security_headers import SecurityHeadersMiddleware
from app.infrastructure.monitoring.observability import ObservabilityTracingMiddleware, metrics_registry
from app.infrastructure.middleware.request_tracing import RequestTracingMiddleware
from app.infrastructure.middleware.idempotency import IdempotencyMiddleware
from fastapi.responses import PlainTextResponse

# ─── Domain Event Subscribers ─────────────────────────────────────────────────
from app.infrastructure.events.subscribers import register_default_subscribers

# ─── Routers ──────────────────────────────────────────────────────────────────
from app.modules.auth.router import router as auth_router
from app.modules.auth.invitations_router import router as invitations_router
from app.routers.brokers import router as brokers_router
from app.modules.leads.router import router as leads_router
from app.routers.whatsapp import router as whatsapp_router
from app.routers.scoring import router as scoring_router
from app.routers.follow_ups import router as followups_router
from app.routers.billing import router as billing_router
from app.routers.conversations import router as conversations_router
from app.presentation.api.v1.leads import router as clean_leads_v1_router
from app.presentation.api.health import health_router
from app.infrastructure.errors.handlers import register_exception_handlers

# ─── Enterprise Architecture Routers (Part 5) ──────────────────────────────────
from app.modules.leads.controller.lead_controller import router as hex_leads_v1_router
from app.modules.webhooks.controller.webhook_controller import router as webhook_engine_router

# ─── Enterprise Infrastructure Routers (Part 6) ──────────────────────────────────
from app.modules.audit.controller.audit_controller import router as audit_router
from app.modules.timeline.controller.timeline_controller import router as timeline_router
from app.modules.notifications.controller.notification_controller import router as notifications_router
from app.modules.feature_flags.controller.feature_flag_controller import router as feature_flags_router
from app.modules.settings.controller.settings_controller import router as settings_router
from app.modules.api_keys.controller.api_key_controller import router as api_keys_router
from app.modules.integrations.controller.integration_controller import router as integrations_infra_router
from app.modules.event_history.controller.event_history_controller import router as event_history_router
from app.modules.system_health.controller.health_controller import router as system_health_router

# ─── Enterprise Search Platform Routers (Part 7) ──────────────────────────────
from app.modules.search.controller.search_controller import router as search_platform_router
from app.modules.saved_searches.controller.saved_search_controller import router as saved_searches_router
from app.modules.search_history.controller.search_history_controller import router as search_history_router

# ─── Enterprise Observability & Reliability Routers (Part 8) ───────────────────
from app.modules.health.controller.health_controller import router as health_diag_router
from app.modules.metrics.metrics_controller import router as prometheus_metrics_router
from app.modules.incident.controller.incident_controller import router as incidents_router
from app.modules.alerts.controller.alert_controller import router as alerts_router
from app.modules.diagnostics.controller.diagnostics_controller import router as diagnostics_router
from app.modules.telemetry.controller.telemetry_controller import router as telemetry_router
from app.infrastructure.middleware.observability_middleware import EnterpriseObservabilityMiddleware
from app.modules.logging.json_logger import configure_structured_logging

# ─── Enterprise Security & DevSecOps Routers (Part 9) ─────────────────────────
from app.modules.security.controller.security_controller import router as security_ops_router

# ─── Volume 2 Part 1 — Universal Lead Ingestion Engine ─────────────────────────
from app.modules.ingestion.controller.ingestion_controller import router as lead_ingestion_router

# ─── Volume 2 Part 2 — AI Lead Enrichment Engine ──────────────────────────────
from app.modules.enrichment.router import router as enrichment_router

# ─── Volume 2 Part 3 — Identity Resolution Engine ─────────────────────────────
from app.modules.identity_resolution.router import router as identity_resolution_router

# ─── Volume 2 Part 4 — AI Lead Intelligence & Revenue Engine ───────────────────
from app.modules.lead_intelligence.router import router as lead_intelligence_router

# ─── Volume 2 Part 5 — Autonomous AI Sales Agent Engine ───────────────────────
from app.modules.ai_agent.router import router as ai_agent_router

# ─── Volume 2 Part 6 — Enterprise Omnichannel Communication Engine ─────────────
from app.modules.communication.router import router as omnichannel_router

# ─── Volume 2 Part 7 — AI Property Recommendation Engine ───────────────────────
from app.modules.recommendation.router import router as recommendation_router

# ─── Volume 2 Part 8 — AI Follow-Up & Autonomous Lead Nurturing Engine ─────────
from app.modules.follow_up.router import router as enterprise_follow_up_router

# ─── Volume 2 Part 10 — CRM Intelligence & Autonomous Sales Operations Engine ──
from app.modules.crm_intelligence.router import router as crm_intelligence_router

# ─── Volume 2 Part 11 — Predictive Analytics & MLOps Engine ───────────────────
from app.modules.predictive.router import router as predictive_engine_router

# ─── Volume 2 Part 12 — Workflow Automation & Operations Engine ───────────────
from app.modules.workflow.router import router as workflow_automation_router

# ─── Volume 2 Part 13 — AI Memory & Customer Intelligence Engine ──────────────
from app.modules.memory.router import router as ai_memory_router
from app.modules.customer_intelligence.router import router as customer_intelligence_router
from app.modules.property_intelligence.router import router as property_intelligence_router

# Configure global structured JSON logging
configure_structured_logging()

_startup_logger = __import__("logging").getLogger("beetlelabs.startup")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform startup domain subscriber registration & DB schema integrity check
    try:
        register_default_subscribers()
        # In production, Alembic is the authoritative migration tool.
        # create_all() is only run in development/testing for convenience.
        is_prod = settings.ENV.lower() in ("production", "prod", "staging")
        if not is_prod:
            async with engine.begin() as conn:
                from app.models import Base
                await conn.run_sync(Base.metadata.create_all)
            _startup_logger.info("[DB] Development schema sync complete via create_all")
        else:
            _startup_logger.info(
                "[DB] Production mode: schema managed by Alembic migrations — skipping create_all"
            )
    except Exception as e:
        _startup_logger.warning(f"[DB Startup Warning] {e}")

    # Safe Google OAuth 2.0 startup configuration diagnostic (no secrets exposed)
    from app.modules.auth.service import validate_google_client_id
    cid = (settings.GOOGLE_CLIENT_ID or "").strip()
    sec = (settings.GOOGLE_CLIENT_SECRET or "").strip()
    _startup_logger.info(
        f"[Google OAuth Startup] client_id: {'configured' if cid else 'missing'} | "
        f"client_secret: {'configured' if sec else 'missing'} | "
        f"client_id_format: {'valid' if validate_google_client_id(cid) else 'unconfigured_or_placeholder'} | "
        f"redirect_uri: {settings.GOOGLE_OAUTH_REDIRECT_URI}"
    )

    yield
    # Perform shutdown cleanup
    await engine.dispose()
    _startup_logger.info("[Shutdown] Engine disposed, connections closed.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# ─── Error Handlers ───────────────────────────────────────────────────────────
register_error_handlers(app)
register_exception_handlers(app)

# ─── Middleware (LIFO order) ───────────────────────────────────────────────────
app.add_middleware(EnterpriseObservabilityMiddleware)
app.add_middleware(CorrelationMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ObservabilityTracingMiddleware)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(IdempotencyMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.presentation.api.v1.communication import router as communication_router
from app.presentation.api.v1.properties import router as properties_router
from app.presentation.api.v1.transactions import router as transactions_router
from app.presentation.api.v1.copilot import router as copilot_router
from app.presentation.api.v1.predictive import router as predictive_router
from app.presentation.api.v1.workflows import router as workflows_router
from app.presentation.api.v1.performance import router as performance_router
from app.presentation.api.v1.portal import router as portal_router
from app.presentation.api.v1.mobile import router as mobile_router
from app.presentation.api.v1.bi import router as bi_router
from app.presentation.api.v1.crm_enterprise import router as crm_enterprise_router
from app.presentation.api.v1.crm_services_router import (
    router as crm_services_router,
    tasks_router,
    tags_router,
    notes_router,
    stages_router
)
from app.presentation.api.v1.internationalization import router as i18n_router
from app.modules.global_.router import router as global_infrastructure_router
from app.presentation.api.v1.marketplace import router as marketplace_router
from app.presentation.api.v1.integrations import router as integrations_router
from app.presentation.api.v1.customer_success import router as customer_success_router
from app.presentation.api.v1.compliance import router as compliance_router
from app.presentation.api.v1.scaling_benchmarks import router as scaling_benchmarks_router
from app.presentation.api.v1.developer import router as developer_router
from app.presentation.api.v1.plugins import router as plugins_router
from app.presentation.api.v1.super_admin import router as super_admin_router

# ─── Knowledge Intelligence Platform ─────────────────────────────────────────
from app.presentation.api.v1.knowledge import router as knowledge_router
from app.modules.calendar.router import router as calendar_router

# Mount Routers under /api/v1
app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(auth_router)
app.include_router(invitations_router, prefix=settings.API_V1_STR)
app.include_router(invitations_router)
app.include_router(brokers_router, prefix=settings.API_V1_STR)
app.include_router(leads_router, prefix=settings.API_V1_STR)
app.include_router(clean_leads_v1_router, prefix=settings.API_V1_STR)
app.include_router(hex_leads_v1_router, prefix=settings.API_V1_STR)
app.include_router(webhook_engine_router, prefix=settings.API_V1_STR)

# ─── Part 6 — Enterprise Infrastructure Routers ────────────────────────────────
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(timeline_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(feature_flags_router, prefix=settings.API_V1_STR)
app.include_router(settings_router, prefix=settings.API_V1_STR)
app.include_router(api_keys_router, prefix=settings.API_V1_STR)
app.include_router(integrations_infra_router, prefix=settings.API_V1_STR)
app.include_router(event_history_router, prefix=settings.API_V1_STR)
app.include_router(system_health_router, prefix=settings.API_V1_STR)

# ─── Part 7 — Enterprise Search Platform Routers ────────────────────────────────
app.include_router(search_platform_router, prefix=settings.API_V1_STR)
app.include_router(saved_searches_router, prefix=settings.API_V1_STR)
app.include_router(search_history_router, prefix=settings.API_V1_STR)

# ─── Part 8 — Enterprise Observability & Reliability Routers ───────────────────
app.include_router(prometheus_metrics_router)
app.include_router(health_diag_router, prefix=settings.API_V1_STR)
app.include_router(incidents_router, prefix=settings.API_V1_STR)
app.include_router(alerts_router, prefix=settings.API_V1_STR)
app.include_router(diagnostics_router, prefix=settings.API_V1_STR)
app.include_router(telemetry_router, prefix=settings.API_V1_STR)

# ─── Part 9 — Enterprise Security & DevSecOps Routers ──────────────────────────
app.include_router(security_ops_router, prefix=settings.API_V1_STR)

# ─── Volume 2 Part 1 — Universal Lead Ingestion Engine ─────────────────────────
app.include_router(lead_ingestion_router, prefix=settings.API_V1_STR)
app.include_router(enrichment_router)
app.include_router(identity_resolution_router)
app.include_router(lead_intelligence_router)
app.include_router(ai_agent_router, prefix=settings.API_V1_STR)

# ─── Core Product Part 1 — Customer Intelligence & Conversation Foundation ─────
app.include_router(customer_intelligence_router, prefix=settings.API_V1_STR)

# ─── Core Product Part 2 — Property Intelligence & Grounded Retrieval ─────────
app.include_router(property_intelligence_router, prefix=settings.API_V1_STR)

# ─── Volume 2 Part 6 — Omnichannel Communication Engine v2 ────────────────────
app.include_router(omnichannel_router, prefix=settings.API_V1_STR)
app.include_router(crm_enterprise_router, prefix=settings.API_V1_STR)
app.include_router(crm_services_router, prefix=settings.API_V1_STR)
app.include_router(tasks_router, prefix=settings.API_V1_STR)
app.include_router(tags_router, prefix=settings.API_V1_STR)
app.include_router(notes_router, prefix=settings.API_V1_STR)
app.include_router(stages_router, prefix=settings.API_V1_STR)
app.include_router(calendar_router, prefix=settings.API_V1_STR)
app.include_router(i18n_router, prefix=settings.API_V1_STR)
app.include_router(marketplace_router, prefix=settings.API_V1_STR)
app.include_router(integrations_router, prefix=settings.API_V1_STR)
app.include_router(customer_success_router, prefix=settings.API_V1_STR)
app.include_router(compliance_router, prefix=settings.API_V1_STR)
app.include_router(scaling_benchmarks_router, prefix=settings.API_V1_STR)
app.include_router(developer_router, prefix=settings.API_V1_STR)
app.include_router(plugins_router, prefix=settings.API_V1_STR)
app.include_router(super_admin_router, prefix=settings.API_V1_STR)
app.include_router(communication_router, prefix=settings.API_V1_STR)
app.include_router(properties_router, prefix=settings.API_V1_STR)
app.include_router(transactions_router, prefix=settings.API_V1_STR)
app.include_router(copilot_router, prefix=settings.API_V1_STR)
app.include_router(predictive_router, prefix=settings.API_V1_STR)
app.include_router(workflows_router, prefix=settings.API_V1_STR)
app.include_router(performance_router, prefix=settings.API_V1_STR)
app.include_router(portal_router, prefix=settings.API_V1_STR)
app.include_router(mobile_router, prefix=settings.API_V1_STR)
app.include_router(bi_router, prefix=settings.API_V1_STR)
app.include_router(conversations_router, prefix=settings.API_V1_STR)
app.include_router(whatsapp_router, prefix=settings.API_V1_STR)
app.include_router(scoring_router, prefix=settings.API_V1_STR)
app.include_router(followups_router, prefix=settings.API_V1_STR)
app.include_router(billing_router, prefix=settings.API_V1_STR)

# ─── Knowledge Intelligence Platform ─────────────────────────────────────────
app.include_router(knowledge_router, prefix=settings.API_V1_STR)

# ─── Volume 2 Part 7 — AI Property Recommendation Engine ───────────────────────
app.include_router(recommendation_router, prefix=settings.API_V1_STR)

# ─── Volume 2 Part 8 — AI Follow-Up & Autonomous Lead Nurturing Engine ─────────
app.include_router(enterprise_follow_up_router, prefix=settings.API_V1_STR)

# ─── Volume 2 Part 10 — CRM Intelligence & Autonomous Sales Operations Engine ──
app.include_router(crm_intelligence_router)

# ─── Volume 2 Part 11 — Predictive Analytics & MLOps Engine ───────────────────
app.include_router(predictive_engine_router)

# ─── Volume 2 Part 12 — Workflow Automation & Operations Engine ───────────────
app.include_router(workflow_automation_router)

# ─── Volume 2 Part 13 — AI Memory & Customer Intelligence Engine ──────────────
app.include_router(ai_memory_router)

# ─── Volume 2 Part 14 — Global Multi-Country Infrastructure & Localization Engine ───
app.include_router(global_infrastructure_router)

# ─── Part 21.1 & Part 26 — Real-Estate Lead Acquisition & Capture Hub ──────────
from app.modules.lead_acquisition.controller.acquisition_controller import (
    router as lead_acquisition_router,
    website_router as website_acquisition_router,
)
from app.modules.lead_acquisition.controller.public_capture_controller import (
    router as public_capture_router,
)
app.include_router(lead_acquisition_router)
app.include_router(website_acquisition_router)
app.include_router(public_capture_router)

# ─── Part 21.2 — Real-Estate AI Lead Discovery Engine ─────────────────────────
from app.modules.discovery import discovery_router
app.include_router(discovery_router)

# ─── Part 21.2A — AI Prospect Intelligence Engine ────────────────────────────
from app.modules.prospect_intelligence import prospect_intelligence_router
app.include_router(prospect_intelligence_router)

# ─── Part 21.3 — AI Property Recommendation Engine ───────────────────────────
from app.modules.property_recommendation import property_recommendation_router
app.include_router(property_recommendation_router)

# ─── Part 21.4.1 — AI Lead Qualification Domain Foundation ───────────────────
from app.modules.lead_qualification import lead_qualification_router
app.include_router(lead_qualification_router)

# ─── Part 21.5 — AI Sales Action & Follow-Up Engine ───────────────────────────
from app.modules.sales_action import sales_action_router
app.include_router(sales_action_router, prefix=settings.API_V1_STR)

# ─── Part 21.7 — AI Conversation Intelligence Engine ───────────────────────────
from app.modules.conversation_intelligence.router import router as conversation_intelligence_router
app.include_router(conversation_intelligence_router, prefix=settings.API_V1_STR)

# ─── Part 21.8 — AI Autonomous Sales Loop & Event-Driven Orchestration Engine ──
from app.modules.autonomous_loop import autonomous_loop_router
app.include_router(autonomous_loop_router, prefix=settings.API_V1_STR)

# ─── Part 30 — AI Real-Estate Agent Daily Command Center Engine ──────────────
from app.modules.command_center import command_center_router
app.include_router(command_center_router)

# ─── Part 31 — Customer Onboarding, Tenant Activation & Demo Mode ────────────
from app.modules.onboarding import onboarding_router
app.include_router(onboarding_router)

# ─── Part 35 — AI Real Estate Revenue Autopilot Engine ───────────────────────
from app.modules.revenue_autopilot import revenue_router
app.include_router(revenue_router, prefix=settings.API_V1_STR)

@app.get("/metrics", response_class=PlainTextResponse, tags=["Observability"])
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    return metrics_registry.generate_prometheus_text()

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to WefyLabs Enterprise API. Visit /api/v1/docs for documentation."}
