"""Appointment endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.appointment import AppointmentStatus
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentDetail,
    AppointmentRead,
    AppointmentStatusUpdate,
)
from app.schemas.common import Page
from app.services.appointment import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])


async def get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AppointmentService:
    """Provide an AppointmentService bound to the current session."""
    return AppointmentService(db)


ServiceDep = Annotated[AppointmentService, Depends(get_service)]


# ============================================
# Create (patient)
# ============================================


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Записаться на приём",
    description=(
        "Записаться на приём к врачу. Доступно только пациенту. "
        "Проверяются: прошедшее время, занятость слота, пересечения у пациента, "
        "лимит активных записей."
    ),
)
async def create_appointment(
    data: AppointmentCreate,
    service: ServiceDep,
    user: CurrentUser,
) -> AppointmentRead:
    """Book a slot for the current patient."""
    appointment = await service.create_appointment(data.slot_id, data.notes, user)
    return AppointmentRead.model_validate(appointment)


# ============================================
# List (role-aware)
# ============================================


@router.get(
    "",
    response_model=Page[AppointmentDetail],
    summary="Записи на приём",
    description=(
        "Список записей на приём в зависимости от роли: "
        "пациент видит свои записи, врач — приёмы к себе, "
        "администратор — все записи."
    ),
)
async def list_my_appointments(
    service: ServiceDep,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    appointment_status: Annotated[AppointmentStatus | None, Query(alias="status")] = None,
) -> Page[AppointmentDetail]:
    """Return a paginated list of appointments for the current user."""
    items, total, _scope = await service.list_my_appointments(
        user,
        status=appointment_status,
        page=page,
        size=size,
    )
    return Page.create(
        items=[AppointmentDetail.model_validate(_to_detail(a)) for a in items],
        total=total,
        page=page,
        size=size,
    )


# ============================================
# Get one
# ============================================


@router.get(
    "/{appointment_id}",
    response_model=AppointmentDetail,
    summary="Запись по ID",
    description="Детали записи. Доступно пациенту (своя), врачу (свой приём) и администратору.",
)
async def get_appointment(
    appointment_id: uuid.UUID,
    service: ServiceDep,
    user: CurrentUser,
) -> AppointmentDetail:
    """Return a single appointment with access check."""
    appointment = await service.get_appointment(appointment_id, user)
    return AppointmentDetail.model_validate(_to_detail(appointment))


# ============================================
# Update status (doctor/admin)
# ============================================


@router.patch(
    "/{appointment_id}/status",
    response_model=AppointmentDetail,
    summary="Изменить статус записи",
    description="Изменить статус записи. Доступно врачу (свой приём) или администратору.",
)
async def update_appointment_status(
    appointment_id: uuid.UUID,
    data: AppointmentStatusUpdate,
    service: ServiceDep,
    user: CurrentUser,
) -> AppointmentDetail:
    """Update appointment status."""
    appointment = await service.update_status(appointment_id, data.status, user)
    return AppointmentDetail.model_validate(_to_detail(appointment))


# ============================================
# Cancel
# ============================================


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentDetail,
    summary="Отменить запись",
    description=(
        "Отменить запись. Пациент может отменить только свою запись и не позднее "
        "чем за N часов до приёма. Врач и администратор — без ограничений."
    ),
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    service: ServiceDep,
    user: CurrentUser,
) -> AppointmentDetail:
    """Cancel an appointment."""
    appointment = await service.cancel_appointment(appointment_id, user)
    return AppointmentDetail.model_validate(_to_detail(appointment))


# ============================================
# Serialization helper
# ============================================


def _to_detail(appointment) -> dict:
    """Flatten an Appointment ORM object into a dict for AppointmentDetail.

    AppointmentDetail expects flat fields (patient_full_name, doctor_full_name)
    that are not direct attributes of the Appointment model.
    """
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "doctor_id": appointment.doctor_id,
        "slot_id": appointment.slot_id,
        "status": appointment.status,
        "notes": appointment.notes,
        "slot": appointment.slot,
        "patient_full_name": appointment.patient.full_name,
        "patient_email": appointment.patient.email,
        "doctor_full_name": appointment.doctor.user.full_name,
        "created_at": appointment.created_at,
        "updated_at": appointment.updated_at,
    }
