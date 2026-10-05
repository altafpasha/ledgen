from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SheetExportCampaignRequest(BaseModel):
    spreadsheet_id: Optional[str] = None
    sheet_name: str = "Leads"


class SheetExportLeadsRequest(BaseModel):
    lead_ids: List[str] = Field(min_length=1, max_length=1000)
    spreadsheet_id: Optional[str] = None
    sheet_name: str = "Exported Leads"


class SheetExportResponse(BaseModel):
    export_id: str
    campaign_id: Optional[str] = None
    spreadsheet_id: str
    sheet_name: str
    total_rows_exported: int
    status: str
    spreadsheet_url: str
    message: str


class SheetStatusRead(BaseModel):
    configured: bool
    mock_mode: bool
    spreadsheet_id: Optional[str] = None
    status: str
