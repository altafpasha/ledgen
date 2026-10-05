from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.core.config import settings
from app.db.models.provider_usage import ProviderUsage
from app.db.models.user import User
from app.schemas.provider import ProviderStatusItem, ProviderStatusResponse, ProviderUsageItem

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.get(
    "",
    response_model=ProviderStatusResponse,
    summary="List Lead Intelligence Providers",
    description="Lists all integrated external providers and their operational status.",
)
@router.get(
    "/status",
    response_model=ProviderStatusResponse,
    summary="Get Provider Connection Status",
    description="Returns connectivity status of Apify, Apollo, OpenRouter, and Google Sheets without revealing any secrets.",
)
async def get_providers_status_endpoint(user: User = Depends(get_current_active_user)):
    providers = [
        ProviderStatusItem(
            provider="apify",
            configured=bool(settings.apify_api_token),
            status="healthy" if (settings.apify_api_token or settings.mock_providers) else "unconfigured",
            mock_mode=settings.mock_providers or not bool(settings.apify_api_token),
            description="Lead discovery from Google Places / Google Maps",
        ),
        ProviderStatusItem(
            provider="apollo",
            configured=bool(settings.apollo_api_key),
            status="healthy" if (settings.apollo_api_key or settings.mock_providers) else "unconfigured",
            mock_mode=settings.mock_providers or not bool(settings.apollo_api_key),
            description="Executive and business contact enrichment",
        ),
        ProviderStatusItem(
            provider="openrouter",
            configured=bool(settings.openrouter_api_key),
            status="healthy" if (settings.openrouter_api_key or settings.mock_providers) else "unconfigured",
            mock_mode=settings.mock_providers or not bool(settings.openrouter_api_key),
            description=f"Jev qualification layer ({settings.openrouter_model})",
        ),
        ProviderStatusItem(
            provider="google_sheets",
            configured=bool(settings.google_client_id and settings.google_client_secret and settings.google_refresh_token),
            status="healthy" if ((settings.google_client_id and settings.google_refresh_token) or settings.mock_providers) else "unconfigured",
            mock_mode=settings.mock_providers or not bool(settings.google_client_id),
            description="Direct synchronization to Google Sheets",
        ),
    ]
    return ProviderStatusResponse(providers=providers)


@router.get(
    "/usage",
    response_model=List[ProviderUsageItem],
    summary="Recent Provider Calls",
    description="Retrieves a list of recent provider API invocations and token/credit consumption.",
)
async def get_providers_usage_endpoint(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(ProviderUsage).order_by(ProviderUsage.created_at.desc()).limit(100)
    res = await session.execute(stmt)
    return list(res.scalars().all())
