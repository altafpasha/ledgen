import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, GUID, TimestampMixin, utc_now


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    locations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    max_leads: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    enrich_contacts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    analyze_websites: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_qualification: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    google_sheet_sync: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Budget Limits
    max_apify_cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    max_apollo_credits: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    max_ai_requests: Mapped[int] = mapped_column(Integer, default=500, nullable=False)

    # State: DRAFT, QUEUED, DISCOVERING, NORMALIZING, DEDUPLICATING, QUALIFYING, ENRICHING, ANALYZING, SCORING, EXPORTING, COMPLETED, FAILED, PAUSED
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False, index=True)

    # Counter metrics
    leads_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_enriched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_scored: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_exported: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by_id: Mapped[Optional[str]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    created_by: Mapped[Optional["User"]] = relationship("User", back_populates="campaigns")
    leads: Mapped[List["CampaignLead"]] = relationship("CampaignLead", back_populates="campaign", cascade="all, delete-orphan")
    discovery_jobs: Mapped[List["DiscoveryJob"]] = relationship("DiscoveryJob", back_populates="campaign", cascade="all, delete-orphan")
    sheet_exports: Mapped[List["GoogleSheetExport"]] = relationship("GoogleSheetExport", back_populates="campaign", cascade="all, delete-orphan")


class CampaignLead(Base):
    __tablename__ = "campaign_leads"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    campaign_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="DISCOVERED", nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="leads")
    business: Mapped["Business"] = relationship("Business", back_populates="campaign_associations")

    __table_args__ = (
        Index("ix_campaign_lead_uniq", "campaign_id", "business_id", unique=True),
    )
