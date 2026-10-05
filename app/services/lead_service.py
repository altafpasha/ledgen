from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.db.models.business import Business, BusinessContact
from app.db.models.campaign import CampaignLead
from app.db.models.lead_score import LeadScore
from app.db.models.outreach import OutreachStatus
from app.db.models.ai_decision import AIDecision
from app.db.models.website_analysis import WebsiteAnalysis
from app.schemas.lead import LeadUpdate, LeadOutreachUpdate


class LeadService:
    @staticmethod
    async def get_lead_by_id(session: AsyncSession, lead_id: str) -> Business:
        stmt = (
            select(Business)
            .where(Business.id == lead_id)
            .options(
                selectinload(Business.scores),
                selectinload(Business.website_analyses),
                selectinload(Business.ai_decisions),
                selectinload(Business.contacts),
                selectinload(Business.outreach),
            )
        )
        res = await session.execute(stmt)
        lead = res.scalars().first()
        if not lead:
            raise NotFoundException("Lead", lead_id)
        return lead

    @staticmethod
    async def list_leads(
        session: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        location: Optional[str] = None,
        category: Optional[str] = None,
        has_website: Optional[bool] = None,
        has_email: Optional[bool] = None,
        has_phone: Optional[bool] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        opportunity: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
        campaign_id: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Business], int]:
        filters = []

        if location:
            filters.append(
                or_(
                    Business.city.ilike(f"%{location}%"),
                    Business.district.ilike(f"%{location}%"),
                    Business.state.ilike(f"%{location}%"),
                )
            )

        if category:
            filters.append(Business.category.ilike(f"%{category}%"))

        if has_website is not None:
            filters.append(Business.has_website == has_website)

        if has_email is not None:
            if has_email:
                filters.append(Business.email.isnot(None))
            else:
                filters.append(Business.email.is_(None))

        if has_phone is not None:
            if has_phone:
                filters.append(Business.phone.isnot(None))
            else:
                filters.append(Business.phone.is_(None))

        if source:
            filters.append(Business.source == source)

        if created_after:
            filters.append(Business.created_at >= created_after)

        if created_before:
            filters.append(Business.created_at <= created_before)

        # Campaign filter
        if campaign_id:
            filters.append(
                Business.id.in_(
                    select(CampaignLead.business_id).where(CampaignLead.campaign_id == campaign_id)
                )
            )

        # Outreach status filter
        if status:
            filters.append(
                Business.id.in_(
                    select(OutreachStatus.business_id).where(OutreachStatus.status == status)
                )
            )

        # Score filters
        if score_min is not None:
            filters.append(
                Business.id.in_(
                    select(LeadScore.business_id).where(LeadScore.final_score >= score_min)
                )
            )
        if score_max is not None:
            filters.append(
                Business.id.in_(
                    select(LeadScore.business_id).where(LeadScore.final_score <= score_max)
                )
            )

        # Opportunity filter
        if opportunity:
            filters.append(
                Business.id.in_(
                    select(AIDecision.business_id).where(AIDecision.opportunity == opportunity)
                )
            )

        # Count total
        count_stmt = select(func.count()).select_from(Business)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total_res = await session.execute(count_stmt)
        total = total_res.scalar() or 0

        # Query items
        stmt = (
            select(Business)
            .options(
                selectinload(Business.scores),
                selectinload(Business.website_analyses),
                selectinload(Business.ai_decisions),
                selectinload(Business.contacts),
                selectinload(Business.outreach),
            )
        )
        if filters:
            stmt = stmt.where(and_(*filters))

        # Sorting
        sort_col = getattr(Business, sort_by, Business.created_at)
        if sort_order.lower() == "asc":
            stmt = stmt.order_by(asc(sort_col))
        else:
            stmt = stmt.order_by(desc(sort_col))

        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items_res = await session.execute(stmt)
        leads = items_res.scalars().all()
        return list(leads), total

    @staticmethod
    async def update_lead(session: AsyncSession, lead_id: str, update_data: LeadUpdate) -> Business:
        lead = await LeadService.get_lead_by_id(session, lead_id)
        data = update_data.model_dump(exclude_unset=True)

        for k, v in data.items():
            setattr(lead, k, v)

        if "website" in data:
            lead.has_website = bool(data["website"])
            from app.utils.domains import extract_domain
            lead.website_domain = extract_domain(data["website"])

        await session.commit()
        await session.refresh(lead)
        return lead

    @staticmethod
    async def update_outreach_status(
        session: AsyncSession,
        lead_id: str,
        outreach_data: LeadOutreachUpdate,
    ) -> OutreachStatus:
        lead = await LeadService.get_lead_by_id(session, lead_id)
        stmt = select(OutreachStatus).where(OutreachStatus.business_id == lead_id)
        res = await session.execute(stmt)
        outreach = res.scalars().first()

        now = datetime.now(timezone.utc)
        if not outreach:
            outreach = OutreachStatus(
                business_id=lead_id,
                status=outreach_data.status,
                contact_notes=outreach_data.contact_notes,
                next_followup_at=outreach_data.next_followup_at,
                last_contacted_at=now if outreach_data.status == "CONTACTED" else None,
            )
            session.add(outreach)
        else:
            outreach.status = outreach_data.status
            if outreach_data.contact_notes is not None:
                outreach.contact_notes = outreach_data.contact_notes
            if outreach_data.next_followup_at is not None:
                outreach.next_followup_at = outreach_data.next_followup_at
            if outreach_data.status == "CONTACTED":
                outreach.last_contacted_at = now

        await session.commit()
        await session.refresh(outreach)
        return outreach
