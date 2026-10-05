from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.db.models.business import Business
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.google_sheet import GoogleSheetExport
from app.db.models.lead_score import LeadScore
from app.db.models.outreach import OutreachStatus
from app.db.models.ai_decision import AIDecision
from app.providers.google_sheets import GoogleSheetsProvider


class SheetsService:
    @staticmethod
    async def export_campaign_to_sheet(
        session: AsyncSession,
        campaign_id: str,
        spreadsheet_id: Optional[str] = None,
        sheet_name: str = "Leads",
    ) -> GoogleSheetExport:
        campaign_stmt = select(Campaign).where(Campaign.id == campaign_id)
        c_res = await session.execute(campaign_stmt)
        campaign = c_res.scalars().first()
        if not campaign:
            raise NotFoundException("Campaign", campaign_id)

        # Get all leads in this campaign
        lead_ids_stmt = select(CampaignLead.business_id).where(CampaignLead.campaign_id == campaign_id)
        lead_ids_res = await session.execute(lead_ids_stmt)
        business_ids = lead_ids_res.scalars().all()

        leads_stmt = (
            select(Business)
            .where(Business.id.in_(business_ids))
            .options(
                selectinload(Business.scores),
                selectinload(Business.outreach),
                selectinload(Business.ai_decisions),
            )
        )
        leads_res = await session.execute(leads_stmt)
        leads = leads_res.scalars().all()

        leads_data: List[Dict[str, Any]] = []
        for lead in leads:
            score_val = lead.scores[0].final_score if lead.scores else 0
            status_val = lead.outreach.status if lead.outreach else "NEW"
            opp_val = lead.ai_decisions[0].opportunity if lead.ai_decisions else "UNKNOWN"

            leads_data.append({
                "business_name": lead.business_name,
                "owner_name": lead.owner_name,
                "email": lead.email,
                "phone": lead.phone,
                "city": lead.city,
                "district": lead.district,
                "state": lead.state,
                "address": lead.address,
                "website": lead.website,
                "google_maps_url": lead.google_maps_url,
                "category": lead.category,
                "lead_score": score_val,
                "opportunity": opp_val,
                "status": status_val,
                "source": lead.source,
                "created_at": lead.created_at,
            })

        provider = GoogleSheetsProvider()
        result = await provider.export_leads(spreadsheet_id, sheet_name, leads_data)

        export_record = GoogleSheetExport(
            campaign_id=campaign_id,
            spreadsheet_id=result.get("spreadsheet_id", "default"),
            sheet_name=sheet_name,
            total_rows_exported=len(leads_data),
            status=result.get("status", "completed"),
            last_synced_at=datetime.now(timezone.utc),
        )
        session.add(export_record)
        await session.commit()
        await session.refresh(export_record)
        return export_record

    @staticmethod
    async def export_selected_leads_to_sheet(
        session: AsyncSession,
        lead_ids: List[str],
        spreadsheet_id: Optional[str] = None,
        sheet_name: str = "Exported Leads",
    ) -> GoogleSheetExport:
        leads_stmt = (
            select(Business)
            .where(Business.id.in_(lead_ids))
            .options(
                selectinload(Business.scores),
                selectinload(Business.outreach),
                selectinload(Business.ai_decisions),
            )
        )
        leads_res = await session.execute(leads_stmt)
        leads = leads_res.scalars().all()

        leads_data: List[Dict[str, Any]] = []
        for lead in leads:
            score_val = lead.scores[0].final_score if lead.scores else 0
            status_val = lead.outreach.status if lead.outreach else "NEW"
            opp_val = lead.ai_decisions[0].opportunity if lead.ai_decisions else "UNKNOWN"

            leads_data.append({
                "business_name": lead.business_name,
                "owner_name": lead.owner_name,
                "email": lead.email,
                "phone": lead.phone,
                "city": lead.city,
                "district": lead.district,
                "state": lead.state,
                "address": lead.address,
                "website": lead.website,
                "google_maps_url": lead.google_maps_url,
                "category": lead.category,
                "lead_score": score_val,
                "opportunity": opp_val,
                "status": status_val,
                "source": lead.source,
                "created_at": lead.created_at,
            })

        provider = GoogleSheetsProvider()
        result = await provider.export_leads(spreadsheet_id, sheet_name, leads_data)

        export_record = GoogleSheetExport(
            campaign_id=None,
            spreadsheet_id=result.get("spreadsheet_id", "default"),
            sheet_name=sheet_name,
            total_rows_exported=len(leads_data),
            status=result.get("status", "completed"),
            last_synced_at=datetime.now(timezone.utc),
        )
        session.add(export_record)
        await session.commit()
        await session.refresh(export_record)
        return export_record
