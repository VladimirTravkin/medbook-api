"""Specialization endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.specialization import (
    SpecializationCreate,
    SpecializationRead,
    SpecializationUpdate,
)
from app.services.specialization import SpecializationService

router = APIRouter(prefix="/specializations", tags=["specializations"])


async def get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SpecializationService:
    """Provide a SpecializationService bound to the current session."""
    return SpecializationService(db)


ServiceDep = Annotated[SpecializationService, Depends(get_service)]


@router.get(
    "",
    response_model=list[SpecializationRead],
    summary="Список специализаций",
    description="Публичный список всех специализаций.",
)
async def list_specializations(service: ServiceDep) -> list[SpecializationRead]:
    """Return all specializations."""
    items = await service.list_all()
    return [SpecializationRead.model_validate(s) for s in items]


@router.get(
    "/{specialization_id}",
    response_model=SpecializationRead,
    summary="Специализация по ID",
    description="Информация о специализации по её идентификатору.",
)
async def get_specialization(
    specialization_id: uuid.UUID,
    service: ServiceDep,
) -> SpecializationRead:
    """Return a single specialization by id."""
    spec = await service.get_or_404(specialization_id)
    return SpecializationRead.model_validate(spec)


@router.post(
    "",
    response_model=SpecializationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать специализацию",
    description="Создать новую специализацию. Доступно только администратору.",
)
async def create_specialization(
    data: SpecializationCreate,
    service: ServiceDep,
    _: Annotated[User, Depends(require_admin)],
) -> SpecializationRead:
    """Create a new specialization (admin only)."""
    spec = await service.create(data)
    return SpecializationRead.model_validate(spec)


@router.patch(
    "/{specialization_id}",
    response_model=SpecializationRead,
    summary="Обновить специализацию",
    description="Обновить специализацию. Доступно только администратору.",
)
async def update_specialization(
    specialization_id: uuid.UUID,
    data: SpecializationUpdate,
    service: ServiceDep,
    _: Annotated[User, Depends(require_admin)],
) -> SpecializationRead:
    """Update a specialization (admin only)."""
    spec = await service.update(specialization_id, data)
    return SpecializationRead.model_validate(spec)


@router.delete(
    "/{specialization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить специализацию",
    description="Удалить специализацию. Нельзя, если к ней привязаны врачи. Только администратор.",
)
async def delete_specialization(
    specialization_id: uuid.UUID,
    service: ServiceDep,
    _: Annotated[User, Depends(require_admin)],
) -> None:
    """Delete a specialization (admin only)."""
    await service.delete(specialization_id)
