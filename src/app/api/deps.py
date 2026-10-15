"""FastAPI dependencies for authentication and authorization."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.services.auth import AuthService

# HTTP Bearer scheme for Swagger "Authorize" button.
# The client pastes a ready access token; no login form is shown.
http_bearer = HTTPBearer(auto_error=False)


# ============================================
# Service dependencies
# ============================================


async def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    """Provide an AuthService instance bound to the current DB session."""
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ============================================
# Current user
# ============================================


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode the access token and return the corresponding active user."""
    if credentials is None:
        raise UnauthorizedError("Требуется авторизация")

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise UnauthorizedError("Недействительный или просроченный токен") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Неверный тип токена")

    subject = payload.get("sub")
    if not subject:
        raise UnauthorizedError("Некорректный токен")

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise UnauthorizedError("Некорректный subject токена") from exc

    user = await UserRepository(db).get(user_id)
    if user is None:
        raise UnauthorizedError("Пользователь не найден")
    if not user.is_active:
        raise UnauthorizedError("Учётная запись деактивирована")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ============================================
# Role-based access control
# ============================================


def require_role(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory: allow access only to users with one of the given roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
        async def admin_endpoint(): ...
    """

    allowed = set(roles)

    async def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Недостаточно прав для выполнения операции")
        return user

    return checker


# Ready-to-use role dependencies
require_admin = require_role(UserRole.ADMIN)
require_doctor = require_role(UserRole.DOCTOR)
require_doctor_or_admin = require_role(UserRole.DOCTOR, UserRole.ADMIN)
require_patient = require_role(UserRole.PATIENT)
