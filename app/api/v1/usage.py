from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.db.models.provider_usage import ProviderUsage
from app.db.models.user import User
from app.schemas.provider import ProviderUsageItem, UsageSummary

router = APIRouter(prefix="/usage", tags=["Usage & Cost Analytics"])


@router.get(
    "",
    response_model=UsageSummary,
    summary="Get Usage & Budget Overview",
    description="Aggregates requests, credits consumed, and estimated cost across all integrated providers.",
)
async def get_usage_summary_endpoint(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(
        ProviderUsage.provider,
        func.count(ProviderUsage.id).label("requests"),
        func.sum(ProviderUsage.credits_used).label("credits"),
        func.sum(ProviderUsage.estimated_cost).label("cost"),
    ).group_by(ProviderUsage.provider)

    res = await session.execute(stmt)
    rows = res.all()

    by_provider = {}
    total_req = 0
    total_cred = 0.0
    total_cost = 0.0

    for r in rows:
        provider_name = r[0]
        reqs = int(r[1] or 0)
        credits = float(r[2] or 0.0)
        cost = float(r[3] or 0.0)

        total_req += reqs
        total_cred += credits
        total_cost += cost

        by_provider[provider_name] = {
            "requests": reqs,
            "credits_used": round(credits, 2),
            "estimated_cost_usd": round(cost, 4),
        }

    return UsageSummary(
        total_requests=total_req,
        total_credits=round(total_cred, 2),
        total_estimated_cost=round(total_cost, 4),
        by_provider=by_provider,
    )


@router.get(
    "/{provider_name}",
    response_model=List[ProviderUsageItem],
    summary="Get Provider Usage Details",
    description="Lists chronological invocation logs for a specific provider (apify, apollo, openrouter).",
)
async def get_specific_provider_usage_endpoint(
    provider_name: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ProviderUsage)
        .where(ProviderUsage.provider == provider_name.lower())
        .order_by(ProviderUsage.created_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())
