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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Perform startup database verification / resource allocation
    async with engine.begin() as conn:
        pass
    yield
    # Perform shutdown cleanup
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers under /api/v1
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(brokers_router, prefix=settings.API_V1_STR)
app.include_router(leads_router, prefix=settings.API_V1_STR)
app.include_router(conversations_router, prefix=settings.API_V1_STR)
app.include_router(whatsapp_router, prefix=settings.API_V1_STR)
app.include_router(scoring_router, prefix=settings.API_V1_STR)
app.include_router(followups_router, prefix=settings.API_V1_STR)
app.include_router(billing_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to BeetleLabs API. Visit /docs for OpenAPI documentation."}
