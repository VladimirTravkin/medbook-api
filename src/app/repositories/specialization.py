"""Specialization repository."""

from sqlalchemy import select

from app.models.specialization import Specialization
from app.repositories.base import BaseRepository


class SpecializationRepository(BaseRepository[Specialization]):
    """Repository for Specialization model."""

    model = Specialization

    async def get_by_name(self, name: str) -> Specialization | None:
        """Get specialization by name (case-insensitive)."""
        stmt = select(Specialization).where(Specialization.name == name).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def name_exists(self, name: str, exclude_id: object | None = None) -> bool:
        """Check whether a specialization with given name already exists.

        Args:
            name: specialization name to check.
            exclude_id: optional id to exclude from the check (for updates).
        """
        stmt = select(Specialization.id).where(Specialization.name == name)
        if exclude_id is not None:
            stmt = stmt.where(Specialization.id != exclude_id)
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
