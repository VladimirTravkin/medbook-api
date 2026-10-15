"""Authentication endpoints."""

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация пациента",
    description="Создать нового пользователя с ролью «пациент».",
)
async def register(data: RegisterRequest, service: AuthServiceDep) -> UserRead:
    """Register a new patient account."""
    user = await service.register(data)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Вход в систему",
    description="Аутентификация по email и паролю. Возвращает пару access и refresh токенов.",
)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenPair:
    """Authenticate a user and return a token pair."""
    return await service.login(data.email, data.password)


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Обновление токенов",
    description="Обменять действующий refresh-токен на новую пару токенов (с ротацией).",
)
async def refresh(data: RefreshRequest, service: AuthServiceDep) -> TokenPair:
    """Rotate a refresh token and return a new token pair."""
    return await service.refresh(data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выход из системы",
    description="Отозвать refresh-токен. После этого его нельзя использовать.",
)
async def logout(data: LogoutRequest, service: AuthServiceDep) -> None:
    """Revoke a refresh token."""
    await service.logout(data.refresh_token)
