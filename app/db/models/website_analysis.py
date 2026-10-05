import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, GUID, TimestampMixin


class WebsiteAnalysis(Base, TimestampMixin):
    __tablename__ = "website_analysis"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    website_url: Mapped[str] = mapped_column(Text, nullable=False)

    is_https: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Detected technologies: WordPress, WooCommerce, Shopify, Wix, Next.js, React, etc.
    technologies: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    # Security headers: Content-Security-Policy, Strict-Transport-Security, X-Frame-Options, etc.
    security_headers: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    # Performance indicators: page size bytes, has viewport meta, slow TTFB, etc.
    performance_indicators: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    # Extracted contact points
    emails_found: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    phones_found: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="website_analyses")
