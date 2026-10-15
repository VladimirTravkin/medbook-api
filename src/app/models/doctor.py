"""Doctor model (profile linked to a user with doctor role)."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Doctor(Base, TimestampMixin):
    """Doctor profile linked to a User with role 'doctor'."""

    __tablename__ = "doctors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    specialization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("specializations.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    experience_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # === Relationships ===
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        lazy="joined",
        foreign_keys=[user_id],
    )
    specialization: Mapped["Specialization"] = relationship(  # noqa: F821
        "Specialization",
        lazy="joined",
        foreign_keys=[specialization_id],
    )

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} user_id={self.user_id}>"
