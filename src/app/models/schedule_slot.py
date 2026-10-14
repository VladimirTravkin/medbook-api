"""ScheduleSlot model (doctor's time slot available for booking)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ScheduleSlot(Base, TimestampMixin):
    """Time slot published by a doctor and available for booking."""

    __tablename__ = "schedule_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_slot_time_range"),
        Index("ix_slots_doctor_start", "doctor_id", "start_time"),
        Index("ix_slots_doctor_booked_start", "doctor_id", "is_booked", "start_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    is_booked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # === Relationships ===
    doctor: Mapped["Doctor"] = relationship(  # noqa: F821
        "Doctor",
        foreign_keys=[doctor_id],
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduleSlot id={self.id} doctor_id={self.doctor_id} "
            f"start={self.start_time} booked={self.is_booked}>"
        )
