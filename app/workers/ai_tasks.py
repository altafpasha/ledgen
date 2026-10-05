import asyncio
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import select

from app.ai.jev import JevIntelligenceLayer
from app.core.config import settings
from app.core.logging import logger
from app.db.models.ai_decision import AIDecision
from app.db.models.business import Business
from app.db.models.job import EnrichmentJob
from app.db.models.lead_score import LeadScore
from app.db.models.provider_usage import ProviderUsage
from app.db.session import get_task_async_session
from app.services.scoring_service import ScoringService


async def _run_ai_qualification(enrichment_job_id: str, lead_id: str):
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
            jev_layer = JevIntelligenceLayer()
            decision = await jev_layer.qualify_lead(business=lead)

            ai_record = AIDecision(
                business_id=lead.id,
                model_name=settings.openrouter_model,
                lead_quality=decision.lead_quality,
                score=decision.score,
                recommended_service=decision.recommended_service,
                opportunity=decision.opportunity,
                reason=decision.reason,
                needs_enrichment=decision.needs_enrichment,
                confidence=decision.confidence,
            )
            session.add(ai_record)

            # Re-score lead
            det_score, breakdown = ScoringService.calculate_deterministic_score(lead)
            final_score = ScoringService.compute_final_score(det_score, decision.score)
            session.add(LeadScore(
                business_id=lead.id,
                deterministic_score=det_score,
                ai_score=decision.score,
                final_score=final_score,
                scoring_breakdown=breakdown,
            ))

            session.add(ProviderUsage(
                provider="openrouter",
                operation="qualify_single_lead",
                job_id=job.id,
                requests=1,
                credits_used=1.0,
                estimated_cost=0.002,
                status="success",
            ))

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.result_summary = decision.model_dump()
            await session.commit()

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()


@shared_task(name="app.workers.ai_tasks.qualify_lead_ai")
def qualify_lead_ai(enrichment_job_id: str, lead_id: str):
    asyncio.run(_run_ai_qualification(enrichment_job_id, lead_id))
    return {"job_id": enrichment_job_id, "lead_id": lead_id, "status": "completed"}
