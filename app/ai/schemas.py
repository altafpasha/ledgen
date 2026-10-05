from typing import Literal
from pydantic import BaseModel, Field

OpportunityType = Literal[
    "NO_WEBSITE",
    "WEBSITE_REBUILD",
    "ECOMMERCE_OPPORTUNITY",
    "MOBILE_APP_OPPORTUNITY",
    "AUTOMATION_OPPORTUNITY",
    "DEVOPS_OPPORTUNITY",
    "CYBERSECURITY_OPPORTUNITY",
    "WEBSITE_SECURITY",
    "PERFORMANCE_OPTIMIZATION",
    "UNKNOWN",
]

LeadQualityType = Literal["high", "medium", "low", "unqualified"]


class JevDecisionSchema(BaseModel):
    lead_quality: LeadQualityType
    score: int = Field(ge=0, le=100, description="Lead rating between 0 and 100 based on opportunity fit")
    recommended_service: str = Field(description="Primary service from catalog")
    opportunity: OpportunityType
    reason: str = Field(description="Concise factual explanation based purely on provided evidence")
    needs_enrichment: bool = Field(description="Whether executive contact enrichment via Apollo is justified")
    confidence: float = Field(ge=0.0, le=1.0, default=0.9, description="Confidence score between 0.0 and 1.0")
