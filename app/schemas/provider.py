from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ProviderStatusItem(BaseModel):
    provider: str
    configured: bool
    status: str
    mock_mode: bool
    description: str


class ProviderStatusResponse(BaseModel):
    providers: List[ProviderStatusItem]


class ProviderUsageItem(BaseModel):
    id: str
    provider: str
    operation: str
    campaign_id: Optional[str] = None
    job_id: Optional[str] = None
    requests: int
    credits_used: float
    estimated_cost: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsageSummary(BaseModel):
    total_requests: int
    total_credits: float
    total_estimated_cost: float
    by_provider: dict
