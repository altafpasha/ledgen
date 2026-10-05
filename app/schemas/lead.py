from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LeadScoreRead(BaseModel):
    deterministic_score: int
    ai_score: Optional[int] = None
    final_score: int
    scoring_breakdown: Optional[dict] = None
    scored_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebsiteAnalysisRead(BaseModel):
    website_url: str
    is_https: bool
    http_status: Optional[int] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    technologies: Optional[dict] = None
    security_headers: Optional[dict] = None
    performance_indicators: Optional[dict] = None
    emails_found: List[str] = []
    phones_found: List[str] = []
    analysis_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AIDecisionRead(BaseModel):
    model_name: str
    lead_quality: str
    score: int
    recommended_service: str
    opportunity: str
    reason: str
    confidence: float
    needs_enrichment: bool

    model_config = ConfigDict(from_attributes=True)


class OutreachStatusRead(BaseModel):
    status: str
    last_contacted_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    contact_notes: Optional[str] = None
    assigned_to_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ContactRead(BaseModel):
    id: str
    name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    source: str
    is_verified: bool

    model_config = ConfigDict(from_attributes=True)


class LeadRead(BaseModel):
    id: str
    business_name: str
    category: Optional[str] = None
    subcategory: Optional[str] = None

    phone: Optional[str] = None
    email: Optional[str] = None
    owner_name: Optional[str] = None
    website: Optional[str] = None
    has_website: bool

    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    google_maps_url: Optional[str] = None
    source: str

    lead_score: int = 0
    opportunity: str = "UNKNOWN"
    status: str = "NEW"

    last_enriched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    scores: Optional[List[LeadScoreRead]] = None
    website_analyses: Optional[List[WebsiteAnalysisRead]] = None
    ai_decisions: Optional[List[AIDecisionRead]] = None
    contacts: Optional[List[ContactRead]] = None
    outreach: Optional[OutreachStatusRead] = None

    model_config = ConfigDict(from_attributes=True)


class LeadUpdate(BaseModel):
    business_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    owner_name: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    category: Optional[str] = None


class LeadOutreachUpdate(BaseModel):
    status: str = Field(description="NEW, CONTACTED, INTERESTED, FOLLOW_UP, PROPOSAL, WON, LOST, NOT_INTERESTED, INVALID")
    contact_notes: Optional[str] = None
    next_followup_at: Optional[datetime] = None


class LeadNotesUpdate(BaseModel):
    contact_notes: str


class LeadBulkRequest(BaseModel):
    lead_ids: List[str] = Field(min_length=1, max_length=100, description="List of lead UUIDs (max 100 per bulk call)")
