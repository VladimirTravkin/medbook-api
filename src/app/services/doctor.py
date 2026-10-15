"""Doctor service with Redis caching."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.redis import cache_delete_pattern, cache_get, cache_set
from app.core.security import hash_password
from app.models.doctor import Doctor
from app.models.user import UserRole
from app.repositories.doctor import DoctorRepository
from app.repositories.specialization import SpecializationRepository
from app.repositories.user import UserRepository
from app.schemas.doctor import DoctorCreate, DoctorUpdate


class DoctorService:
    """Business logic for doctor profiles, with Redis caching."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.doctors = DoctorRepository(session)
        self.users = UserRepository(session)
        self.specializations = SpecializationRepository(session)

    # ============================================
    # Cache keys
    # ============================================

    @staticmethod
    def _list_key(specialization_id: uuid.UUID | None, page: int, size: int) -> str:
        spec_part = str(specialization_id) if specialization_id else "all"
        return f"doctors:list:{spec_part}:{page}:{size}"

    @staticmethod
    def _item_key(doctor_id: uuid.UUID) -> str:
        return f"doctor:{doctor_id}"

    async def _invalidate_cache(self, doctor_id: uuid.UUID | None = None) -> None:
        """Invalidate cached doctor lists and (optionally) a single doctor."""
        await cache_delete_pattern("doctors:list:*")
        if doctor_id is not None:
            await cache_delete_pattern(f"doctor:{doctor_id}")

    # ============================================
    # Read
    # ============================================

    async def list_doctors(
        self,
        *,
        specialization_id: uuid.UUID | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict], int]:
        """Return a page of doctors with total count, using cache when possible.

        Cached value is a dict: {"items": [...], "total": N}.
        """
        key = self._list_key(specialization_id, page, size)
        cached = await cache_get(key)
        if cached is not None:
            return cached["items"], cached["total"]

        offset = (page - 1) * size
        doctors = await self.doctors.list_with_filters(
            specialization_id=specialization_id,
            offset=offset,
            limit=size,
        )
        total = await self.doctors.count_filtered(specialization_id=specialization_id)

        items = [self._serialize_doctor(d) for d in doctors]
        await cache_set(
            key,
            {"items": items, "total": total},
            ttl=settings.CACHE_TTL_DOCTORS,
        )
        return items, total

    async def get_doctor(self, doctor_id: uuid.UUID) -> dict:
        """Return a single doctor by id, using cache when possible."""
        key = self._item_key(doctor_id)
        cached = await cache_get(key)
        if cached is not None:
            return cached

        doctor = await self.doctors.get_with_relations(doctor_id)
        if doctor is None:
            raise NotFoundError("Врач не найден")

        data = self._serialize_doctor(doctor)
        await cache_set(key, data, ttl=settings.CACHE_TTL_DOCTOR)
        return data

    async def get_doctor_model(self, doctor_id: uuid.UUID) -> Doctor:
        """Return a Doctor ORM object (used internally, no cache)."""
        doctor = await self.doctors.get_with_relations(doctor_id)
        if doctor is None:
            raise NotFoundError("Врач не найден")
        return doctor

    # ============================================
    # Write
    # ============================================

    async def create_doctor(self, data: DoctorCreate) -> dict:
        """Create a User with role=doctor and a linked Doctor profile."""
        email = data.email.lower()
        if await self.users.email_exists(email):
            raise ConflictError("Пользователь с таким email уже существует")

        spec = await self.specializations.get(data.specialization_id)
        if spec is None:
            raise NotFoundError("Специализация не найдена")

        user = await self.users.create(
            email=email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.DOCTOR,
            is_active=True,
        )
        doctor = await self.doctors.create(
            user_id=user.id,
            specialization_id=data.specialization_id,
            bio=data.bio,
            experience_years=data.experience_years,
            avatar_url=str(data.avatar_url) if data.avatar_url else None,
        )
        await self.session.commit()

        await self._invalidate_cache()
        created = await self.doctors.get_with_relations(doctor.id)
        assert created is not None  # just created
        return self._serialize_doctor(created)

    async def update_doctor(
        self,
        doctor_id: uuid.UUID,
        data: DoctorUpdate,
    ) -> dict:
        """Update a doctor profile."""
        doctor = await self.get_doctor_model(doctor_id)
        updates = data.model_dump(exclude_unset=True)

        if "specialization_id" in updates:
            spec = await self.specializations.get(updates["specialization_id"])
            if spec is None:
                raise NotFoundError("Специализация не найдена")

        if "avatar_url" in updates and updates["avatar_url"] is not None:
            updates["avatar_url"] = str(updates["avatar_url"])

        if updates:
            await self.doctors.update(doctor, **updates)
            await self.session.commit()

        await self._invalidate_cache(doctor_id)
        updated = await self.doctors.get_with_relations(doctor_id)
        assert updated is not None  # just updated
        return self._serialize_doctor(updated)

    async def delete_doctor(self, doctor_id: uuid.UUID) -> None:
        """Delete a doctor profile (and linked user via cascade)."""
        doctor = await self.get_doctor_model(doctor_id)
        # Deleting the user cascades to doctor; delete user to be explicit
        await self.users.delete(doctor.user)
        await self.session.commit()
        await self._invalidate_cache(doctor_id)

    # ============================================
    # Serialization for cache
    # ============================================

    @staticmethod
    def _serialize_doctor(doctor: Doctor) -> dict:
        """Serialize a Doctor ORM object into a JSON-friendly dict for cache/response."""
        return {
            "id": str(doctor.id),
            "user_id": str(doctor.user_id),
            "specialization_id": str(doctor.specialization_id),
            "full_name": doctor.user.full_name,
            "email": doctor.user.email,
            "bio": doctor.bio,
            "experience_years": doctor.experience_years,
            "avatar_url": doctor.avatar_url,
            "specialization": {
                "id": str(doctor.specialization.id),
                "name": doctor.specialization.name,
                "description": doctor.specialization.description,
                "created_at": doctor.specialization.created_at.isoformat(),
                "updated_at": doctor.specialization.updated_at.isoformat(),
            },
            "created_at": doctor.created_at.isoformat(),
            "updated_at": doctor.updated_at.isoformat(),
        }
