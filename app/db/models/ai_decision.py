import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, GUID, TimestampMixin


class AIDecision(Base, TimestampMixin):
    __tablename__ = "ai_decisions"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[Optional[str]] = mapped_column(
        GUID(), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    lead_quality: Mapped[str] = mapped_column(String(50), nullable=False)  # high, medium, low, unqualified
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_service: Mapped[str] = mapped_column(String(100), nullable=False)
    opportunity: Mapped[str] = mapped_column(String(100), nullable=False)  # NO_WEBSITE, WEBSITE_REBUILD, etc.
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    needs_enrichment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    raw_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    business: Mapped["Business"] = relationship("Business", back_populates="ai_decisions")
