"""Doctor repository."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models.doctor import Doctor
from app.repositories.base import BaseRepository


class DoctorRepository(BaseRepository[Doctor]):
    """Repository for Doctor model."""

    model = Doctor

    async def get_with_relations(self, doctor_id: uuid.UUID) -> Doctor | None:
        """Get a doctor with user and specialization eagerly loaded."""
        stmt = (
            select(Doctor)
            .options(joinedload(Doctor.user), joinedload(Doctor.specialization))
            .where(Doctor.id == doctor_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Doctor | None:
        """Get a doctor profile by linked user id."""
        stmt = select(Doctor).where(Doctor.user_id == user_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_with_filters(
        self,
        *,
        specialization_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Doctor]:
        """List doctors with optional specialization filter and pagination."""
        stmt = select(Doctor).options(
            joinedload(Doctor.user),
            joinedload(Doctor.specialization),
        )
        if specialization_id is not None:
            stmt = stmt.where(Doctor.specialization_id == specialization_id)
        stmt = stmt.order_by(Doctor.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_filtered(
        self,
        *,
        specialization_id: uuid.UUID | None = None,
    ) -> int:
        """Count doctors matching optional specialization filter."""
        stmt = select(func.count()).select_from(Doctor)
        if specialization_id is not None:
            stmt = stmt.where(Doctor.specialization_id == specialization_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def specialization_in_use(self, specialization_id: uuid.UUID) -> bool:
        """Check whether any doctor uses the given specialization."""
        stmt = select(Doctor.id).where(Doctor.specialization_id == specialization_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
