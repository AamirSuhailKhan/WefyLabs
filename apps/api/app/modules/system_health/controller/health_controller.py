from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.system_health.service.health_service import SystemHealthService

router = APIRouter(prefix="/v1/health", tags=["System Health"])


@router.get("")
async def health_liveness(db: AsyncSession = Depends(get_db)):
    """Kubernetes liveness probe."""
    service = SystemHealthService(db)
    return await service.liveness()


@router.get("/ready")
async def health_readiness(db: AsyncSession = Depends(get_db)):
    """Kubernetes readiness probe — checks DB + Redis."""
    service = SystemHealthService(db)
    return await service.readiness()


@router.get("/deep")
async def health_deep_check(db: AsyncSession = Depends(get_db)):
    """Full diagnostic health check for monitoring dashboards."""
    service = SystemHealthService(db)
    return await service.deep_check()
