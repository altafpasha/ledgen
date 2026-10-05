from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException, NotFoundException
from app.db.models.business import Business
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.job import DiscoveryJob
from app.db.models.lead_score import LeadScore
from app.db.models.ai_decision import AIDecision
from app.schemas.campaign import CampaignCreate, CampaignStats, CampaignUpdate


class CampaignService:
    @staticmethod
    async def create_campaign(session: AsyncSession, data: CampaignCreate, user_id: Optional[str] = None) -> Campaign:
        campaign = Campaign(
            name=data.name,
            description=data.description,
            locations=data.locations,
            categories=data.categories,
            max_leads=data.max_leads,
            enrich_contacts=data.enrich_contacts,
            analyze_websites=data.analyze_websites,
            ai_qualification=data.ai_qualification,
            google_sheet_sync=data.google_sheet_sync,
            max_apollo_credits=data.max_apollo_credits,
            max_ai_requests=data.max_ai_requests,
            status="DRAFT",
            created_by_id=user_id,
        )
        session.add(campaign)
        await session.commit()
        await session.refresh(campaign)
        return campaign

    @staticmethod
    async def get_campaign(session: AsyncSession, campaign_id: str) -> Campaign:
        stmt = select(Campaign).where(Campaign.id == campaign_id)
        res = await session.execute(stmt)
        campaign = res.scalars().first()
        if not campaign:
            raise NotFoundException("Campaign", campaign_id)
        return campaign

    @staticmethod
    async def list_campaigns(
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Campaign], int]:
        count_stmt = select(func.count()).select_from(Campaign)
        total_res = await session.execute(count_stmt)
        total = total_res.scalar() or 0

        stmt = select(Campaign).order_by(Campaign.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        res = await session.execute(stmt)
        return list(res.scalars().all()), total

    @staticmethod
    async def update_campaign(session: AsyncSession, campaign_id: str, data: CampaignUpdate) -> Campaign:
        campaign = await CampaignService.get_campaign(session, campaign_id)
        updates = data.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(campaign, k, v)
        await session.commit()
        await session.refresh(campaign)
        return campaign

    @staticmethod
    async def delete_campaign(session: AsyncSession, campaign_id: str) -> None:
        campaign = await CampaignService.get_campaign(session, campaign_id)
        await session.delete(campaign)
        await session.commit()

    @staticmethod
    async def get_stats(session: AsyncSession, campaign_id: str) -> CampaignStats:
        campaign = await CampaignService.get_campaign(session, campaign_id)

        # Get business IDs for this campaign
        lead_ids_stmt = select(CampaignLead.business_id).where(CampaignLead.campaign_id == campaign_id)
        lead_ids_res = await session.execute(lead_ids_stmt)
        business_ids = lead_ids_res.scalars().all()

        total_leads = len(business_ids)
        if total_leads == 0:
            return CampaignStats(
                campaign_id=campaign_id,
                status=campaign.status,
                total_leads=0,
                leads_with_website=0,
                leads_without_website=0,
                leads_with_email=0,
                leads_with_phone=0,
                high_quality_leads=0,
                average_score=0.0,
                opportunities={},
            )

        # Query metrics
        b_stmt = select(Business).where(Business.id.in_(business_ids))
        b_res = await session.execute(b_stmt)
        businesses = b_res.scalars().all()

        leads_with_web = sum(1 for b in businesses if b.has_website and b.website)
        leads_without_web = total_leads - leads_with_web
        leads_with_email = sum(1 for b in businesses if b.email)
        leads_with_phone = sum(1 for b in businesses if b.phone)

        # Query scores
        score_stmt = select(LeadScore).where(LeadScore.business_id.in_(business_ids))
        score_res = await session.execute(score_stmt)
        scores = score_res.scalars().all()
        avg_score = float(sum(s.final_score for s in scores) / len(scores)) if scores else 0.0

        # Query AI decisions
        ai_stmt = select(AIDecision).where(AIDecision.business_id.in_(business_ids))
        ai_res = await session.execute(ai_stmt)
        ai_decisions = ai_res.scalars().all()

        high_quality = sum(1 for d in ai_decisions if d.lead_quality == "high")
        opportunities: Dict[str, int] = {}
        for d in ai_decisions:
            opportunities[d.opportunity] = opportunities.get(d.opportunity, 0) + 1

        return CampaignStats(
            campaign_id=campaign_id,
            status=campaign.status,
            total_leads=total_leads,
            leads_with_website=leads_with_web,
            leads_without_website=leads_without_web,
            leads_with_email=leads_with_email,
            leads_with_phone=leads_with_phone,
            high_quality_leads=high_quality,
            average_score=round(avg_score, 1),
            opportunities=opportunities,
        )
