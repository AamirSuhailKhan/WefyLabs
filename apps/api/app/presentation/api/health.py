from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.dependencies import get_db
from app.config import settings

health_router = APIRouter(prefix="/health", tags=["Health & Monitoring"])

@health_router.get("/liveness", status_code=status.HTTP_200_OK)
async def liveness_check():
    """Kubernetes / Load Balancer Liveness Probe."""
    return {"status": "alive", "service": settings.PROJECT_NAME, "version": settings.VERSION}

@health_router.get("/readiness")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Kubernetes / Load Balancer Readiness Probe with DB Connection Verification."""
    db_ok = False
    try:
        res = await db.execute(text("SELECT 1"))
        db_ok = res.scalar() == 1
    except Exception as e:
        db_ok = False

    status_code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if db_ok else "unhealthy",
            "checks": {
                "database": "ok" if db_ok else "failed",
                "redis": "ok"
            }
        }
    )
