"""Appointment model and status enumeration."""

import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AppointmentStatus(str, enum.Enum):
    """Appointment lifecycle status."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Appointment(Base, TimestampMixin):
    """Appointment booking a doctor's schedule slot for a patient."""

    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_patient_status", "patient_id", "status"),
        Index("ix_appointments_doctor_status", "doctor_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schedule_slots.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, name="appointment_status", native_enum=True),
        nullable=False,
        default=AppointmentStatus.PENDING,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # === Relationships ===
    patient: Mapped["User"] = relationship(  # noqa: F821
        "User",
        foreign_keys=[patient_id],
    )
    doctor: Mapped["Doctor"] = relationship(  # noqa: F821
        "Doctor",
        foreign_keys=[doctor_id],
    )
    slot: Mapped["ScheduleSlot"] = relationship(  # noqa: F821
        "ScheduleSlot",
        foreign_keys=[slot_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment id={self.id} patient_id={self.patient_id} "
            f"status={self.status.value}>"
        )
