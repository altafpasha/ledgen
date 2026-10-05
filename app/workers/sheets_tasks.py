import asyncio
from typing import List, Optional
from celery import shared_task
from app.db.session import get_task_async_session
from app.services.sheets_service import SheetsService


async def _run_export_campaign(campaign_id: str, spreadsheet_id: Optional[str], sheet_name: str):
    async with get_task_async_session() as session:
        await SheetsService.export_campaign_to_sheet(session, campaign_id, spreadsheet_id, sheet_name)


async def _run_export_leads(lead_ids: List[str], spreadsheet_id: Optional[str], sheet_name: str):
    async with get_task_async_session() as session:
        await SheetsService.export_selected_leads_to_sheet(session, lead_ids, spreadsheet_id, sheet_name)


@shared_task(name="app.workers.sheets_tasks.export_campaign_sheet_task")
def export_campaign_sheet_task(campaign_id: str, spreadsheet_id: Optional[str] = None, sheet_name: str = "Leads"):
    asyncio.run(_run_export_campaign(campaign_id, spreadsheet_id, sheet_name))
    return {"campaign_id": campaign_id, "status": "completed"}


@shared_task(name="app.workers.sheets_tasks.export_leads_sheet_task")
def export_leads_sheet_task(lead_ids: List[str], spreadsheet_id: Optional[str] = None, sheet_name: str = "Exported Leads"):
    asyncio.run(_run_export_leads(lead_ids, spreadsheet_id, sheet_name))
    return {"count": len(lead_ids), "status": "completed"}
