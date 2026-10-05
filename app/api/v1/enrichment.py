import asyncio
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import RateLimiter, get_current_active_user, get_db
from app.db.models.job import EnrichmentJob
from app.db.models.user import User
from app.schemas.lead import AIDecisionRead, LeadBulkRequest, WebsiteAnalysisRead
from app.services.enrichment_service import EnrichmentService
from app.services.lead_service import LeadService
from app.workers.ai_tasks import qualify_lead_ai
from app.workers.enrichment_tasks import enrich_lead_contact

router = APIRouter(prefix="/leads", tags=["Enrichment & Intelligence"])


@router.post(
    "/{lead_id}/website-analysis",
    response_model=WebsiteAnalysisRead,
    summary="Inspect & Analyze Lead Website",
    description="Safely inspects the public website (SSRF protected) to extract technologies, security posture, and contacts.",
)
async def analyze_lead_website_endpoint(
    lead_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.get_lead_by_id(session, lead_id)
    if not lead.website:
        from app.core.exceptions import AppException
        raise AppException("NO_WEBSITE", "This lead does not have a verified website to inspect.")

    analysis, emails, phones = await EnrichmentService.inspect_website(lead.website)
    if not analysis:
        from app.core.exceptions import AppException
        raise AppException("INSPECTION_FAILED", "Failed to inspect website or address blocked by SSRF.")

    analysis.business_id = lead.id
    session.add(analysis)

    # Backfill missing public contact data if found on site
    if not lead.email and emails:
        lead.email = emails[0]
        lead.normalized_email = emails[0]
    if not lead.phone and phones:
        lead.phone = phones[0]
        lead.normalized_phone = phones[0]

    await session.commit()
    await session.refresh(analysis)
    return analysis


@router.post(
    "/{lead_id}/ai-analysis",
    summary="Trigger Jev AI Qualification",
    description="Evaluates lead qualification and technology opportunity via Jev AI.",
)
async def analyze_lead_ai_endpoint(
    lead_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    lead = await LeadService.get_lead_by_id(session, lead_id)
    job = EnrichmentJob(lead_id=lead.id, job_type="ai_qualification", status="queued")
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        qualify_lead_ai.delay(job.id, lead.id)
    except Exception:
        from app.workers.ai_tasks import _run_ai_qualification
        asyncio.create_task(_run_ai_qualification(job.id, lead.id))

    return {"job_id": job.id, "lead_id": lead.id, "status": "queued"}


@router.post(
    "/bulk/analyze",
    summary="Bulk Website Analysis",
    description="Enqueues safe website analysis for a batch of leads (max 100 per request).",
    dependencies=[Depends(RateLimiter(requests_per_minute=10))],
)
async def bulk_analyze_leads_endpoint(
    req: LeadBulkRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    analyzed_count = 0
    for lid in req.lead_ids:
        try:
            lead = await LeadService.get_lead_by_id(session, lid)
            if lead.website:
                analysis, _, _ = await EnrichmentService.inspect_website(lead.website)
                if analysis:
                    analysis.business_id = lead.id
                    session.add(analysis)
                    analyzed_count += 1
        except Exception:
            continue

    await session.commit()
    return {"message": f"Successfully analyzed {analyzed_count} lead websites", "total_requested": len(req.lead_ids)}
