from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RateLimiter,
    get_current_active_user,
    get_db,
    record_audit_log,
)
from app.core.exceptions import NotFoundException
from app.db.models.business import Business
from app.db.models.job import EnrichmentJob
from app.db.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.lead import (
    LeadBulkRequest,
    LeadNotesUpdate,
    LeadOutreachUpdate,
    LeadRead,
    LeadUpdate,
    OutreachStatusRead,
)
from app.services.enrichment_service import EnrichmentService
from app.services.lead_service import LeadService
from app.services.scoring_service import ScoringService
from app.workers.enrichment_tasks import enrich_lead_contact

router = APIRouter(prefix="/leads", tags=["Leads"])


def _lead_to_read(lead: Business) -> LeadRead:
    final_score = lead.scores[0].final_score if lead.scores else 0
    opp = lead.ai_decisions[0].opportunity if lead.ai_decisions else "UNKNOWN"
    st = lead.outreach.status if lead.outreach else "NEW"

    return LeadRead(
        id=lead.id,
        business_name=lead.business_name,
        category=lead.category,
        subcategory=lead.subcategory,
        phone=lead.phone,
        email=lead.email,
        owner_name=lead.owner_name,
        website=lead.website,
        has_website=lead.has_website,
        address=lead.address,
        city=lead.city,
        district=lead.district,
        state=lead.state,
        country=lead.country,
        pincode=lead.pincode,
        google_maps_url=lead.google_maps_url,
        source=lead.source,
        lead_score=final_score,
        opportunity=opp,
        status=st,
        last_enriched_at=lead.last_enriched_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        scores=lead.scores,
        website_analyses=lead.website_analyses,
        ai_decisions=lead.ai_decisions,
        contacts=lead.contacts,
        outreach=lead.outreach,
    )


@router.get(
    "",
    response_model=PaginatedResponse[LeadRead],
    summary="List & Filter Leads",
    description="Query leads with advanced filters (location, category, website existence, score range, CRM status).",
)
async def list_leads_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    location: Optional[str] = Query(default=None, description="City, district or state"),
    category: Optional[str] = Query(default=None),
    has_website: Optional[bool] = Query(default=None),
    has_email: Optional[bool] = Query(default=None),
    has_phone: Optional[bool] = Query(default=None),
    score_min: Optional[int] = Query(default=None, ge=0, le=100),
    score_max: Optional[int] = Query(default=None, ge=0, le=100),
    opportunity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    campaign_id: Optional[str] = Query(default=None),
    created_after: Optional[datetime] = Query(default=None),
    created_before: Optional[datetime] = Query(default=None),
    sort_by: str = Query(default="created_at", description="created_at, business_name, lead_score, updated_at"),
    sort_order: str = Query(default="desc", description="asc or desc"),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    leads, total = await LeadService.list_leads(
        session=session,
        page=page,
        page_size=page_size,
        location=location,
        category=category,
        has_website=has_website,
        has_email=has_email,
        has_phone=has_phone,
        score_min=score_min,
        score_max=score_max,
        opportunity=opportunity,
        status=status,
        source=source,
        campaign_id=campaign_id,
        created_after=created_after,
        created_before=created_before,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[_lead_to_read(l) for l in leads],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Get Lead Details",
    description="Retrieves a complete lead record including contacts, website analyses, AI decisions, and scores.",
)
async def get_lead_endpoint(
    lead_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.get_lead_by_id(session, lead_id)
    return _lead_to_read(lead)


@router.patch(
    "/{lead_id}",
    response_model=LeadRead,
    summary="Update Lead",
    description="Updates editable business attributes.",
)
async def update_lead_endpoint(
    lead_id: str,
    data: LeadUpdate,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.update_lead(session, lead_id, data)
    return _lead_to_read(lead)


@router.post(
    "/{lead_id}/enrich",
    summary="Enrich Single Lead",
    description="Enqueues Apollo contact enrichment for this lead.",
    dependencies=[Depends(RateLimiter(requests_per_minute=30))],
)
async def enrich_lead_endpoint(
    lead_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.get_lead_by_id(session, lead_id)
    job = EnrichmentJob(lead_id=lead.id, job_type="apollo_enrichment", status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        enrich_lead_contact.delay(job.id, lead.id)
    except Exception:
        import asyncio
        from app.workers.enrichment_tasks import _run_lead_enrichment
        asyncio.create_task(_run_lead_enrichment(job.id, lead.id))

    return {"job_id": job.id, "lead_id": lead.id, "status": "queued"}


@router.post(
    "/{lead_id}/contacted",
    response_model=OutreachStatusRead,
    summary="Mark Lead as Contacted",
    description="Sets outreach status to CONTACTED and stamps the last_contacted_at timestamp.",
)
async def mark_lead_contacted_endpoint(
    lead_id: str,
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    outreach = await LeadService.update_outreach_status(
        session, lead_id, LeadOutreachUpdate(status="CONTACTED")
    )
    await record_audit_log(
        session=session,
        action="LEAD_CONTACTED",
        resource_type="LEAD",
        resource_id=lead_id,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return outreach


@router.post(
    "/{lead_id}/notes",
    response_model=OutreachStatusRead,
    summary="Update Lead Contact Notes",
    description="Appends or updates outreach CRM notes for a lead.",
)
async def update_lead_notes_endpoint(
    lead_id: str,
    notes: LeadNotesUpdate,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.get_lead_by_id(session, lead_id)
    curr_status = lead.outreach.status if lead.outreach else "NEW"
    outreach = await LeadService.update_outreach_status(
        session, lead_id, LeadOutreachUpdate(status=curr_status, contact_notes=notes.contact_notes)
    )
    return outreach


@router.delete(
    "/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Lead",
    description="Removes a lead record from the database.",
)
async def delete_lead_endpoint(
    lead_id: str,
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.get_lead_by_id(session, lead_id)
    await session.delete(lead)
    await session.commit()
    await record_audit_log(
        session=session,
        action="LEAD_DELETED",
        resource_type="LEAD",
        resource_id=lead_id,
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )


@router.post(
    "/bulk/enrich",
    summary="Bulk Enrich Leads",
    description="Enqueues contact enrichment for a batch of leads (max 100 per request).",
    dependencies=[Depends(RateLimiter(requests_per_minute=10))],
)
async def bulk_enrich_leads_endpoint(
    req: LeadBulkRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    queued_jobs = []
    for lid in req.lead_ids:
        job = EnrichmentJob(lead_id=lid, job_type="apollo_enrichment", status="queued")
        session.add(job)
        await session.flush()
        try:
            enrich_lead_contact.delay(job.id, lid)
        except Exception:
            import asyncio
            from app.workers.enrichment_tasks import _run_lead_enrichment
            asyncio.create_task(_run_lead_enrichment(job.id, lid))
        queued_jobs.append(job.id)

    await session.commit()
    return {"message": f"Enqueued {len(queued_jobs)} leads for enrichment", "job_ids": queued_jobs}
