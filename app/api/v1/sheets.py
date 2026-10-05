from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import RateLimiter, get_current_active_user, get_db, record_audit_log
from app.core.config import settings
from app.db.models.user import User
from app.schemas.sheets import (
    SheetExportCampaignRequest,
    SheetExportLeadsRequest,
    SheetExportResponse,
    SheetStatusRead,
)
from app.services.sheets_service import SheetsService

router = APIRouter(prefix="/google-sheets", tags=["Google Sheets Export & Sync"])


@router.get(
    "/status",
    response_model=SheetStatusRead,
    summary="Google Sheets Integration Status",
    description="Returns current Google Sheets configuration and mock status.",
)
async def get_google_sheets_status_endpoint(user: User = Depends(get_current_active_user)):
    is_configured = bool(settings.google_client_id and settings.google_client_secret and settings.google_refresh_token)
    return SheetStatusRead(
        configured=is_configured,
        mock_mode=settings.mock_providers or not is_configured,
        spreadsheet_id=settings.google_sheets_spreadsheet_id,
        status="ready" if (is_configured or settings.mock_providers) else "unconfigured",
    )


@router.post(
    "/export/campaign/{campaign_id}",
    response_model=SheetExportResponse,
    summary="Export Campaign to Google Sheets",
    description="Synchronizes all leads in the campaign into Google Sheets rows. Adheres to strict null cell rules.",
    dependencies=[Depends(RateLimiter(requests_per_minute=10))],
)
async def export_campaign_endpoint(
    campaign_id: str,
    req: SheetExportCampaignRequest = SheetExportCampaignRequest(),
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    export_record = await SheetsService.export_campaign_to_sheet(
        session=session,
        campaign_id=campaign_id,
        spreadsheet_id=req.spreadsheet_id,
        sheet_name=req.sheet_name,
    )

    await record_audit_log(
        session=session,
        action="SHEET_EXPORT_CAMPAIGN",
        resource_type="CAMPAIGN",
        resource_id=campaign_id,
        user_id=user.id,
        details={"spreadsheet_id": export_record.spreadsheet_id, "rows": export_record.total_rows_exported},
    )

    return SheetExportResponse(
        export_id=export_record.id,
        campaign_id=campaign_id,
        spreadsheet_id=export_record.spreadsheet_id,
        sheet_name=export_record.sheet_name,
        total_rows_exported=export_record.total_rows_exported,
        status=export_record.status,
        spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{export_record.spreadsheet_id}/edit",
        message=f"Successfully exported {export_record.total_rows_exported} leads to Google Sheets.",
    )


@router.post(
    "/export/leads",
    response_model=SheetExportResponse,
    summary="Export Selected Leads to Google Sheets",
    description="Exports a specific list of lead UUIDs into a Google Sheets spreadsheet.",
    dependencies=[Depends(RateLimiter(requests_per_minute=10))],
)
async def export_selected_leads_endpoint(
    req: SheetExportLeadsRequest,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    export_record = await SheetsService.export_selected_leads_to_sheet(
        session=session,
        lead_ids=req.lead_ids,
        spreadsheet_id=req.spreadsheet_id,
        sheet_name=req.sheet_name,
    )

    return SheetExportResponse(
        export_id=export_record.id,
        campaign_id=None,
        spreadsheet_id=export_record.spreadsheet_id,
        sheet_name=export_record.sheet_name,
        total_rows_exported=export_record.total_rows_exported,
        status=export_record.status,
        spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{export_record.spreadsheet_id}/edit",
        message=f"Successfully exported {export_record.total_rows_exported} selected leads to Google Sheets.",
    )


@router.post(
    "/sync/{campaign_id}",
    response_model=SheetExportResponse,
    summary="Sync Campaign with Existing Google Sheet",
    description="Updates existing rows and appends any newly qualified leads.",
)
async def sync_campaign_sheet_endpoint(
    campaign_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    export_record = await SheetsService.export_campaign_to_sheet(
        session=session,
        campaign_id=campaign_id,
    )
    return SheetExportResponse(
        export_id=export_record.id,
        campaign_id=campaign_id,
        spreadsheet_id=export_record.spreadsheet_id,
        sheet_name=export_record.sheet_name,
        total_rows_exported=export_record.total_rows_exported,
        status=export_record.status,
        spreadsheet_url=f"https://docs.google.com/spreadsheets/d/{export_record.spreadsheet_id}/edit",
        message="Campaign synchronized with Google Sheets.",
    )
