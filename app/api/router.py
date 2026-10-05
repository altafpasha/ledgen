from fastapi import APIRouter
from app.api.v1 import (
    auth,
    campaigns,
    enrichment,
    health,
    jobs,
    leads,
    providers,
    sheets,
    usage,
)

api_router = APIRouter()

# Health endpoints mounted at root (/health, /health/live, /health/ready)
api_router.include_router(health.router)

# Versioned v1 endpoints (/api/v1/...)
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth.router)
v1_router.include_router(campaigns.router)
v1_router.include_router(leads.router)
v1_router.include_router(enrichment.router)
v1_router.include_router(jobs.router)
v1_router.include_router(providers.router)
v1_router.include_router(usage.router)
v1_router.include_router(sheets.router)

api_router.include_router(v1_router)
