import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, GUID, utc_now


class ProviderUsage(Base):
    __tablename__ = "provider_usage"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # provider: apify, apollo, openrouter, google_sheets
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    campaign_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True, index=True)

    requests: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    credits_used: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
