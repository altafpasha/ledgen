import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.jev import JevIntelligenceLayer
from app.core.config import settings
from app.core.logging import logger
from app.db.models.ai_decision import AIDecision
from app.db.models.business import Business, BusinessContact
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.job import DiscoveryJob
from app.db.models.lead_score import LeadScore
from app.db.models.outreach import OutreachStatus
from app.db.models.provider_usage import ProviderUsage
from app.db.session import AsyncSessionLocal
from app.providers.apify import ApifyLeadDiscoveryProvider
from app.providers.apollo import ApolloProvider
from app.providers.google_sheets import GoogleSheetsProvider
from app.services.deduplication_service import DeduplicationService
from app.services.enrichment_service import EnrichmentService
from app.services.scoring_service import ScoringService
from app.services.sheets_service import SheetsService
from app.utils.domains import extract_domain
from app.utils.normalization import normalize_business_name


from app.db.session import AsyncSessionLocal, get_task_async_session
from contextlib import asynccontextmanager


@asynccontextmanager
async def _get_task_session(provided_session: Optional[AsyncSession] = None):
    if provided_session is not None:
        yield provided_session
    else:
        async with get_task_async_session() as s:
            yield s


async def _run_campaign_discovery(job_id: str, campaign_id: str, session: Optional[AsyncSession] = None):
    async with _get_task_session(session) as session:
        # Load Job and Campaign
        job_stmt = select(DiscoveryJob).where(DiscoveryJob.id == job_id)
        job_res = await session.execute(job_stmt)
        job = job_res.scalars().first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        camp_stmt = select(Campaign).where(Campaign.id == campaign_id)
        camp_res = await session.execute(camp_stmt)
        campaign = camp_res.scalars().first()
        if not campaign:
            job.status = "failed"
            job.error_message = f"Campaign {campaign_id} not found"
            await session.commit()
            return

        # Stage 1: DISCOVERING
        job.status = "running"
        job.current_stage = "discovering"
        job.started_at = datetime.now(timezone.utc)
        campaign.status = "DISCOVERING"
        await session.commit()

        try:
            discovery_provider = ApifyLeadDiscoveryProvider()
            raw_records = await discovery_provider.search_businesses(
                locations=campaign.locations,
                categories=campaign.categories,
                limit=campaign.max_leads,
            )

            # Record Apify usage
            apify_usage = ProviderUsage(
                provider="apify",
                operation="search_businesses",
                campaign_id=campaign.id,
                job_id=job.id,
                requests=1,
                credits_used=float(len(raw_records)),
                estimated_cost=0.01 * len(raw_records),
                status="success",
            )
            session.add(apify_usage)
            await session.commit()

            total_found = len(raw_records)
            job.total = total_found
            job.current_stage = "deduplicating"
            campaign.status = "DEDUPLICATING"
            await session.commit()

            processed_businesses: List[Business] = []
            apollo_credits_used = 0
            ai_requests_used = 0

            # Process leads
            for idx, record in enumerate(raw_records):
                # Deduplication check
                existing = await DeduplicationService.find_duplicate(session, record)
                lead_business = None

                if existing:
                    lead_business = existing
                    # Associate with campaign if not already linked
                    link_stmt = select(CampaignLead).where(
                        and_(CampaignLead.campaign_id == campaign.id, CampaignLead.business_id == existing.id)
                    )
                    link_res = await session.execute(link_stmt)
                    if not link_res.scalars().first():
                        session.add(CampaignLead(campaign_id=campaign.id, business_id=existing.id, status="EXISTING"))
                else:
                    norm_name = normalize_business_name(record.business_name)
                    domain = extract_domain(record.website) if record.website else None

                    lead_business = Business(
                        business_name=record.business_name,
                        normalized_business_name=norm_name,
                        category=record.category,
                        subcategory=record.subcategory,
                        phone=record.phone,
                        normalized_phone=record.phone,
                        email=record.email,
                        normalized_email=record.email,
                        owner_name=record.owner_name,
                        website=record.website,
                        website_domain=domain,
                        has_website=bool(record.website),
                        address=record.address,
                        city=record.city,
                        district=record.district,
                        state=record.state,
                        country=record.country or "India",
                        pincode=record.pincode,
                        latitude=record.latitude,
                        longitude=record.longitude,
                        source=record.source,
                        source_business_id=record.source_business_id,
                        google_maps_url=record.google_maps_url,
                        description=record.description,
                    )
                    session.add(lead_business)
                    await session.flush()

                    session.add(CampaignLead(campaign_id=campaign.id, business_id=lead_business.id, status="DISCOVERED"))
                    session.add(OutreachStatus(business_id=lead_business.id, status="NEW"))

                # Website Inspection if enabled and website present
                analysis_obj = None
                if campaign.analyze_websites and lead_business.website:
                    job.current_stage = "analyzing"
                    analysis_obj, emails, phones = await EnrichmentService.inspect_website(lead_business.website)
                    if analysis_obj:
                        analysis_obj.business_id = lead_business.id
                        session.add(analysis_obj)
                        # Backfill email/phone if business didn't have them
                        if not lead_business.email and emails:
                            lead_business.email = emails[0]
                            lead_business.normalized_email = emails[0]
                        if not lead_business.phone and phones:
                            lead_business.phone = phones[0]
                            lead_business.normalized_phone = phones[0]

                # AI Qualification with Jev
                jev_decision = None
                if campaign.ai_qualification and ai_requests_used < campaign.max_ai_requests:
                    job.current_stage = "qualifying"
                    jev_layer = JevIntelligenceLayer()
                    jev_decision = await jev_layer.qualify_lead(
                        business=lead_business,
                        website_analysis=analysis_obj,
                        campaign_context={"locations": campaign.locations, "categories": campaign.categories},
                    )
                    ai_requests_used += 1

                    ai_record = AIDecision(
                        business_id=lead_business.id,
                        campaign_id=campaign.id,
                        model_name=settings.openrouter_model,
                        lead_quality=jev_decision.lead_quality,
                        score=jev_decision.score,
                        recommended_service=jev_decision.recommended_service,
                        opportunity=jev_decision.opportunity,
                        reason=jev_decision.reason,
                        needs_enrichment=jev_decision.needs_enrichment,
                        confidence=jev_decision.confidence,
                    )
                    session.add(ai_record)

                    # Usage tracking
                    session.add(ProviderUsage(
                        provider="openrouter",
                        operation="qualify_lead",
                        campaign_id=campaign.id,
                        job_id=job.id,
                        requests=1,
                        credits_used=1.0,
                        estimated_cost=0.002,
                        status="success",
                    ))

                # Apollo Contact Enrichment if qualified and within budget
                if campaign.enrich_contacts and apollo_credits_used < campaign.max_apollo_credits:
                    should_enrich = jev_decision.needs_enrichment if jev_decision else True
                    if should_enrich and (not lead_business.owner_name or not lead_business.email):
                        job.current_stage = "enriching"
                        enrichment_res = await EnrichmentService.enrich_contacts_via_apollo(lead_business)
                        apollo_credits_used += 1

                        if enrichment_res.found and enrichment_res.contacts:
                            for contact in enrichment_res.contacts:
                                contact_model = BusinessContact(
                                    business_id=lead_business.id,
                                    name=contact.name,
                                    title=contact.title,
                                    email=contact.email,
                                    phone=contact.phone,
                                    linkedin_url=contact.linkedin_url,
                                    source="apollo",
                                    is_verified=contact.is_verified,
                                )
                                session.add(contact_model)

                                # Update primary owner if missing
                                if not lead_business.owner_name and contact.name:
                                    lead_business.owner_name = contact.name
                                if not lead_business.email and contact.email:
                                    lead_business.email = contact.email
                                    lead_business.normalized_email = contact.email

                        # Usage tracking
                        session.add(ProviderUsage(
                            provider="apollo",
                            operation="enrich_contacts",
                            campaign_id=campaign.id,
                            job_id=job.id,
                            requests=1,
                            credits_used=enrichment_res.credits_used,
                            estimated_cost=0.05 * enrichment_res.credits_used,
                            status=enrichment_res.status,
                        ))

                # Lead Scoring (Deterministic + AI hybrid)
                job.current_stage = "scoring"
                det_score, breakdown = ScoringService.calculate_deterministic_score(lead_business, analysis_obj)
                ai_score = jev_decision.score if jev_decision else None
                final_score = ScoringService.compute_final_score(det_score, ai_score)

                score_record = LeadScore(
                    business_id=lead_business.id,
                    deterministic_score=det_score,
                    ai_score=ai_score,
                    final_score=final_score,
                    scoring_breakdown=breakdown,
                )
                session.add(score_record)

                processed_businesses.append(lead_business)
                job.processed = idx + 1
                job.successful += 1
                job.progress = int(((idx + 1) / max(total_found, 1)) * 100)
                await session.commit()

            # Google Sheets Export if enabled
            if campaign.google_sheet_sync:
                job.current_stage = "exporting"
                campaign.status = "EXPORTING"
                await session.commit()
                await SheetsService.export_campaign_to_sheet(session, campaign.id)

            # Finalize Campaign & Job
            campaign.status = "COMPLETED"
            campaign.leads_discovered = len(processed_businesses)
            campaign.leads_enriched = apollo_credits_used
            campaign.leads_scored = len(processed_businesses)

            job.status = "completed"
            job.current_stage = "completed"
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Campaign {campaign.id} discovery and enrichment successfully finished.")

        except Exception as e:
            logger.error(f"Error executing discovery job {job.id}: {str(e)}", exc_info=True)
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            campaign.status = "FAILED"
            await session.commit()


@shared_task(bind=True, name="app.workers.discovery_tasks.discover_campaign_leads")
def discover_campaign_leads(self, job_id: str, campaign_id: str):
    logger.info(f"Starting Celery task discover_campaign_leads for job {job_id}")
    asyncio.run(_run_campaign_discovery(job_id, campaign_id))
    return {"status": "completed", "job_id": job_id, "campaign_id": campaign_id}


async def _run_daily_lead_scraping_and_sync():
    """
    Periodic Background Job (Celery Beat):
    Finds active campaigns, automatically triggers lead discovery for newly added businesses,
    deduplicates against existing records, executes enrichment & Jev AI qualification,
    and syncs the fresh lead list with clickable Google Maps source links to Google Sheets.
    """
    async with get_task_async_session() as session:
        stmt = select(Campaign).where(
            and_(
                Campaign.status.in_(["ACTIVE", "COMPLETED", "SCHEDULED", "QUEUED"]),
                Campaign.google_sheet_sync == True
            )
        )
        res = await session.execute(stmt)
        campaigns = res.scalars().all()

        if not campaigns:
            logger.info("No active Google Sheet campaign found. Initializing daily campaign from .env settings...")
            new_camp = Campaign(
                name="Daily Automated Lead Generation",
                description="Daily auto-scraping pipeline powered by .env locations and categories",
                locations=settings.scrape_location_list,
                categories=settings.scrape_category_list,
                max_leads=settings.default_daily_lead_limit,
                google_sheet_sync=True,
                ai_qualification=True,
                enrich_contacts=True,
                analyze_websites=True,
                status="ACTIVE",
            )
            session.add(new_camp)
            await session.commit()
            await session.refresh(new_camp)
            campaigns = [new_camp]
        else:
            # Sync any updated locations/categories from .env for daily campaigns
            for campaign in campaigns:
                if "daily" in (campaign.name or "").lower():
                    campaign.locations = settings.scrape_location_list
                    campaign.categories = settings.scrape_category_list
                    campaign.max_leads = settings.default_daily_lead_limit
            await session.commit()

        logger.info(f"Daily scraping job found {len(campaigns)} eligible campaigns.")

        for campaign in campaigns:
            try:
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

                logger.info(f"Triggering automated daily discovery for campaign '{campaign.name}' ({campaign.id})")
                await _run_campaign_discovery(job.id, campaign.id, session=session)
            except Exception as e:
                logger.error(f"Error executing daily sync for campaign {campaign.id}: {str(e)}", exc_info=True)


from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.discovery_tasks.daily_lead_scraping_and_sync")
def daily_lead_scraping_and_sync():
    logger.info("Starting daily automated lead discovery, enrichment, and Google Sheets sync...")
    asyncio.run(_run_daily_lead_scraping_and_sync())
    return {"status": "completed"}


