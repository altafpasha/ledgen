from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    id: str
    campaign_id: str
    status: str
    progress: int
    current_stage: str
    processed: int
    total: int
    successful: int
    failed: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobActionResponse(BaseModel):
    job_id: str
    status: str
    message: str
