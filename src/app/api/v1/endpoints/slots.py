"""Schedule slot endpoints."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.schemas.common import Page
from app.schemas.slot import (
    SlotCreate,
    SlotGenerateRequest,
    SlotGenerateResponse,
    SlotRead,
)
from app.services.slot import SlotService

router = APIRouter(tags=["slots"])


async def get_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SlotService:
    """Provide a SlotService bound to the current session."""
    return SlotService(db)


ServiceDep = Annotated[SlotService, Depends(get_service)]


# ============================================
# List (public)
# ============================================


@router.get(
    "/doctors/{doctor_id}/slots",
    response_model=Page[SlotRead],
    summary="Слоты врача",
    description="Публичный список слотов врача с фильтром по датам и пагинацией.",
)
async def list_slots(
    doctor_id: uuid.UUID,
    service: ServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 100,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    only_free: Annotated[bool, Query()] = False,
) -> Page[SlotRead]:
    """Return paginated slots for a doctor."""
    items, total = await service.list_slots(
        doctor_id,
        date_from=date_from,
        date_to=date_to,
        only_free=only_free,
        page=page,
        size=size,
    )
    return Page.create(
        items=[SlotRead.model_validate(s) for s in items],
        total=total,
        page=page,
        size=size,
    )


# ============================================
# Create single (doctor/admin)
# ============================================


@router.post(
    "/doctors/{doctor_id}/slots",
    response_model=SlotRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать слот",
    description="Создать один слот вручную. Доступно врачу (для себя) или администратору.",
)
async def create_slot(
    doctor_id: uuid.UUID,
    data: SlotCreate,
    service: ServiceDep,
    user: CurrentUser,
) -> SlotRead:
    """Create a single slot manually."""
    slot = await service.create_slot(doctor_id, data, user)
    return SlotRead.model_validate(slot)


# ============================================
# Generate (doctor/admin)
# ============================================


@router.post(
    "/doctors/{doctor_id}/slots/generate",
    response_model=SlotGenerateResponse,
    summary="Сгенерировать слоты",
    description=(
        "Массовая генерация слотов на диапазон дат. "
        "Существующие и пересекающиеся слоты пропускаются. "
        "Доступно врачу (для себя) или администратору."
    ),
)
async def generate_slots(
    doctor_id: uuid.UUID,
    data: SlotGenerateRequest,
    service: ServiceDep,
    user: CurrentUser,
) -> SlotGenerateResponse:
    """Bulk generate slots for a doctor."""
    created, skipped = await service.generate_slots(doctor_id, data, user)
    return SlotGenerateResponse(created=created, skipped=skipped)


# ============================================
# Delete (doctor/admin)
# ============================================


@router.delete(
    "/slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить слот",
    description="Удалить незанятый слот. Доступно врачу (свой) или администратору.",
)
async def delete_slot(
    slot_id: uuid.UUID,
    service: ServiceDep,
    user: CurrentUser,
) -> None:
    """Delete an unbooked slot."""
    await service.delete_slot(slot_id, user)
