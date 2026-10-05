from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.core.exceptions import NotFoundException
from app.db.models.job import DiscoveryJob
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.job import JobActionResponse, JobRead

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "",
    response_model=PaginatedResponse[JobRead],
    summary="List Background Jobs",
    description="Retrieves a paginated list of background discovery and enrichment jobs.",
)
async def list_jobs_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    campaign_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(DiscoveryJob).order_by(DiscoveryJob.created_at.desc())
    if campaign_id:
        stmt = stmt.where(DiscoveryJob.campaign_id == campaign_id)
    if status:
        stmt = stmt.where(DiscoveryJob.status == status)

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await session.execute(count_stmt)
    total = total_res.scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    res = await session.execute(stmt)
    jobs = res.scalars().all()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedResponse(
        items=[JobRead.model_validate(j) for j in jobs],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get(
    "/{job_id}",
    response_model=JobRead,
    summary="Get Job Progress Status",
    description="Polls real-time execution status, current processing stage, progress percentage, and success/failure counters.",
)
async def get_job_status_endpoint(
    job_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(DiscoveryJob).where(DiscoveryJob.id == job_id)
    res = await session.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise NotFoundException("Job", job_id)
    return job


@router.post(
    "/{job_id}/retry",
    response_model=JobActionResponse,
    summary="Retry Failed Job",
    description="Retries a failed background discovery job.",
)
async def retry_job_endpoint(
    job_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(DiscoveryJob).where(DiscoveryJob.id == job_id)
    res = await session.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise NotFoundException("Job", job_id)

    job.status = "queued"
    job.error_message = None
    await session.commit()

    from app.workers.discovery_tasks import discover_campaign_leads
    try:
        task = discover_campaign_leads.delay(job.id, job.campaign_id)
        job.celery_task_id = task.id
        await session.commit()
    except Exception:
        import asyncio
        from app.workers.discovery_tasks import _run_campaign_discovery
        asyncio.create_task(_run_campaign_discovery(job.id, job.campaign_id))

    return JobActionResponse(job_id=job.id, status="queued", message="Job has been requeued.")


@router.post(
    "/{job_id}/cancel",
    response_model=JobActionResponse,
    summary="Cancel Job",
    description="Cancels an active or queued background job.",
)
async def cancel_job_endpoint(
    job_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(DiscoveryJob).where(DiscoveryJob.id == job_id)
    res = await session.execute(stmt)
    job = res.scalars().first()
    if not job:
        raise NotFoundException("Job", job_id)

    job.status = "cancelled"
    await session.commit()
    return JobActionResponse(job_id=job.id, status="cancelled", message="Job marked as cancelled.")
