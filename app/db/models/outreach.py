import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, GUID, TimestampMixin


class OutreachStatus(Base, TimestampMixin):
    __tablename__ = "outreach_status"

    id: Mapped[str] = mapped_column(
        GUID(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    business_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # Status: NEW, CONTACTED, INTERESTED, FOLLOW_UP, PROPOSAL, WON, LOST, NOT_INTERESTED, INVALID
    status: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False, index=True)

    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    business: Mapped["Business"] = relationship("Business", back_populates="outreach")
    assigned_to: Mapped[Optional["User"]] = relationship("User")
