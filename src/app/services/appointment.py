"""Appointment service with booking rules and lifecycle management."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User, UserRole
from app.repositories.appointment import AppointmentRepository
from app.repositories.doctor import DoctorRepository
from app.repositories.slot import SlotRepository


class AppointmentService:
    """Business logic for patient appointments."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.appointments = AppointmentRepository(session)
        self.slots = SlotRepository(session)
        self.doctors = DoctorRepository(session)

    # ============================================
    # Create
    # ============================================

    async def create_appointment(
        self,
        slot_id: uuid.UUID,
        notes: str | None,
        patient: User,
    ) -> Appointment:
        """Book a slot for the current patient.

        Rules enforced (in order):
            1. Slot must exist.
            2. Slot start must be in the future.
            3. Slot must not be already booked.
            4. Patient must not have another active appointment overlapping.
            5. Patient must not exceed the active appointments limit.
        """
        if patient.role != UserRole.PATIENT:
            raise ForbiddenError("Записаться может только пациент")

        # Row-level lock prevents two concurrent bookings on the same slot
        slot = await self.slots.get_with_lock(slot_id)
        if slot is None:
            raise NotFoundError("Слот не найден")

        # Rule 1: slot must be in the future
        if slot.start_time <= datetime.now(UTC):
            raise BadRequestError("Нельзя записаться на прошедшее время")

        # Rule 2: slot must not be booked
        if slot.is_booked:
            raise ConflictError("Этот слот уже занят")

        # Rule 3: patient must not have overlapping active appointments
        conflict = await self.appointments.find_patient_conflict(
            patient.id, slot.start_time, slot.end_time
        )
        if conflict is not None:
            raise ConflictError("У вас уже есть запись на это время")

        # Rule 4: active appointments limit
        active_count = await self.appointments.count_active_by_patient(patient.id)
        if active_count >= settings.MAX_ACTIVE_APPOINTMENTS:
            raise ConflictError(
                f"Достигнут лимит активных записей ({settings.MAX_ACTIVE_APPOINTMENTS})"
            )

        # Create appointment and mark slot as booked
        appointment = await self.appointments.create(
            patient_id=patient.id,
            doctor_id=slot.doctor_id,
            slot_id=slot.id,
            status=AppointmentStatus.PENDING,
            notes=notes,
        )
        await self.slots.update(slot, is_booked=True)
        await self.session.commit()

        # Reload with relations
        created = await self.appointments.get_with_relations(appointment.id)
        assert created is not None  # just created
        return created

    # ============================================
    # Read
    # ============================================

    async def list_my_appointments(
        self,
        user: User,
        *,
        status: AppointmentStatus | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[Appointment], int, str]:
        """List appointments for the current user.

        Behavior depends on role:
            - patient: sees only their own appointments
            - doctor:  sees appointments to themselves
            - admin:   sees all appointments

        Returns:
            (items, total, scope) where scope is "patient" | "doctor" | "admin".
        """
        offset = (page - 1) * size

        if user.role == UserRole.PATIENT:
            items = await self.appointments.list_for_patient(
                user.id, status=status, offset=offset, limit=size
            )
            total = await self.appointments.count_for_patient(user.id, status=status)
            return items, total, "patient"

        if user.role == UserRole.DOCTOR:
            doctor = await self.doctors.get_by_user_id(user.id)
            if doctor is None:
                raise NotFoundError("Профиль врача не найден")
            items = await self.appointments.list_for_doctor(
                doctor.id, status=status, offset=offset, limit=size
            )
            total = await self.appointments.count_for_doctor(doctor.id, status=status)
            return items, total, "doctor"

        # Admin
        items = await self.appointments.list_all(status=status, offset=offset, limit=size)
        total = await self.appointments.count_all(status=status)
        return items, total, "admin"

    async def get_appointment(self, appointment_id: uuid.UUID, user: User) -> Appointment:
        """Get a single appointment with access check."""
        appointment = await self.appointments.get_with_relations(appointment_id)
        if appointment is None:
            raise NotFoundError("Запись не найдена")

        await self._ensure_can_view(appointment, user)
        return appointment

    async def _ensure_can_view(self, appointment: Appointment, user: User) -> None:
        """Raise ForbiddenError if user cannot view this appointment."""
        if user.role == UserRole.ADMIN:
            return
        if user.role == UserRole.PATIENT and appointment.patient_id == user.id:
            return
        if user.role == UserRole.DOCTOR:
            doctor = await self.doctors.get_by_user_id(user.id)
            if doctor is not None and appointment.doctor_id == doctor.id:
                return
        raise ForbiddenError("Нет доступа к этой записи")

    # ============================================
    # Update status (doctor/admin)
    # ============================================

    async def update_status(
        self,
        appointment_id: uuid.UUID,
        new_status: AppointmentStatus,
        user: User,
    ) -> Appointment:
        """Update appointment status. Doctor (owner) or admin only.

        Allowed transitions:
            pending   -> confirmed, cancelled, no_show
            confirmed -> completed, cancelled, no_show
            cancelled -> (terminal)
            completed -> (terminal)
            no_show   -> (terminal)
        """
        if user.role not in (UserRole.DOCTOR, UserRole.ADMIN):
            raise ForbiddenError("Менять статус может только врач или администратор")

        appointment = await self.appointments.get_with_relations(appointment_id)
        if appointment is None:
            raise NotFoundError("Запись не найдена")

        # Doctors can only manage their own appointments
        if user.role == UserRole.DOCTOR:
            doctor = await self.doctors.get_by_user_id(user.id)
            if doctor is None or appointment.doctor_id != doctor.id:
                raise ForbiddenError("Нет доступа к этой записи")

        if appointment.status in (
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        ):
            raise ConflictError("Нельзя изменить статус завершённой записи")

        if new_status == appointment.status:
            return appointment

        previous_status = appointment.status
        await self.appointments.update(appointment, status=new_status)

        # Release the slot if the appointment becomes cancelled
        if new_status == AppointmentStatus.CANCELLED:
            slot = await self.slots.get(appointment.slot_id)
            if slot is not None and slot.is_booked:
                await self.slots.update(slot, is_booked=False)

        await self.session.commit()

        # Refresh with relations after commit
        updated = await self.appointments.get_with_relations(appointment.id)
        assert updated is not None
        _ = previous_status  # for future audit log
        return updated

    # ============================================
    # Cancel (patient)
    # ============================================

    async def cancel_appointment(
        self,
        appointment_id: uuid.UUID,
        user: User,
    ) -> Appointment:
        """Cancel an appointment.

        Rules:
            - patient: only own appointment, at least CANCELLATION_MIN_HOURS before start
            - doctor:  only own appointments, anytime
            - admin:   any appointment, anytime
        """
        appointment = await self.appointments.get_with_relations(appointment_id)
        if appointment is None:
            raise NotFoundError("Запись не найдена")

        # Access check
        if user.role == UserRole.PATIENT:
            if appointment.patient_id != user.id:
                raise ForbiddenError("Нет доступа к этой записи")
        elif user.role == UserRole.DOCTOR:
            doctor = await self.doctors.get_by_user_id(user.id)
            if doctor is None or appointment.doctor_id != doctor.id:
                raise ForbiddenError("Нет доступа к этой записи")
        # admin — ok

        if appointment.status in (
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        ):
            raise ConflictError("Запись уже завершена или отменена")

        # Time-based rule applies only to patients
        if user.role == UserRole.PATIENT:
            min_hours = settings.CANCELLATION_MIN_HOURS
            deadline = appointment.slot.start_time - timedelta(hours=min_hours)
            if datetime.now(UTC) >= deadline:
                raise BadRequestError(f"Отмена возможна не позднее чем за {min_hours} ч. до приёма")

        await self.appointments.update(appointment, status=AppointmentStatus.CANCELLED)

        # Release the slot
        slot = await self.slots.get(appointment.slot_id)
        if slot is not None and slot.is_booked:
            await self.slots.update(slot, is_booked=False)

        await self.session.commit()

        cancelled = await self.appointments.get_with_relations(appointment.id)
        assert cancelled is not None
        return cancelled
