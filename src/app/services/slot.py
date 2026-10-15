"""Schedule slot service."""

import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.schedule_slot import ScheduleSlot
from app.models.user import User, UserRole
from app.repositories.doctor import DoctorRepository
from app.repositories.slot import SlotRepository
from app.schemas.slot import SlotCreate, SlotGenerateRequest


class SlotService:
    """Business logic for doctor schedule slots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.slots = SlotRepository(session)
        self.doctors = DoctorRepository(session)

    # ============================================
    # Authorization helper
    # ============================================

    async def _resolve_doctor_for_user(
        self,
        doctor_id: uuid.UUID,
        user: User,
    ) -> None:
        """Ensure the user may manage slots for the given doctor.

        Allowed: admin (any doctor), doctor (only their own profile).
        Raises ForbiddenError otherwise.
        """
        if user.role == UserRole.ADMIN:
            return
        if user.role == UserRole.DOCTOR:
            doctor = await self.doctors.get(doctor_id)
            if doctor is None:
                raise NotFoundError("Врач не найден")
            if doctor.user_id != user.id:
                raise ForbiddenError("Можно управлять только своими слотами")
            return
        raise ForbiddenError("Недостаточно прав для управления слотами")

    async def _get_doctor_or_404(self, doctor_id: uuid.UUID):
        """Get doctor profile or raise NotFoundError."""
        doctor = await self.doctors.get(doctor_id)
        if doctor is None:
            raise NotFoundError("Врач не найден")
        return doctor

    # ============================================
    # Create (single)
    # ============================================

    async def create_slot(
        self,
        doctor_id: uuid.UUID,
        data: SlotCreate,
        user: User,
    ) -> ScheduleSlot:
        """Create a single slot manually."""
        await self._resolve_doctor_for_user(doctor_id, user)
        await self._get_doctor_or_404(doctor_id)

        self._ensure_future(data.start_time)

        overlapping = await self.slots.find_overlapping(doctor_id, data.start_time, data.end_time)
        if overlapping is not None:
            raise ConflictError("Слот пересекается с существующим слотом врача")

        slot = await self.slots.create(
            doctor_id=doctor_id,
            start_time=data.start_time,
            end_time=data.end_time,
            is_booked=False,
        )
        await self.session.commit()
        return slot

    # ============================================
    # Generate (bulk)
    # ============================================

    async def generate_slots(
        self,
        doctor_id: uuid.UUID,
        data: SlotGenerateRequest,
        user: User,
    ) -> tuple[int, int]:
        """Bulk generate slots for a doctor over a date range.

        Returns:
            (created_count, skipped_count)
        """
        await self._resolve_doctor_for_user(doctor_id, user)
        await self._get_doctor_or_404(doctor_id)

        if data.date_to < datetime.now(UTC):
            raise BadRequestError("Диапазон дат полностью в прошлом")

        # Collect existing start times to skip duplicates
        range_start = datetime.combine(data.date_from.date(), time.min, tzinfo=UTC)
        range_end = datetime.combine(data.date_to.date(), time.max, tzinfo=UTC)
        existing_starts = await self.slots.list_existing_starts(doctor_id, range_start, range_end)

        created = 0
        skipped = 0
        now = datetime.now(UTC)

        current_date = data.date_from.date()
        end_date = data.date_to.date()

        while current_date <= end_date:
            if current_date.isoweekday() not in data.weekdays:
                current_date += timedelta(days=1)
                continue

            day_start = datetime.combine(current_date, data.work_day_start, tzinfo=UTC)
            day_end = datetime.combine(current_date, data.work_day_end, tzinfo=UTC)
            slot_delta = timedelta(minutes=data.slot_duration_minutes)

            cursor = day_start
            while cursor + slot_delta <= day_end:
                slot_start = cursor
                slot_end = cursor + slot_delta
                cursor = slot_end

                # Skip past slots
                if slot_start <= now:
                    skipped += 1
                    continue

                # Skip break
                if data.break_start and data.break_end:
                    break_start_dt = datetime.combine(current_date, data.break_start, tzinfo=UTC)
                    break_end_dt = datetime.combine(current_date, data.break_end, tzinfo=UTC)
                    if slot_start < break_end_dt and slot_end > break_start_dt:
                        skipped += 1
                        continue

                # Skip if a slot with this start already exists
                if slot_start in existing_starts:
                    skipped += 1
                    continue

                await self.slots.create(
                    doctor_id=doctor_id,
                    start_time=slot_start,
                    end_time=slot_end,
                    is_booked=False,
                )
                created += 1

            current_date += timedelta(days=1)

        await self.session.commit()
        return created, skipped

    # ============================================
    # Read
    # ============================================

    async def list_slots(
        self,
        doctor_id: uuid.UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        only_free: bool = False,
        page: int = 1,
        size: int = 100,
    ) -> tuple[list[ScheduleSlot], int]:
        """List doctor's slots with filters and pagination."""
        await self._get_doctor_or_404(doctor_id)
        offset = (page - 1) * size
        items = await self.slots.list_by_doctor(
            doctor_id,
            date_from=date_from,
            date_to=date_to,
            only_free=only_free,
            offset=offset,
            limit=size,
        )
        total = await self.slots.count_by_doctor(
            doctor_id,
            date_from=date_from,
            date_to=date_to,
            only_free=only_free,
        )
        return items, total

    # ============================================
    # Delete
    # ============================================

    async def delete_slot(self, slot_id: uuid.UUID, user: User) -> None:
        """Delete an unbooked slot. Doctor (owner) or admin only."""
        slot = await self.slots.get(slot_id)
        if slot is None:
            raise NotFoundError("Слот не найден")

        await self._resolve_doctor_for_user(slot.doctor_id, user)

        if slot.is_booked:
            raise ConflictError("Нельзя удалить занятый слот")

        await self.slots.delete(slot)
        await self.session.commit()

    # ============================================
    # Helpers
    # ============================================

    @staticmethod
    def _ensure_future(start_time: datetime) -> None:
        """Raise BadRequestError if start_time is not in the future."""
        # Normalize tz
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)
        if start_time <= datetime.now(UTC):
            raise BadRequestError("Нельзя создать слот в прошлом")


__all__ = ["SlotService"]
