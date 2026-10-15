"""Doctor endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import Page
from app.schemas.doctor import DoctorCreate, DoctorRead, DoctorShort, DoctorUpdate
from app.services.doctor import DoctorService

router = APIRouter(prefix="/doctors", tags=["doctors"])


async def get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DoctorService:
    """Provide a DoctorService bound to the current session."""
    return DoctorService(db)


ServiceDep = Annotated[DoctorService, Depends(get_service)]


@router.get(
    "",
    response_model=Page[DoctorShort],
    summary="Список врачей",
    description="Публичный список врачей с пагинацией и фильтром по специализации.",
)
async def list_doctors(
    service: ServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    specialization_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[DoctorShort]:
    """Return a paginated list of doctors, optionally filtered by specialization."""
    items, total = await service.list_doctors(
        specialization_id=specialization_id,
        page=page,
        size=size,
    )
    doctors = [DoctorShort.model_validate(item) for item in items]
    return Page.create(items=doctors, total=total, page=page, size=size)


@router.get(
    "/{doctor_id}",
    response_model=DoctorRead,
    summary="Врач по ID",
    description="Подробная информация о враче по его идентификатору.",
)
async def get_doctor(doctor_id: uuid.UUID, service: ServiceDep) -> DoctorRead:
    """Return a single doctor by id."""
    data = await service.get_doctor(doctor_id)
    return DoctorRead.model_validate(data)


@router.post(
    "",
    response_model=DoctorRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать врача",
    description="Создать нового врача (учётную запись и профиль). Только администратор.",
)
async def create_doctor(
    data: DoctorCreate,
    service: ServiceDep,
    _: Annotated[User, Depends(require_admin)],
) -> DoctorRead:
    """Create a new doctor (admin only)."""
    doctor = await service.create_doctor(data)
    return DoctorRead.model_validate(doctor)


@router.patch(
    "/{doctor_id}",
    response_model=DoctorRead,
    summary="Обновить врача",
    description="Обновить профиль врача. Доступно администратору или самому врачу.",
)
async def update_doctor(
    doctor_id: uuid.UUID,
    data: DoctorUpdate,
    service: ServiceDep,
    _: Annotated[User, Depends(require_admin)],
) -> DoctorRead:
    """Update a doctor profile (admin only for now)."""
    doctor = await service.update_doctor(doctor_id, data)
    return DoctorRead.model_validate(doctor)


@router.delete(
    "/{doctor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить врача",
    description="Удалить врача (вместе с учётной записью). Только администратор.",
)
async def delete_doctor(
    doctor_id: uuid.UUID,
    service: ServiceDep,
    _: Annotated[User, Depends(require_admin)],
) -> None:
    """Delete a doctor (admin only)."""
    await service.delete_doctor(doctor_id)
