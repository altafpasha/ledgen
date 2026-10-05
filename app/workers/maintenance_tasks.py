import asyncio
from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy import select, delete

from app.core.logging import logger
from app.db.models.job import DiscoveryJob, EnrichmentJob
from app.db.session import AsyncSessionLocal


async def _cleanup_old_jobs(retention_days: int = 30):
    async with AsyncSessionLocal() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        # Delete completed or failed jobs older than retention_days
        stmt1 = delete(DiscoveryJob).where(
            DiscoveryJob.status.in_(["completed", "failed", "cancelled"]),
            DiscoveryJob.created_at < cutoff,
        )
        stmt2 = delete(EnrichmentJob).where(
            EnrichmentJob.status.in_(["completed", "failed", "cancelled"]),
            EnrichmentJob.created_at < cutoff,
        )
        await session.execute(stmt1)
        await session.execute(stmt2)
        await session.commit()
        logger.info(f"Cleaned up background jobs older than {retention_days} days.")


@shared_task(name="app.workers.maintenance_tasks.cleanup_old_jobs")
def cleanup_old_jobs(retention_days: int = 30):
    asyncio.run(_cleanup_old_jobs(retention_days))
    return {"status": "success"}
