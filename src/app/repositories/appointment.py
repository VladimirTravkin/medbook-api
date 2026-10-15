"""Appointment repository."""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from app.models.appointment import Appointment, AppointmentStatus
from app.models.doctor import Doctor
from app.models.schedule_slot import ScheduleSlot
from app.repositories.base import BaseRepository

ACTIVE_STATUSES = (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)


class AppointmentRepository(BaseRepository[Appointment]):
    """Repository for Appointment model."""

    model = Appointment

    async def get_with_relations(self, appointment_id: uuid.UUID) -> Appointment | None:
        """Get appointment with slot, patient and doctor eagerly loaded."""
        stmt = (
            select(Appointment)
            .options(
                joinedload(Appointment.slot),
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor).joinedload(Doctor.user),
            )
            .where(Appointment.id == appointment_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slot(self, slot_id: uuid.UUID) -> Appointment | None:
        """Get appointment by slot id (slot is unique per appointment)."""
        stmt = select(Appointment).where(Appointment.slot_id == slot_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_active_by_patient(self, patient_id: uuid.UUID) -> int:
        """Count patient's active (pending or confirmed) appointments."""
        stmt = (
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status.in_(ACTIVE_STATUSES),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def find_patient_conflict(
        self,
        patient_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment | None:
        """Find an active appointment of the patient overlapping the given time.

        Joins with schedule_slots to compare time ranges.
        """
        stmt = (
            select(Appointment)
            .join(ScheduleSlot, Appointment.slot_id == ScheduleSlot.id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status.in_(ACTIVE_STATUSES),
                and_(
                    ScheduleSlot.start_time < end_time,
                    ScheduleSlot.end_time > start_time,
                ),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_patient(
        self,
        patient_id: uuid.UUID,
        *,
        status: AppointmentStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Appointment]:
        """List patient's appointments with slot loaded."""
        stmt = (
            select(Appointment)
            .options(
                joinedload(Appointment.slot),
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor).joinedload(Doctor.user),
            )
            .where(Appointment.patient_id == patient_id)
        )
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        stmt = (
            stmt.order_by(ScheduleSlot.start_time.desc())
            .join(ScheduleSlot, Appointment.slot_id == ScheduleSlot.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_for_patient(
        self,
        patient_id: uuid.UUID,
        *,
        status: AppointmentStatus | None = None,
    ) -> int:
        """Count patient's appointments."""
        stmt = (
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.patient_id == patient_id)
        )
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_for_doctor(
        self,
        doctor_id: uuid.UUID,
        *,
        status: AppointmentStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Appointment]:
        """List doctor's appointments with slot and patient loaded."""
        stmt = (
            select(Appointment)
            .options(
                joinedload(Appointment.slot),
                joinedload(Appointment.patient),
                joinedload(Appointment.doctor).joinedload(Doctor.user),
            )
            .where(Appointment.doctor_id == doctor_id)
        )
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        stmt = (
            stmt.order_by(ScheduleSlot.start_time.desc())
            .join(ScheduleSlot, Appointment.slot_id == ScheduleSlot.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_for_doctor(
        self,
        doctor_id: uuid.UUID,
        *,
        status: AppointmentStatus | None = None,
    ) -> int:
        """Count doctor's appointments."""
        stmt = (
            select(func.count()).select_from(Appointment).where(Appointment.doctor_id == doctor_id)
        )
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_all(
        self,
        *,
        status: AppointmentStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Appointment]:
        """List all appointments (admin view)."""
        stmt = select(Appointment).options(
            joinedload(Appointment.slot),
            joinedload(Appointment.patient),
            joinedload(Appointment.doctor).joinedload(Doctor.user),
        )
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        stmt = (
            stmt.order_by(ScheduleSlot.start_time.desc())
            .join(ScheduleSlot, Appointment.slot_id == ScheduleSlot.id)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def count_all(
        self,
        *,
        status: AppointmentStatus | None = None,
    ) -> int:
        """Count all appointments (admin view)."""
        stmt = select(func.count()).select_from(Appointment)
        if status is not None:
            stmt = stmt.where(Appointment.status == status)
        result = await self.session.execute(stmt)
        return result.scalar_one()
