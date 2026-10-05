from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CampaignCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None
    locations: List[str] = Field(min_length=1, description="Target locations e.g. KGF, Bangarapet, Bangalore")
    categories: List[str] = Field(min_length=1, description="Target categories e.g. restaurants, clinics, retail")
    max_leads: int = Field(default=500, ge=1, le=5000)
    enrich_contacts: bool = True
    analyze_websites: bool = True
    ai_qualification: bool = True
    google_sheet_sync: bool = True
    max_apollo_credits: int = Field(default=100, ge=0)
    max_ai_requests: int = Field(default=500, ge=0)


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    locations: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    max_leads: Optional[int] = Field(default=None, ge=1, le=5000)
    enrich_contacts: Optional[bool] = None
    analyze_websites: Optional[bool] = None
    ai_qualification: Optional[bool] = None
    google_sheet_sync: Optional[bool] = None
    max_apollo_credits: Optional[int] = None
    max_ai_requests: Optional[int] = None
    status: Optional[str] = None


class CampaignRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    locations: List[str]
    categories: List[str]
    max_leads: int
    enrich_contacts: bool
    analyze_websites: bool
    ai_qualification: bool
    google_sheet_sync: bool
    status: str
    leads_discovered: int
    leads_enriched: int
    leads_scored: int
    leads_exported: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignStats(BaseModel):
    campaign_id: str
    status: str
    total_leads: int
    leads_with_website: int
    leads_without_website: int
    leads_with_email: int
    leads_with_phone: int
    high_quality_leads: int
    average_score: float
    opportunities: dict


class CampaignRunResponse(BaseModel):
    job_id: str
    campaign_id: str
    status: str
    message: str
