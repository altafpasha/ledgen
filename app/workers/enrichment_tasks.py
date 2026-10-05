import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from celery import shared_task
from sqlalchemy import select

from app.core.logging import logger
from app.db.models.business import Business, BusinessContact
from app.db.models.job import EnrichmentJob
from app.db.models.provider_usage import ProviderUsage
from app.db.session import get_task_async_session
from app.services.enrichment_service import EnrichmentService


async def _run_lead_enrichment(enrichment_job_id: str, lead_id: str):
    async with get_task_async_session() as session:
        job_stmt = select(EnrichmentJob).where(EnrichmentJob.id == enrichment_job_id)
        job_res = await session.execute(job_stmt)
        job = job_res.scalars().first()
        if not job:
            return

        lead_stmt = select(Business).where(Business.id == lead_id)
        lead_res = await session.execute(lead_stmt)
        lead = lead_res.scalars().first()
        if not lead:
            job.status = "failed"
            job.error_message = "Lead not found"
            await session.commit()
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await session.commit()

        try:
            res = await EnrichmentService.enrich_contacts_via_apollo(lead)
            if res.found and res.contacts:
                for c in res.contacts:
                    session.add(BusinessContact(
                        business_id=lead.id,
                        name=c.name,
                        title=c.title,
                        email=c.email,
                        phone=c.phone,
                        linkedin_url=c.linkedin_url,
                        source="apollo",
                        is_verified=c.is_verified,
                    ))
                    if not lead.owner_name and c.name:
                        lead.owner_name = c.name
                    if not lead.email and c.email:
                        lead.email = c.email
                        lead.normalized_email = c.email

            lead.last_enriched_at = datetime.now(timezone.utc)

            # Record usage
            session.add(ProviderUsage(
                provider="apollo",
                operation="enrich_single_lead",
                job_id=job.id,
                requests=1,
                credits_used=res.credits_used,
                estimated_cost=0.05 * res.credits_used,
                status=res.status,
            ))

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = {"found": res.found, "contacts_count": len(res.contacts)}
            await session.commit()

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()


@shared_task(name="app.workers.enrichment_tasks.enrich_lead_contact")
def enrich_lead_contact(enrichment_job_id: str, lead_id: str):
    asyncio.run(_run_lead_enrichment(enrichment_job_id, lead_id))
    return {"job_id": enrichment_job_id, "lead_id": lead_id, "status": "completed"}
