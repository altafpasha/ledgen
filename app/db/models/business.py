import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, GUID, TimestampMixin, utc_now


class Business(Base, TimestampMixin):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    normalized_business_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    normalized_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    has_website: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), default="India", nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="apify", nullable=False, index=True)
    source_business_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    google_maps_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    last_enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    contacts: Mapped[List["BusinessContact"]] = relationship(
        "BusinessContact", back_populates="business", cascade="all, delete-orphan"
    )
    locations: Mapped[List["BusinessLocation"]] = relationship(
        "BusinessLocation", back_populates="business", cascade="all, delete-orphan"
    )
    websites: Mapped[List["BusinessWebsite"]] = relationship(
        "BusinessWebsite", back_populates="business", cascade="all, delete-orphan"
    )
    scores: Mapped[List["LeadScore"]] = relationship(
        "LeadScore", back_populates="business", cascade="all, delete-orphan"
    )
    website_analyses: Mapped[List["WebsiteAnalysis"]] = relationship(
        "WebsiteAnalysis", back_populates="business", cascade="all, delete-orphan"
    )
    ai_decisions: Mapped[List["AIDecision"]] = relationship(
        "AIDecision", back_populates="business", cascade="all, delete-orphan"
    )
    outreach: Mapped[Optional["OutreachStatus"]] = relationship(
        "OutreachStatus", back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    campaign_associations: Mapped[List["CampaignLead"]] = relationship(
        "CampaignLead", back_populates="business", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_businesses_source_id", "source", "source_business_id"),
        Index("ix_businesses_city_cat", "city", "category"),
    )


class BusinessContact(Base, TimestampMixin):
    __tablename__ = "business_contacts"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="apollo", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="contacts")


class BusinessLocation(Base):
    __tablename__ = "business_locations"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="India")
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="locations")


class BusinessWebsite(Base):
    __tablename__ = "business_websites"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    is_https: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technology_stack: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    business: Mapped["Business"] = relationship("Business", back_populates="websites")


class LeadSource(Base):
    __tablename__ = "lead_sources"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
