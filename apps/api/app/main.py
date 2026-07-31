from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.modules.auth.router import router as auth_router
from app.routers.brokers import router as brokers_router
from app.modules.leads.router import router as leads_router
from app.routers.whatsapp import router as whatsapp_router
from app.routers.scoring import router as scoring_router
from app.routers.follow_ups import router as followups_router
from app.routers.billing import router as billing_router
from app.routers.conversations import router as conversations_router
from app.presentation.api.v1.leads import router as clean_leads_v1_router
from app.presentation.api.health import health_router
from app.infrastructure.middleware.request_tracing import RequestTracingMiddleware
from app.infrastructure.middleware.idempotency import IdempotencyMiddleware
from app.infrastructure.errors.handlers import register_exception_handlers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform startup database verification / resource allocation
    async with engine.begin() as conn:
        pass
    yield
    # Perform shutdown cleanup
    await engine.dispose()

from app.infrastructure.security.security_headers import SecurityHeadersMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Register Custom Middleware
app.add_middleware(SecurityHeadersMiddleware)
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

# Register Global Exception Handlers
register_exception_handlers(app)

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

# Mount Routers under /api/v1
app.include_router(health_router)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(brokers_router, prefix=settings.API_V1_STR)
app.include_router(leads_router, prefix=settings.API_V1_STR)
app.include_router(clean_leads_v1_router, prefix=settings.API_V1_STR)
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

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to BeetleLabs API. Visit /docs for OpenAPI documentation."}
