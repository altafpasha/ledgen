import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, GUID, TimestampMixin, utc_now


class LeadScore(Base, TimestampMixin):
    __tablename__ = "lead_scores"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )

    deterministic_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    final_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)

    scoring_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    business: Mapped["Business"] = relationship("Business", back_populates="scores")

    __table_args__ = (
        Index("ix_lead_score_final", "final_score"),
    )
