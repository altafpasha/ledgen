import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RateLimiter,
    get_current_active_user,
    get_db,
    record_audit_log,
)
from app.core.exceptions import AppException, NotFoundException
from app.db.models.campaign import Campaign
from app.db.models.job import DiscoveryJob
from app.db.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignRead,
    CampaignRunResponse,
    CampaignStats,
    CampaignUpdate,
)
from app.schemas.common import PaginatedResponse
from app.schemas.lead import LeadRead
from app.services.campaign_service import CampaignService
from app.services.lead_service import LeadService
from app.workers.discovery_tasks import discover_campaign_leads

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post(
    "",
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Campaign",
    description="Creates a new lead generation campaign with specified locations and categories.",
    dependencies=[Depends(RateLimiter(requests_per_minute=20))],
)
async def create_campaign_endpoint(
    data: CampaignCreate,
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    campaign = await CampaignService.create_campaign(session, data, user.id)
    await record_audit_log(
        session=session,
        action="CAMPAIGN_CREATED",
        resource_type="CAMPAIGN",
        resource_id=campaign.id,
        user_id=user.id,
        details={"name": campaign.name, "locations": campaign.locations},
        ip_address=request.client.host if request.client else None,
    )
    return campaign


@router.get(
    "",
    response_model=PaginatedResponse[CampaignRead],
    summary="List Campaigns",
    description="Retrieves a paginated list of all campaigns.",
)
async def list_campaigns_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    campaigns, total = await CampaignService.list_campaigns(session, page, page_size)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[CampaignRead.model_validate(c) for c in campaigns],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignRead,
    summary="Get Campaign Details",
    description="Fetches a specific campaign by its UUID.",
)
async def get_campaign_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    return await CampaignService.get_campaign(session, campaign_id)


@router.patch(
    "/{campaign_id}",
    response_model=CampaignRead,
    summary="Update Campaign (PATCH)",
    description="Updates editable parameters of an existing campaign.",
)
@router.put(
    "/{campaign_id}",
    response_model=CampaignRead,
    summary="Update Campaign (PUT)",
    description="Updates editable parameters of an existing campaign.",
)
async def update_campaign_endpoint(
    campaign_id: str,
    data: CampaignUpdate,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    return await CampaignService.update_campaign(session, campaign_id, data)


@router.delete(
    "/{campaign_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Campaign",
    description="Deletes a campaign and its associations.",
)
async def delete_campaign_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    await CampaignService.delete_campaign(session, campaign_id)


@router.post(
    "/{campaign_id}/run",
    response_model=CampaignRunResponse,
    summary="Run Campaign",
    description="Triggers the discovery, enrichment, qualification, and scoring pipeline in Celery.",
    dependencies=[Depends(RateLimiter(requests_per_minute=10))],
)
async def run_campaign_endpoint(
    campaign_id: str,
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    campaign = await CampaignService.get_campaign(session, campaign_id)
    if campaign.status in ["DISCOVERING", "NORMALIZING", "ENRICHING", "QUALIFYING", "SCORING"]:
        raise AppException("CAMPAIGN_ALREADY_RUNNING", "Campaign is already running.", status_code=400)

    # Create DiscoveryJob record
    job = DiscoveryJob(
        campaign_id=campaign.id,
        status="queued",
        current_stage="queued",
        progress=0,
        total=campaign.max_leads,
    )
    session.add(job)
    campaign.status = "QUEUED"
    await session.commit()
    await session.refresh(job)

    # Enqueue Celery task asynchronously
    try:
        task = discover_campaign_leads.delay(job.id, campaign.id)
        job.celery_task_id = task.id
        await session.commit()
    except Exception as e:
        # If Redis is not currently reachable during local tests, run synchronously in mock mode
        import asyncio
        from app.workers.discovery_tasks import _run_campaign_discovery
        asyncio.create_task(_run_campaign_discovery(job.id, campaign.id))

    await record_audit_log(
        session=session,
        action="CAMPAIGN_STARTED",
        resource_type="CAMPAIGN",
        resource_id=campaign.id,
        user_id=user.id,
        details={"job_id": job.id},
        ip_address=request.client.host if request.client else None,
    )

    return CampaignRunResponse(
        job_id=job.id,
        campaign_id=campaign.id,
        status="queued",
        message="Campaign queued for execution. Poll /api/v1/jobs/{job_id} for live progress.",
    )


@router.post(
    "/{campaign_id}/pause",
    response_model=CampaignRead,
    summary="Pause Campaign",
    description="Pauses an active campaign.",
)
async def pause_campaign_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    campaign = await CampaignService.get_campaign(session, campaign_id)
    campaign.status = "PAUSED"
    await session.commit()
    await session.refresh(campaign)
    return campaign


@router.post(
    "/{campaign_id}/resume",
    response_model=CampaignRead,
    summary="Resume Campaign",
    description="Resumes a paused campaign.",
)
async def resume_campaign_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    campaign = await CampaignService.get_campaign(session, campaign_id)
    if campaign.status == "PAUSED":
        campaign.status = "QUEUED"
        await session.commit()
        await session.refresh(campaign)
    return campaign


@router.post(
    "/{campaign_id}/cancel",
    response_model=CampaignRead,
    summary="Cancel Campaign",
    description="Cancels an active or queued campaign.",
)
async def cancel_campaign_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    campaign = await CampaignService.get_campaign(session, campaign_id)
    campaign.status = "CANCELLED"
    await session.commit()
    await session.refresh(campaign)
    return campaign


@router.get(
    "/{campaign_id}/stats",
    response_model=CampaignStats,
    summary="Get Campaign Analytics & Statistics",
    description="Returns aggregate quality metrics, opportunities breakdown, and average lead scores.",
)
async def get_campaign_stats_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    return await CampaignService.get_stats(session, campaign_id)


@router.get(
    "/{campaign_id}/leads",
    response_model=PaginatedResponse[LeadRead],
    summary="Get Campaign Leads",
    description="Fetches paginated leads associated with this specific campaign.",
)
async def get_campaign_leads_endpoint(
    campaign_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    leads, total = await LeadService.list_leads(
        session=session,
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[LeadRead.model_validate(l) for l in leads],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.post(
    "/daily-sync",
    summary="Trigger Daily Scraping & Sync",
    description="Manually triggers the daily automated lead scraping, deduplication, enrichment, and Google Sheets sync for all campaigns.",
    dependencies=[Depends(RateLimiter(requests_per_minute=5))],
)
async def trigger_daily_sync_endpoint(
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    task_id = str(uuid.uuid4())
    try:
        from app.workers.celery_app import celery_app
        task = celery_app.send_task("app.workers.discovery_tasks.daily_lead_scraping_and_sync")
        task_id = task.id
    except Exception as e:
        import asyncio
        from app.workers.discovery_tasks import _run_daily_lead_scraping_and_sync
        asyncio.create_task(_run_daily_lead_scraping_and_sync())

    await record_audit_log(
        session=session,
        action="DAILY_SYNC_TRIGGERED",
        resource_type="CAMPAIGN",
        resource_id=None,
        user_id=user.id,
        details={"celery_task_id": task_id},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "status": "queued",
        "task_id": task_id,
        "message": "Daily lead scraping, qualification, and Google Sheets sync has been started in background.",
    }

