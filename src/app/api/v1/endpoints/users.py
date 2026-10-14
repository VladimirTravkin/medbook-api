"""User profile endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Вернуть профиль текущего авторизованного пользователя.",
)
async def get_me(user: CurrentUser) -> UserRead:
    """Return the current user's profile."""
    return UserRead.model_validate(user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update current user",
    description="Обновить профиль текущего пользователя (только поле full_name).",
)
async def update_me(
    data: UserUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    """Update the current user's profile."""
    updates = data.model_dump(exclude_unset=True)
    if updates:
        repo = UserRepository(db)
        await repo.update(user, **updates)
        await db.commit()
        await db.refresh(user)
    return UserRead.model_validate(user)
