"""Specialization service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.specialization import Specialization
from app.repositories.doctor import DoctorRepository
from app.repositories.specialization import SpecializationRepository
from app.schemas.specialization import SpecializationCreate, SpecializationUpdate


class SpecializationService:
    """Business logic for medical specializations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.specializations = SpecializationRepository(session)
        self.doctors = DoctorRepository(session)

    async def list_all(self, *, offset: int = 0, limit: int = 100) -> list[Specialization]:
        """Return all specializations."""
        return await self.specializations.list(
            offset=offset,
            limit=limit,
            order_by=Specialization.name.asc(),
        )

    async def count(self) -> int:
        """Count all specializations."""
        return await self.specializations.count()

    async def get_or_404(self, specialization_id: uuid.UUID) -> Specialization:
        """Get specialization by id or raise NotFoundError."""
        spec = await self.specializations.get(specialization_id)
        if spec is None:
            raise NotFoundError("Специализация не найдена")
        return spec

    async def create(self, data: SpecializationCreate) -> Specialization:
        """Create a new specialization."""
        if await self.specializations.name_exists(data.name):
            raise ConflictError("Специализация с таким названием уже существует")

        spec = await self.specializations.create(
            name=data.name,
            description=data.description,
        )
        await self.session.commit()
        return spec

    async def update(
        self,
        specialization_id: uuid.UUID,
        data: SpecializationUpdate,
    ) -> Specialization:
        """Update an existing specialization."""
        spec = await self.get_or_404(specialization_id)
        updates = data.model_dump(exclude_unset=True)

        if "name" in updates and updates["name"] != spec.name:
            if await self.specializations.name_exists(updates["name"], exclude_id=spec.id):
                raise ConflictError("Специализация с таким названием уже существует")

        if updates:
            await self.specializations.update(spec, **updates)
            await self.session.commit()
        return spec

    async def delete(self, specialization_id: uuid.UUID) -> None:
        """Delete a specialization if no doctors reference it."""
        spec = await self.get_or_404(specialization_id)
        if await self.doctors.specialization_in_use(spec.id):
            raise ConflictError("Нельзя удалить специализацию, пока к ней привязаны врачи")
        await self.specializations.delete(spec)
        await self.session.commit()
