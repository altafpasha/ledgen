from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Overview",
    description="Returns high-level system health and operational mode.",
)
async def health_check(session: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    redis_status = "ok"
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
    except Exception:
        redis_status = "unreachable"

    overall = "healthy" if db_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        app_env=settings.app_env,
        database=db_status,
        redis=redis_status,
        mock_mode=settings.mock_providers,
    )


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Kubernetes / Docker liveness probe confirming API process is running.",
)
async def liveness():
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Kubernetes / Docker readiness probe validating database and cache availability.",
)
async def readiness(session: AsyncSession = Depends(get_db)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not ready"
        )
