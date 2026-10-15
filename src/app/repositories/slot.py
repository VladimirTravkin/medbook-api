"""Schedule slot repository."""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, select

from app.models.schedule_slot import ScheduleSlot
from app.repositories.base import BaseRepository


class SlotRepository(BaseRepository[ScheduleSlot]):
    """Repository for ScheduleSlot model."""

    model = ScheduleSlot

    async def list_by_doctor(
        self,
        doctor_id: uuid.UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        only_free: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ScheduleSlot]:
        """List doctor's slots with optional date range and free-only filter."""
        stmt = select(ScheduleSlot).where(ScheduleSlot.doctor_id == doctor_id)
        if date_from is not None:
            stmt = stmt.where(ScheduleSlot.start_time >= date_from)
        if date_to is not None:
            stmt = stmt.where(ScheduleSlot.start_time <= date_to)
        if only_free:
            stmt = stmt.where(ScheduleSlot.is_booked.is_(False))
        stmt = stmt.order_by(ScheduleSlot.start_time.asc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_doctor(
        self,
        doctor_id: uuid.UUID,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        only_free: bool = False,
    ) -> int:
        """Count doctor's slots matching filters."""
        stmt = (
            select(func.count())
            .select_from(ScheduleSlot)
            .where(ScheduleSlot.doctor_id == doctor_id)
        )
        if date_from is not None:
            stmt = stmt.where(ScheduleSlot.start_time >= date_from)
        if date_to is not None:
            stmt = stmt.where(ScheduleSlot.start_time <= date_to)
        if only_free:
            stmt = stmt.where(ScheduleSlot.is_booked.is_(False))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def find_overlapping(
        self,
        doctor_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> ScheduleSlot | None:
        """Find a slot of the doctor overlapping the given time range.

        Overlap condition: existing.start < new.end AND existing.end > new.start.
        """
        stmt = (
            select(ScheduleSlot)
            .where(
                ScheduleSlot.doctor_id == doctor_id,
                and_(
                    ScheduleSlot.start_time < end_time,
                    ScheduleSlot.end_time > start_time,
                ),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_existing_starts(
        self,
        doctor_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> set[datetime]:
        """Return set of start_time values of the doctor's slots in a range.

        Used during bulk generation to skip already existing slots efficiently.
        """
        stmt = select(ScheduleSlot.start_time).where(
            ScheduleSlot.doctor_id == doctor_id,
            ScheduleSlot.start_time >= start_time,
            ScheduleSlot.start_time <= end_time,
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_with_lock(self, slot_id: uuid.UUID) -> ScheduleSlot | None:
        """Get slot with row-level lock (SELECT ... FOR UPDATE).

        Used when booking to prevent race conditions on the same slot.
        """
        stmt = select(ScheduleSlot).where(ScheduleSlot.id == slot_id).with_for_update().limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
